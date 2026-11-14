import hashlib
import math
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from .auth import get_allowed_tariffs
from .config import get_settings
from .models import AromaMessage, Course, KbChunk, Lesson, Tariff, utcnow


settings = get_settings()

# Safety state machine rules evaluated BEFORE any LLM/RAG call (Section 6 & 9).
SAFETY_RULES: list[tuple[str, str, str]] = [
    (
        "pregnancy_lactation",
        r"(вагітн|беремен|грудн|лактац|годуван|кормлен|полог|род[иыа])",
        "Питання стосується вагітності або грудного вигодовування.",
    ),
    (
        "children_infants",
        r"(немовля|новонародж|младен|дитин|діт[ея]|ребен|дет[ия]|малюк|малыш|до\s*[0-6]\s*(рок|лет|міс|мес))",
        "Питання стосується застосування ефірних олій дітям.",
    ),
    (
        "medical_diagnosis_or_internal",
        r"(діагноз|диагноз|лікуван|лечен|вилікув|вылеч|онколог|рак\b|епілепс|эпилепс|астм|анафілак|діабет|диабет|замість\s+ліків|вместо\s+лекарств|пити\s+олі|пить\s+масл|внутрішн|внутрь|дозуван|дозиров)",
        "Питання містить запит на медичне лікування, діагноз, внутрішній прийом або точне дозування.",
    ),
]


def check_safety_state_machine(message: str) -> tuple[bool, Optional[str], Optional[str]]:
    text = message.lower().strip()
    for reason_code, pattern, description in SAFETY_RULES:
        if re.search(pattern, text):
            return True, reason_code, description
    return False, None, None


