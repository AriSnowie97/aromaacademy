from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..aroma_service import get_remaining_daily_quota, process_aroma_ask
from ..auth import get_current_user, get_effective_tariff_id
from ..database import get_db
from ..models import AromaMessage, User
from ..schemas import AromaAskClientRequest, AromaAskResponse, AromaAskServiceRequest


router = APIRouter(tags=["aroma"])


@router.post("/api/aroma/ask", response_model=AromaAskResponse)
def client_ask_aroma(
    body: AromaAskClientRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """App server endpoint: derives user_id and tariff strictly from DB, never from client body."""
    tariff_id, _ = get_effective_tariff_id(db, user)
    return process_aroma_ask(
        db=db,
        user_id=user.id,
        tariff_id=tariff_id,
        message=body.message,
        lesson_id=body.lesson_id,
        language=user.language,
    )


@router.post("/v1/aroma/ask", response_model=AromaAskResponse)
def aroma_service_ask(
    body: AromaAskServiceRequest,
    db: Session = Depends(get_db),
):
    """Internal Aroma service contract matching ТЗ Section 6."""
    return process_aroma_ask(
        db=db,
        user_id=body.user_id,
        tariff_id=body.tariff,
        message=body.message,
        lesson_id=body.lesson_id,
        language=body.language,
    )


@router.get("/api/aroma/history")
def aroma_history(
    lesson_id: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tariff_id, _ = get_effective_tariff_id(db, user)
    q = db.query(AromaMessage).filter(AromaMessage.user_id == user.id)
    if lesson_id:
        q = q.filter(AromaMessage.lesson_id == lesson_id)
    messages = q.order_by(AromaMessage.created_at.asc()).limit(50).all()
    return {
        "remaining_today": get_remaining_daily_quota(db, user.id, tariff_id),
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "text": m.text,
                "sources": m.sources,
                "safety_triggered": m.safety_triggered,
                "lesson_id": m.lesson_id,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }

