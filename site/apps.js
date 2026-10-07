// PythonOS App Library: lists every app of the store from the catalog, with search, filters and a detail window. No dependencies.
(function () {
  "use strict";
  var P = window.PyOS;
  var SOURCES = ["data/catalog.json", "https://raw.githubusercontent.com/Kalmai221/PythonOS/main/online_packages/index-api2.json", "https://raw.githubusercontent.com/Kalmai221/PythonOS/main/online_packages/index.json"];
  var PERMS = {
    network: ["Internet", "connect to the internet"], files: ["Your files", "read and change your files"], notifications: ["Notifications", "show notifications"],
    schedule: ["Schedule", "schedule tasks"], system: ["System info", "read information about this computer"], exec: ["Other programs", "start other programs"]
  };
  var EXPORTS = { windows: "Windows app", linux: "Linux and Docker", android: "Android app", iso: "Bootable ISO and VMs" };
  var EXPORT_SHORT = { windows: "Windows", linux: "Linux", android: "Android", iso: "ISO / VM" };
  var state = { apps: [], cats: {}, q: "", cat: "all", perm: "all", exp: "all", live: false, plain: false, sort: "featured", page: 1, per: 24 };
  function exportsOf(a) { return a.exports && a.exports.length ? a.exports : Object.keys(EXPORTS); }
  function everywhere(a) { return exportsOf(a).length === Object.keys(EXPORTS).length; }
  // the live USB runs apps that cannot reach anything underneath PythonOS (lockdown_safe) and that list the ISO
  function onLive(a) { return !!a.lockdown_safe && exportsOf(a).indexOf("iso") >= 0; }
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
  function worksOn(a) {
    return everywhere(a) ? "Every export" : exportsOf(a).map(function (k) { return EXPORTS[k] || k; }).join(", ");
  }
  function runFiles(a) {
    var r = a.run_exports || [];
    return r.length ? "Its own start file on: " + r.map(function (k) { return EXPORT_SHORT[k] || k; }).join(", ") + " (the others use the common one)" : "";
  }
  function pills(a) {
    var p = (a.permissions || []).map(function (k) { return "<span class='chip perm' title='" + esc((PERMS[k] || [k, k])[1]) + "'>" + esc((PERMS[k] || [k])[0]) + "</span>"; }).join("");
    return p || "<span class='chip quiet'>Needs nothing special</span>";
  }

  // ---- the filters and the list
  function matches(a) {
    if (state.cat !== "all" && (a.categories || [a.category]).indexOf(state.cat) < 0) return false;
    if (state.perm !== "all" && (a.permissions || []).indexOf(state.perm) < 0) return false;
    if (state.exp !== "all" && exportsOf(a).indexOf(state.exp) < 0) return false;
    if (state.live && !onLive(a)) return false;
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
      (a.featured ? "<span class='chip hot'>Featured</span>" : "") + (onLive(a) ? "<span class='chip ok' title='Also runs on the live USB'>Live USB</span>" : "") +
      (everywhere(a) ? "" : "<span class='chip quiet' title='" + esc(worksOn(a)) + "'>" + esc(exportsOf(a).map(function (k) { return EXPORT_SHORT[k] || k; }).join(" · ")) + "</span>") +
      ((a.pip || []).length ? "<span class='chip lib' title='Installs Python libraries'>Libraries</span>" : "") + "<span class='muted'>" + P.size(sizeOf(a)) + "</span></span></span></button>";
  }
  // ---- pages: a window of the filtered list (state.per apps, 0 = all of them)
  function pageCount(total) { return state.per > 0 ? Math.max(1, Math.ceil(total / state.per)) : 1; }
  // the page numbers to show: the first, the last and the ones around the current page, with "..." where numbers are left out
  function pageNumbers(current, last) {
    var keep = {}, out = [], prev = 0;
    [1, last, current - 1, current, current + 1].forEach(function (n) { if (n >= 1 && n <= last) keep[n] = true; });
    Object.keys(keep).map(Number).sort(function (a, b) { return a - b; }).forEach(function (n) {
      if (prev && n - prev > 1) out.push(n - prev === 2 ? prev + 1 : 0);          // one missing number is just shown; more become an ellipsis
      out.push(n);
      prev = n;
    });
    return out;
  }
  function pager(total) {
    var last = pageCount(total), nav = $("pager");
    if (last <= 1) { nav.hidden = true; nav.innerHTML = ""; return; }
    var html = "<button class='tab' type='button' data-page='" + (state.page - 1) + "'" + (state.page <= 1 ? " disabled" : "") + " aria-label='Previous page'>&larr; Previous</button>";
    pageNumbers(state.page, last).forEach(function (n) {
      html += n === 0 ? "<span class='gap' aria-hidden='true'>&hellip;</span>" :
        "<button class='tab' type='button' data-page='" + n + "' aria-label='Page " + n + "'" + (n === state.page ? " aria-current='page' aria-pressed='true'" : " aria-pressed='false'") + ">" + n + "</button>";
    });
    html += "<button class='tab' type='button' data-page='" + (state.page + 1) + "'" + (state.page >= last ? " disabled" : "") + " aria-label='Next page'>Next &rarr;</button>";
    nav.innerHTML = html;
    nav.hidden = false;
    nav.querySelectorAll("[data-page]").forEach(function (b) {
      b.addEventListener("click", function () {
        var n = parseInt(b.getAttribute("data-page"), 10);
        if (n >= 1 && n <= last && n !== state.page) { state.page = n; sync(); render(); $("result-count").scrollIntoView({ block: "start", behavior: "smooth" }); }
      });
    });
  }
  function render() {
    var all = order(state.apps.filter(matches));
    state.page = Math.min(Math.max(state.page, 1), pageCount(all.length));                 // a filter can leave fewer pages than before
    var from = state.per > 0 ? (state.page - 1) * state.per : 0;
    var shown = state.per > 0 ? all.slice(from, from + state.per) : all;
    $("apps").innerHTML = shown.map(card).join("");
    $("empty").hidden = all.length > 0;
    var filtered = all.length !== state.apps.length;
    var total = filtered ? all.length + " of " + state.apps.length + " apps" : all.length + " apps";
    $("result-count").textContent = shown.length && shown.length < all.length
      ? "Showing " + (from + 1) + "–" + (from + shown.length) + " of " + all.length + (filtered ? " matching apps (" + state.apps.length + " in all)" : " apps")
      : total;
    pager(all.length);
    document.querySelectorAll(".app-card").forEach(function (b) { b.addEventListener("click", function () { open(b.getAttribute("data-id"), true); }); });
  }
  // a new search, filter or sort starts from the first page again
  function refresh() { state.page = 1; sync(); render(); }
  function chips(el, items, key) {
    el.innerHTML = items.map(function (it) { return "<button class='tab' type='button' data-v='" + esc(it[0]) + "' aria-pressed='" + (state[key] === it[0]) + "'>" + esc(it[1]) + "</button>"; }).join("");
    el.querySelectorAll("[data-v]").forEach(function (b) { b.addEventListener("click", function () { state[key] = b.getAttribute("data-v"); chips(el, items, key); refresh(); }); });
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
      ["Works on", worksOn(a)],
      ["Start file", runFiles(a)],
      ["Marketplace API", String(a.api || 1)]
    ].filter(function (f) { return f[1]; }).map(function (f) { return "<tr><th>" + f[0] + "</th><td>" + f[1] + "</td></tr>"; }).join("");
    var needs = (a.requires || []).length ? "<p>" + a.requires.map(function (r) { return "<code>" + esc(r) + "</code>"; }).join(" ") + "</p><p class='muted'>Installed together with it (you are asked first).</p>" : "";
    var opt = (a.optional || []).length ? "<p>" + a.optional.map(function (r) { r = typeof r === "string" ? r : (r.ref || ""); return "<code>" + esc(r) + "</code>"; }).join(" ") + "</p>" : "";
    var libs = (a.pip || []).length ? "<p>" + a.pip.map(function (r) { return "<code>" + esc(r) + "</code>"; }).join(" ") + "</p><p class='muted'>Python libraries from PyPI (marketplace API 2). The marketplace installs them (wheels only) inside the app's own folder and shows them before you agree. The locked-down live USB and VM images cannot run apps with libraries, so these apps list the exports they do work on.</p>" : "";
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
    if (state.exp !== "all") parts.push("e=" + encodeURIComponent(state.exp));
    if (state.page > 1) parts.push("pg=" + state.page);
    if (state.per !== 24) parts.push("n=" + state.per);
    try { history.replaceState(null, "", parts.length ? "#" + parts.join("&") : location.pathname + location.search); } catch (e) {}
  }
  function fromAddress() {
    var h = location.hash.replace(/^#/, "");
    h.split("&").forEach(function (kv) {
      var i = kv.indexOf("="), k = kv.slice(0, i), v = decodeURIComponent(kv.slice(i + 1));
      if (k === "q") state.q = v; else if (k === "c") state.cat = v; else if (k === "p") state.perm = v; else if (k === "e") state.exp = v; else if (k === "pg") state.page = parseInt(v, 10) || 1; else if (k === "n") state.per = [0, 12, 24, 48].indexOf(parseInt(v, 10)) >= 0 ? parseInt(v, 10) : 24; else if (k === "app") state.open = v;
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    fromAddress();
    $("q").value = state.q;
    $("per").value = String(state.per);
    $("q").addEventListener("input", function () { state.q = this.value.trim(); refresh(); });
    $("sort").addEventListener("change", function () { state.sort = this.value; refresh(); });
    $("per").addEventListener("change", function () { state.per = parseInt(this.value, 10); refresh(); });
    [["only-live", "live"], ["only-plain", "plain"]].forEach(function (p) {
      $(p[0]).addEventListener("click", function () { state[p[1]] = !state[p[1]]; this.setAttribute("aria-pressed", String(state[p[1]])); refresh(); });
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
      var expItems = [["all", "Anywhere"]].concat(Object.keys(EXPORTS).map(function (k) { return [k, EXPORTS[k]]; }));
      chips($("exports"), expItems, "exp");
      $("lib-count").textContent = state.apps.length + " apps";
      render();
      if (state.open) open(state.open, false);
    }).catch(function (e) {
      $("apps").innerHTML = "<p class='note err'>Could not load the app list (" + esc(e.message) + "). Open the <a href='https://github.com/" + P.REPO + "/tree/main/online_packages'>apps folder</a> on GitHub instead.</p>";
    });
  });
})();
