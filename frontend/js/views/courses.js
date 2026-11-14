import { apiRequest } from "../api.js";
import { UK_I18N } from "../i18n.uk.js";
import { escapeHtml, openModal, closeModal } from "../utils.js";

let activeLevel = "learn";

export async function renderCourses(container, { navigate }) {
  container.innerHTML = `<div class="card">Завантаження модулів...</div>`;
  const data = await apiRequest("/api/courses");
  const courses = data.courses || [];

  const draw = () => {
    const filtered = courses.filter((c) => c.level === activeLevel);
    container.innerHTML = `
      <div class="flex-between" style="margin-bottom:14px;">
        <h1 style="margin:0;">Програма навчання</h1>
        <span class="pill-badge">Тариф: ${escapeHtml(data.tariff_id)}</span>
      </div>

      <div class="tabs">
        <button class="tab-btn ${activeLevel === "learn" ? "active" : ""}" data-lvl="learn">${UK_I18N.levels.learn}</button>
        <button class="tab-btn ${activeLevel === "share" ? "active" : ""}" data-lvl="share">${UK_I18N.levels.share}</button>
      </div>

      <div class="grid-3">
        ${filtered
          .map((c) => {
            const locked = !c.has_access;
            return `
            <div class="card" style="display:flex; flex-direction:column; justify-content:space-between; ${locked ? "opacity:0.86; border-style:dashed;" : ""}">
              <div>
                <div class="flex-between">
                  <span class="pill-badge ${c.is_mandatory ? "warn" : ""}">
                    Модуль ${c.order}${c.is_mandatory ? " · Обов'язковий" : ""}
                  </span>
                  <span class="muted">${c.total_lessons} відео</span>
                </div>
                <h3 style="margin: 12px 0 6px;">${escapeHtml(c.title)}</h3>
                <p class="muted" style="margin: 0 0 14px;">${escapeHtml(c.description)}</p>
              </div>
              <div class="flex-between">
                <span class="muted">Пройдено: ${c.completed_lessons} · Готово: ${c.published_lessons}</span>
                ${
                  locked
                    ? `<button class="btn btn-accent btn-sm open-tariff-btn" data-req="${c.min_tariff}">🔒 Тариф «${c.min_tariff}»</button>`
                    : `<button class="btn btn-primary btn-sm open-course-btn" data-id="${c.id}">Відкрити</button>`
                }
              </div>
            </div>
          `;
          })
          .join("")}
      </div>
    `;

    container.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.onclick = () => {
        activeLevel = btn.dataset.lvl;
        draw();
      };
    });

    container.querySelectorAll(".open-course-btn").forEach((btn) => {
      btn.onclick = () => navigate(`#course/${btn.dataset.id}`);
    });

    container.querySelectorAll(".open-tariff-btn").forEach((btn) => {
      btn.onclick = () => {
        openModal(`
          <h2 style="margin-top:0;">Відкрийте тариф «${escapeHtml(btn.dataset.req)}»</h2>
          <p>Доступ до цього модуля перевіряється на сервері й відкривається одразу після активації тарифу.</p>
          <div style="display:flex; gap:10px; justify-content:flex-end;">
            <button class="btn btn-secondary" id="modal-close-btn">Пізніше</button>
            <button class="btn btn-primary" id="modal-go-tariffs">Перейти до тарифів</button>
          </div>
        `);
        document.getElementById("modal-close-btn").onclick = closeModal;
        document.getElementById("modal-go-tariffs").onclick = () => {
          closeModal();
          navigate("#tariffs");
        };
      };
    });
  };

  draw();
}

export async function renderCourseMap(container, { courseId, navigate }) {
  container.innerHTML = `<div class="card">Завантаження карти курсу...</div>`;
  const course = await apiRequest(`/api/courses/${courseId}`);

  container.innerHTML = `
    <div style="margin-bottom:14px;">
      <button class="btn btn-secondary btn-sm" id="back-courses">← До всіх модулів</button>
    </div>

    <div class="course-map-grid">
      <div class="card sticky-panel">
        <div class="flex-between">
          <span class="pill-badge">Модуль ${course.order}</span>
          ${course.has_access ? `<span class="pill-badge">✓ Доступно</span>` : `<span class="pill-badge warn">🔒 Тариф «${course.min_tariff}»</span>`}
        </div>
        <h1 style="margin: 12px 0 8px; font-size:38px;">${escapeHtml(course.title)}</h1>
        <p class="muted" style="margin:0 0 14px;">${escapeHtml(course.description)}</p>
        <div class="card-soft">
          <strong>Відео-уроків у модулі:</strong> ${course.lessons.length}
        </div>
      </div>

      <div class="course-path">
        ${course.lessons
          .map((l) => {
            const isDone = l.progress_status === "completed";
            const isDraft = l.status !== "published";
            return `
            <div class="lesson-node ${isDone ? "done" : ""} ${isDraft ? "draft" : ""}" data-lesson-id="${l.id}">
              <div style="display:flex; align-items:center; gap:14px;">
                <div class="lesson-circle">${isDone ? "✓" : escapeHtml(l.code)}</div>
                <div>
                  <div style="font-weight:700; font-size:15px;">${escapeHtml(l.title)}</div>
                  <div class="muted">
                    ${isDraft ? "Чернетка (на підготовці в Наталії)" : `${l.steps_count} кроків`}
                    ${l.has_video ? " · 🎬 Відео" : ""}
                  </div>
                </div>
              </div>
              <span class="pill-badge">${isDone ? "Пройдено" : isDraft ? "Чернетка" : "Старт →"}</span>
            </div>
          `;
          })
          .join("")}
      </div>
    </div>
  `;

  container.querySelector("#back-courses").onclick = () => navigate("#courses");
  container.querySelectorAll(".lesson-node").forEach((node) => {
    node.onclick = () => navigate(`#lesson/${node.dataset.lessonId}`);
  });
}
