import { apiRequest, setToken } from "../api.js";
import { escapeHtml, showToast } from "../utils.js";

export async function renderTariffs(container, { user, refreshUser, onLogout }) {
  container.innerHTML = `<div class="card">Завантаження тарифів і підписки...</div>`;
  const [tariffs, subInfo] = await Promise.all([
    apiRequest("/api/tariffs"),
    apiRequest("/api/billing/subscription"),
  ]);

  container.innerHTML = `
    <div class="card">
      <div class="flex-between">
        <div>
          <h1 style="margin:0;">Профіль і підписка</h1>
          <div class="muted">${escapeHtml(user.name)} · ${escapeHtml(user.email)} · Роль: ${escapeHtml(user.role)}</div>
        </div>
        <span class="pill-badge gold">Поточний тариф: ${escapeHtml(user.tariff_name)}</span>
      </div>
      ${
        subInfo.subscription?.pending_downgrade_tariff_id
          ? `<p class="muted" style="margin-top:8px;">Заплановане зниження тарифу наприкінці періоду: <strong>${escapeHtml(subInfo.subscription.pending_downgrade_tariff_id)}</strong></p>`
          : ""
      }
    </div>

    <h2>Тарифи Аромакадемії</h2>
    <div class="grid-3">
      ${tariffs
        .map((t) => {
          const isCurrent = user.tariff_id === t.id;
          return `
          <div class="card" style="${isCurrent ? "border:2px solid var(--primary);" : ""}">
            <div class="flex-between">
              <h3 style="margin:0;">${escapeHtml(t.name)}</h3>
              ${isCurrent ? `<span class="pill-badge">Активний</span>` : ""}
            </div>
            <div style="font-size:1.7rem; font-weight:800; margin:10px 0;">${t.price_uah} ₴ <span class="muted" style="font-size:0.85rem;">/ міс</span></div>
            <p class="muted">${escapeHtml(t.description)}</p>
            <div class="muted" style="margin-bottom:12px;">
              Арома: ${t.aroma_daily_limit ? `${t.aroma_daily_limit} запитань/день` : "безліміт"}
            </div>
            <button class="btn ${isCurrent ? "btn-secondary" : "btn-primary"} btn-block buy-tariff-btn" data-id="${t.id}">
              ${isCurrent ? "Продовжити підписку" : "Обрати тариф"}
            </button>
          </div>
        `;
        })
        .join("")}
    </div>

    <div class="card">
      <h3 style="margin-top:0;">Історія оплат</h3>
      ${
        (subInfo.payments || []).length === 0
          ? `<p class="muted">Оплат поки немає.</p>`
          : `<ul>${subInfo.payments
              .map(
                (p) =>
                  `<li>${escapeHtml(p.tariff_id)} — ${p.amount} ${p.currency} (${escapeHtml(p.status)})</li>`
              )
              .join("")}</ul>`
      }
      <div style="display:flex; gap:10px; flex-wrap:wrap; margin-top:16px;">
        <button class="btn btn-secondary" id="logout-btn">Вийти з акаунта</button>
        ${
          user.role === "student"
            ? `<button class="btn btn-danger" id="delete-acc-btn">Видалити мій акаунт і дані</button>`
            : ""
        }
      </div>
    </div>
  `;

  container.querySelectorAll(".buy-tariff-btn").forEach((btn) => {
    btn.onclick = async () => {
      try {
        const checkout = await apiRequest("/api/billing/checkout", {
          method: "POST",
          body: { tariff_id: btn.dataset.id },
        });
        // Simulate signed payment provider webhook callback (Section 8)
        await apiRequest("/api/billing/webhook", {
          method: "POST",
          body: checkout.demo_webhook_payload,
        });
        showToast("Оплату підтверджено через підписаний webhook! Тариф оновлено.");
        await refreshUser();
        renderTariffs(container, { user: await apiRequest("/api/auth/me"), refreshUser, onLogout });
      } catch (err) {
        showToast(err.message);
      }
    };
  });

  container.querySelector("#logout-btn").onclick = () => {
    setToken(null);
    onLogout();
  };

  const delBtn = container.querySelector("#delete-acc-btn");
  if (delBtn) {
    delBtn.onclick = async () => {
      if (!confirm("Точно видалити акаунт і всі ваші дані прогресу?")) return;
      await apiRequest("/api/auth/account", { method: "DELETE" });
      setToken(null);
      showToast("Акаунт видалено.");
      onLogout();
    };
  }
}

