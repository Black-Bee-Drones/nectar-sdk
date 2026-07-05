// Fullscreen zoom/pan for Zensical-rendered Mermaid diagrams.
//
// Zensical renders each diagram's SVG into a CLOSED shadow root on a `.mermaid` host
// element, so the SVG itself is unreachable from page scripts (svg-pan-zoom etc. cannot
// attach to it). We therefore zoom/pan the HOST element inside a fullscreen overlay --
// the shadow content scales with its host. Dependency-free.
(function () {
  "use strict";

  let overlay, stage, host, originParent, originNext;
  let scale = 1, tx = 0, ty = 0, dragging = false, startX = 0, startY = 0;

  function ensureOverlay() {
    if (overlay) return;
    overlay = document.createElement("div");
    overlay.className = "diagram-overlay";
    overlay.innerHTML =
      '<button class="diagram-overlay__close" type="button" aria-label="Close diagram">\u2715</button>' +
      '<p class="diagram-overlay__hint">scroll to zoom \u00b7 drag to pan \u00b7 Esc to close</p>' +
      '<div class="diagram-overlay__stage"></div>';
    stage = overlay.querySelector(".diagram-overlay__stage");
    overlay.querySelector(".diagram-overlay__close").addEventListener("click", close);
    overlay.addEventListener("click", function (e) { if (e.target === overlay || e.target === stage) close(); });
    overlay.addEventListener("wheel", onWheel, { passive: false });
    stage.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    document.body.appendChild(overlay);
  }

  function applyTransform() {
    if (host) host.style.transform = "translate(" + tx + "px," + ty + "px) scale(" + scale + ")";
  }

  function open(h) {
    ensureOverlay();
    host = h;
    scale = 1; tx = 0; ty = 0;
    originParent = host.parentNode;
    originNext = host.nextSibling;
    host.classList.add("diagram-zooming");
    stage.appendChild(host);
    applyTransform();
    // Open fit-to-screen: scale the host so the diagram fills most of the viewport.
    var r = host.getBoundingClientRect();
    if (r.width && r.height) {
      var fit = Math.min((window.innerWidth * 0.92) / r.width, (window.innerHeight * 0.82) / r.height);
      scale = Math.max(1, Math.min(fit, 6));
      applyTransform();
    }
    overlay.classList.add("is-open");
    document.body.classList.add("diagram-overlay-open");
    document.addEventListener("keydown", onKey);
  }

  function close() {
    if (!host) return;
    host.classList.remove("diagram-zooming");
    host.style.transform = "";
    // Return the host to its original position in the page.
    if (originParent) originParent.insertBefore(host, originNext);
    overlay.classList.remove("is-open");
    document.body.classList.remove("diagram-overlay-open");
    document.removeEventListener("keydown", onKey);
    host = null;
    originParent = null;
    originNext = null;
  }

  function onKey(e) { if (e.key === "Escape") close(); }

  function onWheel(e) {
    if (!host) return;
    e.preventDefault();
    var k = e.deltaY < 0 ? 1.12 : 1 / 1.12;
    scale = Math.min(10, Math.max(0.2, scale * k));
    applyTransform();
  }

  function onPointerDown(e) {
    if (!host) return;
    dragging = true;
    startX = e.clientX - tx;
    startY = e.clientY - ty;
  }
  function onPointerMove(e) {
    if (!dragging) return;
    tx = e.clientX - startX;
    ty = e.clientY - startY;
    applyTransform();
  }
  function onPointerUp() { dragging = false; }

  function enhance(h) {
    if (h.dataset.zoomable) return;
    h.dataset.zoomable = "1";
    h.classList.add("diagram-zoomable");
    h.addEventListener("click", function () { open(h); });
  }

  function scan() {
    document.querySelectorAll(".mermaid").forEach(enhance);
  }

  // Mermaid renders asynchronously, and Zensical re-renders diagrams on navigation, so
  // rescan whenever the DOM changes (debounced).
  var pending = 0;
  var observer = new MutationObserver(function () {
    if (pending) return;
    pending = requestAnimationFrame(function () { pending = 0; scan(); });
  });
  observer.observe(document.body, { childList: true, subtree: true });
  scan();
})();
