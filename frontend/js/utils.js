export function escapeHtml(str) {
  return String(str ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function showToast(msg) {
  const root = document.getElementById("toast-container");
  if (!root) return;
  const el = document.createElement("div");
  el.className = "toast";
  el.textContent = msg;
  root.appendChild(el);
  setTimeout(() => el.remove(), 3500);
}

export function openModal(html) {
  const root = document.getElementById("modal-root");
  if (!root) return;
  root.innerHTML = `<div class="modal-box" role="dialog" aria-modal="true">${html}</div>`;
  root.classList.remove("hidden");
  root.onclick = (e) => {
    if (e.target === root) closeModal();
  };
}

export function closeModal() {
  const root = document.getElementById("modal-root");
  if (!root) return;
  root.classList.add("hidden");
  root.innerHTML = "";
}

