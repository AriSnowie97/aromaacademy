import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Use an isolated temporary SQLite database for tests
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db.name}"

from backend.app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c
    try:
        os.unlink(_tmp_db.name)
    except OSError:
        pass


def _auth_header(client: TestClient, email: str) -> dict[str, str]:
    res = client.post("/api/auth/demo-switch", json={"email": email})
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_1_tariff_gating_blocks_direct_lesson_api(client: TestClient):
    """Criterion 1: Student on Basic tariff cannot read Standard-tier lesson 5.1 via API."""
    headers = _auth_header(client, "student-basic@aroma.ua")
    res = client.get("/api/lessons/lesson_5_1", headers=headers)
    assert res.status_code == 403
    assert res.json()["detail"]["code"] == "TARIFF_REQUIRED"


def test_2_webhook_opens_tariff_and_is_idempotent(client: TestClient):
    """Criterion 2: Payment webhook grants access; replaying same webhook does not duplicate."""
    login = client.post(
        "/api/auth/login",
        json={"email": "new-buyer@aroma.ua", "name": "Тестова", "accept_consent": True},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    # Before payment, lesson 5.1 is blocked
    assert client.get("/api/lessons/lesson_5_1", headers=headers).status_code == 403

    checkout = client.post("/api/billing/checkout", json={"tariff_id": "standard"}, headers=headers)
    assert checkout.status_code == 200
    webhook_payload = checkout.json()["demo_webhook_payload"]

    wh1 = client.post("/api/billing/webhook", json=webhook_payload)
    assert wh1.status_code == 200
    assert wh1.json()["status"] == "processed"

    # Replay same webhook -> idempotent
    wh2 = client.post("/api/billing/webhook", json=webhook_payload)
    assert wh2.status_code == 200
    assert wh2.json()["status"] == "already_processed"

    # Now lesson 5.1 is accessible
    res_lesson = client.get("/api/lessons/lesson_5_1", headers=headers)
    assert res_lesson.status_code == 200
    assert len(res_lesson.json()["steps"]) >= 4


def test_3_and_7_lesson_flow_persists_progress_and_has_disclaimer(client: TestClient):
    """Criteria 3 & 7: Lesson 1.1 steps complete, persist progress, and include disclaimer."""
    headers = _auth_header(client, "student-basic@aroma.ua")
    lesson = client.get("/api/lessons/lesson_1_1", headers=headers).json()
    assert "не медична консультація" in lesson["disclaimer"]

    answers = {
        "card": "viewed",
        "choice": 0,
        "true_false": False,
        "match": {
            "Ефірна олія": "Леткі ароматичні сполуки рослини",
            "Базова (жирна) олія": "Розведення та комфортне нанесення на шкіру",
            "1 крапля": "Безпечний старт для знайомства з ароматом",
        },
        "flashcard": "known",
    }
    for step in lesson["steps"]:
        ans_res = client.post(
            f"/api/steps/{step['id']}/answer",
            json={"answer": answers[step["type"]]},
            headers=headers,
        )
        assert ans_res.status_code == 200
        assert ans_res.json()["is_correct"] is True

    comp = client.post("/api/lessons/lesson_1_1/complete", headers=headers)
    assert comp.status_code == 200
    assert comp.json()["status"] == "completed"
    assert "не медична консультація" in comp.json()["disclaimer"]

    # Reload persists completed status
    reloaded = client.get("/api/lessons/lesson_1_1", headers=headers).json()
    assert reloaded["progress_status"] == "completed"


def test_4_module_3_key_safety_questions_block_until_correct(client: TestClient):
    """Criterion 4: Module 3 Safety lesson blocks completion if key safety steps are wrong."""
    headers = _auth_header(client, "student-basic@aroma.ua")
    lesson = client.get("/api/lessons/lesson_3_1", headers=headers).json()

    # Submit wrong answer for key step (step 3: choice, correct is 0)
    key_step = next(s for s in lesson["steps"] if s["is_key"] and s["type"] == "choice")
    wrong_res = client.post(f"/api/steps/{key_step['id']}/answer", json={"answer": 1}, headers=headers)
    assert wrong_res.status_code == 200
    assert wrong_res.json()["is_correct"] is False

    # Completing now must fail
    fail_comp = client.post("/api/lessons/lesson_3_1/complete", headers=headers)
    assert fail_comp.status_code == 400
    assert fail_comp.json()["detail"]["code"] == "KEY_SAFETY_UNANSWERED"

    # Answer all key steps correctly
    for step in lesson["steps"]:
        if step["is_key"]:
            val = 0 if step["type"] == "choice" else False
            ok_res = client.post(f"/api/steps/{step['id']}/answer", json={"answer": val}, headers=headers)
            assert ok_res.json()["is_correct"] is True

    ok_comp = client.post("/api/lessons/lesson_3_1/complete", headers=headers)
    assert ok_comp.status_code == 200
    assert ok_comp.json()["status"] == "completed"


def test_5_aroma_citations_tariff_filter_and_safety_state_machine(client: TestClient):
    """Criterion 5: Aroma cites lessons, respects tariff filter, and triggers safety on pregnancy."""
    basic_headers = _auth_header(client, "student-basic@aroma.ua")

    # Normal question within Module 1
    res_ok = client.post(
        "/api/aroma/ask",
        json={"lesson_id": "lesson_1_1", "message": "Чим ефірна олія відрізняється від жирної олії?"},
        headers=basic_headers,
    )
    assert res_ok.status_code == 200
    body_ok = res_ok.json()
    assert body_ok["safety"]["triggered"] is False
    assert len(body_ok["sources"]) >= 1
    assert body_ok["disclaimer"] is True

    # Pregnancy red flag triggers safety BEFORE model
    res_safe = client.post(
        "/api/aroma/ask",
        json={"message": "Яку ефірну олію можна при вагітності на 2 триместрі?"},
        headers=basic_headers,
    )
    assert res_safe.status_code == 200
    body_safe = res_safe.json()
    assert body_safe["safety"]["triggered"] is True
    assert body_safe["safety"]["route_to"] == "natalia_or_doctor"
    assert body_safe["sources"] == []


def test_6_admin_publish_updates_aroma_kb_and_markdown_import(client: TestClient):
    """Criterion 6: Importing & publishing a lesson in Admin panel immediately indexes it for Aroma."""
    admin_headers = _auth_header(client, "natalia@aroma.ua")
    md = """# 1.9 Гідролати та дифузори
**Мета:** Розібратися з унікальним терміном ультразвуковий гідролат у домашньому просторі.
**Тези:**
- Гідролат містить водорозчинні компоненти рослини
**Для кадру:** Флакон гідролату поруч із дифузором.
**Фінальна думка:** Гідролати дуже делікатні.
"""
    imp = client.post(
        "/api/admin/import-markdown",
        json={"course_id": "course_1", "markdown_text": md},
        headers=admin_headers,
    )
    assert imp.status_code == 200
    new_lesson_id = imp.json()["lesson_id"]

    pub = client.post(f"/api/admin/lessons/{new_lesson_id}/publish", headers=admin_headers)
    assert pub.status_code == 200
    assert pub.json()["kb_chunks"] >= 1

    student_headers = _auth_header(client, "student-basic@aroma.ua")
    ask = client.post(
        "/api/aroma/ask",
        json={"message": "Що таке ультразвуковий гідролат і які його компоненти?"},
        headers=student_headers,
    )
    assert ask.status_code == 200
    source_ids = [s["lesson_id"] for s in ask.json()["sources"]]
    assert new_lesson_id in source_ids


def test_7_aroma_remote_and_gemini_modes(client: TestClient, monkeypatch):
    """Remote Aroma service mode and direct Gemini REST mode work while preserving safety gating."""
    from backend.app import aroma_service

    student_headers = _auth_header(client, "student-standard@aroma.ua")
    captured: list[dict] = []

    class _MockResp:
        def __init__(self, status_code: int, payload: dict):
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"HTTP {self.status_code}")

        def json(self):
            return self._payload

    def fake_post(url, **kwargs):
        captured.append({"url": url, "kwargs": kwargs})
        if "/v1/aroma/ask" in url:
            return _MockResp(
                200,
                {
                    "answer": "Привіт з віддаленої Ароми 🌸",
                    "safety": {"triggered": False, "route_to": None, "reason": None},
                },
            )
        return _MockResp(
            200,
            {
                "candidates": [
                    {"content": {"parts": [{"text": "**Арома**: Тепло з курсу 🌿"}]}}
                ]
            },
        )

    monkeypatch.setattr(aroma_service.httpx, "post", fake_post)
    monkeypatch.setattr(aroma_service.settings, "aroma_service_mode", "remote")
    monkeypatch.setattr(aroma_service.settings, "aroma_service_url", "https://bot.example.com")
    monkeypatch.setattr(aroma_service.settings, "aroma_service_token", "secret-token")

    # Safety red-flag must still stop BEFORE calling external HTTP service
    safe_resp = client.post(
        "/api/aroma/ask",
        json={"message": "Яка доза олії безпечна при вагітності?"},
        headers=student_headers,
    )
    assert safe_resp.status_code == 200
    assert safe_resp.json()["safety"]["triggered"] is True
    assert captured == []

    # Normal query goes to remote /v1/aroma/ask with X-Service-Token & DB-derived tariff
    remote_resp = client.post(
        "/api/aroma/ask",
        json={"lesson_id": "lesson_1_1", "message": "Що таке ефірні олії?"},
        headers=student_headers,
    )
    assert remote_resp.status_code == 200
    assert remote_resp.json()["answer"] == "Привіт з віддаленої Ароми 🌸"
    assert len(captured) == 1
    assert captured[0]["url"] == "https://bot.example.com/v1/aroma/ask"
    assert captured[0]["kwargs"]["headers"]["X-Service-Token"] == "secret-token"
    assert captured[0]["kwargs"]["json"]["tariff"] == "standard"

    # Direct Gemini mode (without remote URL) strips ** markdown
    captured.clear()
    monkeypatch.setattr(aroma_service.settings, "aroma_service_mode", "gemini")
    monkeypatch.setattr(aroma_service.settings, "aroma_service_url", "")
    monkeypatch.setattr(aroma_service.settings, "gemini_api_key", "fake-gemini-key")

    gem_resp = client.post(
        "/api/aroma/ask",
        json={"lesson_id": "lesson_1_1", "message": "Як використовувати лаванду?"},
        headers=student_headers,
    )
    assert gem_resp.status_code == 200
    assert gem_resp.json()["answer"] == "Арома: Тепло з курсу 🌿"
    assert len(captured) == 1
    assert "generativelanguage.googleapis.com" in captured[0]["url"]


