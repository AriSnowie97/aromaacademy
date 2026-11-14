from datetime import timedelta
import random
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..aroma_service import evaluate_open_answer_with_aroma
from ..auth import get_current_user, get_effective_tariff_id, has_tariff_access
from ..config import get_settings
from ..database import get_db
from ..models import (
    AromaClip,
    CardReview,
    Course,
    Lesson,
    LessonProgress,
    OpenAnswer,
    Step,
    StepAttempt,
    User,
    utcnow,
)
from ..schemas import CardReviewRequest, OpenFeedbackRequest, StepAnswerRequest


router = APIRouter(prefix="/api", tags=["courses"])
settings = get_settings()


def _resolve_clip_video_url(clip: AromaClip) -> str | None:
    if clip.video_url:
        return clip.video_url
    videos_dir = settings.media_dir / "videos"
    if not videos_dir.exists():
        return None
    video_files = sorted(
        p.name
        for p in videos_dir.iterdir()
        if p.is_file() and p.suffix.lower() in (".mp4", ".webm", ".mov")
    )
    for vf in video_files:
        if vf.startswith(f"{clip.order}.") or vf.startswith(f"clip_{clip.order}"):
            return f"/media/videos/{vf}"
    if clip.order == 1 and len(video_files) == 1:
        return f"/media/videos/{video_files[0]}"
    return None


def _sanitize_step_for_student(step: Step) -> dict:
    payload = dict(step.payload or {})
    if step.type == "choice":
        payload.pop("correct_index", None)
        payload.pop("explanation", None)
    elif step.type == "true_false":
        payload.pop("correct", None)
        payload.pop("explanation", None)
    elif step.type == "match":
        pairs = payload.get("pairs", [])
        lefts = [p["left"] for p in pairs]
        rights = [p["right"] for p in pairs]
        rng = random.Random(step.id)
        rng.shuffle(rights)
        payload = {
            "prompt": payload.get("prompt", "Зіставте пари:"),
            "lefts": lefts,
            "rights": rights,
        }
    elif step.type == "order":
        items = list(payload.get("items", []))
        rng = random.Random(step.id)
        shuffled = list(items)
        if len(shuffled) > 1:
            rng.shuffle(shuffled)
            if shuffled == items:
                shuffled = shuffled[1:] + shuffled[:1]
        payload = {
            "prompt": payload.get("prompt", "Розставте кроки у правильному порядку:"),
            "items": shuffled,
        }
    elif step.type == "open":
        # Hide sample answer until student submits
        payload = {
            "question": payload.get("question", ""),
            "max_length": payload.get("max_length", 500),
        }
    return {
        "id": step.id,
        "order": step.order,
        "type": step.type,
        "payload": payload,
        "source_ref": step.source_ref,
        "is_key": step.is_key,
    }


