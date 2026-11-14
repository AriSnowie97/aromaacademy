import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import Subscription, Tariff, User, utcnow


settings = get_settings()
bearer_scheme = HTTPBearer(auto_error=False)

TARIFF_RANK = {
    "free": 0,
    "basic": 1,
    "standard": 2,
    "personal": 3,
}


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def create_access_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": int(time.time()) + settings.token_ttl_seconds,
    }
    encoded = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(
        settings.secret_key.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{encoded}.{_b64url_encode(sig)}"


def decode_access_token(token: str) -> dict:
    try:
        encoded, sig_b64 = token.split(".", 1)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недійсний формат токена",
        ) from exc

    expected_sig = hmac.new(
        settings.secret_key.encode("utf-8"),
        encoded.encode("ascii"),
        hashlib.sha256,
    ).digest()
    actual_sig = _b64url_decode(sig_b64)
    if not hmac.compare_digest(expected_sig, actual_sig):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недійсний підпис токена",
        )

    payload = json.loads(_b64url_decode(encoded).decode("utf-8"))
    if payload.get("exp", 0) < int(time.time()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Термін дії сесії вичерпано",
        )
    return payload


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Потрібна авторизація",
        )
    payload = decode_access_token(credentials.credentials)
    user = db.get(User, payload["sub"])
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Користувача не знайдено",
        )
    return user


def require_roles(*allowed_roles: str):
    def _guard(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостатньо прав для цієї дії",
            )
        return user

    return _guard


def get_effective_tariff_id(db: Session, user: User) -> tuple[str, Optional[Subscription]]:
    """Server-side truth for user's active tariff and subscription."""
    if user.role in ("admin", "editor", "superadmin"):
        return "personal", None

    now = utcnow()
    sub = (
        db.query(Subscription)
        .filter(
            Subscription.user_id == user.id,
            Subscription.status.in_(["active", "cancelled"]),
        )
        .order_by(Subscription.period_end.desc())
        .first()
    )
    if not sub:
        return "free", None

    period_end = sub.period_end
    if period_end.tzinfo is None:
        period_end = period_end.replace(tzinfo=now.tzinfo)

    if period_end < now:
        sub.status = "expired"
        db.commit()
        return "free", sub

    return sub.tariff_id, sub


def has_tariff_access(user_tariff_id: str, min_tariff_id: str, user_role: str = "student") -> bool:
    if user_role in ("admin", "editor", "superadmin"):
        return True
    return TARIFF_RANK.get(user_tariff_id, 0) >= TARIFF_RANK.get(min_tariff_id, 1)


def get_allowed_tariffs(user_tariff_id: str) -> list[str]:
    rank = TARIFF_RANK.get(user_tariff_id, 0)
    return [t for t, r in TARIFF_RANK.items() if r > 0 and r <= rank]


def get_tariff_obj(db: Session, tariff_id: str) -> Optional[Tariff]:
    return db.get(Tariff, tariff_id)

