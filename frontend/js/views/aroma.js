import { apiRequest } from "../api.js";
import { UK_I18N } from "../i18n.uk.js";
import { escapeHtml, showToast } from "../utils.js";

const SEND_SVG = `<svg viewBox="0 0 24 24" fill="none" width="20" height="20"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

export async function renderAroma(container, { user, lessonId = null, navigate }) {
  container.innerHTML = `<div class="card">Завантаження чату з Аромою...</div>`;
  const hist = await apiRequest(
    lessonId ? `/api/aroma/history?lesson_id=${encodeURIComponent(lessonId)}` : "/api/aroma/history"
  );

  const messages = hist.messages || [];
  let remaining = hist.remaining_today;

  const draw = () => {
    container.innerHTML = `
      <div class="aroma-workspace">
        <div class="card sticky-panel">
          <h1 style="margin:0; font-size:40px;">Арома 🌸</h1>
          <div class="muted" style="margin-bottom:10px;">${UK_I18N.aiLabel} · шукає лише у матеріалах вашого тарифу</div>
          ${
            remaining !== null && remaining !== undefined
              ? `<div class="pill-badge gold" style="margin-bottom:10px;">Залишилось сьогодні: ${remaining}</div>`
              : `<div class="pill-badge" style="margin-bottom:10px;">Безліміт за тарифом</div>`
          }
          ${lessonId ? `<div class="pill-badge" style="margin-bottom:10px;">Контекст: ${escapeHtml(lessonId)}</div>` : ""}

          <div class="disclaimer-box">
            <span>ℹ️</span>
            <span>${UK_I18N.disclaimer}</span>
          </div>

          <div class="section-label" style="margin-top:14px;">Швидкі запитання</div>
          <div style="display:flex; flex-direction:column; gap:8px;">
            <button class="chat-suggestion-chip quick-q">Чим ефірна олія відрізняється від жирної?</button>
            <button class="chat-suggestion-chip quick-q">Що робити, якщо олія потрапила в очі?</button>
            <button class="chat-suggestion-chip quick-q">Чи можна олії при вагітності?</button>
          </div>

          ${
            user.tariff_id === "personal"
              ? `<div style="margin-top:14px;"><button class="btn btn-primary btn-block btn-sm" id="book-natalia-btn">👩‍🏫 Запис до Наталії</button></div>`
              : ""
          }
        </div>

        <div class="card">
          <div class="chat-log" id="aroma-chat-log">
            ${
              messages.length === 0
                ? `<div style="text-align:center; padding:48px 16px;">
                     <div style="font-size:44px; margin-bottom:8px;">🌸</div>
                     <div style="font-weight:700; font-size:17px; color:var(--color-text-h);">Привіт! Я Арома</div>
                     <div class="muted" style="margin-top:6px;">Запитайте мене про основи ефірних олій, правила безпеки або тему доступного вам модуля.</div>
                   </div>`
                : messages
                    .map(
                      (m) => `
                    <div class="chat-msg ${m.role} ${m.safety_triggered ? "safety" : ""}">
                      ${m.safety_triggered && m.role === "assistant" ? `<div class="pill-badge warn" style="margin-bottom:6px;">⚠ Автомат безпеки</div>` : ""}
                      <div style="white-space:pre-line;">${escapeHtml(m.text)}</div>
                      ${
                        (m.sources || []).length > 0
                          ? `<div>${m.sources
                              .map(
                                (s) =>
                                  `<button class="source-chip" data-lesson="${escapeHtml(s.lesson_id)}">📖 ${escapeHtml(s.title)}</button>`
                              )
                              .join("")}</div>`
                          : ""
                      }
                    </div>
                  `
                    )
                    .join("")
            }
          </div>

          <form id="aroma-form" class="chat-write-bar">
            <input id="aroma-input" class="chat-pill-input" type="text" placeholder="Запитайте Арому..." required />
            <button class="chat-send-circle" type="submit" aria-label="Надіслати">${SEND_SVG}</button>
          </form>
        </div>
      </div>
    `;

    const logEl = container.querySelector("#aroma-chat-log");
    logEl.scrollTop = logEl.scrollHeight;

    container.querySelectorAll(".source-chip").forEach((chip) => {
      chip.onclick = () => navigate(`#lesson/${chip.dataset.lesson}`);
    });

    const sendQuestion = async (text) => {
      messages.push({ role: "user", text, sources: [], safety_triggered: false });
      draw();
      try {
        const res = await apiRequest("/api/aroma/ask", {
          method: "POST",
          body: { lesson_id: lessonId, message: text },
        });
        remaining = res.remaining_today;
        messages.push({
          role: "assistant",
          text: res.answer,
          sources: res.sources || [],
          safety_triggered: res.safety?.triggered,
        });
        draw();
      } catch (err) {
        showToast(err.message);
      }
    };

    container.querySelector("#aroma-form").onsubmit = (e) => {
      e.preventDefault();
      const val = container.querySelector("#aroma-input").value.trim();
      if (val) sendQuestion(val);
    };

    container.querySelectorAll(".quick-q").forEach((btn) => {
      btn.onclick = () => sendQuestion(btn.textContent);
    });

    const bookBtn = container.querySelector("#book-natalia-btn");
    if (bookBtn) {
      bookBtn.onclick = () =>
        showToast("Запит на персональний розбір передано Наталії (функція тарифу Персональний).");
    }
  };

  draw();
}
