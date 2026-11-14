import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, get_effective_tariff_id
from ..config import get_settings
from ..database import get_db
from ..models import Consent, LessonProgress, Tariff, User, utcnow
from ..schemas import ConsentRequest, DemoSwitchRequest, LoginRequest, VerifyRequest


router = APIRouter(prefix="/api/auth", tags=["auth"])
settings = get_settings()


def _serialize_user(db: Session, user: User) -> dict:
    tariff_id, sub = get_effective_tariff_id(db, user)
    tariff = db.get(Tariff, tariff_id) if tariff_id != "free" else None
    completed_lessons = (
        db.query(LessonProgress)
        .filter(LessonProgress.user_id == user.id, LessonProgress.status == "completed")
        .count()
    )
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "telegram_id": user.telegram_id,
        "role": user.role,
        "language": user.language,
        "streak_days": user.streak_days,
        "tariff_id": tariff_id,
        "tariff_name": tariff.name if tariff else "Без підписки (режим читання)",
        "subscription_status": sub.status if sub else ("admin" if user.role != "student" else "none"),
        "subscription_period_end": sub.period_end.isoformat() if sub and sub.period_end else None,
        "completed_lessons": completed_lessons,
    }


@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Вкажіть коректний email")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        if not body.accept_consent:
            raise HTTPException(
                status_code=400,
                detail="Потрібна згода на обробку персональних даних",
            )
        user = User(
            id=f"u_{uuid.uuid4().hex[:10]}",
            email=email,
            name=body.name or email.split("@")[0].capitalize(),
            telegram_id=body.telegram_id,
            role="student",
            language="uk",
            last_active_at=utcnow(),
        )
        db.add(user)
        db.flush()
        db.add(
            Consent(
                id=f"cons_{uuid.uuid4().hex[:10]}",
                user_id=user.id,
                type="personal_data",
                version=settings.consent_version,
            )
        )
        db.commit()
        db.refresh(user)

    token = create_access_token(user.id, user.role)
    return {
        "message": "Вхід виконано (демо magic-link підтверджено)",
        "access_token": token,
        "token_type": "bearer",
        "user": _serialize_user(db, user),
    }


@router.post("/verify")
def verify_magic_link(body: VerifyRequest, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Користувача не знайдено")
    token = create_access_token(user.id, user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _serialize_user(db, user),
    }


@router.post("/demo-switch")
def demo_switch(body: DemoSwitchRequest, db: Session = Depends(get_db)):
    """Convenience helper for v1 testing between demo student tariffs and Natalia admin."""
    user = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="Демо-акаунт не знайдено")
    token = create_access_token(user.id, user.role)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": _serialize_user(db, user),
    }


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _serialize_user(db, user)


@router.post("/consent")
def record_consent(
    body: ConsentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    consent = Consent(
        id=f"cons_{uuid.uuid4().hex[:10]}",
        user_id=user.id,
        type=body.type,
        version=body.version or settings.consent_version,
    )
    db.add(consent)
    db.commit()
    return {"status": "accepted", "version": consent.version}


@router.delete("/account", status_code=status.HTTP_200_OK)
def delete_account(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role in ("admin", "superadmin"):
        raise HTTPException(status_code=400, detail="Адмін-акаунт не можна видалити з кабінету")
    db.delete(user)
    db.commit()
    return {"status": "deleted"}
