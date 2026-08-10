/**
 * Rewrite the Zensical/Material language alternate links so switching language
 * keeps the same page when a Portuguese sibling exists; otherwise fall back to
 * the language home.
 *
 * Expects i18n-paths.json next to this script:
 *   { "base": "/nectar-sdk", "paths": ["", "get-started", "get-started/control", ...] }
 *
 * `base` matches GitHub Pages (`/nectar-sdk`). Local bilingual preview serves the
 * same prefix via `make docs-serve`. If the page is served without that prefix
 * (site at `/` and `/pt/`), the base is detected from the URL.
 */
(function () {
  var PATHS_URL = new URL("i18n-paths.json", document.currentScript.src).href;

  function detectBase(configured) {
    var path = window.location.pathname || "/";
    if (configured && (path === configured || path.indexOf(configured + "/") === 0)) {
      return configured;
    }
    if (path === "/nectar-sdk" || path.indexOf("/nectar-sdk/") === 0) {
      return "/nectar-sdk";
    }
    // build/site served at server root: / and /pt/...
    return "";
  }

  function normalizePath(pathname, base) {
    var p = pathname || "/";
    if (base && (p === base || p.indexOf(base + "/") === 0)) {
      p = p.slice(base.length) || "/";
    }
    if (p.length > 1 && p.charAt(p.length - 1) === "/") {
      p = p.slice(0, -1);
    }
    if (p.charAt(0) === "/") {
      p = p.slice(1);
    }
    return p;
  }

  function stripPtPrefix(rel) {
    if (rel === "pt") return "";
    if (rel.indexOf("pt/") === 0) return rel.slice(3);
    return null;
  }

  function siblingHref(base, wantPt, pageKey) {
    var root = (base || "").replace(/\/$/, "");
    var parts = [];
    if (wantPt) parts.push("pt");
    if (pageKey) parts.push(pageKey);
    if (!root && parts.length === 0) return "/";
    if (!root) return "/" + parts.join("/") + "/";
    if (parts.length === 0) return root + "/";
    return root + "/" + parts.join("/") + "/";
  }

  function homeHref(base, wantPt) {
    return siblingHref(base, wantPt, "");
  }

  function rewrite(data) {
    var configured = (data && data.base) || "/nectar-sdk";
    var base = detectBase(configured);
    var translated = Object.create(null);
    (data.paths || []).forEach(function (p) {
      translated[p] = true;
    });

    var rel = normalizePath(window.location.pathname, base);
    var withoutPt = stripPtPrefix(rel);
    var isOnPt = withoutPt !== null;
    var pageKey = isOnPt ? withoutPt : rel;
    var hasSibling = Object.prototype.hasOwnProperty.call(translated, pageKey);

    document.querySelectorAll("a[hreflang]").forEach(function (a) {
      var lang = (a.getAttribute("hreflang") || "").toLowerCase();
      var wantPt = lang === "pt" || lang.indexOf("pt-") === 0;
      if (lang !== "en" && !wantPt) return;

      if (wantPt === isOnPt) {
        a.setAttribute(
          "href",
          hasSibling || pageKey === ""
            ? siblingHref(base, wantPt, pageKey)
            : homeHref(base, wantPt)
        );
        return;
      }

      a.setAttribute(
        "href",
        hasSibling ? siblingHref(base, wantPt, pageKey) : homeHref(base, wantPt)
      );
    });
  }

  fetch(PATHS_URL, { credentials: "same-origin" })
    .then(function (r) {
      if (!r.ok) throw new Error("i18n-paths.json " + r.status);
      return r.json();
    })
    .then(rewrite)
    .catch(function () {
      /* keep YAML alternate defaults */
    });
})();
