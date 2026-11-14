import { apiRequest } from "../api.js";
import { UK_I18N } from "../i18n.uk.js";
import { closeModal, escapeHtml, openModal, showToast } from "../utils.js";

export async function renderLesson(container, { lessonId, navigate, refreshUser }) {
  container.innerHTML = `<div class="card">Завантаження уроку...</div>`;

  let lesson;
  try {
    lesson = await apiRequest(`/api/lessons/${lessonId}`);
  } catch (err) {
    if (err.status === 403 && err.detail?.code === "TARIFF_REQUIRED") {
      container.innerHTML = `
        <div class="card" style="text-align:center; padding:32px 20px;">
          <div style="font-size:2.4rem;">🔒</div>
          <h2>Відкрийте тариф «${escapeHtml(err.detail.required_tariff)}»</h2>
          <p class="muted">${escapeHtml(err.detail.message)}</p>
          <div style="display:flex; gap:10px; justify-content:center; margin-top:16px;">
            <button class="btn btn-secondary" id="back-btn">Назад до курсів</button>
            <button class="btn btn-primary" id="upgrade-btn">Перейти до тарифів</button>
          </div>
        </div>
      `;
      container.querySelector("#back-btn").onclick = () => navigate("#courses");
      container.querySelector("#upgrade-btn").onclick = () => navigate("#tariffs");
      return;
    }
    container.innerHTML = `
      <div class="card">
        <h2>${escapeHtml(err.message)}</h2>
        <button class="btn btn-secondary" id="back-btn">Повернутися до курсів</button>
      </div>
    `;
    container.querySelector("#back-btn").onclick = () => navigate("#courses");
    return;
  }

  const queue = [...(lesson.steps || [])];
  let currentIdx = 0;
  let phase = "intro"; // intro | playing | completed
  let stepFeedback = null;
  let selectedChoice = null;
  let matchState = { leftSelected: null, pairs: {} };
  let orderItems = [];
  let flashFlipped = false;
  let openResult = null;
  let retryCount = 0;

  const initStepState = () => {
    stepFeedback = null;
    selectedChoice = null;
    matchState = { leftSelected: null, pairs: {} };
    flashFlipped = false;
    openResult = null;
    const step = queue[currentIdx];
    if (step?.type === "order") {
      orderItems = [...(step.payload?.items || [])];
    }
  };

  const openAromaModal = () => {
    openModal(`
      <div class="flex-between">
        <h2 style="margin:0;">🌿 Запитати Арому</h2>
        <button class="btn btn-secondary btn-sm" id="close-aroma-m">✕</button>
      </div>
      <div class="muted" style="margin:4px 0 8px;">${UK_I18N.aiLabel} · Контекст: ${escapeHtml(lesson.code)} ${escapeHtml(lesson.title)}</div>
      <div class="disclaimer-box"><span>ℹ️</span><span>${UK_I18N.disclaimer}</span></div>
      <form id="modal-aroma-form" style="display:flex; gap:8px; margin-bottom:12px;">
        <input id="modal-aroma-q" class="input" type="text" placeholder="Питання до цього уроку..." required />
        <button class="btn btn-primary" type="submit">Запитати</button>
      </form>
      <div id="modal-aroma-ans" class="card-soft muted">Поставте питання, і Арома відповість за матеріалами курсу з посиланням на джерело.</div>
    `);
    document.getElementById("close-aroma-m").onclick = closeModal;
    document.getElementById("modal-aroma-form").onsubmit = async (e) => {
      e.preventDefault();
      const q = document.getElementById("modal-aroma-q").value.trim();
      const ansEl = document.getElementById("modal-aroma-ans");
      ansEl.textContent = "Арома шукає в матеріалах...";
      try {
        const res = await apiRequest("/api/aroma/ask", {
          method: "POST",
          body: { lesson_id: lesson.id, message: q },
        });
        ansEl.innerHTML = `
          ${res.safety?.triggered ? `<div class="pill-badge warn" style="margin-bottom:6px;">⚠ Автомат безпеки</div>` : ""}
          <div style="color:var(--ink); white-space:pre-line;">${escapeHtml(res.answer)}</div>
          <div style="margin-top:8px;">
            ${(res.sources || []).map((s) => `<span class="pill-badge">📖 ${escapeHtml(s.title)}</span>`).join(" ")}
          </div>
        `;
      } catch (err) {
        ansEl.textContent = err.message;
      }
    };
  };

  const draw = () => {
    if (phase === "intro") {
      container.innerHTML = `
        <div style="margin-bottom:12px;">
          <button class="btn btn-secondary btn-sm" id="back-course-btn">← Назад до модуля ${lesson.course_order}</button>
        </div>
        <div class="card">
          <div class="flex-between">
            <span class="pill-badge">Урок ${escapeHtml(lesson.code)}</span>
            ${lesson.read_only ? `<span class="pill-badge gold">Режим читання</span>` : ""}
          </div>
          <h1 style="margin:10px 0 6px;">${escapeHtml(lesson.title)}</h1>
          <p class="muted">${escapeHtml(lesson.goal)}</p>
          ${
            lesson.ai_checked_label
              ? `<div class="pill-badge" style="margin-bottom:10px;">✓ ${escapeHtml(lesson.ai_checked_label)}</div>`
              : ""
          }
          <div class="disclaimer-box">
            <span>ℹ️</span>
            <span>${escapeHtml(lesson.disclaimer)}</span>
          </div>
          <div class="muted" style="margin-bottom:14px;">Кроків в уроці: ${queue.length} · Без штрафів і «життів»</div>
          <button class="btn btn-primary btn-block" id="start-lesson-btn">Почати урок →</button>
        </div>
      `;
      container.querySelector("#back-course-btn").onclick = () =>
        navigate(`#course/${lesson.course_id}`);
      container.querySelector("#start-lesson-btn").onclick = () => {
        phase = "playing";
        currentIdx = 0;
        initStepState();
        draw();
      };
      return;
    }

    if (phase === "completed") {
      container.innerHTML = `
        <div class="card" style="text-align:center; padding:30px 20px;">
          <div style="font-size:3rem;">🎉</div>
          <h1 style="margin:8px 0;">Урок ${escapeHtml(lesson.code)} пройдено!</h1>
          <p class="muted">${escapeHtml(lesson.final_thought || "Чудова робота! Прогрес збережено.")}</p>
          ${retryCount > 0 ? `<div class="pill-badge" style="margin:8px 0;">Повторено складних кроків: ${retryCount}</div>` : ""}
          <div class="disclaimer-box" style="text-align:left;">
            <span>ℹ️</span>
            <span>${escapeHtml(lesson.disclaimer)}</span>
          </div>
          <div style="display:flex; gap:10px; justify-content:center; flex-wrap:wrap; margin-top:16px;">
            <button class="btn btn-secondary" id="ask-aroma-done">🌿 Запитати Арому про урок</button>
            <button class="btn btn-primary" id="done-back-course">До карти курсу →</button>
          </div>
        </div>
      `;
      container.querySelector("#ask-aroma-done").onclick = openAromaModal;
      container.querySelector("#done-back-course").onclick = () =>
        navigate(`#course/${lesson.course_id}`);
      return;
    }

    // Playing phase
    const step = queue[currentIdx];
    const pct = Math.round(((currentIdx + (stepFeedback ? 1 : 0)) / Math.max(queue.length, 1)) * 100);
    const p = step.payload || {};

    let bodyHtml = "";

    if (step.type === "card") {
      const clip = step.clip;
      bodyHtml = `
        <span class="pill-badge">${escapeHtml(p.badge || "Картка знання")}</span>
        <h2 style="margin:10px 0 8px;">${escapeHtml(p.title || "")}</h2>
        <p style="white-space:pre-line; font-size:1.05rem;">${escapeHtml(p.body || "")}</p>
        ${
          clip
            ? clip.video_url
              ? `<div class="video-wrapper">
                   <video controls playsinline preload="metadata" src="${escapeHtml(clip.video_url)}"></video>
                 </div>
                 <div class="muted">🎬 Арома-ролик: ${escapeHtml(clip.title)}</div>`
              : `<div class="card-soft" style="margin-top:12px;">
                   <strong>🎬 Арома-ролик: ${escapeHtml(clip.title)}</strong>
                   <p class="muted" style="margin:6px 0;">${escapeHtml(clip.script_text)} (відеоплеєр підключається після завантаження файлу в Адмінці).</p>
                 </div>`
            : ""
        }
      `;
    } else if (step.type === "choice") {
      bodyHtml = `
        <h2 style="margin:8px 0 14px;">${escapeHtml(p.question)}</h2>
        <div>
          ${(p.options || [])
            .map(
              (opt, idx) => `
            <button class="option-btn ${selectedChoice === idx ? "selected" : ""}" data-idx="${idx}" ${stepFeedback ? "disabled" : ""}>
              <span>${idx + 1}.</span>
              <span>${escapeHtml(opt)}</span>
            </button>
          `
            )
            .join("")}
        </div>
      `;
    } else if (step.type === "true_false") {
      bodyHtml = `
        <h2 style="margin:8px 0 14px;">Правда чи ні?</h2>
        <p style="font-size:1.1rem; font-weight:600; margin-bottom:14px;">${escapeHtml(p.statement)}</p>
        <div class="grid-2">
          <button class="option-btn ${selectedChoice === true ? "selected" : ""}" data-tf="true" ${stepFeedback ? "disabled" : ""}>✓ Правда</button>
          <button class="option-btn ${selectedChoice === false ? "selected" : ""}" data-tf="false" ${stepFeedback ? "disabled" : ""}>✕ Неправда</button>
        </div>
      `;
    } else if (step.type === "match") {
      const lefts = p.lefts || [];
      const rights = p.rights || [];
      bodyHtml = `
        <h2 style="margin:8px 0 10px;">${escapeHtml(p.prompt || "Зіставте пари:")}</h2>
        <p class="muted">Оберіть лівий елемент, потім відповідний правий.</p>
        <div class="grid-2">
          <div>
            ${lefts
              .map((l) => {
                const isSel = matchState.leftSelected === l;
                const paired = matchState.pairs[l];
                return `<button class="option-btn match-left ${isSel ? "selected" : ""} ${paired ? "matched" : ""}" data-left="${escapeHtml(l)}" ${stepFeedback ? "disabled" : ""}>
                  <span>${escapeHtml(l)}${paired ? ` → ${escapeHtml(paired)}` : ""}</span>
                </button>`;
              })
              .join("")}
          </div>
          <div>
            ${rights
              .map((r) => {
                const used = Object.values(matchState.pairs).includes(r);
                return `<button class="option-btn match-right ${used ? "matched" : ""}" data-right="${escapeHtml(r)}" ${stepFeedback ? "disabled" : ""}>
                  <span>${escapeHtml(r)}</span>
                </button>`;
              })
              .join("")}
          </div>
        </div>
      `;
    } else if (step.type === "order") {
      bodyHtml = `
        <h2 style="margin:8px 0 10px;">${escapeHtml(p.prompt || "Розставте кроки:")}</h2>
        <p class="muted">Переміщуйте кроки кнопками ▲ / ▼ у правильному порядку.</p>
        <div>
          ${orderItems
            .map(
              (item, idx) => `
            <div class="option-btn" style="justify-content:space-between; cursor:default;">
              <span><strong>${idx + 1}.</strong> ${escapeHtml(item)}</span>
              <span style="display:flex; gap:6px;">
                <button class="btn btn-secondary btn-sm move-up" data-idx="${idx}" ${idx === 0 || stepFeedback ? "disabled" : ""}>▲</button>
                <button class="btn btn-secondary btn-sm move-down" data-idx="${idx}" ${idx === orderItems.length - 1 || stepFeedback ? "disabled" : ""}>▼</button>
              </span>
            </div>
          `
            )
            .join("")}
        </div>
      `;
    } else if (step.type === "flashcard") {
      bodyHtml = `
        <h2 style="margin:8px 0 10px;">Картка для запам'ятовування</h2>
        <div class="flashcard-box" id="lesson-flash-flip" tabindex="0">
          <div class="muted">${flashFlipped ? "Відповідь:" : "Натисніть, щоб відкрити відповідь:"}</div>
          <div style="font-size:1.15rem; font-weight:700;">${escapeHtml(flashFlipped ? p.back : p.front)}</div>
        </div>
        ${
          !stepFeedback
            ? `<div class="grid-2" style="margin-top:12px;">
                 <button class="btn btn-secondary flash-rate" data-rate="repeat">🔁 Повторити пізніше</button>
                 <button class="btn btn-primary flash-rate" data-rate="known">✓ Знаю</button>
               </div>`
            : ""
        }
      `;
    } else if (step.type === "open") {
      bodyHtml = `
        <h2 style="margin:8px 0 10px;">Відкрите питання</h2>
        <p style="font-weight:600;">${escapeHtml(p.question)}</p>
        <textarea id="open-answer-text" class="input" rows="4" maxlength="${p.max_length || 500}" placeholder="Напишіть відповідь своїми словами..." ${openResult ? "disabled" : ""}>${escapeHtml(openResult?.userText || "")}</textarea>
        ${
          openResult
            ? `<div class="card-soft" style="margin-top:12px;">
                 <strong>Зразок відповіді:</strong>
                 <p style="margin:6px 0;">${escapeHtml(openResult.sample_answer)}</p>
                 <strong>Ключові пункти для самоперевірки:</strong>
                 <ul style="margin:6px 0;">${(openResult.key_points || []).map((k) => `<li>${escapeHtml(k)}</li>`).join("")}</ul>
                 <button class="btn btn-secondary btn-sm" id="ask-open-feedback">🌿 Отримати відгук Ароми за ключовими пунктами</button>
                 <div id="open-aroma-fb" class="muted" style="margin-top:8px;"></div>
               </div>`
            : ""
        }
      `;
    }

    container.innerHTML = `
      <div class="flex-between" style="margin-bottom:10px;">
        <button class="btn btn-secondary btn-sm" id="exit-lesson-btn">✕ Вийти</button>
        <span class="muted">Крок ${currentIdx + 1} з ${queue.length}</span>
        <button class="btn btn-secondary btn-sm" id="lesson-aroma-btn">🌿 Запитати Арому</button>
      </div>

      <div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>

      <div class="lesson-workspace">
        <div class="card">
          ${step.is_key ? `<div class="pill-badge warn" style="margin-bottom:10px;">🛡 Ключове питання безпеки (обов'язкове)</div>` : ""}
          ${bodyHtml}
          ${step.source_ref ? `<div class="muted" style="margin-top:12px; font-size:12px;">Джерело: ${escapeHtml(step.source_ref)}</div>` : ""}

          ${
            stepFeedback
              ? `<div class="feedback-banner ${stepFeedback.is_correct ? "ok" : "err"}">
                   ${stepFeedback.is_correct ? "✓ Вірно!" : "✕ Варто повторити:"} ${escapeHtml(stepFeedback.explanation)}
                 </div>`
              : ""
          }

          <div style="margin-top:16px;">
            ${
              stepFeedback || step.type === "card"
                ? step.type === "card" && !stepFeedback
                  ? `<button class="btn btn-primary btn-block" id="card-next-btn">Зрозуміло, далі →</button>`
                  : `<button class="btn btn-primary btn-block" id="next-step-btn">${currentIdx + 1 >= queue.length ? "Завершити урок →" : "Наступний крок →"}</button>`
                : step.type !== "flashcard"
                ? `<button class="btn btn-primary btn-block" id="check-step-btn">Перевірити відповідь</button>`
                : ""
            }
          </div>
        </div>

        <div class="card sticky-panel">
          <div class="section-label">Урок ${escapeHtml(lesson.code)}</div>
          <h3 style="margin-top:0;">${escapeHtml(lesson.title)}</h3>
          <p class="muted">${escapeHtml(lesson.goal)}</p>
          <div class="disclaimer-box">
            <span>ℹ️</span>
            <span>${escapeHtml(lesson.disclaimer)}</span>
          </div>
          <button class="btn btn-secondary btn-block btn-sm" id="side-aroma-btn">🌸 Запитати Арому про цей урок</button>
        </div>
      </div>
    `;

    container.querySelector("#exit-lesson-btn").onclick = () =>
      navigate(`#course/${lesson.course_id}`);
    container.querySelector("#lesson-aroma-btn").onclick = openAromaModal;
    const sideAroma = container.querySelector("#side-aroma-btn");
    if (sideAroma) sideAroma.onclick = openAromaModal;

    // Bind step-type interactions
    container.querySelectorAll("[data-idx].option-btn").forEach((b) => {
      b.onclick = () => {
        selectedChoice = Number(b.dataset.idx);
        draw();
      };
    });
    container.querySelectorAll("[data-tf]").forEach((b) => {
      b.onclick = () => {
        selectedChoice = b.dataset.tf === "true";
        draw();
      };
    });
    container.querySelectorAll(".match-left").forEach((b) => {
      b.onclick = () => {
        matchState.leftSelected = b.dataset.left;
        draw();
      };
    });
    container.querySelectorAll(".match-right").forEach((b) => {
      b.onclick = () => {
        if (!matchState.leftSelected) return;
        matchState.pairs[matchState.leftSelected] = b.dataset.right;
        matchState.leftSelected = null;
        draw();
      };
    });
    container.querySelectorAll(".move-up").forEach((b) => {
      b.onclick = () => {
        const i = Number(b.dataset.idx);
        [orderItems[i - 1], orderItems[i]] = [orderItems[i], orderItems[i - 1]];
        draw();
      };
    });
    container.querySelectorAll(".move-down").forEach((b) => {
      b.onclick = () => {
        const i = Number(b.dataset.idx);
        [orderItems[i + 1], orderItems[i]] = [orderItems[i], orderItems[i + 1]];
        draw();
      };
    });

    const flipBox = container.querySelector("#lesson-flash-flip");
    if (flipBox) {
      flipBox.onclick = () => {
        flashFlipped = !flashFlipped;
        draw();
      };
    }

    container.querySelectorAll(".flash-rate").forEach((b) => {
      b.onclick = async () => {
        const res = await apiRequest(`/api/steps/${step.id}/answer`, {
          method: "POST",
          body: { answer: b.dataset.rate },
        });
        stepFeedback = res;
        draw();
      };
    });

    const cardNext = container.querySelector("#card-next-btn");
    if (cardNext) {
      cardNext.onclick = async () => {
        if (!lesson.read_only) {
          await apiRequest(`/api/steps/${step.id}/answer`, {
            method: "POST",
            body: { answer: "viewed" },
          });
        }
        if (currentIdx + 1 >= queue.length) {
          await finishLesson();
        } else {
          currentIdx += 1;
          initStepState();
          draw();
        }
      };
    }

    const checkBtn = container.querySelector("#check-step-btn");
    if (checkBtn) {
      checkBtn.onclick = async () => {
        let answerPayload;
        if (step.type === "choice" || step.type === "true_false") {
          if (selectedChoice === null) return showToast("Оберіть варіант відповіді");
          answerPayload = selectedChoice;
        } else if (step.type === "match") {
          if (Object.keys(matchState.pairs).length < (p.lefts || []).length) {
            return showToast("Зіставте всі пари");
          }
          answerPayload = matchState.pairs;
        } else if (step.type === "order") {
          answerPayload = orderItems;
        } else if (step.type === "open") {
          const val = container.querySelector("#open-answer-text").value.trim();
          if (!val) return showToast("Напишіть відповідь");
          answerPayload = val;
        }

        const res = await apiRequest(`/api/steps/${step.id}/answer`, {
          method: "POST",
          body: { answer: answerPayload },
        });
        stepFeedback = res;
        if (step.type === "open") {
          openResult = {
            userText: answerPayload,
            sample_answer: res.sample_answer,
            key_points: res.key_points,
          };
        }
        // Wrong steps are returned to the end of the lesson for retry (Section 5)
        if (!res.is_correct) {
          queue.push(step);
          retryCount += 1;
        }
        draw();
      };
    }

    const openFbBtn = container.querySelector("#ask-open-feedback");
    if (openFbBtn) {
      openFbBtn.onclick = async () => {
        const fbEl = container.querySelector("#open-aroma-fb");
        fbEl.textContent = "Арома звіряє з ключовими пунктами...";
        const res = await apiRequest(`/api/open-answers/${step.id}/aroma-feedback`, {
          method: "POST",
          body: { step_id: step.id, answer_text: openResult.userText },
        });
        fbEl.textContent = res.feedback;
      };
    }

    const nextBtn = container.querySelector("#next-step-btn");
    if (nextBtn) {
      nextBtn.onclick = async () => {
        if (currentIdx + 1 >= queue.length) {
          await finishLesson();
        } else {
          currentIdx += 1;
          initStepState();
          draw();
        }
      };
    }
  };

  const finishLesson = async () => {
    if (lesson.read_only) {
      phase = "completed";
      draw();
      return;
    }
    try {
      await apiRequest(`/api/lessons/${lesson.id}/complete`, { method: "POST" });
      await refreshUser();
      phase = "completed";
      draw();
    } catch (err) {
      showToast(err.message);
    }
  };

  draw();
}

