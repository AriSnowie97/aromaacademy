import { apiRequest } from "../api.js";
import { UK_I18N } from "../i18n.uk.js";
import { escapeHtml } from "../utils.js";

export async function renderHome(container, { user, navigate }) {
  container.innerHTML = `<div class="card">Завантаження кабінету...</div>`;
  const data = await apiRequest("/api/courses");
  const courses = data.courses || [];

  const available = courses.filter((c) => c.has_access);
  const nextCourse =
    available.find((c) => c.published_lessons > c.completed_lessons) || available[0];

  let nextLessonId = "lesson_1_1";
  let nextLessonLabel = "1.1 Що таке ефірна олія";
  if (nextCourse) {
    const detail = await apiRequest(`/api/courses/${nextCourse.id}`);
    const nextLesson =
      detail.lessons.find(
        (l) => l.status === "published" && l.progress_status !== "completed"
      ) || detail.lessons.find((l) => l.status === "published");
    if (nextLesson) {
      nextLessonId = nextLesson.id;
      nextLessonLabel = `${nextLesson.code} ${nextLesson.title}`;
    }
  }

  const totalCompleted = courses.reduce((acc, c) => acc + c.completed_lessons, 0);

  container.innerHTML = `
    <div class="card hero-card">
      <div class="flex-between">
        <div>
          <span class="pill-badge">Тариф: ${escapeHtml(user.tariff_name)}</span>
          <h1 style="margin: 10px 0 6px;">Вітаємо, ${escapeHtml(user.name)} 🌸</h1>
          <p class="muted" style="font-size:15px; max-width:620px; color:var(--color-text);">
            Короткі уроки з ароматерапії без штрафів та «життів» — навчайтесь у комфортному ритмі на телефоні чи комп'ютері.
          </p>
        </div>
        <div style="text-align:right;">
          <div style="font-size:32px; font-weight:800; color:var(--color-surface);">🔥 ${user.streak_days || 0}</div>
          <div class="muted">днів серії</div>
        </div>
      </div>
    </div>

    <div class="section-label">Швидкі дії</div>
    <div class="grid-3" style="margin-bottom:20px;">
      <button class="action-card-btn" id="continue-lesson-btn">
        <div class="action-card-icon">▶</div>
        <div class="action-card-text">
          <strong>Продовжити урок</strong>
          <span>${escapeHtml(nextLessonLabel)}</span>
        </div>
        <div>→</div>
      </button>

      <button class="action-card-btn" id="open-courses-btn">
        <div class="action-card-icon">📚</div>
        <div class="action-card-text">
          <strong>Усі 12 модулів</strong>
          <span>Рівні «Вчитися» та «Ділитися»</span>
        </div>
        <div>→</div>
      </button>

      <button class="action-card-btn" id="go-aroma-btn">
        <div class="action-card-icon">🌸</div>
        <div class="action-card-text">
          <strong>Запитати Арому</strong>
          <span>Відповіді з посиланням на урок</span>
        </div>
        <div>→</div>
      </button>
    </div>

    <div class="section-label">Ваш прогрес зараз</div>
    <div class="grid-3">
      <div class="card">
        <div class="muted">Пройдено уроків</div>
        <div style="font-size:30px; font-weight:800; color:var(--color-surface); margin:6px 0;">${totalCompleted}</div>
        <div class="muted">Готові уроки: 1.1, 3.1, 5.1</div>
      </div>
      <div class="card">
        <div class="muted">Картки повторення</div>
        <div style="font-size:18px; font-weight:700; margin:8px 0 12px;">Колода інтервалів</div>
        <button class="btn btn-secondary btn-sm" id="go-review-btn">Повторити зараз</button>
      </div>
      <div class="card">
        <div class="muted">Доступ до модулів</div>
        <div style="font-size:18px; font-weight:700; margin:8px 0 12px;">${available.length} з ${courses.length} модулів</div>
        <button class="btn btn-secondary btn-sm" id="go-tariffs-btn">Керувати тарифом</button>
      </div>
    </div>

    <div class="disclaimer-box">
      <span>ℹ️</span>
      <span>${UK_I18N.disclaimer}</span>
    </div>
  `;

  container.querySelector("#continue-lesson-btn").onclick = () =>
    navigate(`#lesson/${nextLessonId}`);
  container.querySelector("#open-courses-btn").onclick = () => navigate("#courses");
  container.querySelector("#go-review-btn").onclick = () => navigate("#review");
  container.querySelector("#go-aroma-btn").onclick = () => navigate("#aroma");
  container.querySelector("#go-tariffs-btn").onclick = () => navigate("#tariffs");
}