def _check_lesson_access(db: Session, user: User, lesson: Lesson, allow_read_only_if_completed: bool = True) -> tuple[bool, bool]:
    """Returns (allowed, read_only)."""
    course = db.get(Course, lesson.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не знайдено")

    tariff_id, _ = get_effective_tariff_id(db, user)
    if has_tariff_access(tariff_id, course.min_tariff, user.role):
        return True, False

    if allow_read_only_if_completed and tariff_id == "free":
        prog = (
            db.query(LessonProgress)
            .filter(
                LessonProgress.user_id == user.id,
                LessonProgress.lesson_id == lesson.id,
                LessonProgress.status == "completed",
            )
            .first()
        )
        if prog:
            return True, True

    return False, False


@router.get("/courses")
def list_courses(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tariff_id, _ = get_effective_tariff_id(db, user)
    courses = db.query(Course).order_by(Course.order.asc()).all()

    completed_lesson_ids = {
        lp.lesson_id
        for lp in db.query(LessonProgress)
        .filter(LessonProgress.user_id == user.id, LessonProgress.status == "completed")
        .all()
    }

    result = []
    for c in courses:
        lessons = c.lessons
        published_lessons = [l for l in lessons if l.status == "published"]
        done_count = sum(1 for l in lessons if l.id in completed_lesson_ids)
        result.append(
            {
                "id": c.id,
                "title": c.title,
                "description": c.description,
                "order": c.order,
                "level": c.level,
                "min_tariff": c.min_tariff,
                "is_mandatory": c.is_mandatory,
                "has_access": has_tariff_access(tariff_id, c.min_tariff, user.role),
                "total_lessons": len(lessons),
                "published_lessons": len(published_lessons),
                "completed_lessons": done_count,
            }
        )
    return {"tariff_id": tariff_id, "courses": result}


@router.get("/courses/{course_id}")
def get_course_detail(course_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course = db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не знайдено")

    tariff_id, _ = get_effective_tariff_id(db, user)
    has_access = has_tariff_access(tariff_id, course.min_tariff, user.role)

    progress_map = {
        lp.lesson_id: lp.status
        for lp in db.query(LessonProgress).filter(LessonProgress.user_id == user.id).all()
    }

    lessons_out = []
    for l in course.lessons:
        lessons_out.append(
            {
                "id": l.id,
                "code": l.code,
                "title": l.title,
                "order": l.order,
                "status": l.status,
                "steps_count": len(l.steps),
                "progress_status": progress_map.get(l.id, "not_started"),
                "has_video": any(_resolve_clip_video_url(c) for c in l.clips),
            }
        )

    return {
        "id": course.id,
        "title": course.title,
        "description": course.description,
        "order": course.order,
        "level": course.level,
        "min_tariff": course.min_tariff,
        "is_mandatory": course.is_mandatory,
        "has_access": has_access,
        "lessons": lessons_out,
    }


@router.get("/lessons/{lesson_id}")
def get_lesson(lesson_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не знайдено")

    course = db.get(Course, lesson.course_id)
    allowed, read_only = _check_lesson_access(db, user, lesson, allow_read_only_if_completed=True)
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "TARIFF_REQUIRED",
                "message": f"Відкрийте тариф «{course.min_tariff}», щоб пройти цей урок.",
                "required_tariff": course.min_tariff,
            },
        )

    if lesson.status != "published" and user.role not in ("admin", "editor", "superadmin"):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "LESSON_DRAFT",
                "message": "Цей урок ще на підготовці у Наталії та скоро буде опублікований.",
            },
        )

    prog = (
        db.query(LessonProgress)
        .filter(LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson.id)
        .first()
    )

    clips_map = {c.id: c for c in lesson.clips}
    steps_out = []
    for s in lesson.steps:
        step_dict = _sanitize_step_for_student(s)
        clip_id = (s.payload or {}).get("clip_id")
        if clip_id:
            clip = clips_map.get(clip_id) or db.get(AromaClip, clip_id)
            if clip:
                step_dict["clip"] = {
                    "id": clip.id,
                    "title": clip.title,
                    "video_url": _resolve_clip_video_url(clip),
                    "script_text": clip.script_text,
                    "fragments_count": clip.fragments_count,
                    "fragments": clip.fragments_json,
                }
        steps_out.append(step_dict)

    return {
        "id": lesson.id,
        "course_id": lesson.course_id,
        "course_title": course.title,
        "course_order": course.order,
        "code": lesson.code,
        "title": lesson.title,
        "goal": lesson.goal,
        "theses": lesson.theses,
        "final_thought": lesson.final_thought,
        "source_ref": lesson.source_ref,
        "version": lesson.version,
        "status": lesson.status,
        "ai_assisted_checked": lesson.ai_assisted_checked,
        "ai_checked_label": "Картки підготовлено за допомогою ШІ й перевірено Наталією" if lesson.ai_assisted_checked else None,
        "disclaimer": settings.disclaimer_text,
        "read_only": read_only,
        "progress_status": prog.status if prog else "not_started",
        "completed_steps": prog.completed_steps if prog else [],
        "steps": steps_out,
    }


