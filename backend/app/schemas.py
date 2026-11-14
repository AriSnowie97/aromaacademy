from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    name: Optional[str] = None
    telegram_id: Optional[str] = None
    accept_consent: bool = True


class VerifyRequest(BaseModel):
    email: str
    code: str = "0000"


class DemoSwitchRequest(BaseModel):
    email: str


class ConsentRequest(BaseModel):
    type: str = "personal_data"
    version: Optional[str] = None


class StepAnswerRequest(BaseModel):
    answer: Any


class CardReviewRequest(BaseModel):
    step_id: str
    result: str = Field(pattern="^(known|repeat)$")


class OpenFeedbackRequest(BaseModel):
    step_id: str
    answer_text: str


class AromaAskClientRequest(BaseModel):
    lesson_id: Optional[str] = None
    message: str


class AromaAskServiceRequest(BaseModel):
    user_id: str
    tariff: str
    lesson_id: Optional[str] = None
    language: str = "uk"
    message: str


class AromaSource(BaseModel):
    lesson_id: str
    title: str
    source_ref: str = ""


class AromaSafetyInfo(BaseModel):
    triggered: bool = False
    route_to: Optional[str] = None
    reason: Optional[str] = None


class AromaAskResponse(BaseModel):
    answer: str
    sources: list[AromaSource] = []
    safety: AromaSafetyInfo
    disclaimer: bool = True
    disclaimer_text: str
    ai_label: str = "Штучний інтелект Арома"
    remaining_today: Optional[int] = None


class CheckoutRequest(BaseModel):
    tariff_id: str


class WebhookPayload(BaseModel):
    event_id: str
    provider_ref: str
    user_id: str
    tariff_id: str
    amount: int
    currency: str = "UAH"
    status: str  # succeeded, failed, cancelled
    signature: str


class AdminLessonCreate(BaseModel):
    course_id: str
    code: str
    title: str
    goal: str = ""
    theses: list[str] = []
    for_frame: str = ""
    final_thought: str = ""
    source_ref: str = ""
    ai_assisted_checked: bool = True


class AdminLessonUpdate(BaseModel):
    code: Optional[str] = None
    title: Optional[str] = None
    goal: Optional[str] = None
    theses: Optional[list[str]] = None
    for_frame: Optional[str] = None
    final_thought: Optional[str] = None
    source_ref: Optional[str] = None
    status: Optional[str] = None
    ai_assisted_checked: Optional[bool] = None


class AdminStepCreate(BaseModel):
    type: str
    payload: dict[str, Any]
    source_ref: str = ""
    is_key: bool = False
    order: Optional[int] = None


class AdminStepUpdate(BaseModel):
    type: Optional[str] = None
    payload: Optional[dict[str, Any]] = None
    source_ref: Optional[str] = None
    is_key: Optional[bool] = None
    order: Optional[int] = None


class AdminReorderSteps(BaseModel):
    step_ids: list[str]


class AdminMarkdownImport(BaseModel):
    course_id: str
    markdown_text: str


class AdminMentorReply(BaseModel):
    reply: str


class AdminTariffUpdate(BaseModel):
    price_uah: Optional[int] = None
    aroma_daily_limit: Optional[int] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None