def compute_text_embedding(text: str, dims: int = 96) -> list[float]:
    """Lightweight deterministic character-trigram + token embedding for local RAG."""
    vec = [0.0] * dims
    cleaned = re.sub(r"[^\w\sа-яА-ЯіїєґІЇЄҐёЁ]", " ", text.lower())
    tokens = cleaned.split()
    features: list[str] = []
    for tok in tokens:
        features.append(f"w:{tok}")
        if len(tok) >= 3:
            for i in range(len(tok) - 2):
                features.append(f"g:{tok[i:i+3]}")
    if not features:
        return vec
    for feat in features:
        digest = hashlib.blake2b(feat.encode("utf-8"), digest_size=4).digest()
        idx = int.from_bytes(digest, "little") % dims
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [round(v / norm, 6) for v in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


def reindex_lesson_kb(db: Session, lesson: Lesson) -> int:
    """Rebuild kb_chunks whenever a lesson is published or updated (Section 7 & 10)."""
    db.query(KbChunk).filter(KbChunk.lesson_id == lesson.id).delete()

    if lesson.status != "published":
        db.commit()
        return 0

    course = db.get(Course, lesson.course_id)
    if not course:
        db.commit()
        return 0

    sections: list[tuple[str, str]] = []
    header = f"Урок {lesson.code}: {lesson.title}"
    summary_parts = [header]
    if lesson.goal:
        summary_parts.append(f"Мета: {lesson.goal}")
    if lesson.theses:
        summary_parts.append("Тези: " + "; ".join(lesson.theses))
    if lesson.final_thought:
        summary_parts.append(f"Фінальна думка: {lesson.final_thought}")
    sections.append((" ".join(summary_parts), lesson.source_ref or header))

    for step in lesson.steps:
        p = step.payload or {}
        if step.type == "card":
            body = f"{header}. {p.get('title', '')}. {p.get('body', '')}".strip()
            sections.append((body, step.source_ref or lesson.source_ref or header))
        elif step.type in ("choice", "true_false", "open", "flashcard"):
            q = p.get("question") or p.get("statement") or p.get("front") or ""
            exp = p.get("explanation") or p.get("sample_answer") or p.get("back") or ""
            if q or exp:
                sections.append(
                    (f"{header}. {q} {exp}".strip(), step.source_ref or lesson.source_ref or header)
                )

    count = 0
    for idx, (chunk_text, source_ref) in enumerate(sections, start=1):
        if not chunk_text.strip():
            continue
        chunk = KbChunk(
            id=f"kb_{lesson.id}_{idx}_{uuid.uuid4().hex[:6]}",
            lesson_id=lesson.id,
            course_id=course.id,
            min_tariff=course.min_tariff,
            version=lesson.version,
            title=f"{lesson.code} {lesson.title}",
            text=chunk_text.strip(),
            embedding=compute_text_embedding(chunk_text),
            source_ref=source_ref,
        )
        db.add(chunk)
        count += 1

    db.commit()
    return count


def get_remaining_daily_quota(db: Session, user_id: str, tariff_id: str) -> Optional[int]:
    tariff = db.get(Tariff, tariff_id)
    if not tariff or tariff.aroma_daily_limit is None:
        return None
    since = utcnow() - timedelta(hours=24)
    used = (
        db.query(AromaMessage)
        .filter(
            AromaMessage.user_id == user_id,
            AromaMessage.role == "user",
            AromaMessage.created_at >= since,
        )
        .count()
    )
    return max(0, tariff.aroma_daily_limit - used)


def process_aroma_ask(
    db: Session,
    user_id: str,
    tariff_id: str,
    message: str,
    lesson_id: Optional[str] = None,
    language: str = "uk",
) -> dict:
    """Core Aroma service logic adhering to POST /v1/aroma/ask contract (Section 6)."""
    clean_msg = message.strip()
    if not clean_msg:
        return {
            "answer": "Напишіть, будь ласка, запитання за матеріалами курсу.",
            "sources": [],
            "safety": {"triggered": False, "route_to": None, "reason": None},
            "disclaimer": True,
            "disclaimer_text": settings.disclaimer_text,
            "ai_label": "Штучний інтелект Арома",
            "remaining_today": get_remaining_daily_quota(db, user_id, tariff_id),
        }

    # Check daily limit on Basic tariff
    remaining = get_remaining_daily_quota(db, user_id, tariff_id)
    if remaining is not None and remaining <= 0:
        return {
            "answer": (
                "Денний ліміт запитань до Ароми на тарифі «Базовий» вичерпано. "
                "Перейдіть на тариф «Стандарт» для безлімітних запитань за всіма курсами або поверніться завтра."
            ),
            "sources": [],
            "safety": {"triggered": False, "route_to": None, "reason": None},
            "disclaimer": True,
            "disclaimer_text": settings.disclaimer_text,
            "ai_label": "Штучний інтелект Арома",
            "remaining_today": 0,
        }

    # Log user message minimally (avoid storing health details if safety triggers)
    triggered, reason_code, reason_desc = check_safety_state_machine(clean_msg)

    user_msg = AromaMessage(
        id=f"amsg_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        lesson_id=lesson_id,
        role="user",
        text="[Запит зупинено автоматом безпеки]" if triggered else clean_msg,
        sources=[],
        safety_triggered=triggered,
        safety_reason=reason_code,
    )
    db.add(user_msg)

    if triggered:
        safe_answer = (
            f"Я зупинила підбір поради: {reason_desc} "
            "За правилами безпеки Аромакадемії, у таких випадках я не даю рекомендацій, "
            "дозувань чи медичних порад. Будь ласка, зверніться до лікаря або передайте запит Наталії "
            "для індивідуального розгляду."
        )
        bot_msg = AromaMessage(
            id=f"amsg_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            lesson_id=lesson_id,
            role="assistant",
            text=safe_answer,
            sources=[],
            safety_triggered=True,
            safety_reason=reason_code,
        )
        db.add(bot_msg)
        db.commit()
        return {
            "answer": safe_answer,
            "sources": [],
            "safety": {
                "triggered": True,
                "route_to": "natalia_or_doctor",
                "reason": reason_code,
            },
            "disclaimer": True,
            "disclaimer_text": settings.disclaimer_text,
            "ai_label": "Штучний інтелект Арома",
            "remaining_today": get_remaining_daily_quota(db, user_id, tariff_id),
        }

    # Filter KB strictly at DB query level by tariff (Section 6.1 & 7)
    allowed_tariffs = get_allowed_tariffs(tariff_id)
    if not allowed_tariffs:
        answer = (
            "Зараз у вас немає активної підписки. Оформіть тариф «Базовий» або вищий, "
            "щоб ставити запитання Аромі за матеріалами курсу."
        )
        bot_msg = AromaMessage(
            id=f"amsg_{uuid.uuid4().hex[:12]}",
            user_id=user_id,
            lesson_id=lesson_id,
            role="assistant",
            text=answer,
            sources=[],
            safety_triggered=False,
        )
        db.add(bot_msg)
        db.commit()
        return {
            "answer": answer,
            "sources": [],
            "safety": {"triggered": False, "route_to": None, "reason": None},
            "disclaimer": True,
            "disclaimer_text": settings.disclaimer_text,
            "ai_label": "Штучний інтелект Арома",
            "remaining_today": None,
        }

    chunks = (
        db.query(KbChunk)
        .filter(KbChunk.min_tariff.in_(allowed_tariffs))
        .all()
    )

    query_vec = compute_text_embedding(clean_msg)
    query_words = {
        w for w in re.findall(r"[\wа-яА-ЯіїєґІЇЄҐ]{3,}", clean_msg.lower())
    }

    scored: list[tuple[float, KbChunk]] = []
    for chunk in chunks:
        sim = cosine_similarity(query_vec, chunk.embedding or [])
        chunk_lower = chunk.text.lower()
        overlap = sum(1 for w in query_words if w in chunk_lower) * 0.08
        lesson_boost = 0.18 if (lesson_id and chunk.lesson_id == lesson_id) else 0.0
        total_score = sim + overlap + lesson_boost
        scored.append((total_score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    top_matches = [(s, c) for s, c in scored[:3] if s >= 0.14]

    if not top_matches:
        answer = (
            "У доступних матеріалах вашого тарифу немає точної відповіді на це питання. "
            "Рекомендую переглянути картки уроків або запитати Наталію."
        )
        sources = []
    else:
        best_snippets: list[str] = []
        seen_lessons: set[str] = set()
        sources = []
        for _, chunk in top_matches:
            best_snippets.append(chunk.text)
            if chunk.lesson_id not in seen_lessons:
                seen_lessons.add(chunk.lesson_id)
                sources.append(
                    {
                        "lesson_id": chunk.lesson_id,
                        "title": chunk.title,
                        "source_ref": chunk.source_ref,
                    }
                )
        lead_text = best_snippets[0]
        if len(best_snippets) > 1:
            answer = f"Ось що є в матеріалах курсу: {lead_text}\n\nДодатково: {best_snippets[1]}"
        else:
            answer = f"За матеріалами курсу: {lead_text}"

    bot_msg = AromaMessage(
        id=f"amsg_{uuid.uuid4().hex[:12]}",
        user_id=user_id,
        lesson_id=lesson_id,
        role="assistant",
        text=answer,
        sources=sources,
        safety_triggered=False,
    )
    db.add(bot_msg)
    db.commit()

    return {
        "answer": answer,
        "sources": sources,
        "safety": {"triggered": False, "route_to": None, "reason": None},
        "disclaimer": True,
        "disclaimer_text": settings.disclaimer_text,
        "ai_label": "Штучний інтелект Арома",
        "remaining_today": get_remaining_daily_quota(db, user_id, tariff_id),
    }


def evaluate_open_answer_with_aroma(
    answer_text: str, key_points: list[str], sample_answer: str
) -> str:
    """Compare student's open answer ONLY against sample key points (Section 5)."""
    triggered, _, _ = check_safety_state_machine(answer_text)
    if triggered:
        return (
            "Ваша відповідь згадує тему здоров'я, вагітності або дітей. "
            "Арома не оцінює індивідуальні випадки здоров'я — звіртеся, будь ласка, зі зразком або запитайте Наталію."
        )

    lower_ans = answer_text.lower()
    matched = []
    missed = []
    for kp in key_points:
        words = [w for w in re.findall(r"[\wа-яА-ЯіїєґІЇЄҐ]{4,}", kp.lower())]
        if any(w in lower_ans for w in words):
            matched.append(kp)
        else:
            missed.append(kp)

    if not key_points:
        return "Відповідь збережено! Порівняйте її зі зразком відповіді вище."

    parts = [f"Зі зразком збігаються {len(matched)} з {len(key_points)} ключових пунктів."]
    if matched:
        parts.append("Добре розкрито: " + "; ".join(matched) + ".")
    if missed:
        parts.append("Варто звернути увагу також на: " + "; ".join(missed) + ".")
    return " ".join(parts)

