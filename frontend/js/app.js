import { apiRequest, getToken, setToken } from "./api.js";
import { UK_I18N } from "./i18n.uk.js";
import { renderAdmin } from "./views/admin.js";
import { renderAroma } from "./views/aroma.js";
import { renderCourseMap, renderCourses } from "./views/courses.js";
import { renderHome } from "./views/home.js";
import { renderLesson } from "./views/lesson.js";
import { renderLogin } from "./views/login.js";
import { renderReview } from "./views/review.js";
import { renderTariffs } from "./views/tariffs.js";
import { escapeHtml, showToast } from "./utils.js";

const sidebarEl = document.getElementById("sidebar");
const topbarEl = document.getElementById("topbar");
const mainEl = document.getElementById("main-content");
const bottomNavEl = document.getElementById("bottom-nav");

const THEME_KEY = "aroma_color_theme";
let currentTheme = localStorage.getItem(THEME_KEY) || "light";
document.documentElement.setAttribute("color-theme", currentTheme);

const SUN_SVG = `<svg viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="4" stroke="currentColor" stroke-width="2"/><path d="M12 2v2M12 20v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M2 12h2M20 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>`;
const MOON_SVG = `<svg viewBox="0 0 24 24" fill="none"><path d="M21 12.79A9 9 0 1111.21 3a7 7 0 109.79 9.79z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

let currentUser = null;

function toggleTheme() {
  currentTheme = currentTheme === "light" ? "dark" : "light";
  localStorage.setItem(THEME_KEY, currentTheme);
  document.documentElement.setAttribute("color-theme", currentTheme);
  document.querySelectorAll(".js-theme-btn").forEach((btn) => {
    btn.innerHTML = currentTheme === "light" ? SUN_SVG : MOON_SVG;
    btn.title = currentTheme === "light" ? "Темна тема" : "Світла тема";
  });
}

async function refreshUser() {
  if (!getToken()) {
    currentUser = null;
    return null;
  }
  try {
    currentUser = await apiRequest("/api/auth/me");
    return currentUser;
  } catch {
    setToken(null);
    currentUser = null;
    return null;
  }
}

function navigate(hash) {
  if (window.location.hash === hash) {
    renderRoute();
  } else {
    window.location.hash = hash;
  }
}

function renderChrome(activeRoute) {
  if (!currentUser) {
    sidebarEl.classList.add("hidden");
    topbarEl.classList.add("hidden");
    bottomNavEl.classList.add("hidden");
    return;
  }

  sidebarEl.classList.remove("hidden");
  topbarEl.classList.remove("hidden");
  bottomNavEl.classList.remove("hidden");

  const isAdmin = ["admin", "editor", "superadmin"].includes(currentUser.role);
  const navItems = [
    { id: "home", hash: "#home", label: UK_I18N.nav.home, icon: "🏠" },
    { id: "courses", hash: "#courses", label: UK_I18N.nav.courses, icon: "📚" },
    { id: "review", hash: "#review", label: UK_I18N.nav.review, icon: "🃏" },
    { id: "aroma", hash: "#aroma", label: UK_I18N.nav.aroma, icon: "🌸" },
    { id: "tariffs", hash: "#tariffs", label: UK_I18N.nav.tariffs, icon: "⭐" },
  ];
  if (isAdmin) {
    navItems.push({ id: "admin", hash: "#admin", label: UK_I18N.nav.admin, icon: "🛠" });
  }

  const roleSwitcherHtml = `
    <select class="input js-role-switch" style="padding:6px 10px; font-size:12px;" title="Швидке перемикання ролі (v1)">
      <option value="">🎭 Демо-роль...</option>
      <option value="student-basic@aroma.ua">Олена (Базовий)</option>
      <option value="student-standard@aroma.ua">Марія (Стандарт)</option>
      <option value="student-personal@aroma.ua">Софія (Персональний)</option>
      <option value="natalia@aroma.ua">Наталія (Адмін)</option>
    </select>
  `;

  // Desktop Sidebar
  sidebarEl.innerHTML = `
    <div>
      <div class="brand" id="sidebar-brand">
        <img src="/static/assets/icon.svg" alt="" />
        <span class="brand-script">${UK_I18N.appName}</span>
      </div>
      <nav class="sidebar-nav">
        ${navItems
          .map(
            (item) =>
              `<button class="sidebar-btn ${activeRoute === item.id ? "active" : ""}" data-hash="${item.hash}">
                <span>${item.icon}</span>
                <span>${item.label}</span>
              </button>`
          )
          .join("")}
      </nav>
    </div>

    <div class="sidebar-footer">
      <div class="flex-between">
        <div>
          <div style="font-weight:700; font-size:14px; color:var(--color-text-h);">${escapeHtml(currentUser.name)}</div>
          <div class="muted" style="font-size:12px;">Тариф: ${escapeHtml(currentUser.tariff_name)}</div>
        </div>
        <button class="theme-toggle-btn js-theme-btn" title="${currentTheme === "light" ? "Темна тема" : "Світла тема"}">
          ${currentTheme === "light" ? SUN_SVG : MOON_SVG}
        </button>
      </div>
      <div class="pill-badge gold" style="justify-content:center;">🔥 ${currentUser.streak_days || 0} дн. серії</div>
      ${roleSwitcherHtml}
    </div>
  `;

  // Mobile Topbar
  topbarEl.innerHTML = `
    <div class="brand" id="brand-home">
      <img src="/static/assets/icon.svg" alt="" />
      <span class="brand-script">${UK_I18N.appName}</span>
    </div>
    <div class="topbar-right">
      <span class="pill-badge">${escapeHtml(currentUser.tariff_name)}</span>
      <button class="theme-toggle-btn js-theme-btn" title="${currentTheme === "light" ? "Темна тема" : "Світла тема"}">
        ${currentTheme === "light" ? SUN_SVG : MOON_SVG}
      </button>
    </div>
  `;

  // Mobile Bottom Nav
  bottomNavEl.innerHTML = navItems
    .slice(0, 5)
    .map(
      (item) => `
    <button class="bottom-nav-btn ${activeRoute === item.id ? "active" : ""}" data-hash="${item.hash}">
      <span style="font-size:18px; line-height:1;">${item.icon}</span>
      <span>${item.label}</span>
    </button>
  `
    )
    .join("");

  document.getElementById("brand-home").onclick = () => navigate("#home");
  document.getElementById("sidebar-brand").onclick = () => navigate("#home");

  document.querySelectorAll(".js-theme-btn").forEach((b) => {
    b.onclick = toggleTheme;
  });

  document.querySelectorAll(".sidebar-btn, .bottom-nav-btn").forEach((b) => {
    b.onclick = () => navigate(b.dataset.hash);
  });

  document.querySelectorAll(".js-role-switch").forEach((sel) => {
    sel.onchange = async (e) => {
      const email = e.target.value;
      if (!email) return;
      const res = await apiRequest("/api/auth/demo-switch", {
        method: "POST",
        body: { email },
      });
      setToken(res.access_token);
      currentUser = res.user;
      showToast(`Перемкнуто: ${currentUser.name}`);
      renderRoute();
    };
  });
}

async function renderRoute() {
  if (!currentUser) {
    await refreshUser();
  }

  if (!currentUser) {
    renderChrome("login");
    renderLogin(mainEl, {
      onAuthenticated: (user) => {
        currentUser = user;
        navigate("#home");
      },
      toggleTheme,
      getTheme: () => currentTheme,
    });
    return;
  }

  const rawHash = window.location.hash || "#home";
  const [routeBase, param] = rawHash.replace(/^#/, "").split("/");
  const activeNav =
    routeBase === "course" || routeBase === "lesson" ? "courses" : routeBase || "home";

  renderChrome(activeNav);

  if (routeBase === "courses") {
    await renderCourses(mainEl, { user: currentUser, navigate });
  } else if (routeBase === "course" && param) {
    await renderCourseMap(mainEl, { courseId: param, user: currentUser, navigate });
  } else if (routeBase === "lesson" && param) {
    await renderLesson(mainEl, { lessonId: param, user: currentUser, navigate, refreshUser });
  } else if (routeBase === "review") {
    await renderReview(mainEl, { user: currentUser });
  } else if (routeBase === "aroma") {
    await renderAroma(mainEl, { user: currentUser, lessonId: param || null, navigate });
  } else if (routeBase === "tariffs") {
    await renderTariffs(mainEl, {
      user: currentUser,
      refreshUser,
      onLogout: () => {
        currentUser = null;
        navigate("#login");
      },
    });
  } else if (routeBase === "admin") {
    await renderAdmin(mainEl, { user: currentUser, navigate });
  } else {
    await renderHome(mainEl, { user: currentUser, navigate });
  }
}

window.addEventListener("hashchange", renderRoute);

if ("serviceWorker" in navigator) {
  navigator.serviceWorker.register("/sw.js").catch(() => {});
}

renderRoute();
