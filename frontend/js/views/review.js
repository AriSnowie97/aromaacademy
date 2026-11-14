import { apiRequest } from "../api.js";
import { escapeHtml, showToast } from "../utils.js";

export async function renderReview(container) {
  container.innerHTML = `<div class="card">Завантаження колоди карток...</div>`;
  const data = await apiRequest("/api/review");
  const cards = data.cards || [];
  let idx = 0;
  let flipped = false;

  const draw = () => {
    if (cards.length === 0) {
      container.innerHTML = `
        <div class="card">
          <h1 style="margin-top:0;">Картки для повторення</h1>
          <p class="muted">Поки що в доступних уроках немає карток. Пройдіть урок 1.1 або 5.1!</p>
        </div>
      `;
      return;
    }

    const card = cards[idx];
    container.innerHTML = `
      <div class="flex-between" style="margin-bottom:12px;">
        <h1 style="margin:0;">Повторити картки</h1>
        <span class="pill-badge">Картка ${idx + 1} з ${cards.length}</span>
      </div>

      <div class="card">
        <div class="muted" style="margin-bottom:8px;">
          Урок ${escapeHtml(card.lesson_code)} · Інтервал: ${card.interval_days} дн.
        </div>

        <div class="flashcard-box" id="review-flip-box" tabindex="0">
          <div class="muted">${flipped ? "Відповідь:" : "Питання (натисніть, щоб перегорнути):"}</div>
          <div style="font-size:1.2rem; font-weight:700;">
            ${escapeHtml(flipped ? card.back : card.front)}
          </div>
        </div>

        <div class="muted" style="margin-top:10px; font-size:0.82rem;">Джерело: ${escapeHtml(card.source_ref)}</div>

        <div style="display:flex; gap:10px; margin-top:16px;">
          <button class="btn btn-secondary btn-block" id="btn-repeat">🔁 Повторити (1 день)</button>
          <button class="btn btn-primary btn-block" id="btn-known">✓ Знав (збільшити інтервал)</button>
        </div>
      </div>
    `;

    container.querySelector("#review-flip-box").onclick = () => {
      flipped = !flipped;
      draw();
    };

    const submit = async (result) => {
      const res = await apiRequest("/api/review", {
        method: "POST",
        body: { step_id: card.step_id, result },
      });
      showToast(`Наступне повторення через ${res.interval_days} дн.`);
      flipped = false;
      idx = (idx + 1) % cards.length;
      cards[idx === 0 ? cards.length - 1 : idx - 1].interval_days = res.interval_days;
      draw();
    };

    container.querySelector("#btn-repeat").onclick = () => submit("repeat");
    container.querySelector("#btn-known").onclick = () => submit("known");
  };

  draw();
}

