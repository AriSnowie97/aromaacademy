import { apiRequest, setToken } from "../api.js";
import { UK_I18N } from "../i18n.uk.js";
import { showToast } from "../utils.js";

const DEMO_ACCOUNTS = [
  { email: "student-basic@aroma.ua", label: "Олена · Тариф «Базовий»", desc: "Модулі 1–3, ліміт Ароми" },
  { email: "student-standard@aroma.ua", label: "Марія · Тариф «Стандарт»", desc: "Модулі 1–7, безліміт Арома" },
  { email: "student-personal@aroma.ua", label: "Софія · Тариф «Персональний»", desc: "Усі 12 модулів + супровід" },
  { email: "natalia@aroma.ua", label: "Наталія Котелянська · Адмін", desc: "Керування уроками та публікація" },
];

export function renderLogin(container, { onAuthenticated, toggleTheme, getTheme }) {
  container.innerHTML = `
    <div style="max-width: 980px; margin: 20px auto;">
      <div class="flex-between" style="margin-bottom: 14px;">
        <span class="pill-badge">doTERRA · Навчання</span>
        <button id="login-theme-btn" class="theme-toggle-btn" title="Перемкнути тему">
          ${getTheme?.() === "dark" ? "🌙" : "☀️"}
        </button>
      </div>

      <div class="login-split">
        <div style="display:flex; flex-direction:column; gap:16px;">
          <div class="card hero-card" style="margin-bottom:0;">
            <h1>${UK_I18N.appName} 🌸</h1>
            <p style="margin: 0; font-size:15px;">
              Короткі кроки з ароматерапії у форматі Duolingo + цифрова помічниця Арома. Працює на комп'ютері та телефоні.
            </p>
          </div>

          <div class="card" style="margin-bottom:0; flex:1;">
            <div class="section-label">Швидкий вхід для тестування версії 1</div>
            <div class="grid-2">
              ${DEMO_ACCOUNTS.map(
                (acc) => `
                <button class="btn btn-secondary demo-login-btn" data-email="${acc.email}" style="flex-direction:column; align-items:flex-start; text-align:left; padding:12px;">
                  <strong>${acc.label}</strong>
                  <span class="muted" style="font-size:12px;">${acc.desc}</span>
                </button>
              `
              ).join("")}
            </div>
          </div>
        </div>

        <div class="card" style="margin-bottom:0;">
          <h2 style="margin-top:0;">Вхід або реєстрація</h2>
          <form id="login-form">
            <div class="form-row">
              <label class="field-label" for="login-email">Email</label>
              <input id="login-email" class="input" type="email" required placeholder="your@email.com" />
            </div>
            <div class="form-row">
              <label class="field-label" for="login-name">Ім'я (для нових учнів)</label>
              <input id="login-name" class="input" type="text" placeholder="Олена" />
            </div>
            <div class="form-row">
              <label class="field-label" for="login-tg">Telegram ID / @username (необов'язково)</label>
              <input id="login-tg" class="input" type="text" placeholder="@username" />
            </div>
            <div class="form-row" style="display:flex; gap:8px; align-items:flex-start;">
              <input id="login-consent" type="checkbox" checked style="margin-top:4px;" />
              <label for="login-consent" class="muted">
                Погоджуюсь на обробку персональних даних (версія 2026-11-v1) і розумію, що матеріали не є медичною консультацією.
              </label>
            </div>
            <button class="btn btn-primary btn-block" type="submit">Увійти без пароля</button>
          </form>
        </div>
      </div>
    </div>
  `;

  const tBtn = container.querySelector("#login-theme-btn");
  if (tBtn && toggleTheme) {
    tBtn.onclick = () => {
      toggleTheme();
      tBtn.textContent = getTheme() === "dark" ? "🌙" : "☀️";
    };
  }

  container.querySelector("#login-form").onsubmit = async (e) => {
    e.preventDefault();
    const email = container.querySelector("#login-email").value.trim();
    const name = container.querySelector("#login-name").value.trim();
    const telegram_id = container.querySelector("#login-tg").value.trim() || null;
    const accept_consent = container.querySelector("#login-consent").checked;
    try {
      const res = await apiRequest("/api/auth/login", {
        method: "POST",
        body: { email, name: name || null, telegram_id, accept_consent },
      });
      setToken(res.access_token);
      showToast("Вітаємо в Аромакадемії!");
      onAuthenticated(res.user);
    } catch (err) {
      showToast(err.message);
    }
  };

  container.querySelectorAll(".demo-login-btn").forEach((btn) => {
    btn.onclick = async () => {
      try {
        const res = await apiRequest("/api/auth/demo-switch", {
          method: "POST",
          body: { email: btn.dataset.email },
        });
        setToken(res.access_token);
        showToast(`Акаунт: ${res.user.name}`);
        onAuthenticated(res.user);
      } catch (err) {
        showToast(err.message);
      }
    };
  });
}
