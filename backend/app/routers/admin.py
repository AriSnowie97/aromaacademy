import re
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..aroma_service import reindex_lesson_kb
from ..auth import require_roles
from ..config import get_settings
from ..database import get_db
from ..models import (
    AromaClip,
    AromaMessage,
    AuditLog,
    Course,
    Lesson,
    LessonProgress,
    LessonVersion,
    OpenAnswer,
    Step,
    StepAttempt,
    Tariff,
    User,
)
from ..schemas import (
    AdminLessonCreate,
    AdminLessonUpdate,
    AdminMarkdownImport,
    AdminMentorReply,
    AdminReorderSteps,
    AdminStepCreate,
    AdminStepUpdate,
    AdminTariffUpdate,
)


router = APIRouter(prefix="/api/admin", tags=["admin"])
settings = get_settings()


def _snapshot_lesson(lesson: Lesson) -> dict:
    return {
        "title": lesson.title,
        "code": lesson.code,
        "goal": lesson.goal,
        "theses": lesson.theses,
        "for_frame": lesson.for_frame,
        "final_thought": lesson.final_thought,
        "source_ref": lesson.source_ref,
        "status": lesson.status,
        "steps": [
            {
                "id": s.id,
                "order": s.order,
                "type": s.type,
                "payload": s.payload,
                "source_ref": s.source_ref,
                "is_key": s.is_key,
            }
            for s in lesson.steps
        ],
    }


@router.get("/tree")
def admin_tree(
    user: User = Depends(require_roles("admin", "editor", "superadmin")),
    db: Session = Depends(get_db),
):
    courses = db.query(Course).order_by(Course.order.asc()).all()
    clips = db.query(AromaClip).order_by(AromaClip.order.asc()).all()
    return {
        "courses": [
            {
                "id": c.id,
                "title": c.title,
                "order": c.order,
                "level": c.level,
                "min_tariff": c.min_tariff,
                "is_mandatory": c.is_mandatory,
                "lessons": [
                    {
                        "id": l.id,
                        "code": l.code,
                        "title": l.title,
                        "order": l.order,
                        "status": l.status,
                        "version": l.version,
                        "steps_count": len(l.steps),
                    }
                    for l in c.lessons
                ],
            }
            for c in courses
        ],
        "clips": [
            {
                "id": cl.id,
                "order": cl.order,
                "title": cl.title,
                "lesson_id": cl.lesson_id,
                "suggested_lesson_ref": cl.suggested_lesson_ref,
                "fragments_count": cl.fragments_count,
                "video_url": cl.video_url,
            }
            for cl in clips
        ],
    }


