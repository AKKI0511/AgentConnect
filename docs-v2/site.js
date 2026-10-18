/**
 * AgentConnect docs chrome.
 * Skip link: Mintlify does not provide one.
 *
 * Mintlify includes any .js file in this directory on every page.
 * docs.json has no custom-script field; do not add one.
 * Do not store, clone, or restore sidebar markup.
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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", ensureSkip, { once: true });
  } else {
    ensureSkip();
  }

  const mo = new MutationObserver(ensureSkip);
  mo.observe(document.documentElement, { childList: true, subtree: true });
})();
