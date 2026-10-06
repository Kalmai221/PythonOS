// PythonOS download page: finds the latest release, works out which system and processor you have, and lists the files for each system.
// No dependencies. The file tables below (GROUPS, USE, ARCHS) say which release file is for what.
document.addEventListener("DOMContentLoaded", function () {
  "use strict";
  var P = window.PyOS;
  var $ = function (id) { return document.getElementById(id); };
  var GROUPS = [
    { id: "windows", title: "Windows", match: /(web-setup\.exe|-setup\.exe|windows(-arm64)?-portable\.zip)$/, note: "Windows 10 (1809) or newer, on Intel/AMD or ARM. The web installer is a tiny download that fetches and checks the right package for your PC." },
    { id: "android", title: "Android", match: /\.apk$/, note: "Android 7 or newer. The installer app (about 1 MB) finds out which processor your device has and downloads the right PythonOS app, checking it first. Or download the full app yourself: arm64 for nearly every phone." },
    { id: "linux", title: "Linux", match: /(\.deb|-linux\.tar\.gz|\.pkg\.tar\.zst|\.rpm)$/, note: "Any Linux with Python 3.9+, on any processor. Debian/Ubuntu: .deb. Arch: .pkg.tar.zst. Fedora/RHEL/openSUSE: .rpm. Everything else: the tarball." },
    { id: "usb", title: "Bootable USB", match: /((x86_64|aarch64)\.iso|pythonos-wizard-[\d.]+\.zip)$/, note: "Boot a PC (x86_64) or an ARM computer (aarch64, UEFI) from a stick without touching its disk. Write it with the Setup Wizard, which only offers USB sticks and checks what it wrote." },
    { id: "vm", title: "Virtual machine", match: /(\.ova|\.qcow2|vm-kit\.zip)$/, note: "Import the .ova into VirtualBox or VMware, or attach the .qcow2 in QEMU, KVM or Proxmox. These are for PCs (x86_64)." }
  ];
  var USE = [
    [/web-setup\.exe$/, "Recommended installer (picks the right package for your PC)"], [/arm64-setup\.exe$/, "Full installer for Windows on ARM"], [/-setup\.exe$/, "Full installer (offline)"],
    [/windows-arm64-portable/, "Portable, Windows on ARM"], [/windows-portable/, "Portable: unzip and run"],
    [/android-installer\.apk$/, "Recommended: a tiny installer that picks the right app for your device"], [/arm64-v8a\.apk$/, "Phones and tablets (full app)"], [/x86_64\.apk$/, "Chromebooks and emulators"], [/android\.apk$/, "Universal APK"],
    [/\.deb$/, "Debian, Ubuntu and friends"], [/pkg\.tar\.zst$/, "Arch, Manjaro"], [/\.rpm$/, "Fedora, RHEL, openSUSE"], [/linux\.tar\.gz$/, "Any Linux, any processor"],
    [/minimal-aarch64\.iso$/, "Live system only, 64-bit ARM"], [/aarch64\.iso$/, "Full image for 64-bit ARM (UEFI)"], [/minimal-x86_64\.iso$/, "Live system only, small (512 MB RAM)"], [/x86_64\.iso$/, "Full image: installer, Bluetooth, printing"],
    [/pythonos-wizard-/, "Setup Wizard: install, write a USB stick, set up a VM (Windows, Linux)"],
    [/\.ova$/, "VirtualBox / VMware appliance"], [/vm-data\.qcow2$/, "Data disk: attach it next to the .qcow2 to keep your files"], [/\.qcow2$/, "QEMU / KVM / Proxmox disk"], [/vm-kit/, "Run scripts for QEMU, VirtualBox, VMware"]
  ];
  var ARCHS = {
    windows: [["x64", "Intel / AMD (x64)"], ["arm64", "ARM64 (Surface Pro X, Copilot+)"]],
    android: [["arm64", "ARM 64-bit (arm64-v8a)"], ["x64", "Intel / AMD (x86_64)"]],
    usb: [["x64", "PC (x86_64)"], ["arm64", "ARM 64-bit (aarch64, UEFI)"]]
  };                                                  // Linux packages and the VM images are the same for every choice, so they show no chooser
  function archName(id, arch) {
    var list = ARCHS[id] || [];
    for (var i = 0; i < list.length; i++) if (list[i][0] === arch) return list[i][1];
    return arch === "arm64" ? "ARM" : "Intel / AMD";
  }
  function order(n) { for (var i = 0; i < USE.length; i++) if (USE[i][0].test(n)) return i; return 99; }
  function useOf(n) { for (var i = 0; i < USE.length; i++) if (USE[i][0].test(n)) return USE[i][1]; return ""; }

  // which processor a file is for: "x64", "arm64", or "any" (works on both)
  function archOf(name) {
    if (/arm64-v8a\.apk$/.test(name) || /arm64/.test(name) || /aarch64/.test(name)) return "arm64";
    if (/x86_64/.test(name)) return "x64";
    if (/windows-portable\.zip$/.test(name) || (/-setup\.exe$/.test(name) && !/web-setup/.test(name))) return "x64";
    return "any";
  }
  function platformGuess() {
    var ua = navigator.userAgent || "";
    if (/Android/i.test(ua)) return "android";
    if (/Windows/i.test(ua)) return "windows";
    if (/Linux|X11|CrOS/i.test(ua)) return "linux";
    return "usb";
  }
  function archFromUA() { return /aarch64|arm64|\barm\b/i.test(navigator.userAgent || "") ? "arm64" : "x64"; }

  var state = { arch: null, detected: null, how: "", platform: platformGuess(), assets: [], release: null, tab: null };
  try { state.arch = sessionStorage.getItem("arch"); } catch (e) {}

  // The graphics chip's name, which gives away what the user agent hides: Apple-silicon Macs say "Intel" in the user agent (Safari always
  // does), and an x64 browser running emulated on Windows on ARM says x86. Empty when the browser does not share it.
  function gpuName() {
    try {
      var canvas = document.createElement("canvas");
      var gl = canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
      var info = gl && gl.getExtension("WEBGL_debug_renderer_info");
      return info ? String(gl.getParameter(info.UNMASKED_RENDERER_WEBGL) || "") : "";
    } catch (e) { return ""; }
  }

  // Detect the processor, as well as a web page can: the browser's own report first (Chromium), then the graphics chip, then the user agent
  // text. Returns {arch: "x64" | "arm64", how: where the answer came from}. The visitor can always change it.
  function detectArch() {
    var ua = navigator.userAgent || "";
    var gpu = gpuName();
    var found = { arch: archFromUA(), how: "your browser's description of itself" };
    if (/Macintosh|Mac OS X/.test(ua) && !/iPhone|iPad/.test(ua)) {
      if (/Apple (M\d|GPU)/i.test(gpu)) found = { arch: "arm64", how: "your Mac's graphics chip (Apple silicon)" };
      else if (/Intel|AMD|Radeon|NVIDIA/i.test(gpu)) found = { arch: "x64", how: "your Mac's graphics chip (Intel)" };
    }
    function adjust(result) {
      // an x64 browser emulated on Windows on ARM reports x86, but its graphics chip is a Qualcomm Adreno
      if (/Windows/.test(ua) && /Adreno|Qualcomm|Snapdragon/i.test(gpu) && result.arch !== "arm64") return { arch: "arm64", how: "your PC's graphics chip (Qualcomm, Windows on ARM)" };
      return result;
    }
    if (navigator.userAgentData && navigator.userAgentData.getHighEntropyValues) {
      return navigator.userAgentData.getHighEntropyValues(["architecture", "bitness"]).then(function (v) {
        if (!v.architecture) return adjust(found);
        var detail = v.architecture + (v.bitness ? ", " + v.bitness + "-bit" : "");
        return adjust({ arch: /arm/i.test(v.architecture) ? "arm64" : "x64", how: "your browser (" + detail + ")" });
      }, function () { return adjust(found); });
    }
    return Promise.resolve(adjust(found));
  }

  function fits(a, arch) { var x = archOf(a.name); return x === "any" || x === arch || (x === "arm64" && arch === "arm64"); }
  function mainFile(assets, id, arch) {
    var by = function (re) { return assets.filter(function (a) { return re.test(a.name); })[0]; };
    if (id === "android") return by(/android-installer\.apk$/) || (arch === "arm64" ? by(/arm64-v8a\.apk$/) : by(/x86_64\.apk$/)) || by(/android\.apk$/);
    if (id === "windows") return by(/web-setup\.exe$/) || (arch === "arm64" ? by(/arm64-setup\.exe$/) : by(/-setup\.exe$/));
    if (id === "linux") return by(/\.deb$/) || by(/linux\.tar\.gz$/);
    return arch === "arm64" ? (by(/(?<!minimal-)aarch64\.iso$/) || by(/aarch64\.iso$/)) : by(/(?<!minimal-)x86_64\.iso$/);
  }
  var NAMES = { android: "Android", windows: "Windows", linux: "Linux", usb: "a bootable USB" };

  // ---- drawing
  function setArch(arch) {
    state.arch = arch;
    try { sessionStorage.setItem("arch", arch); } catch (e) {}
    render();
  }
  function renderArchBar(groupId) {
    var bar = $("archbar");
    var list = ARCHS[groupId];
    if (!list) { bar.hidden = true; bar.innerHTML = ""; return; }
    bar.hidden = false;
    var guess = state.detected ? "Detected " + (state.detected === "arm64" ? "ARM" : "Intel / AMD") + (state.how ? " from " + state.how : "") + (state.arch !== state.detected ? "; you chose " + (state.arch === "arm64" ? "ARM" : "Intel / AMD") : "") + "." : "";
    bar.innerHTML = "<span class='label'>Processor</span><div class='tabs' role='group' aria-label='Processor'>" + list.map(function (a) {
      return "<button class='tab' type='button' data-arch='" + a[0] + "' aria-pressed='" + (state.arch === a[0]) + "'>" + a[1] + "</button>";
    }).join("") + "</div><span class='detected'>" + P.esc(guess) + "</span>";
    bar.querySelectorAll("[data-arch]").forEach(function (b) { b.addEventListener("click", function () { setArch(b.getAttribute("data-arch")); }); });
  }

  function render() {
    var assets = state.assets, rel = state.release;
    if (!rel) return;
    var main = mainFile(assets, state.platform, state.arch);
    $("rec").innerHTML = main
      ? "<p><b>For " + NAMES[state.platform] + ":</b> <span class='name'>" + P.esc(main.name) + "</span> <span class='muted'>(" + P.size(main.size) + (ARCHS[state.platform] ? ", " + archName(state.platform, state.arch) : "") + ")</span></p>" +
        "<p><a class='btn primary' href='" + main.browser_download_url + "'>Download</a> <a class='btn ghost' href='" + rel.html_url + "'>Release notes</a></p>" +
        "<p class='muted'>Not the right system? Choose another below.</p>"
      : "<p class='muted'>Choose your system below.</p>";
    $("ver").textContent = rel.tag_name.replace(/^v/, "") + ", released " + P.when(rel.published_at);

    var tabs = $("tabs");
    tabs.innerHTML = "";
    var present = GROUPS.filter(function (g) { return assets.some(function (a) { return g.match.test(a.name); }); });
    var chosen = present.some(function (g) { return g.id === state.tab; }) ? state.tab : (present.some(function (g) { return g.id === state.platform; }) ? state.platform : (present[0] && present[0].id));
    present.forEach(function (g) {
      var b = document.createElement("button");
      b.className = "tab"; b.type = "button"; b.textContent = g.title;
      b.setAttribute("aria-pressed", String(g.id === chosen));
      b.addEventListener("click", function () { state.tab = g.id; render(); });
      tabs.appendChild(b);
    });
    var group = present.filter(function (g) { return g.id === chosen; })[0];
    renderArchBar(chosen);
    if (!group) { $("files").innerHTML = ""; $("note").textContent = ""; return; }
    var all = assets.filter(function (a) { return group.match.test(a.name); });
    var items = all.filter(function (a) { return fits(a, state.arch); }).sort(function (a, b) { return order(a.name) - order(b.name); });
    var hidden = all.length - items.length;
    var top = mainFile(assets, group.id, state.arch);
    $("files").innerHTML = items.length ? items.map(function (a) {
      return "<li><span><span class='name'>" + P.esc(a.name) + "</span>" + (top && top.name === a.name ? "<span class='rec'>recommended</span>" : "") + "</span>" +
             "<span><span class='muted'>" + P.size(a.size) + "</span> &nbsp; <a href='" + a.browser_download_url + "'>Download</a></span>" +
             "<span class='use'>" + P.esc(useOf(a.name)) + "</span></li>";
    }).join("") : "<li class='note'>There is no " + archName(group.id, state.arch) + " build of this in the release. Pick the other processor.</li>";
    $("note").innerHTML = P.esc(group.note) + (hidden > 0 ? " <span class='muted'>(" + hidden + " file" + (hidden > 1 ? "s" : "") + " for the other processor hidden.)</span>" : "");
    var wizard = assets.filter(function (a) { return /pythonos-wizard-[\d.]+\.zip$/.test(a.name); })[0];
    if (wizard) { $("wizard").hidden = false; $("wizard-link").href = wizard.browser_download_url; }
  }

  Promise.all([P.api("releases/latest"), detectArch()]).then(function (r) {
    var rel = r[0];
    state.detected = r[1].arch;
    state.how = r[1].how;
    if (state.arch !== "x64" && state.arch !== "arm64") state.arch = state.detected;
    state.release = rel;
    state.assets = rel.assets.filter(function (a) { return !/SHA256SUMS|core|manifest|\.json$/i.test(a.name); });
    render();
  }).catch(function (e) {
    $("rec").innerHTML = "<p class='note err'>Could not load the latest release (" + P.esc(e.message) + "). Open the <a href='https://github.com/Kalmai221/PythonOS/releases/latest'>releases page</a> instead.</p>";
    $("tabs").hidden = true;
  });
});