@router.get("/lessons/{lesson_id}")
def admin_get_lesson(
    lesson_id: str,
    user: User = Depends(require_roles("admin", "editor", "superadmin")),
    db: Session = Depends(get_db),
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не знайдено")
    versions = (
        db.query(LessonVersion)
        .filter(LessonVersion.lesson_id == lesson_id)
        .order_by(LessonVersion.version.desc())
        .all()
    )
    return {
        "id": lesson.id,
        "course_id": lesson.course_id,
        "code": lesson.code,
        "title": lesson.title,
        "goal": lesson.goal,
        "theses": lesson.theses,
        "for_frame": lesson.for_frame,
        "final_thought": lesson.final_thought,
        "source_ref": lesson.source_ref,
        "order": lesson.order,
        "status": lesson.status,
        "version": lesson.version,
        "ai_assisted_checked": lesson.ai_assisted_checked,
        "steps": [
            {
                "id": s.id,
                "order": s.order,
                "type": s.type,
                "payload": s.payload,
                "source_ref": s.source_ref,
                "is_key": s.is_key,
            }
            for s in lesson.steps
        ],
        "versions": [
            {
                "id": v.id,
                "version": v.version,
                "created_by": v.created_by,
                "created_at": v.created_at.isoformat(),
            }
            for v in versions
        ],
    }


@router.post("/lessons")
def admin_create_lesson(
    body: AdminLessonCreate,
    user: User = Depends(require_roles("admin", "editor", "superadmin")),
    db: Session = Depends(get_db),
):
    course = db.get(Course, body.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не знайдено")

    next_order = (max((l.order for l in course.lessons), default=0)) + 1
    lesson = Lesson(
        id=f"lesson_{uuid.uuid4().hex[:8]}",
        course_id=course.id,
        code=body.code,
        title=body.title,
        goal=body.goal,
        theses=body.theses,
        for_frame=body.for_frame,
        final_thought=body.final_thought,
        source_ref=body.source_ref,
        order=next_order,
        status="draft",
        version=1,
        ai_assisted_checked=body.ai_assisted_checked,
    )
    db.add(lesson)
    db.commit()
    return {"id": lesson.id, "status": lesson.status}


@router.patch("/lessons/{lesson_id}")
def admin_update_lesson(
    lesson_id: str,
    body: AdminLessonUpdate,
    user: User = Depends(require_roles("admin", "editor", "superadmin")),
    db: Session = Depends(get_db),
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не знайдено")

    if body.status == "published" and user.role not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Публікувати уроки може лише адміністратор (Наталія)")

    # Save version snapshot before modifying
    db.add(
        LessonVersion(
            id=f"lver_{lesson.id}_{lesson.version}_{uuid.uuid4().hex[:4]}",
            lesson_id=lesson.id,
            version=lesson.version,
            snapshot_json=_snapshot_lesson(lesson),
            created_by=user.id,
        )
    )

    for field in ("code", "title", "goal", "theses", "for_frame", "final_thought", "source_ref", "ai_assisted_checked"):
        val = getattr(body, field)
        if val is not None:
            setattr(lesson, field, val)

    if body.status is not None:
        if body.status not in ("draft", "review", "published"):
            raise HTTPException(status_code=400, detail="Невідомий статус уроку")
        lesson.status = body.status

    lesson.version += 1
    db.add(
        AuditLog(
            id=f"aud_{uuid.uuid4().hex[:10]}",
            actor_id=user.id,
            action="lesson_updated",
            entity="lesson",
            entity_id=lesson.id,
            details={"status": lesson.status, "version": lesson.version},
        )
    )
    db.commit()
    db.refresh(lesson)

    # Reindex Aroma KB whenever published or unpublished (Section 7 & 10 & 11.6)
    chunks_count = reindex_lesson_kb(db, lesson)
    return {"id": lesson.id, "status": lesson.status, "version": lesson.version, "kb_chunks": chunks_count}


@router.post("/lessons/{lesson_id}/publish")
def admin_publish_lesson(
    lesson_id: str,
    user: User = Depends(require_roles("admin", "superadmin")),
    db: Session = Depends(get_db),
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не знайдено")

    db.add(
        LessonVersion(
            id=f"lver_{lesson.id}_{lesson.version}_{uuid.uuid4().hex[:4]}",
            lesson_id=lesson.id,
            version=lesson.version,
            snapshot_json=_snapshot_lesson(lesson),
            created_by=user.id,
        )
    )
    lesson.status = "published"
    lesson.version += 1
    db.add(
        AuditLog(
            id=f"aud_{uuid.uuid4().hex[:10]}",
            actor_id=user.id,
            action="lesson_published",
            entity="lesson",
            entity_id=lesson.id,
            details={"version": lesson.version},
        )
    )
    db.commit()
    db.refresh(lesson)
    chunks_count = reindex_lesson_kb(db, lesson)
    return {"id": lesson.id, "status": "published", "version": lesson.version, "kb_chunks": chunks_count}


@router.post("/lessons/{lesson_id}/rollback/{version}")
def admin_rollback_lesson(
    lesson_id: str,
    version: int,
    user: User = Depends(require_roles("admin", "superadmin")),
    db: Session = Depends(get_db),
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не знайдено")

    ver = (
        db.query(LessonVersion)
        .filter(LessonVersion.lesson_id == lesson_id, LessonVersion.version == version)
        .order_by(LessonVersion.created_at.desc())
        .first()
    )
    if not ver:
        raise HTTPException(status_code=404, detail="Версію не знайдено")

    snap = ver.snapshot_json
    lesson.title = snap.get("title", lesson.title)
    lesson.goal = snap.get("goal", lesson.goal)
    lesson.theses = snap.get("theses", lesson.theses)
    lesson.for_frame = snap.get("for_frame", lesson.for_frame)
    lesson.final_thought = snap.get("final_thought", lesson.final_thought)
    lesson.source_ref = snap.get("source_ref", lesson.source_ref)
    lesson.version += 1
    db.commit()
    db.refresh(lesson)
    reindex_lesson_kb(db, lesson)
    return {"status": "rolled_back", "new_version": lesson.version}


@router.post("/lessons/{lesson_id}/steps")
def admin_create_step(
    lesson_id: str,
    body: AdminStepCreate,
    user: User = Depends(require_roles("admin", "editor", "superadmin")),
    db: Session = Depends(get_db),
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не знайдено")

    next_order = body.order or (max((s.order for s in lesson.steps), default=0) + 1)
    step = Step(
        id=f"step_{uuid.uuid4().hex[:10]}",
        lesson_id=lesson_id,
        order=next_order,
        type=body.type,
        payload=body.payload,
        source_ref=body.source_ref or lesson.source_ref,
        is_key=body.is_key,
    )
    db.add(step)
    db.commit()
    if lesson.status == "published":
        db.refresh(lesson)
        reindex_lesson_kb(db, lesson)
    return {"id": step.id, "order": step.order}


@router.patch("/steps/{step_id}")
def admin_update_step(
    step_id: str,
    body: AdminStepUpdate,
    user: User = Depends(require_roles("admin", "editor", "superadmin")),
    db: Session = Depends(get_db),
):
    step = db.get(Step, step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Крок не знайдено")

    for field in ("type", "payload", "source_ref", "is_key", "order"):
        val = getattr(body, field)
        if val is not None:
            setattr(step, field, val)
    db.commit()
    lesson = db.get(Lesson, step.lesson_id)
    if lesson and lesson.status == "published":
        reindex_lesson_kb(db, lesson)
    return {"id": step.id, "status": "updated"}


@router.delete("/steps/{step_id}")
def admin_delete_step(
    step_id: str,
    user: User = Depends(require_roles("admin", "editor", "superadmin")),
    db: Session = Depends(get_db),
):
    step = db.get(Step, step_id)
    if not step:
        raise HTTPException(status_code=404, detail="Крок не знайдено")
    lesson_id = step.lesson_id
    db.delete(step)
    db.commit()
    lesson = db.get(Lesson, lesson_id)
    if lesson and lesson.status == "published":
        reindex_lesson_kb(db, lesson)
    return {"status": "deleted"}


@router.post("/lessons/{lesson_id}/steps/reorder")
def admin_reorder_steps(
    lesson_id: str,
    body: AdminReorderSteps,
    user: User = Depends(require_roles("admin", "editor", "superadmin")),
    db: Session = Depends(get_db),
):
    lesson = db.get(Lesson, lesson_id)
    if not lesson:
        raise HTTPException(status_code=404, detail="Урок не знайдено")
    steps_map = {s.id: s for s in lesson.steps}
    for idx, sid in enumerate(body.step_ids, start=1):
        if sid in steps_map:
            steps_map[sid].order = idx
    db.commit()
    return {"status": "reordered"}


@router.post("/import-markdown")
def admin_import_markdown(
    body: AdminMarkdownImport,
    user: User = Depends(require_roles("admin", "editor", "superadmin")),
    db: Session = Depends(get_db),
):
    """Parse Natalia's markdown plan format (Мета, Тези, Для кадру, Фінальна думка) into a draft lesson (Section 10)."""
    course = db.get(Course, body.course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Курс не знайдено")

    text = body.markdown_text.strip()
    title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    raw_title = title_match.group(1).strip() if title_match else "Імпортований урок"
    code_match = re.search(r"(\d+\.\d+)", raw_title)
    code = code_match.group(1) if code_match else f"{course.order}.{len(course.lessons) + 1}"

    def _extract_section(label: str) -> str:
        pattern = rf"(?:^|\n)(?:#{{1,3}}\s*|\*\*)?{label}[:\*]*\s*\n?(.*?)(?=\n(?:#{{1,3}}\s|\*\*(?:Мета|Тези|Для кадру|Фінальна думка|Джерело))|$)"
        m = re.search(pattern, text, flags=re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else ""

    goal = _extract_section("Мета")
    theses_raw = _extract_section("Тези")
    theses = [
        re.sub(r"^[-*•]\s*", "", line).strip()
        for line in theses_raw.splitlines()
        if line.strip()
    ]
    for_frame = _extract_section("Для кадру")
    final_thought = _extract_section("Фінальна думка")
    source_ref = _extract_section("Джерело") or f"Імпорт із плану Наталії · {code}"

    next_order = max((l.order for l in course.lessons), default=0) + 1
    lesson = Lesson(
        id=f"lesson_{uuid.uuid4().hex[:8]}",
        course_id=course.id,
        code=code,
        title=raw_title,
        goal=goal,
        theses=theses,
        for_frame=for_frame,
        final_thought=final_thought,
        source_ref=source_ref,
        order=next_order,
        status="draft",
        version=1,
        ai_assisted_checked=True,
    )
    db.add(lesson)
    db.flush()

    cards_to_add = []
    if goal or theses:
        cards_to_add.append(
            (
                "Головна ідея уроку",
                (f"Мета: {goal}\n\n" if goal else "") + ("\n".join(f"• {t}" for t in theses)),
            )
        )
    if final_thought:
        cards_to_add.append(("Фінальна думка", final_thought))

    for idx, (ctitle, cbody) in enumerate(cards_to_add, start=1):
        db.add(
            Step(
                id=f"step_{uuid.uuid4().hex[:10]}",
                lesson_id=lesson.id,
                order=idx,
                type="card",
                payload={"title": ctitle, "body": cbody.strip(), "badge": f"Відео {code}"},
                source_ref=source_ref,
                is_key=False,
            )
        )

    db.commit()
    return {"lesson_id": lesson.id, "code": lesson.code, "title": lesson.title, "status": "draft"}


@router.post("/clips/{clip_id}/upload-video")
async def upload_clip_video(
    clip_id: str,
    lesson_id: str | None = None,
    file: UploadFile = File(...),
    user: User = Depends(require_roles("admin", "editor", "superadmin")),
    db: Session = Depends(get_db),
):
    clip = db.get(AromaClip, clip_id)
    if not clip:
        raise HTTPException(status_code=404, detail="Арома-ролик не знайдено")

    ext = Path(file.filename or "video.mp4").suffix.lower()
    if ext not in (".mp4", ".webm", ".mov"):
        raise HTTPException(status_code=400, detail="Підтримуються формати .mp4, .webm, .mov")

    safe_name = f"{clip.id}{ext}"
    dest = settings.media_dir / "videos" / safe_name
    content = await file.read()
    dest.write_bytes(content)

    clip.video_url = f"/media/videos/{safe_name}"
    if lesson_id:
        clip.lesson_id = lesson_id
    db.commit()
    return {"clip_id": clip.id, "video_url": clip.video_url, "lesson_id": clip.lesson_id}


@router.get("/analytics")
def admin_analytics(
    user: User = Depends(require_roles("admin", "editor", "superadmin")),
    db: Session = Depends(get_db),
):
    students = db.query(User).filter(User.role == "student").all()
    student_rows = []
    for st in students:
        completed = (
            db.query(LessonProgress)
            .filter(LessonProgress.user_id == st.id, LessonProgress.status == "completed")
            .count()
        )
        student_rows.append(
            {
                "id": st.id,
                "name": st.name,
                "email": st.email,
                "completed_lessons": completed,
                "streak_days": st.streak_days,
                "last_active_at": st.last_active_at.isoformat() if st.last_active_at else None,
            }
        )

    # Top error questions
    wrong_attempts = (
        db.query(StepAttempt.step_id, func.count(StepAttempt.id).label("errors"))
        .filter(StepAttempt.is_correct == False)
        .group_by(StepAttempt.step_id)
        .order_by(func.count(StepAttempt.id).desc())
        .limit(5)
        .all()
    )
    top_errors = []
    for step_id, err_count in wrong_attempts:
        step = db.get(Step, step_id)
        if step:
            q = (step.payload or {}).get("question") or (step.payload or {}).get("statement") or step.id
            top_errors.append({"step_id": step_id, "question": q, "errors": err_count})

    safety_events = (
        db.query(AromaMessage)
        .filter(AromaMessage.safety_triggered == True, AromaMessage.role == "user")
        .order_by(AromaMessage.created_at.desc())
        .limit(15)
        .all()
    )
    open_answers = (
        db.query(OpenAnswer)
        .order_by(OpenAnswer.created_at.desc())
        .limit(15)
        .all()
    )

    return {
        "students": student_rows,
        "top_errors": top_errors,
        "safety_events": [
            {
                "id": ev.id,
                "user_id": ev.user_id,
                "lesson_id": ev.lesson_id,
                "safety_reason": ev.safety_reason,
                "created_at": ev.created_at.isoformat(),
            }
            for ev in safety_events
        ],
        "open_answers": [
            {
                "id": oa.id,
                "user_id": oa.user_id,
                "step_id": oa.step_id,
                "text": oa.text,
                "aroma_feedback": oa.aroma_feedback,
                "mentor_reply": oa.mentor_reply,
                "created_at": oa.created_at.isoformat(),
            }
            for oa in open_answers
        ],
    }


@router.post("/open-answers/{answer_id}/reply")
def admin_reply_open_answer(
    answer_id: str,
    body: AdminMentorReply,
    user: User = Depends(require_roles("admin", "superadmin")),
    db: Session = Depends(get_db),
):
    oa = db.get(OpenAnswer, answer_id)
    if not oa:
        raise HTTPException(status_code=404, detail="Відповідь не знайдено")
    oa.mentor_reply = body.reply
    oa.reviewed_by = user.id
    db.commit()
    return {"status": "replied"}


@router.patch("/tariffs/{tariff_id}")
def admin_update_tariff(
    tariff_id: str,
    body: AdminTariffUpdate,
    user: User = Depends(require_roles("admin", "superadmin")),
    db: Session = Depends(get_db),
):
    tariff = db.get(Tariff, tariff_id)
    if not tariff:
        raise HTTPException(status_code=404, detail="Тариф не знайдено")
    if body.price_uah is not None:
        tariff.price_uah = body.price_uah
    if body.aroma_daily_limit is not None:
        tariff.aroma_daily_limit = body.aroma_daily_limit
    if body.description is not None:
        tariff.description = body.description
    db.commit()
    return {"id": tariff.id, "price_uah": tariff.price_uah, "aroma_daily_limit": tariff.aroma_daily_limit}

