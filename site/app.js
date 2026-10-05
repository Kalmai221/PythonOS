// PythonOS website - shared script: theme toggle, scroll reveal, GitHub data with a short cache, small helpers. No dependencies.
(function () {
  "use strict";
  var REPO = "Kalmai221/PythonOS";
  var root = document.documentElement;

  // ---- theme: the system choice unless the visitor picked one (remembered if storage is allowed)
  function saved() { try { return localStorage.getItem("theme"); } catch (e) { return null; } }
  if (saved()) root.setAttribute("data-theme", saved());
  function current() {
    return root.getAttribute("data-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  }
  function setTheme(next) {
    var apply = function () { root.setAttribute("data-theme", next); try { localStorage.setItem("theme", next); } catch (e) {} sync(); };
    if (document.startViewTransition && !matchMedia("(prefers-reduced-motion: reduce)").matches) document.startViewTransition(apply); else apply();
  }
  function sync() {
    var b = document.getElementById("theme");
    if (!b) return;
    var dark = current() === "dark";
    b.setAttribute("aria-pressed", String(dark));
    b.setAttribute("aria-label", dark ? "Switch to the light theme" : "Switch to the dark theme");
  }
  document.addEventListener("DOMContentLoaded", function () {
    var b = document.getElementById("theme");
    if (b) b.addEventListener("click", function () { setTheme(current() === "dark" ? "light" : "dark"); });
    sync();

    // scroll reveal: elements start visible if the browser cannot observe, and everything shows at once for reduced motion
    var items = document.querySelectorAll(".reveal");
    if (!("IntersectionObserver" in window) || matchMedia("(prefers-reduced-motion: reduce)").matches) {
      items.forEach(function (el) { el.classList.add("in"); });
    } else {
      var io = new IntersectionObserver(function (entries) {
        entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add("in"); io.unobserve(e.target); } });
      }, { rootMargin: "0px 0px -8% 0px" });
      items.forEach(function (el) { io.observe(el); });
    }
  });

  // ---- GitHub API with a 3-minute session cache (60 requests an hour per visitor is the limit without a token)
  function api(path) {
    var key = "gh:" + path;
    try {
      var hit = JSON.parse(sessionStorage.getItem(key) || "null");
      if (hit && Date.now() - hit.t < 180000) return Promise.resolve(hit.d);
    } catch (e) {}
    return fetch("https://api.github.com/repos/" + REPO + "/" + path, { headers: { Accept: "application/vnd.github+json" } })
      .then(function (r) { if (!r.ok) throw new Error(r.status === 403 ? "GitHub's rate limit was reached; try again in a few minutes" : "HTTP " + r.status); return r.json(); })
      .then(function (d) { try { sessionStorage.setItem(key, JSON.stringify({ t: Date.now(), d: d })); } catch (e) {} return d; });
  }

  function size(n) { return n > 1e9 ? (n / 1e9).toFixed(1) + " GB" : n > 1e6 ? (n / 1e6).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1e3)) + " KB"; }
  function when(d) { return new Date(d).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); }
  function esc(s) { return String(s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }
  function copy(text, button) {
    var done = function () { var old = button.textContent; button.textContent = "Copied"; setTimeout(function () { button.textContent = old; }, 1400); };
    if (navigator.clipboard) navigator.clipboard.writeText(text).then(done, function () {});
  }
  window.PyOS = { api: api, size: size, when: when, esc: esc, copy: copy, REPO: REPO };
})();
