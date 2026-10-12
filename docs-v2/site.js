/**
 * AgentConnect docs chrome.
 * Skip link. Keep groups the reader opened during this visit.
 *
 * Nested groups start closed (docs.json `expanded: false`).
 * Session storage is not used, so a refresh starts closed except
 * the current path. Group rows with a root page navigate on click;
 * restoring those groups must set React state, not click the row.
 */
(function () {
  const SKIP_ID = "ac-skip";

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

  const open = new Set();
  let restoring = false;
  let restoreTimer = 0;

  function groupButtons() {
    const root = document.getElementById("navigation-items");
    if (!root) return [];
    return [...root.querySelectorAll("button[aria-expanded]")];
  }

  function fiberOf(node) {
    if (!node) return null;
    const key = Object.keys(node).find(
      (k) => k.startsWith("__reactFiber$") || k.startsWith("__reactInternalInstance$"),
    );
    return key ? node[key] : null;
  }

  function hooksOf(fiber) {
    const hooks = [];
    let hook = fiber && fiber.memoizedState;
    while (hook) {
      hooks.push(hook);
      hook = hook.next;
    }
    return hooks;
  }

  function forceExpandButton(btn) {
    if (btn.getAttribute("aria-expanded") === "true") return false;
    let fiber = fiberOf(btn);
    while (fiber) {
      for (const hook of hooksOf(fiber)) {
        const queue = hook.queue;
        if (!queue || typeof queue.dispatch !== "function") continue;
        if (hook.memoizedState === false) {
          queue.dispatch(true);
          return true;
        }
      }
      fiber = fiber.return;
    }
    if (!btn.getAttribute("data-nav-href")) {
      btn.click();
      return true;
    }
    return false;
  }

  function restoreOpen() {
    if (restoring || open.size === 0) return;
    restoring = true;
    try {
      for (const btn of groupButtons()) {
        const key = groupKey(btn);
        if (open.has(key) && btn.getAttribute("aria-expanded") !== "true") {
          forceExpandButton(btn);
        }
      }
    } finally {
      restoring = false;
    }
  }

  function scheduleRestore() {
    if (restoring || open.size === 0) return;
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
