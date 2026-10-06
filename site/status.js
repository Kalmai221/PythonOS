// Build status page: reads GitHub Actions and the latest release for this repository. No dependencies.
document.addEventListener("DOMContentLoaded", function () {
  "use strict";
  var P = window.PyOS;
  var $ = function (id) { return document.getElementById(id); };
  var timer = null, show = "all", lastRuns = [];

  // the parts of a build, in the order they run; a job goes in the first stage whose pattern matches its name
  var STAGES = [
    { id: "plan", title: "Plan", hint: "Works out what changed since the last release", re: /^Plan/i },
    { id: "checks", title: "Checks", hint: "Lockdown audit, dependency scan, smoke test", re: /^Checks/i },
    { id: "packages", title: "Packages", hint: "Windows, Android, Linux and the live USB and virtual machine images", re: /^(Windows|Android|Linux|ISO|Bootable|Virtual)/i },
    { id: "wizard", title: "Setup Wizard", hint: "The program that installs PythonOS, per system, and its zip", re: /^Setup Wizard/i },
    { id: "core", title: "Core update", hint: "What installed copies download to update themselves", re: /^Core/i },
    { id: "docker", title: "Docker", hint: "The container image", re: /^Docker/i },
    { id: "release", title: "Release", hint: "Checksums, signatures and the release page", re: /^Publish/i }
  ];
  function state(r) { return r.status === "completed" ? (r.conclusion || "other") : (r.status === "queued" || r.status === "waiting" || r.status === "pending" ? "queued" : "running"); }
  function label(s) { return { success: "passed", failure: "failed", cancelled: "cancelled", timed_out: "timed out", running: "running", queued: "waiting", skipped: "skipped", neutral: "neutral" }[s] || s; }
  function icon(s) { return { success: "✓", failure: "✕", timed_out: "✕", cancelled: "–", skipped: "–", running: "●", queued: "○" }[s] || "·"; }
  function pill(s) { return "<span class='spill " + s + "'>" + label(s) + "</span>"; }
  function bust() { try { Object.keys(sessionStorage).forEach(function (k) { if (k.indexOf("gh:") === 0) sessionStorage.removeItem(k); }); } catch (e) {} }
  function took(a, b) {
    if (!a) return "";
    var s = Math.max(0, Math.round(((b ? new Date(b) : new Date()) - new Date(a)) / 1000));
    return s < 60 ? s + " s" : s < 3600 ? Math.floor(s / 60) + " min " + (s % 60) + " s" : Math.floor(s / 3600) + " h " + Math.floor(s % 3600 / 60) + " min";
  }
  function ago(d) {
    var s = Math.max(0, Math.round((Date.now() - new Date(d)) / 1000));
    if (s < 60) return "just now"; if (s < 3600) return Math.floor(s / 60) + " min ago"; if (s < 86400) return Math.floor(s / 3600) + " h ago";
    return Math.floor(s / 86400) + " day" + (Math.floor(s / 86400) === 1 ? "" : "s") + " ago";
  }
  function isTag(r) { return /^v\d/.test(r.head_branch || ""); }
  function what(r) { return isTag(r) ? "Release " + r.head_branch : (r.display_title || r.head_branch); }

  // ---- the banner and the stages of one run
  function drawRun(run, jobs) {
    var s = state(run), b = $("banner");
    var done = jobs.filter(function (j) { return j.status === "completed"; }).length;
    var failed = jobs.filter(function (j) { return j.conclusion === "failure" || j.conclusion === "timed_out"; }).length;
    var s2 = s === "running" && failed ? "bad" : s === "success" ? "ok" : s === "running" || s === "queued" ? "run" : "bad";
    b.className = "banner " + s2;
    $("b-title").textContent = (isTag(run) ? "Release " + run.head_branch + ": " : "") +
      (s === "success" ? "the build passed" : s === "running" ? "the build is running" : s === "queued" ? "the build is waiting to start" : failed || s === "failure" ? "the build did not pass" : "the build was " + label(s));
    $("b-sub").innerHTML = P.esc(run.display_title || "") + " · run #" + run.run_number + " · " + P.esc(run.head_sha.slice(0, 7)) + " · " + ago(run.created_at) +
      " · <a href='" + run.html_url + "'>open on GitHub</a>";
    var meter = $("meter");
    meter.hidden = !(s === "running" || s === "queued");
    $("meter-fill").style.width = (jobs.length ? Math.round(100 * done / jobs.length) : 0) + "%";
    $("b-note").textContent = s === "running" || s === "queued" ? done + " of " + jobs.length + " steps finished · refreshing every 30 seconds" :
      (took(run.run_started_at || run.created_at, run.updated_at) + " in all");

    var grouped = {};
    STAGES.forEach(function (st) { grouped[st.id] = []; });
    grouped.other = [];
    jobs.forEach(function (j) {
      var st = STAGES.filter(function (x) { return x.re.test(j.name); })[0];
      grouped[st ? st.id : "other"].push(j);
    });
    var list = STAGES.concat([{ id: "other", title: "Other", hint: "" }]).filter(function (st) { return grouped[st.id].length; });
    $("stages").innerHTML = list.map(function (st) {
      var js = grouped[st.id];
      var bad = js.filter(function (j) { return j.conclusion === "failure" || j.conclusion === "timed_out"; }).length;
      var running = js.filter(function (j) { return j.status !== "completed" && j.status !== "queued" && j.status !== "waiting"; }).length;
      var waiting = js.filter(function (j) { return j.status === "queued" || j.status === "waiting" || j.status === "pending"; }).length;
      var ok = js.filter(function (j) { return j.conclusion === "success"; }).length;
      var skipped = js.filter(function (j) { return j.conclusion === "skipped"; }).length;
      var overall = bad ? "failure" : running ? "running" : waiting ? "queued" : ok ? "success" : skipped ? "skipped" : "other";
      var summary = bad ? bad + " failed" : running ? running + " running" : waiting ? waiting + " waiting" : ok ? ok + " passed" + (skipped ? ", " + skipped + " reused" : "") : skipped ? "reused from the last release" : "";
      return "<section class='stage " + overall + "'><header><h3>" + st.title + "</h3>" + (summary ? "<span class='spill " + overall + "'>" + summary + "</span>" : "") + "</header>" +
        (st.hint ? "<p class='muted stage-hint'>" + st.hint + "</p>" : "") + "<ul>" + js.map(function (j) {
          var js2 = state(j);
          var failedStep = (j.steps || []).filter(function (x) { return x.conclusion === "failure"; })[0];
          var note = failedStep ? "<span class='step-note'>failed at: " + P.esc(failedStep.name) + "</span>" : js2 === "skipped" ? "<span class='step-note'>skipped: nothing in it changed, so the file from the last release is reused</span>" : "";
          return "<li class='sj " + js2 + "'><span class='sj-icon' aria-hidden='true'>" + icon(js2) + "</span><span class='sj-name'><a href='" + j.html_url + "'>" + P.esc(j.name) + "</a>" + note + "</span>" +
            "<span class='sj-time muted'>" + (js2 === "skipped" || js2 === "queued" ? "" : took(j.started_at, j.completed_at)) + "</span></li>";
        }).join("") + "</ul></section>";
    }).join("");
    $("stamp").textContent = "Updated " + new Date().toLocaleTimeString();
    clearTimeout(timer);
    if (s === "running" || s === "queued") timer = setTimeout(function () { bust(); load(); }, 30000);
  }

  function drawRuns(runs) {
    var list = runs.filter(function (r) { return show === "all" || isTag(r); }).slice(0, 12);
    $("runs").innerHTML = "<tr><th scope='col'>Run</th><th scope='col'>What</th><th scope='col'>Commit</th><th scope='col'>Took</th><th scope='col'>When</th><th scope='col'>Result</th></tr>" +
      (list.length ? list.map(function (r) {
        return "<tr><td><a href='" + r.html_url + "'>#" + r.run_number + "</a></td><td>" + P.esc(what(r)) + "</td><td><code>" + P.esc(r.head_sha.slice(0, 7)) + "</code></td><td>" +
          took(r.run_started_at || r.created_at, r.status === "completed" ? r.updated_at : null) + "</td><td>" + ago(r.created_at) + "</td><td>" + pill(state(r)) + "</td></tr>";
      }).join("") : "<tr><td colspan='6' class='muted'>No builds to show.</td></tr>");
  }
  document.querySelectorAll("[data-show]").forEach(function (b) {
    b.addEventListener("click", function () {
      show = b.getAttribute("data-show");
      document.querySelectorAll("[data-show]").forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
      drawRuns(lastRuns);
    });
  });

  // the other workflows: tests, security scan, website
  function drawHealth(all) {
    var seen = {}, cards = [];
    all.forEach(function (r) { if (r.name !== "Build PythonOS" && !seen[r.name] && r.status === "completed") { seen[r.name] = 1; cards.push(r); } });
    $("health").innerHTML = cards.map(function (r) {
      return "<a class='hcard " + state(r) + "' href='" + r.html_url + "'><span class='sj-icon' aria-hidden='true'>" + icon(state(r)) + "</span><span><b>" + P.esc(r.name) + "</b><br><span class='muted'>" + label(state(r)) + " · " + ago(r.created_at) + "</span></span></a>";
    }).join("");
  }

  function load() {
    $("stamp").textContent = "Loading…";
    P.api("actions/runs?per_page=40").then(function (data) {
      var all = data.workflow_runs || [];
      drawHealth(all);
      var builds = all.filter(function (r) { return r.name === "Build PythonOS"; });
      lastRuns = builds;
      if (!builds.length) throw new Error("no builds yet");
      drawRuns(builds);
      var run = builds[0];
      return P.api("actions/runs/" + run.id + "/jobs?per_page=100").then(function (jobs) { drawRun(run, jobs.jobs || []); });
    }).catch(function (e) {
      $("b-title").textContent = "Could not load the build";
      $("b-sub").innerHTML = "<span class='err'>" + P.esc(e.message) + "</span>";
      $("stamp").textContent = "";
      $("stages").innerHTML = "";
    });

    P.api("releases?per_page=30").then(function (rels) {
      var total = 0, rows = [];
      rels.forEach(function (rel) { rel.assets.forEach(function (a) { total += a.download_count; rows.push({ n: a.name, r: rel.tag_name, d: a.download_count }); }); });
      var latest = rels[0];
      $("kpis").innerHTML = latest ? "<a class='kpi' href='" + latest.html_url + "'><b>" + P.esc(latest.tag_name) + "</b><span>latest release · " + ago(latest.published_at) + "</span></a>" +
        "<div class='kpi'><b>" + latest.assets.length + "</b><span>files in it</span></div>" +
        "<div class='kpi'><b>" + total.toLocaleString() + "</b><span>downloads in total</span></div>" +
        "<div class='kpi'><b>" + rels.length + "</b><span>releases</span></div>" : "";
      rows.sort(function (a, b) { return b.d - a.d; });
      var top = rows.slice(0, 8), max = Math.max.apply(null, top.map(function (r) { return r.d; }).concat([1]));
      $("downloads").innerHTML = top.length ? top.map(function (r) {
        return "<div class='bar-row'><span title='" + P.esc(r.n) + "'>" + P.esc(r.n) + " <span class='muted'>" + P.esc(r.r) + "</span></span><span class='track'><span class='fill' style='display:block;width:" + Math.round(100 * r.d / max) + "%'></span></span><b>" + r.d.toLocaleString() + "</b></div>";
      }).join("") : "<span class='muted'>No downloads yet.</span>";
    }).catch(function (e) { $("kpis").innerHTML = ""; $("downloads").innerHTML = "<span class='err'>" + P.esc(e.message) + "</span>"; });
  }
  $("refresh").addEventListener("click", function () { bust(); load(); });
  load();
});
