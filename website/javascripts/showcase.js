// play looping clips only while visible (saves CPU/bandwidth),
// and drive the optional carousel. Styles live in website/stylesheets/extra.css.
(function () {
  "use strict";

  var reduce = window.matchMedia
    ? window.matchMedia("(prefers-reduced-motion: reduce)").matches
    : false;

  // Play videos when they scroll into view, pause when they leave.
  function wireAutoplay() {
    var vids = document.querySelectorAll("video.nectar-autoplay");
    if (!vids.length) return;
    if (!("IntersectionObserver" in window)) {
      vids.forEach(function (v) {
        var p = v.play();
        if (p && p.catch) p.catch(function () {});
      });
      return;
    }
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (e) {
          var v = e.target;
          if (e.isIntersecting) {
            var p = v.play();
            if (p && p.catch) p.catch(function () {});
          } else {
            v.pause();
          }
        });
      },
      { threshold: 0.25 }
    );
    vids.forEach(function (v) {
      io.observe(v);
    });
  }

  // Carousel: prev/next buttons + gentle auto-advance that wraps and pauses on hover.
  function wireCarousels() {
    document.querySelectorAll(".nectar-carousel").forEach(function (root) {
      var track = root.querySelector(".nectar-carousel__track");
      if (!track) return;
      var slides = [].slice.call(track.querySelectorAll(".nectar-tile"));
      if (!slides.length) return;
      var prev = root.querySelector(".nectar-carousel__btn--prev");
      var next = root.querySelector(".nectar-carousel__btn--next");

      // Track the index explicitly. Deriving it from scroll fails because the
      // last (wide) tile can't left-align, leaving too little scroll room.
      var index = 0;
      function show(n) {
        index = (n + slides.length) % slides.length;
        var s = slides[index];
        var delta = s.getBoundingClientRect().left - track.getBoundingClientRect().left;
        track.scrollTo({ left: Math.max(0, track.scrollLeft + delta), behavior: "smooth" });
      }
      function go(dir) { show(index + dir); }
      if (prev) prev.addEventListener("click", function () { go(-1); });
      if (next) next.addEventListener("click", function () { go(1); });

      if (reduce) return;
      var timer = null;
      function start() {
        stop();
        timer = setInterval(function () { go(1); }, 9000);
      }
      function stop() {
        if (timer) clearInterval(timer);
        timer = null;
      }
      root.addEventListener("mouseenter", stop);
      root.addEventListener("mouseleave", start);
      root.addEventListener("focusin", stop);
      root.addEventListener("focusout", start);
      start();
    });
  }

  // Click a clip (marquee tile or feature card media) to watch it larger.
  function wireLightbox() {
    var triggers = document.querySelectorAll("[data-src]");
    if (!triggers.length) return;

    var box = document.createElement("div");
    box.className = "nectar-lightbox";
    box.innerHTML =
      '<button class="nectar-lightbox__close" aria-label="Close">\u00d7</button>' +
      '<video controls loop playsinline></video>';
    document.body.appendChild(box);
    var video = box.querySelector("video");
    var closeBtn = box.querySelector(".nectar-lightbox__close");

    function open(src, poster) {
      video.src = src;
      if (poster) video.poster = poster;
      box.classList.add("is-open");
      document.body.classList.add("nectar-lightbox-open");
      var p = video.play();
      if (p && p.catch) p.catch(function () {});
    }
    function close() {
      box.classList.remove("is-open");
      document.body.classList.remove("nectar-lightbox-open");
      video.pause();
      video.removeAttribute("src");
      video.load();
    }

    triggers.forEach(function (el) {
      el.addEventListener("click", function (e) {
        if (e.target.closest("a")) return; // let caption/body links navigate
        open(el.getAttribute("data-src"), el.getAttribute("data-poster"));
      });
    });
    closeBtn.addEventListener("click", close);
    box.addEventListener("click", function (e) {
      if (e.target === box) close();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && box.classList.contains("is-open")) close();
    });
  }

  function init() {
    wireAutoplay();
    wireCarousels();
    wireLightbox();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
