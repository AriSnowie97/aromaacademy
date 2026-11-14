from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120), default="Учениця")
    telegram_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(32), default="student")  # student, editor, admin, superadmin
    language: Mapped[str] = mapped_column(String(8), default="uk")
    streak_days: Mapped[int] = mapped_column(Integer, default=0)
    last_active_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    subscriptions: Mapped[list["Subscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Tariff(Base):
    __tablename__ = "tariffs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)  # basic, standard, personal
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    price_uah: Mapped[int] = mapped_column(Integer, default=0)
    aroma_daily_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # None = unlimited
    access_courses: Mapped[list[int]] = mapped_column(JSON, default=list)
    rank: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    tariff_id: Mapped[str] = mapped_column(ForeignKey("tariffs.id"))
    status: Mapped[str] = mapped_column(String(32), default="active")  # active, pending, cancelled, expired
    pending_downgrade_tariff_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provider_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="subscriptions")
    tariff: Mapped["Tariff"] = relationship()


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subscription_id: Mapped[Optional[str]] = mapped_column(ForeignKey("subscriptions.id"), nullable=True)
    tariff_id: Mapped[str] = mapped_column(String(32))
    amount: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(8), default="UAH")
    status: Mapped[str] = mapped_column(String(32), default="pending")  # pending, succeeded, failed
    provider_ref: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    order: Mapped[int] = mapped_column(Integer, index=True)
    level: Mapped[str] = mapped_column(String(16), default="learn")  # learn, share
    min_tariff: Mapped[str] = mapped_column(String(32), default="basic")  # basic, standard, personal
    status: Mapped[str] = mapped_column(String(24), default="published")  # draft, published
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=False)

    lessons: Mapped[list["Lesson"]] = relationship(
        back_populates="course", cascade="all, delete-orphan", order_by="Lesson.order"
    )


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(16))  # e.g. "1.1"
    title: Mapped[str] = mapped_column(String(240))
    goal: Mapped[str] = mapped_column(Text, default="")
    theses: Mapped[list[str]] = mapped_column(JSON, default=list)
    for_frame: Mapped[str] = mapped_column(Text, default="")
    final_thought: Mapped[str] = mapped_column(Text, default="")
    source_ref: Mapped[str] = mapped_column(String(255), default="")
    order: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="draft")  # draft, review, published
    version: Mapped[int] = mapped_column(Integer, default=1)
    ai_assisted_checked: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    course: Mapped["Course"] = relationship(back_populates="lessons")
    steps: Mapped[list["Step"]] = relationship(
        back_populates="lesson", cascade="all, delete-orphan", order_by="Step.order"
    )
    clips: Mapped[list["AromaClip"]] = relationship(back_populates="lesson")


class LessonVersion(Base):
    __tablename__ = "lesson_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AromaClip(Base):
    __tablename__ = "aroma_clips"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lesson_id: Mapped[Optional[str]] = mapped_column(ForeignKey("lessons.id", ondelete="SET NULL"), nullable=True, index=True)
    order: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(200))
    suggested_lesson_ref: Mapped[str] = mapped_column(String(64), default="")
    fragments_count: Mapped[int] = mapped_column(Integer, default=0)
    fragments_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    video_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    script_text: Mapped[str] = mapped_column(Text, default="")

    lesson: Mapped[Optional["Lesson"]] = relationship(back_populates="clips")


class Step(Base):
    __tablename__ = "steps"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    order: Mapped[int] = mapped_column(Integer, default=1)
    type: Mapped[str] = mapped_column(String(24))  # card, choice, true_false, match, order, flashcard, open
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    source_ref: Mapped[str] = mapped_column(String(255), default="")
    is_key: Mapped[bool] = mapped_column(Boolean, default=False)

    lesson: Mapped["Lesson"] = relationship(back_populates="steps")


class StepAttempt(Base):
    __tablename__ = "step_attempts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[str] = mapped_column(ForeignKey("steps.id", ondelete="CASCADE"), index=True)
    answer: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    __table_args__ = (UniqueConstraint("user_id", "lesson_id", name="uq_user_lesson_progress"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    lesson_version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="in_progress")  # in_progress, completed
    completed_steps: Mapped[list[str]] = mapped_column(JSON, default=list)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class KbChunk(Base):
    __tablename__ = "kb_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lesson_id: Mapped[str] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), index=True)
    course_id: Mapped[str] = mapped_column(String(64), index=True)
    min_tariff: Mapped[str] = mapped_column(String(32), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(240), default="")
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(JSON, default=list)
    source_ref: Mapped[str] = mapped_column(String(255), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AromaMessage(Base):
    __tablename__ = "aroma_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    role: Mapped[str] = mapped_column(String(16))  # user, assistant
    text: Mapped[str] = mapped_column(Text)
    sources: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    safety_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    safety_reason: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Consent(Base):
    __tablename__ = "consents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(64))  # personal_data, health_disclaimer
    accepted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    version: Mapped[str] = mapped_column(String(32))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    actor_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OpenAnswer(Base):
    __tablename__ = "open_answers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[str] = mapped_column(ForeignKey("steps.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    aroma_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    mentor_reply: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CardReview(Base):
    __tablename__ = "card_reviews"
    __table_args__ = (UniqueConstraint("user_id", "step_id", name="uq_user_card_review"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    step_id: Mapped[str] = mapped_column(ForeignKey("steps.id", ondelete="CASCADE"), index=True)
    result: Mapped[str] = mapped_column(String(16))  # known, repeat
    interval_days: Mapped[int] = mapped_column(Integer, default=1)
    next_review_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModuleTest(Base):
    __tablename__ = "module_tests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), unique=True)
    step_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    pass_score: Mapped[int] = mapped_column(Integer, default=75)