@router.post("/steps/{step_id}/answer")
def submit_step_answer(
    step_id: str,
    body: StepAnswerRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    step = db.get(Step, step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Крок не знайдено")

    lesson = db.get(Lesson, step.lesson_id)
    allowed, read_only = _check_lesson_access(db, user, lesson, allow_read_only_if_completed=False)
    if not allowed or read_only:
        raise HTTPException(status_code=403, detail="Потрібен активний тариф для проходження завдань")

    payload = step.payload or {}
    is_correct = False
    explanation = payload.get("explanation", "")
    extra: dict = {}

    if step.type == "card":
        is_correct = True
        explanation = "Картку опрацьовано."
    elif step.type == "choice":
        try:
            chosen = int(body.answer)
        except (TypeError, ValueError):
            chosen = -1
        is_correct = chosen == int(payload.get("correct_index", -99))
    elif step.type == "true_false":
        is_correct = bool(body.answer) is bool(payload.get("correct"))
    elif step.type == "match":
        expected = {p["left"]: p["right"] for p in payload.get("pairs", [])}
        given = body.answer if isinstance(body.answer, dict) else {}
        is_correct = len(given) == len(expected) and all(given.get(k) == v for k, v in expected.items())
    elif step.type == "order":
        expected_items = payload.get("items", [])
        given_items = body.answer if isinstance(body.answer, list) else []
        is_correct = given_items == expected_items
    elif step.type == "flashcard":
        is_correct = True
        result = body.answer if body.answer in ("known", "repeat") else "known"
        _upsert_card_review(db, user.id, step.id, result)
        explanation = "Збережено в колоді повторень."
    elif step.type == "open":
        text = str(body.answer or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="Напишіть відповідь перед відправкою")
        is_correct = True
        open_ans = OpenAnswer(
            id=f"oans_{uuid.uuid4().hex[:10]}",
            user_id=user.id,
            step_id=step.id,
            text=text,
        )
        db.add(open_ans)
        extra["open_answer_id"] = open_ans.id
        extra["sample_answer"] = payload.get("sample_answer", "")
        extra["key_points"] = payload.get("key_points", [])
        explanation = "Порівняйте свою відповідь зі зразком і ключовими пунктами."

    attempt = StepAttempt(
        id=f"att_{uuid.uuid4().hex[:10]}",
        user_id=user.id,
        step_id=step.id,
        answer={"value": body.answer},
        is_correct=is_correct,
    )
    db.add(attempt)

    prog = (
        db.query(LessonProgress)
        .filter(LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson.id)
        .first()
    )
    if not prog:
        prog = LessonProgress(
            id=f"lprog_{uuid.uuid4().hex[:10]}",
            user_id=user.id,
            lesson_id=lesson.id,
            lesson_version=lesson.version,
            status="in_progress",
            completed_steps=[],
        )
        db.add(prog)

    completed_steps = list(prog.completed_steps or [])
    if is_correct and step.id not in completed_steps:
        completed_steps.append(step.id)
        prog.completed_steps = completed_steps

    db.commit()

    return {
        "step_id": step.id,
        "is_correct": is_correct,
        "is_key": step.is_key,
        "explanation": explanation,
        "completed_steps": completed_steps,
        **extra,
    }


@router.post("/open-answers/{step_id}/aroma-feedback")
def get_open_answer_aroma_feedback(
    step_id: str,
    body: OpenFeedbackRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    step = db.get(Step, step_id)
    if not step or step.type != "open":
        raise HTTPException(status_code=404, detail="Відкрите питання не знайдено")
    payload = step.payload or {}
    feedback = evaluate_open_answer_with_aroma(
        answer_text=body.answer_text,
        key_points=payload.get("key_points", []),
        sample_answer=payload.get("sample_answer", ""),
    )
    latest = (
        db.query(OpenAnswer)
        .filter(OpenAnswer.user_id == user.id, OpenAnswer.step_id == step_id)
        .order_by(OpenAnswer.created_at.desc())
        .first()
    )
    if latest:
        latest.aroma_feedback = feedback
        db.commit()
    return {"feedback": feedback, "disclaimer": settings.disclaimer_text}


@router.post("/lessons/{lesson_id}/complete")
def complete_lesson(
    lesson_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не знайдено")

    allowed, read_only = _check_lesson_access(db, user, lesson, allow_read_only_if_completed=False)
    if not allowed or read_only:
        raise HTTPException(status_code=403, detail="Потрібен активний тариф")

    # Check mandatory key questions (Module 3 Safety & any lesson with is_key=True)
    key_steps = [s for s in lesson.steps if s.is_key]
    missing_keys = []
    for ks in key_steps:
        latest = (
            db.query(StepAttempt)
            .filter(StepAttempt.user_id == user.id, StepAttempt.step_id == ks.id)
            .order_by(StepAttempt.created_at.desc())
            .first()
        )
        if not latest or not latest.is_correct:
            missing_keys.append(ks.id)

    if missing_keys:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "KEY_SAFETY_UNANSWERED",
                "message": "Урок безпеки не зараховується, доки всі ключові питання не закриті правильно.",
                "missing_key_steps": missing_keys,
            },
        )

    now = utcnow()
    prog = (
        db.query(LessonProgress)
        .filter(LessonProgress.user_id == user.id, LessonProgress.lesson_id == lesson.id)
        .first()
    )
    if not prog:
        prog = LessonProgress(
            id=f"lprog_{uuid.uuid4().hex[:10]}",
            user_id=user.id,
            lesson_id=lesson.id,
            lesson_version=lesson.version,
            completed_steps=[s.id for s in lesson.steps],
        )
        db.add(prog)

    was_completed = prog.status == "completed"
    prog.status = "completed"
    prog.completed_at = now

    if not was_completed:
        user.streak_days = (user.streak_days or 0) + 1
        user.last_active_at = now

    # Seed flashcards from this lesson into user's review deck if not already present
    for s in lesson.steps:
        if s.type == "flashcard":
            existing = (
                db.query(CardReview)
                .filter(CardReview.user_id == user.id, CardReview.step_id == s.id)
                .first()
            )
            if not existing:
                db.add(
                    CardReview(
                        id=f"crev_{uuid.uuid4().hex[:10]}",
                        user_id=user.id,
                        step_id=s.id,
                        result="repeat",
                        interval_days=1,
                        next_review_at=now,
                    )
                )

    db.commit()
    return {
        "lesson_id": lesson.id,
        "status": "completed",
        "streak_days": user.streak_days,
        "disclaimer": settings.disclaimer_text,
    }


def _upsert_card_review(db: Session, user_id: str, step_id: str, result: str) -> CardReview:
    now = utcnow()
    review = (
        db.query(CardReview)
        .filter(CardReview.user_id == user_id, CardReview.step_id == step_id)
        .first()
    )
    intervals = [1, 3, 7]
    if not review:
        interval = 1 if result == "repeat" else 3
        review = CardReview(
            id=f"crev_{uuid.uuid4().hex[:10]}",
            user_id=user_id,
            step_id=step_id,
            result=result,
            interval_days=interval,
            next_review_at=now + timedelta(days=interval),
            updated_at=now,
        )
        db.add(review)
    else:
        if result == "repeat":
            review.interval_days = 1
        else:
            idx = intervals.index(review.interval_days) if review.interval_days in intervals else 0
            review.interval_days = intervals[min(idx + 1, len(intervals) - 1)]
        review.result = result
        review.next_review_at = now + timedelta(days=review.interval_days)
        review.updated_at = now
    return review


@router.get("/review")
def get_review_deck(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    tariff_id, _ = get_effective_tariff_id(db, user)
    flashcards = db.query(Step).filter(Step.type == "flashcard").all()
    reviews_map = {
        r.step_id: r
        for r in db.query(CardReview).filter(CardReview.user_id == user.id).all()
    }
    deck = []
    for step in flashcards:
        lesson = db.get(Lesson, step.lesson_id)
        course = db.get(Course, lesson.course_id) if lesson else None
        if not lesson or not course or lesson.status != "published":
            continue
        if not has_tariff_access(tariff_id, course.min_tariff, user.role):
            continue
        rev = reviews_map.get(step.id)
        deck.append(
            {
                "step_id": step.id,
                "lesson_id": lesson.id,
                "lesson_code": lesson.code,
                "lesson_title": lesson.title,
                "front": (step.payload or {}).get("front", ""),
                "back": (step.payload or {}).get("back", ""),
                "source_ref": step.source_ref,
                "interval_days": rev.interval_days if rev else 1,
                "last_result": rev.result if rev else "new",
                "next_review_at": rev.next_review_at.isoformat() if rev else None,
            }
        )
    return {"cards": deck}


@router.post("/review")
def record_review(
    body: CardReviewRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    step = db.get(Step, body.step_id)
    if not step or step.type != "flashcard":
        raise HTTPException(status_code=404, detail="Картку не знайдено")
    review = _upsert_card_review(db, user.id, step.id, body.result)
    db.commit()
    return {
        "step_id": step.id,
        "result": review.result,
        "interval_days": review.interval_days,
        "next_review_at": review.next_review_at.isoformat(),
    }

