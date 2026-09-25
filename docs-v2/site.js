/**
 * AgentConnect docs chrome helpers.
 * Aspen already provides logo | search | actions + a second tabs row.
 * We only drive glass-on-scroll and keep chrome metrics fresh.
 */
(function () {
  const THRESHOLD = 6;

  function navbar() {
    return document.getElementById("navbar");
  }

  function syncGlass() {
    const el = navbar();
    if (!el) return;
    const scrolled = (window.scrollY || document.documentElement.scrollTop || 0) > THRESHOLD;
    el.classList.toggle("ac-scrolled", scrolled);
    if (scrolled) el.setAttribute("data-ac-glass", "true");
    else el.removeAttribute("data-ac-glass");
  }

  function boot() {
    syncGlass();
  }

  window.addEventListener("scroll", syncGlass, { passive: true });
  window.addEventListener("pageshow", syncGlass);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }

  // Client-side route changes remount chrome.
  const mo = new MutationObserver(() => syncGlass());
  mo.observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ["class", "data-theme"],
  });
})();
