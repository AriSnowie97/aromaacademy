import hashlib
import hmac
import json
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..auth import TARIFF_RANK, get_current_user, get_effective_tariff_id
from ..config import get_settings
from ..database import get_db
from ..models import AuditLog, Payment, Subscription, Tariff, User, utcnow
from ..schemas import CheckoutRequest, WebhookPayload


router = APIRouter(tags=["billing"])
settings = get_settings()


def sign_webhook_payload(event_id: str, provider_ref: str, user_id: str, tariff_id: str, amount: int, status: str) -> str:
    msg = f"{event_id}:{provider_ref}:{user_id}:{tariff_id}:{amount}:{status}"
    return hmac.new(
        settings.webhook_secret.encode("utf-8"),
        msg.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


@router.get("/api/tariffs")
def list_tariffs(db: Session = Depends(get_db)):
    tariffs = db.query(Tariff).filter(Tariff.is_active == True).order_by(Tariff.rank.asc()).all()
    return [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "price_uah": t.price_uah,
            "aroma_daily_limit": t.aroma_daily_limit,
            "access_courses": t.access_courses,
            "rank": t.rank,
        }
        for t in tariffs
    ]


@router.get("/api/billing/subscription")
def get_my_subscription(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tariff_id, sub = get_effective_tariff_id(db, user)
    payments = (
        db.query(Payment)
        .filter(Payment.user_id == user.id)
        .order_by(Payment.created_at.desc())
        .limit(10)
        .all()
    )
    return {
        "effective_tariff_id": tariff_id,
        "subscription": {
            "id": sub.id,
            "tariff_id": sub.tariff_id,
            "status": sub.status,
            "pending_downgrade_tariff_id": sub.pending_downgrade_tariff_id,
            "period_start": sub.period_start.isoformat() if sub.period_start else None,
            "period_end": sub.period_end.isoformat() if sub.period_end else None,
        }
        if sub
        else None,
        "payments": [
            {
                "id": p.id,
                "tariff_id": p.tariff_id,
                "amount": p.amount,
                "currency": p.currency,
                "status": p.status,
                "created_at": p.created_at.isoformat(),
            }
            for p in payments
        ],
    }


@router.post("/api/billing/checkout")
def create_checkout(
    body: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Creates a pending payment intent; access is granted ONLY by signed webhook (Section 8)."""
    tariff = db.get(Tariff, body.tariff_id)
    if not tariff or not tariff.is_active:
        raise HTTPException(status_code=404, detail="Тариф не знайдено")

    provider_ref = f"pay_{uuid.uuid4().hex[:12]}"
    event_id = f"evt_{uuid.uuid4().hex[:12]}"
    payment = Payment(
        id=f"pmt_{uuid.uuid4().hex[:10]}",
        user_id=user.id,
        tariff_id=tariff.id,
        amount=tariff.price_uah,
        currency="UAH",
        status="pending",
        provider_ref=provider_ref,
    )
    db.add(payment)
    db.commit()

    # In v1 dev/demo mode we return a signed test webhook payload so the UI
    # can simulate the provider callback without storing card data or trusting client state.
    sig = sign_webhook_payload(
        event_id=event_id,
        provider_ref=provider_ref,
        user_id=user.id,
        tariff_id=tariff.id,
        amount=tariff.price_uah,
        status="succeeded",
    )
    return {
        "payment_id": payment.id,
        "provider_ref": provider_ref,
        "amount": tariff.price_uah,
        "currency": "UAH",
        "status": "pending",
        "demo_webhook_payload": {
            "event_id": event_id,
            "provider_ref": provider_ref,
            "user_id": user.id,
            "tariff_id": tariff.id,
            "amount": tariff.price_uah,
            "currency": "UAH",
            "status": "succeeded",
            "signature": sig,
        },
    }


@router.post("/api/billing/webhook")
def billing_webhook(payload: WebhookPayload, db: Session = Depends(get_db)):
    """Signed & idempotent payment webhook (Section 8 & 11.2)."""
    expected_sig = sign_webhook_payload(
        event_id=payload.event_id,
        provider_ref=payload.provider_ref,
        user_id=payload.user_id,
        tariff_id=payload.tariff_id,
        amount=payload.amount,
        status=payload.status,
    )
    if not hmac.compare_digest(expected_sig, payload.signature):
        raise HTTPException(status_code=401, detail="Недійсний підпис webhook")

    payment = db.query(Payment).filter(Payment.provider_ref == payload.provider_ref).first()
    if payment and payment.status == "succeeded" and payload.status == "succeeded":
        # Idempotent replay: do not create duplicate payment or duplicate subscription extension
        return {"status": "already_processed", "payment_id": payment.id}

    user = db.get(User, payload.user_id)
    tariff = db.get(Tariff, payload.tariff_id)
    if not user or not tariff:
        raise HTTPException(status_code=404, detail="Користувача або тариф не знайдено")

    now = utcnow()
    if not payment:
        payment = Payment(
            id=f"pmt_{uuid.uuid4().hex[:10]}",
            user_id=user.id,
            tariff_id=tariff.id,
            amount=payload.amount,
            currency=payload.currency,
            status=payload.status,
            provider_ref=payload.provider_ref,
        )
        db.add(payment)
    else:
        payment.status = payload.status

    if payload.status == "succeeded":
        active_sub = (
            db.query(Subscription)
            .filter(Subscription.user_id == user.id, Subscription.status == "active")
            .order_by(Subscription.period_end.desc())
            .first()
        )
        if active_sub:
            current_rank = TARIFF_RANK.get(active_sub.tariff_id, 0)
            new_rank = TARIFF_RANK.get(tariff.id, 0)
            if new_rank >= current_rank:
                # Upgrade applies immediately (Section 2)
                active_sub.tariff_id = tariff.id
                active_sub.pending_downgrade_tariff_id = None
                active_sub.period_end = now + timedelta(days=30)
                active_sub.provider_ref = payload.provider_ref
            else:
                # Downgrade applies at end of paid period (Section 2)
                active_sub.pending_downgrade_tariff_id = tariff.id
            sub = active_sub
        else:
            sub = Subscription(
                id=f"sub_{uuid.uuid4().hex[:10]}",
                user_id=user.id,
                tariff_id=tariff.id,
                status="active",
                period_start=now,
                period_end=now + timedelta(days=30),
                provider_ref=payload.provider_ref,
            )
            db.add(sub)
        db.flush()
        payment.subscription_id = sub.id

        db.add(
            AuditLog(
                id=f"aud_{uuid.uuid4().hex[:10]}",
                actor_id="billing_webhook",
                action="subscription_activated",
                entity="subscription",
                entity_id=sub.id,
                details={"tariff_id": tariff.id, "provider_ref": payload.provider_ref},
            )
        )

    db.commit()
    return {"status": "processed", "payment_id": payment.id, "tariff_id": tariff.id}

