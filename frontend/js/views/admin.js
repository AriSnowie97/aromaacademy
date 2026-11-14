import { apiRequest } from "../api.js";
import { UK_I18N } from "../i18n.uk.js";
import { closeModal, escapeHtml, openModal, showToast } from "../utils.js";

let adminTab = "editor";
let selectedLessonId = "lesson_1_1";

export async function renderAdmin(container, { user }) {
  if (!["admin", "editor", "superadmin"].includes(user.role)) {
    container.innerHTML = `<div class="card">Доступ лише для Наталії (admin) або редактора.</div>`;
    return;
  }

  container.innerHTML = `<div class="card">Завантаження адмін-панелі Наталії...</div>`;
  const [tree, analytics] = await Promise.all([
    apiRequest("/api/admin/tree"),
    apiRequest("/api/admin/analytics"),
  ]);

  let currentLesson = await apiRequest(`/api/admin/lessons/${selectedLessonId}`);

  const reloadLesson = async (id) => {
    selectedLessonId = id;
    currentLesson = await apiRequest(`/api/admin/lessons/${id}`);
    draw();
  };

  const draw = () => {
    container.innerHTML = `
      <div class="flex-between" style="margin-bottom:14px;">
        <div>
          <h1 style="margin:0;">Адмін-панель Наталії</h1>
          <div class="muted">Курси → Уроки → Кроки · Імпорт Markdown · Арома-ролики · Прогрес</div>
        </div>
        <span class="pill-badge gold">Роль: ${escapeHtml(user.role)}</span>
      </div>

      <div class="tabs">
        <button class="tab-btn ${adminTab === "editor" ? "active" : ""}" data-tab="editor">📚 Конструктор уроків</button>
        <button class="tab-btn ${adminTab === "import" ? "active" : ""}" data-tab="import">📥 Імпорт Markdown</button>
        <button class="tab-btn ${adminTab === "clips" ? "active" : ""}" data-tab="clips">🎬 Арома-ролики (14)</button>
        <button class="tab-btn ${adminTab === "analytics" ? "active" : ""}" data-tab="analytics">📊 Учні та Безпека</button>
      </div>

      <div id="admin-body"></div>
    `;

    container.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.onclick = () => {
        adminTab = btn.dataset.tab;
        draw();
      };
    });

    const body = container.querySelector("#admin-body");

    if (adminTab === "editor") {
      body.innerHTML = `
        <div class="admin-editor-grid">
          <div class="card" style="max-height:72vh; overflow-y:auto;">
            <h3 style="margin-top:0;">Дерево курсів</h3>
            ${tree.courses
              .map(
                (c) => `
              <details ${c.lessons.some((l) => l.id === currentLesson.id) ? "open" : ""} style="margin-bottom:8px;">
                <summary style="cursor:pointer; font-weight:700;">
                  ${c.order}. ${escapeHtml(c.title)} <span class="muted">(${c.min_tariff})</span>
                </summary>
                <div style="padding-left:12px; margin-top:6px; display:flex; flex-direction:column; gap:4px;">
                  ${c.lessons
                    .map(
                      (l) => `
                    <button class="btn btn-sm ${l.id === currentLesson.id ? "btn-primary" : "btn-secondary"} select-lesson-btn" data-id="${l.id}" style="justify-content:space-between; text-align:left;">
                      <span>${escapeHtml(l.code)} ${escapeHtml(l.title)}</span>
                      <span style="font-size:0.75rem;">${UK_I18N.statuses[l.status] || l.status}</span>
                    </button>
                  `
                    )
                    .join("")}
                </div>
              </details>
            `
              )
              .join("")}
          </div>

          <div class="card">
            <div class="flex-between">
              <div>
                <span class="pill-badge">Урок ${escapeHtml(currentLesson.code)} · v${currentLesson.version}</span>
                <span class="pill-badge ${currentLesson.status === "published" ? "" : "gold"}">${UK_I18N.statuses[currentLesson.status]}</span>
              </div>
              <div style="display:flex; gap:6px;">
                <button class="btn btn-secondary btn-sm" id="preview-student-btn">👁 Перегляд</button>
                <button class="btn btn-primary btn-sm" id="publish-lesson-btn">✓ Опублікувати (+ індекс Ароми)</button>
              </div>
            </div>

            <form id="lesson-edit-form" style="margin-top:14px;">
              <div class="form-row">
                <label class="field-label">Назва уроку</label>
                <input id="ed-title" class="input" value="${escapeHtml(currentLesson.title)}" />
              </div>
              <div class="form-row">
                <label class="field-label">Мета</label>
                <textarea id="ed-goal" class="input" rows="2">${escapeHtml(currentLesson.goal)}</textarea>
              </div>
              <div class="form-row">
                <label class="field-label">Джерело (для учня й Ароми)</label>
                <input id="ed-source" class="input" value="${escapeHtml(currentLesson.source_ref)}" />
              </div>
              <div class="form-row" style="display:flex; gap:12px; align-items:center;">
                <label style="display:flex; gap:6px; align-items:center;">
                  <input id="ed-ai-check" type="checkbox" ${currentLesson.ai_assisted_checked ? "checked" : ""} />
                  <span>Позначка «Картки підготовлено з ШІ й перевірено Наталією»</span>
                </label>
                <select id="ed-status" class="input" style="width:auto;">
                  <option value="draft" ${currentLesson.status === "draft" ? "selected" : ""}>Чернетка</option>
                  <option value="review" ${currentLesson.status === "review" ? "selected" : ""}>На перевірці</option>
                  <option value="published" ${currentLesson.status === "published" ? "selected" : ""}>Опубліковано</option>
                </select>
              </div>
              <button class="btn btn-secondary btn-sm" type="submit">Зберегти зміни уроку</button>
            </form>

            <hr style="margin:18px 0; border:none; border-top:1px solid var(--border);" />
            <div class="flex-between">
              <h3 style="margin:0;">Кроки (${currentLesson.steps.length})</h3>
              <button class="btn btn-primary btn-sm" id="add-step-btn">+ Додати крок</button>
            </div>
            <div style="display:flex; flex-direction:column; gap:8px; margin-top:10px;">
              ${currentLesson.steps
                .map(
                  (s, idx) => `
                <div class="card-soft flex-between">
                  <div>
                    <strong>${idx + 1}. [${escapeHtml(s.type)}]</strong>
                    ${s.is_key ? `<span class="pill-badge warn">Ключове безпеки</span>` : ""}
                    <div class="muted">${escapeHtml(s.payload?.title || s.payload?.question || s.payload?.statement || s.payload?.front || "")}</div>
                  </div>
                  <div style="display:flex; gap:4px;">
                    <button class="btn btn-secondary btn-sm step-up" data-idx="${idx}" ${idx === 0 ? "disabled" : ""}>▲</button>
                    <button class="btn btn-secondary btn-sm step-down" data-idx="${idx}" ${idx === currentLesson.steps.length - 1 ? "disabled" : ""}>▼</button>
                    <button class="btn btn-danger btn-sm step-del" data-id="${s.id}">✕</button>
                  </div>
                </div>
              `
                )
                .join("")}
            </div>

            ${
              currentLesson.versions?.length
                ? `<div style="margin-top:14px;">
                     <strong>Історія версій:</strong>
                     <div style="display:flex; gap:6px; flex-wrap:wrap; margin-top:6px;">
                       ${currentLesson.versions
                         .slice(0, 5)
                         .map(
                           (v) =>
                             `<button class="btn btn-secondary btn-sm rollback-btn" data-ver="${v.version}">Відкат до v${v.version}</button>`
                         )
                         .join("")}
                     </div>
                   </div>`
                : ""
            }
          </div>
        </div>
      `;

      body.querySelectorAll(".select-lesson-btn").forEach((b) => {
        b.onclick = () => reloadLesson(b.dataset.id);
      });

      body.querySelector("#lesson-edit-form").onsubmit = async (e) => {
        e.preventDefault();
        try {
          const res = await apiRequest(`/api/admin/lessons/${currentLesson.id}`, {
            method: "PATCH",
            body: {
              title: body.querySelector("#ed-title").value.trim(),
              goal: body.querySelector("#ed-goal").value.trim(),
              source_ref: body.querySelector("#ed-source").value.trim(),
              ai_assisted_checked: body.querySelector("#ed-ai-check").checked,
              status: body.querySelector("#ed-status").value,
            },
          });
          showToast(`Урок оновлено (v${res.version}, чанків Ароми: ${res.kb_chunks})`);
          await reloadLesson(currentLesson.id);
        } catch (err) {
          showToast(err.message);
        }
      };

      body.querySelector("#publish-lesson-btn").onclick = async () => {
        const res = await apiRequest(`/api/admin/lessons/${currentLesson.id}/publish`, {
          method: "POST",
        });
        showToast(`Опубліковано! База знань Ароми оновлена (${res.kb_chunks} фрагментів).`);
        await reloadLesson(currentLesson.id);
      };

      body.querySelector("#preview-student-btn").onclick = () => {
        openModal(`
          <div class="flex-between">
            <h2 style="margin:0;">Попередній перегляд (як бачить учень)</h2>
            <button class="btn btn-secondary btn-sm" id="close-prev">✕</button>
          </div>
          <p class="muted">Урок ${escapeHtml(currentLesson.code)}: ${escapeHtml(currentLesson.title)}</p>
          <div class="disclaimer-box"><span>ℹ️</span><span>${UK_I18N.disclaimer}</span></div>
          ${currentLesson.steps
            .map(
              (s, i) => `
            <div class="card-soft" style="margin-bottom:8px;">
              <strong>Крок ${i + 1} (${escapeHtml(s.type)})</strong>
              <p style="margin:4px 0;">${escapeHtml(s.payload?.title || s.payload?.question || s.payload?.statement || s.payload?.front || "")}</p>
              <div class="muted">${escapeHtml(s.payload?.body || s.payload?.back || "")}</div>
            </div>
          `
            )
            .join("")}
        `);
        document.getElementById("close-prev").onclick = closeModal;
      };

      body.querySelector("#add-step-btn").onclick = () => {
        openModal(`
          <h2 style="margin-top:0;">Додати крок в урок ${escapeHtml(currentLesson.code)}</h2>
          <form id="add-step-form">
            <div class="form-row">
              <label class="field-label">Тип кроку</label>
              <select id="new-step-type" class="input">
                <option value="card">Картка знання</option>
                <option value="true_false">Правда чи неправда</option>
              </select>
            </div>
            <div class="form-row">
              <label class="field-label">Заголовок / Твердження</label>
              <input id="new-step-title" class="input" required />
            </div>
            <div class="form-row">
              <label class="field-label">Текст картки / Пояснення</label>
              <textarea id="new-step-body" class="input" rows="3" required></textarea>
            </div>
            <div class="form-row">
              <label style="display:flex; gap:6px; align-items:center;">
                <input id="new-step-key" type="checkbox" />
                <span>Ключове питання безпеки (для модуля 3)</span>
              </label>
            </div>
            <div style="display:flex; gap:8px; justify-content:flex-end;">
              <button type="button" class="btn btn-secondary" id="cancel-step">Скасувати</button>
              <button type="submit" class="btn btn-primary">Створити</button>
            </div>
          </form>
        `);
        document.getElementById("cancel-step").onclick = closeModal;
        document.getElementById("add-step-form").onsubmit = async (e) => {
          e.preventDefault();
          const t = document.getElementById("new-step-type").value;
          const title = document.getElementById("new-step-title").value.trim();
          const text = document.getElementById("new-step-body").value.trim();
          const is_key = document.getElementById("new-step-key").checked;
          const payload =
            t === "card"
              ? { title, body: text, badge: `Урок ${currentLesson.code}` }
              : { statement: title, correct: true, explanation: text };
          await apiRequest(`/api/admin/lessons/${currentLesson.id}/steps`, {
            method: "POST",
            body: { type: t, payload, is_key },
          });
          closeModal();
          showToast("Крок додано");
          await reloadLesson(currentLesson.id);
        };
      };

      const reorder = async (ids) => {
        await apiRequest(`/api/admin/lessons/${currentLesson.id}/steps/reorder`, {
          method: "POST",
          body: { step_ids: ids },
        });
        await reloadLesson(currentLesson.id);
      };

      body.querySelectorAll(".step-up").forEach((b) => {
        b.onclick = () => {
          const i = Number(b.dataset.idx);
          const ids = currentLesson.steps.map((s) => s.id);
          [ids[i - 1], ids[i]] = [ids[i], ids[i - 1]];
          reorder(ids);
        };
      });
      body.querySelectorAll(".step-down").forEach((b) => {
        b.onclick = () => {
          const i = Number(b.dataset.idx);
          const ids = currentLesson.steps.map((s) => s.id);
          [ids[i + 1], ids[i]] = [ids[i], ids[i + 1]];
          reorder(ids);
        };
      });
      body.querySelectorAll(".step-del").forEach((b) => {
        b.onclick = async () => {
          await apiRequest(`/api/admin/steps/${b.dataset.id}`, { method: "DELETE" });
          showToast("Крок видалено");
          await reloadLesson(currentLesson.id);
        };
      });
      body.querySelectorAll(".rollback-btn").forEach((b) => {
        b.onclick = async () => {
          await apiRequest(`/api/admin/lessons/${currentLesson.id}/rollback/${b.dataset.ver}`, {
            method: "POST",
          });
          showToast(`Відкочено до версії v${b.dataset.ver}`);
          await reloadLesson(currentLesson.id);
        };
      });
    } else if (adminTab === "import") {
      body.innerHTML = `
        <div class="card">
          <h3 style="margin-top:0;">Імпорт уроку з Markdown (формат плану Наталії)</h3>
          <form id="md-import-form">
            <div class="form-row">
              <label class="field-label">Цільовий модуль</label>
              <select id="imp-course" class="input">
                ${tree.courses.map((c) => `<option value="${c.id}">${c.order}. ${escapeHtml(c.title)}</option>`).join("")}
              </select>
            </div>
            <div class="form-row">
              <label class="field-label">Markdown-текст</label>
              <textarea id="imp-md" class="input" rows="10"># 1.8 Сила аромату в щоденних ритуалах

**Мета:** Навчитися використовувати дифузор безпечно й усвідомлено.

**Тези:**
- Дифузор очищує та освіжає атмосферу без нагрівання олії
- Починайте з 2–3 крапель на кімнату середнього розміру
- Робіть перерви між циклами розпилення

**Для кадру:** Показати ультразвуковий дифузор і воду кімнатної температури.

**Фінальна думка:** Чисте повітря і помірність створюють найкращий результат.
</textarea>
            </div>
            <button class="btn btn-primary" type="submit">Створити чернетку уроку</button>
          </form>
        </div>
      `;
      body.querySelector("#md-import-form").onsubmit = async (e) => {
        e.preventDefault();
        const res = await apiRequest("/api/admin/import-markdown", {
          method: "POST",
          body: {
            course_id: body.querySelector("#imp-course").value,
            markdown_text: body.querySelector("#imp-md").value,
          },
        });
        showToast(`Імпортовано чернетку: ${res.code} ${res.title}`);
        selectedLessonId = res.lesson_id;
        adminTab = "editor";
        renderAdmin(container, { user });
      };
    } else if (adminTab === "clips") {
      body.innerHTML = `
        <div class="card">
          <h3 style="margin-top:0;">14 Арома-роликів (завантаження вашого відео)</h3>
          <p class="muted">Завантажте готове відео (.mp4, .webm, .mov) для будь-якого ролика — воно одразу з'явиться у відповідній картці уроку.</p>
          <div style="display:flex; flex-direction:column; gap:10px;">
            ${tree.clips
              .map(
                (cl) => `
              <div class="card-soft flex-between">
                <div>
                  <strong>${escapeHtml(cl.title)}</strong>
                  <div class="muted">Фрагментів: ${cl.fragments_count} · План: ${escapeHtml(cl.suggested_lesson_ref)} · Прив'язаний урок: ${escapeHtml(cl.lesson_id || "—")}</div>
                  ${cl.video_url ? `<span class="pill-badge">✓ Відео завантажено (${escapeHtml(cl.video_url)})</span>` : `<span class="pill-badge gold">Текстовий сценарій</span>`}
                </div>
                <label class="btn btn-secondary btn-sm" style="cursor:pointer;">
                  📤 Завантажити відео
                  <input type="file" accept=".mp4,.webm,.mov" class="upload-clip-input hidden" data-clip="${cl.id}" />
                </label>
              </div>
            `
              )
              .join("")}
          </div>
        </div>
      `;
      body.querySelectorAll(".upload-clip-input").forEach((inp) => {
        inp.onchange = async () => {
          const file = inp.files?.[0];
          if (!file) return;
          const fd = new FormData();
          fd.append("file", file);
          try {
            const res = await apiRequest(`/api/admin/clips/${inp.dataset.clip}/upload-video`, {
              method: "POST",
              body: fd,
            });
            showToast(`Відео завантажено: ${res.video_url}`);
            renderAdmin(container, { user });
          } catch (err) {
            showToast(err.message);
          }
        };
      });
    } else if (adminTab === "analytics") {
      body.innerHTML = `
        <div class="grid-2">
          <div class="card">
            <h3 style="margin-top:0;">Прогрес учнів</h3>
            <ul>
              ${analytics.students
                .map(
                  (s) =>
                    `<li><strong>${escapeHtml(s.name)}</strong> (${escapeHtml(s.email)}) — пройдено уроків: ${s.completed_lessons}, серія: ${s.streak_days}</li>`
                )
                .join("")}
            </ul>
          </div>
          <div class="card">
            <h3 style="margin-top:0;">Спрацювання автомата безпеки Ароми</h3>
            ${
              analytics.safety_events.length === 0
                ? `<p class="muted">Поки що тригерів не зафіксовано.</p>`
                : `<ul>${analytics.safety_events
                    .map(
                      (ev) =>
                        `<li>Користувач ${escapeHtml(ev.user_id)} · Причина: <strong>${escapeHtml(ev.safety_reason)}</strong></li>`
                    )
                    .join("")}</ul>`
            }
          </div>
        </div>

        <div class="card">
          <h3 style="margin-top:0;">Відкриті відповіді учнів (тариф Персональний / розбір Наталії)</h3>
          ${
            analytics.open_answers.length === 0
              ? `<p class="muted">Поки немає відкритих відповідей.</p>`
              : analytics.open_answers
                  .map(
                    (oa) => `
                <div class="card-soft" style="margin-bottom:10px;">
                  <div><strong>Учень ${escapeHtml(oa.user_id)}:</strong> ${escapeHtml(oa.text)}</div>
                  ${oa.aroma_feedback ? `<div class="muted">Арома: ${escapeHtml(oa.aroma_feedback)}</div>` : ""}
                  ${oa.mentor_reply ? `<div class="pill-badge" style="margin-top:6px;">Відповідь Наталії: ${escapeHtml(oa.mentor_reply)}</div>` : ""}
                  <form class="mentor-reply-form" data-id="${oa.id}" style="display:flex; gap:8px; margin-top:8px;">
                    <input class="input" type="text" placeholder="Коментар Наталії..." required />
                    <button class="btn btn-primary btn-sm" type="submit">Відповісти</button>
                  </form>
                </div>
              `
                  )
                  .join("")
          }
        </div>
      `;
      body.querySelectorAll(".mentor-reply-form").forEach((f) => {
        f.onsubmit = async (e) => {
          e.preventDefault();
          const val = f.querySelector("input").value.trim();
          await apiRequest(`/api/admin/open-answers/${f.dataset.id}/reply`, {
            method: "POST",
            body: { reply: val },
          });
          showToast("Коментар Наталії збережено");
          renderAdmin(container, { user });
        };
      });
    }
  };

  draw();
}

