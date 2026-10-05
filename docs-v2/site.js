/**
 * AgentConnect docs chrome.
 * Skip link only. Theme, search, and navigation stay native.
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

  function boot() {
    ensureSkip();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }

  const mo = new MutationObserver(() => ensureSkip());
  mo.observe(document.documentElement, { childList: true, subtree: true });
})();
