// PythonOS App Library: lists every app of the store from the catalog, with search, filters and a detail window. No dependencies.
(function () {
  "use strict";
  var P = window.PyOS;
  var SOURCES = ["data/catalog.json", "https://raw.githubusercontent.com/Kalmai221/PythonOS/main/online_packages/index-api2.json", "https://raw.githubusercontent.com/Kalmai221/PythonOS/main/online_packages/index.json"];
  var PERMS = {
    network: ["Internet", "connect to the internet"], files: ["Your files", "read and change your files"], notifications: ["Notifications", "show notifications"],
    schedule: ["Schedule", "schedule tasks"], system: ["System info", "read information about this computer"], exec: ["Other programs", "start other programs"]
  };
  var state = { apps: [], cats: {}, q: "", cat: "all", perm: "all", live: false, plain: false, sort: "featured" };
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return P.esc(s); };

  function load(i) {
    if (i >= SOURCES.length) return Promise.reject(new Error("the app catalog could not be loaded"));
    return fetch(SOURCES[i], { cache: "no-cache" }).then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }).catch(function () { return load(i + 1); });
  }

  function sizeOf(a) { return (a.files || []).reduce(function (n, f) { return n + (f.size || 0); }, 0); }
  function verKey(v) { return String(v).split(/[.-]/).map(function (x) { return parseInt(x, 10) || 0; }); }
  function newer(a, b) { var x = verKey(a), y = verKey(b); for (var i = 0; i < Math.max(x.length, y.length); i++) { if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) - (y[i] || 0); } return 0; }
  function installCommand(a) { return "pkg install " + (a.command || a.id); }
  function catTitle(id) { return (state.cats[id] && state.cats[id].title) || id; }
  function pills(a) {
    var p = (a.permissions || []).map(function (k) { return "<span class='chip perm' title='" + esc((PERMS[k] || [k, k])[1]) + "'>" + esc((PERMS[k] || [k])[0]) + "</span>"; }).join("");
    return p || "<span class='chip quiet'>Needs nothing special</span>";
  }

  // ---- the filters and the list
  function matches(a) {
    if (state.cat !== "all" && (a.categories || [a.category]).indexOf(state.cat) < 0) return false;
    if (state.perm !== "all" && (a.permissions || []).indexOf(state.perm) < 0) return false;
    if (state.live && !a.lockdown_safe) return false;
    if (state.plain && (a.pip || []).length) return false;
    if (!state.q) return true;
    var hay = [a.name, a.id, a.command, (a.alias || []).join(" "), a.description, (a.tags || []).join(" ")].join(" ").toLowerCase();
    return state.q.toLowerCase().split(/\s+/).every(function (w) { return hay.indexOf(w) >= 0; });
  }
  function order(list) {
    var by = {
      featured: function (a, b) { return (b.featured ? 1 : 0) - (a.featured ? 1 : 0) || a.name.localeCompare(b.name); },
      name: function (a, b) { return a.name.localeCompare(b.name); },
      size: function (a, b) { return sizeOf(a) - sizeOf(b) || a.name.localeCompare(b.name); },
      updated: function (a, b) { return newer(b.version, a.version) || a.name.localeCompare(b.name); }
    }[state.sort];
    return list.slice().sort(by);
  }
  function card(a) {
    return "<button class='app-card' type='button' data-id='" + esc(a.id) + "'>" +
      "<span class='app-top'><b>" + esc(a.name) + "</b><span class='ver'>v" + esc(a.version) + "</span></span>" +
      "<span class='app-desc'>" + esc(a.description) + "</span>" +
      "<span class='chips-row'>" + pills(a) + "</span>" +
      "<span class='app-foot'><span class='muted'>" + esc(catTitle(a.category)) + "</span><span class='badges'>" +
      (a.featured ? "<span class='chip hot'>Featured</span>" : "") + (a.lockdown_safe ? "<span class='chip ok' title='Also runs on the live USB'>Live USB</span>" : "") +
      ((a.pip || []).length ? "<span class='chip lib' title='Installs Python libraries'>Libraries</span>" : "") + "<span class='muted'>" + P.size(sizeOf(a)) + "</span></span></span></button>";
  }
  function render() {
    var shown = order(state.apps.filter(matches));
    $("apps").innerHTML = shown.map(card).join("");
    $("empty").hidden = shown.length > 0;
    $("result-count").textContent = shown.length === state.apps.length ? shown.length + " apps" : shown.length + " of " + state.apps.length + " apps";
    document.querySelectorAll(".app-card").forEach(function (b) { b.addEventListener("click", function () { open(b.getAttribute("data-id"), true); }); });
  }
  function chips(el, items, key) {
    el.innerHTML = items.map(function (it) { return "<button class='tab' type='button' data-v='" + esc(it[0]) + "' aria-pressed='" + (state[key] === it[0]) + "'>" + esc(it[1]) + "</button>"; }).join("");
    el.querySelectorAll("[data-v]").forEach(function (b) { b.addEventListener("click", function () { state[key] = b.getAttribute("data-v"); chips(el, items, key); sync(); render(); }); });
  }

  // ---- the detail window
  function section(title, html) { return html ? "<section><h3>" + title + "</h3>" + html + "</section>" : ""; }
  function changelog(a) {
    var c = a.changelog;
    if (!c) return "";
    if (typeof c === "string") return "<p>" + esc(c) + "</p>";
    var versions = Object.keys(c).sort(function (x, y) { return newer(y, x); });
    return "<ul class='log'>" + versions.map(function (v) { return "<li><b>" + esc(v) + "</b> " + esc(c[v]) + "</li>"; }).join("") + "</ul>";
  }
  function open(id, push) {
    var a = state.apps.filter(function (x) { return x.id === id; })[0];
    if (!a) return;
    $("d-title").textContent = a.name;
    $("d-sub").textContent = "Version " + a.version + " · " + catTitle(a.category) + " · " + P.size(sizeOf(a)) + " · " + (a.files || []).length + " file" + ((a.files || []).length === 1 ? "" : "s");
    $("d-desc").textContent = a.description;
    $("d-cmd").textContent = installCommand(a);
    var perms = (a.permissions || []).length ? "<ul class='perm-list'>" + a.permissions.map(function (k) { return "<li><b>" + esc((PERMS[k] || [k])[0]) + "</b> It may " + esc((PERMS[k] || [k, k])[1]) + ".</li>"; }).join("") + "</ul>" +
      "<p class='muted'>It is held to this while it runs, and you can change it with <code>pkg permissions " + esc(a.command || a.id) + "</code>.</p>" : "<p>It needs no special permissions.</p>";
    var facts = [
      ["Start it with", a.command ? "<code>run " + esc(a.command) + "</code>" + ((a.alias || []).length ? " (also " + a.alias.map(function (x) { return "<code>" + esc(x) + "</code>"; }).join(", ") + ")" : "") : ""],
      ["Runs on the live USB", a.lockdown_safe ? "Yes: it cannot reach anything underneath PythonOS" : "No: it starts other programs or needs libraries, so the locked-down live USB refuses it"],
      ["Marketplace API", String(a.api || 1)]
    ].filter(function (f) { return f[1]; }).map(function (f) { return "<tr><th>" + f[0] + "</th><td>" + f[1] + "</td></tr>"; }).join("");
    var needs = (a.requires || []).length ? "<p>" + a.requires.map(function (r) { return "<code>" + esc(r) + "</code>"; }).join(" ") + "</p><p class='muted'>Installed together with it (you are asked first).</p>" : "";
    var opt = (a.optional || []).length ? "<p>" + a.optional.map(function (r) { r = typeof r === "string" ? r : (r.ref || ""); return "<code>" + esc(r) + "</code>"; }).join(" ") + "</p>" : "";
    var libs = (a.pip || []).length ? "<p>" + a.pip.map(function (r) { return "<code>" + esc(r) + "</code>"; }).join(" ") + "</p><p class='muted'>Python libraries from PyPI. The marketplace installs them (wheels only) inside the app's own folder and shows them before you agree. Not available on the Android app or the live USB.</p>" : "";
    var options = (a.settings || []).length ? "<p>" + a.settings.map(function (r) { return "<code>" + esc(r) + "</code>"; }).join(" ") + "</p><p class='muted'>Change them with <code>settings app " + esc(a.command || a.id) + "</code> or in the Settings app.</p>" : "";
    var files = (a.files || []).length ? "<details><summary>" + a.files.length + " file" + (a.files.length === 1 ? "" : "s") + "</summary><ul class='files-list'>" + a.files.map(function (f) { return "<li><code>" + esc(f.path) + "</code> <span class='muted'>" + P.size(f.size || 0) + "</span></li>"; }).join("") + "</ul><p class='muted'>Each file is checked against a SHA-256 checksum from the catalog before it is installed.</p></details>" : "";
    var tags = (a.tags || []).length ? "<p class='chips-row'>" + a.tags.map(function (t) { return "<span class='chip quiet'>" + esc(t) + "</span>"; }).join("") + "</p>" : "";
    $("d-body").innerHTML = section("What it may do", perms) + section("About", "<table class='facts'>" + facts + "</table>" + tags) + section("Needs", needs) + section("Python libraries", libs) +
      section("Works better with", opt) + section("Options", options) + section("What changed", changelog(a)) + section("Files", files) +
      "<p class='muted'><a href='https://github.com/" + P.REPO + "/tree/main/online_packages/" + esc(a.id) + "'>See the source on GitHub</a></p>";
    var dialog = $("detail");
    if (!dialog.open) { if (dialog.showModal) dialog.showModal(); else dialog.setAttribute("open", ""); }
    dialog.scrollTop = 0;
    if (push) { try { history.replaceState(null, "", "#app=" + encodeURIComponent(id)); } catch (e) {} }
  }
  function close() {
    var dialog = $("detail");
    if (dialog.close) dialog.close(); else dialog.removeAttribute("open");
    try { history.replaceState(null, "", location.pathname + location.search); } catch (e) {}
  }

  // ---- the address keeps the search and the filters, so a link shows the same list
  function sync() {
    var parts = [];
    if (state.q) parts.push("q=" + encodeURIComponent(state.q));
    if (state.cat !== "all") parts.push("c=" + encodeURIComponent(state.cat));
    if (state.perm !== "all") parts.push("p=" + encodeURIComponent(state.perm));
    try { history.replaceState(null, "", parts.length ? "#" + parts.join("&") : location.pathname + location.search); } catch (e) {}
  }
  function fromAddress() {
    var h = location.hash.replace(/^#/, "");
    h.split("&").forEach(function (kv) {
      var i = kv.indexOf("="), k = kv.slice(0, i), v = decodeURIComponent(kv.slice(i + 1));
      if (k === "q") state.q = v; else if (k === "c") state.cat = v; else if (k === "p") state.perm = v; else if (k === "app") state.open = v;
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    fromAddress();
    $("q").value = state.q;
    $("q").addEventListener("input", function () { state.q = this.value.trim(); sync(); render(); });
    $("sort").addEventListener("change", function () { state.sort = this.value; render(); });
    [["only-live", "live"], ["only-plain", "plain"]].forEach(function (p) {
      $(p[0]).addEventListener("click", function () { state[p[1]] = !state[p[1]]; this.setAttribute("aria-pressed", String(state[p[1]])); render(); });
    });
    $("d-close").addEventListener("click", close);
    $("detail").addEventListener("click", function (e) { if (e.target === this) close(); });
    $("detail").addEventListener("close", function () { try { history.replaceState(null, "", location.pathname + location.search); } catch (e) {} });
    $("d-copy").addEventListener("click", function () { P.copy($("d-cmd").textContent, this); });

    load(0).then(function (data) {
      state.apps = data.packages || [];
      (data.categories || []).forEach(function (c) { state.cats[c.id] = c; });
      var counts = {};
      state.apps.forEach(function (a) { (a.categories || [a.category]).forEach(function (c) { counts[c] = (counts[c] || 0) + 1; }); });
      var catItems = [["all", "All (" + state.apps.length + ")"]].concat(Object.keys(counts).sort(function (x, y) { return catTitle(x).localeCompare(catTitle(y)); }).map(function (c) { return [c, catTitle(c) + " (" + counts[c] + ")"]; }));
      chips($("cats"), catItems, "cat");
      var permItems = [["all", "Anything"]].concat(Object.keys(PERMS).filter(function (k) { return state.apps.some(function (a) { return (a.permissions || []).indexOf(k) >= 0; }); }).map(function (k) { return [k, PERMS[k][0]]; }));
      chips($("perms"), permItems, "perm");
      $("lib-count").textContent = state.apps.length + " apps";
      render();
      if (state.open) open(state.open, false);
    }).catch(function (e) {
      $("apps").innerHTML = "<p class='note err'>Could not load the app list (" + esc(e.message) + "). Open the <a href='https://github.com/" + P.REPO + "/tree/main/online_packages'>apps folder</a> on GitHub instead.</p>";
    });
  });
})();
