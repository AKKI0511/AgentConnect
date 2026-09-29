/**
 * AgentConnect docs helpers. Pages work without this file.
 * Adds a skip link, font preloads, and a theme-color meta tag.
 */
(function () {
  const FONTS = [
    "/fonts/atkinson-hyperlegible-next-400.woff2",
    "/fonts/atkinson-hyperlegible-mono-400.woff2",
  ];

  function ensureSkipLink() {
    if (document.querySelector(".ac-skip")) return;
    const skip = document.createElement("a");
    skip.className = "ac-skip";
    skip.href = "#content";
    skip.textContent = "Skip to content";
    document.body.insertBefore(skip, document.body.firstChild);
  }

  function preloadFonts() {
    for (const href of FONTS) {
      if (document.querySelector(`link[rel="preload"][href="${href}"]`)) continue;
      const link = document.createElement("link");
      link.rel = "preload";
      link.as = "font";
      link.type = "font/woff2";
      link.crossOrigin = "anonymous";
      link.href = href;
      document.head.appendChild(link);
    }
  }

  function setThemeColor() {
    let meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) {
      meta = document.createElement("meta");
      meta.setAttribute("name", "theme-color");
      document.head.appendChild(meta);
    }
    meta.setAttribute("content", "#131313");
  }

  function boot() {
    ensureSkipLink();
    preloadFonts();
    setThemeColor();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
