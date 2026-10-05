/**
 * AgentConnect docs chrome.
 * Skip link. Keep previously opened sidebar groups open across page changes.
 */
(function () {
  const SKIP_ID = "ac-skip";
  const STORE = "ac-nav-open";

  function ensureSkip() {
    if (document.getElementById(SKIP_ID)) return;
    const a = document.createElement("a");
    a.id = SKIP_ID;
    a.className = "ac-skip";
    a.href = "#content-area";
    a.textContent = "Skip to content";
    document.body.prepend(a);
  }

  function groupKey(btn) {
    return btn.getAttribute("data-nav-href") || btn.textContent.replace(/\s+/g, " ").trim();
  }

  function loadOpen() {
    try {
      const raw = sessionStorage.getItem(STORE);
      return new Set(raw ? JSON.parse(raw) : []);
    } catch {
      return new Set();
    }
  }

  function saveOpen(open) {
    sessionStorage.setItem(STORE, JSON.stringify([...open]));
  }

  const open = loadOpen();
  let restoring = false;
  let restoreTimer = 0;

  function groupButtons() {
    const root = document.getElementById("navigation-items");
    if (!root) return [];
    return [...root.querySelectorAll("button[aria-expanded]")];
  }

  function rememberExpanded() {
    for (const btn of groupButtons()) {
      if (btn.getAttribute("aria-expanded") === "true") {
        open.add(groupKey(btn));
      }
    }
    saveOpen(open);
  }

  function restoreOpen() {
    if (restoring) return;
    restoring = true;
    try {
      for (const btn of groupButtons()) {
        const key = groupKey(btn);
        if (open.has(key) && btn.getAttribute("aria-expanded") !== "true") {
          btn.click();
        }
      }
    } finally {
      restoring = false;
    }
  }

  function scheduleRestore() {
    if (restoring) return;
    window.clearTimeout(restoreTimer);
    restoreTimer = window.setTimeout(restoreOpen, 40);
  }

  function onNavClick(event) {
    if (restoring) return;
    const btn = event.target.closest("#navigation-items button[aria-expanded]");
    if (!btn) return;
    restoring = true;
    const key = groupKey(btn);
    const wasOpen = btn.getAttribute("aria-expanded") === "true";
    requestAnimationFrame(() => {
      const nowOpen = btn.getAttribute("aria-expanded") === "true";
      const expanded = nowOpen !== wasOpen ? nowOpen : !wasOpen;
      if (expanded) open.add(key);
      else open.delete(key);
      saveOpen(open);
      restoring = false;
    });
  }

  function bootNav() {
    const root = document.getElementById("navigation-items");
    if (!root) return;
    if (!root.dataset.acNavBound) {
      root.dataset.acNavBound = "1";
      root.addEventListener("click", onNavClick, true);
    }
    rememberExpanded();
    scheduleRestore();
  }

  function boot() {
    ensureSkip();
    bootNav();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }

  const mo = new MutationObserver(() => {
    ensureSkip();
    bootNav();
  });
  mo.observe(document.documentElement, { childList: true, subtree: true });
})();
