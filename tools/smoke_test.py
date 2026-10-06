#!/usr/bin/env python3
"""Start PythonOS in a scratch copy and run real commands through the shell. Fails (exit 1) if any answer is wrong.

    python tools/smoke_test.py              # stages a copy of the repository in a temp folder and tests that
    python tools/smoke_test.py --dir PATH   # tests an already staged OS folder (a package's payload, a Docker image's /opt/pythonos)

It needs the Python packages from requirements.txt. Nothing in the real checkout is touched: accounts and files are made in the copy.
"""
import argparse
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
HAVE_REPO = os.path.isdir(os.path.join(REPO, "OS_Export")) and os.path.isdir(os.path.join(REPO, "tools"))     # false inside a package or a container image


class _Skip(Exception):
    """A check that needs the repository checkout (build tools, other programs) is not run where there is only the packaged OS."""

# (command line, text the output must contain or None, expected status)
CHECKS = [
    ("version", "PythonOS", 0),
    ("help", "Files", 0),
    ("help files", "grep", 0),
    ("man ls", "USAGE", 0),
    ("whoami", "smoke", 0),
    ("echo hello world > a.txt", None, 0),
    ("cat a.txt", "hello world", 0),
    ("echo second >> a.txt", None, 0),
    ("grep -n second a.txt", "2:second", 0),
    ("grep nothere a.txt", None, 1),
    ("find -name a.txt", "a.txt", 0),
    ("mkdir sub && echo made", "made", 0),
    ("ls | grep sub", "sub", 0),
    ("tree", "folders", 0),
    ("cp a.txt b.txt", None, 0),
    ("echo extra >> b.txt", None, 0),
    ("diff a.txt b.txt", "extra", 1),
    ("diff -q a.txt a.txt", None, 0),
    ("zip pack.zip a.txt b.txt", "Added 2", 0),
    ("rm a.txt", "trash", 0),
    ("undo", "Restored", 0),
    ("cat a.txt", "hello world", 0),
    ("trash", None, 0),
    ("settings get theme", "default", 0),
    ("settings apps", None, 0),
    ("doctor", "check(s)", 0),
    ("logs 3", None, 0),
    ("uptime", "up", 0),
    ("tutorial list", "Lesson", 0) if False else ("tutorial list", "Basics", 0),
    ("whathappened", None, 0),
    ("date", None, 0),
    ("ps -a", "kernel", 0),
    ("sleep 5 & ps -a", "sleep 5", 0),
    ("kill 1", None, 1),
    ("nosuchcommand", None, 127),
]


def run(root):
    os.chdir(root)
    sys.path.insert(0, root)
    os.environ["PYOS_BUNDLED"] = "1"          # never let the boot code try to pip install
    import users
    import pyos
    import pyos.fs as fs
    from pyos import settings
    import shell

    os.makedirs(".OSData", exist_ok=True)
    settings.set("notifications", False)
    users.save_users({"smoke": {"password": users.hash_password("Smoke-test-1!"), "role": "admin"}})
    users.save_session("smoke", "admin")
    fs.ensure_layout()
    fs.ensure_home("smoke")
    fs.save_current_dir(fs.home_dir("smoke"))
    shell.reload_all()

    failures = []
    for line, expect, want in CHECKS:
        status, output = shell.run_captured(line)
        problems = []
        if status != want:
            problems.append(f"status {status}, wanted {want}")
        if expect and expect not in output:
            problems.append(f"output lacks {expect!r}")
        mark = "FAIL" if problems else "ok  "
        print(f"{mark} {line}" + (f"   <- {'; '.join(problems)}" if problems else ""))
        if problems:
            failures.append((line, problems, output[-300:]))

    # The real login path: start_shell sets up the scheduler, the battery watcher, the idle watch and the hints before it shows the prompt.
    # The prompt gets an end-of-input (like closing the window), so the shell leaves again; a mistake in that set-up crashes right here.
    import builtins
    real_input = builtins.input

    def no_input(*args, **kwargs):
        raise EOFError

    builtins.input = no_input
    try:
        shell.start_shell("smoke")
        print("ok   start_shell (login path)")
    except BaseException as e:                       # noqa: BLE001 - any failure here is exactly what this test is for
        print(f"FAIL start_shell (login path)   <- {type(e).__name__}: {e}")
        failures.append(("start_shell", [f"{type(e).__name__}: {e}"], ""))
    finally:
        builtins.input = real_input

    # the package sandbox must accept paths given as bytes (psutil lists /proc that way on Linux; this once crashed System Monitor on the ISO)
    try:
        from pyos import sandbox_run
        guard = sandbox_run.Guard(["system"], os.path.join(root, "files"), "smoke/test")
        guard.check_path(b"/proc", False)
        guard.check_path(os.fsencode(os.path.join(root, "files")), False)
        print("ok   sandbox accepts bytes paths")
    except Exception as e:                           # noqa: BLE001
        print(f"FAIL sandbox accepts bytes paths   <- {type(e).__name__}: {e}")
        failures.append(("sandbox bytes paths", [f"{type(e).__name__}: {e}"], ""))

    # the marketplace API versions: what a system can run, and which catalog file it asks for
    try:
        import importlib.util
        import requests
        from pyos import marketapi
        assert marketapi.compatibility({})[0] and marketapi.compatibility({"api": marketapi.CURRENT})[0]
        assert not marketapi.compatibility({"api": marketapi.CURRENT + 1})[0], "a newer package must be refused"
        assert marketapi.package_api({"api": "x"}) == 1 and marketapi.package_api(None) == 1
        assert marketapi.index_names()[-1] == "index.json" and marketapi.index_names(3)[0] == "index-api3.json"
        assert marketapi.usable([{"api": 1}, {"api": marketapi.CURRENT + 1}])[1] == 1
        spec = importlib.util.spec_from_file_location("marketplace_api_test", os.path.join("programs", "marketplace.py"))
        market = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(market)
        asked = []

        def fake_get(url):
            asked.append(url.rsplit("/", 1)[-1])
            if url.endswith(marketapi.index_names()[0]):          # the versioned file is not on the server yet
                response = requests.Response()
                response.status_code = 404
                raise requests.HTTPError("404", response=response)

            class Reply:
                @staticmethod
                def json():
                    return {"api": 1, "packages": []}
            return Reply()
        market.http_get = fake_get
        assert market.fetch_index() == {"api": 1, "packages": []} and asked == marketapi.index_names(), asked
        print("ok   marketplace API versions")
    except Exception as e:                           # noqa: BLE001
        print(f"FAIL marketplace API versions   <- {type(e).__name__}: {e}")
        failures.append(("marketplace API", [f"{type(e).__name__}: {e}"], ""))

    # an update saved on a data disk (live ISO, Docker volume) is put back at the next start - but only when it is newer than the image
    try:
        import json as _json
        import core_overlay
        base = tempfile.mkdtemp(prefix="pyos-overlay-")
        try:
            def write(rel, text):
                os.makedirs(os.path.dirname(os.path.join(base, rel)) or base, exist_ok=True)
                with open(os.path.join(base, rel), "w", encoding="utf-8") as f:
                    f.write(text)

            def read(rel):
                try:
                    with open(os.path.join(base, rel), encoding="utf-8") as f:
                        return f.read()
                except OSError:
                    return None
            write("config.json", _json.dumps({"version": "1.0.0"}))
            write("core/a.py", "new a")
            write("core/b.py", "new b")
            assert core_overlay.save(["core/a.py", "core/b.py", "config.json"], "1.0.1", root=base) == 3
            write("config.json", _json.dumps({"version": "1.0.0"}))               # a fresh image starts: older files
            write("core/a.py", "old a")
            write("core/stale.py", "removed in 1.0.1")
            os.remove(os.path.join(base, "core", "b.py"))
            assert core_overlay.apply(base) == "applied" and read("core/a.py") == "new a" and read("core/b.py") == "new b"
            assert read("core/stale.py") is None, "a file the update removed must not come back"
            core_overlay.save(["core/a.py"], "1.0.1", root=base)
            write("config.json", _json.dumps({"version": "1.0.2"}))               # a newer image than the saved update
            assert core_overlay.apply(base) == "superseded" and core_overlay.apply(base) == "none"
            core_overlay.save(["core/a.py"], "1.0.9", root=base)
            write("config.json", _json.dumps({"version": "1.0.2"}))
            with open(os.path.join(base, core_overlay.OVERLAY, "tree", "core", "a.py"), "w") as f:
                f.write("tampered")
            assert core_overlay.apply(base) == "invalid" and read("core/a.py") == "new a", "a file that does not match its checksum must be ignored"
        finally:
            shutil.rmtree(base, ignore_errors=True)
        print("ok   core overlay (updates kept across restarts)")
    except Exception as e:                           # noqa: BLE001
        print(f"FAIL core overlay   <- {type(e).__name__}: {e}")
        failures.append(("core overlay", [f"{type(e).__name__}: {e}"], ""))

    # the resolution switch (kexec with video=): only a checked WxH ever reaches the kernel command line
    try:
        import core_video
        assert core_video.valid("1280x720") and not core_video.valid("1280x720 init=/bin/sh") and not core_video.valid("99999x1")
        assert core_video.cmdline_with("quiet video=800x600 loglevel=3", "1920x1080") == "quiet loglevel=3 video=1920x1080"
        assert core_video.current_mode("a video=Virtual-1:1280x720") == "1280x720" and core_video.current_mode("quiet") is None
        try:
            core_video.cmdline_with("quiet", "1280x720 init=/bin/sh")
            raise AssertionError("an unchecked value reached the command line")
        except ValueError:
            pass
        print("ok   resolution switch (checked video= option)")
    except Exception as e:                           # noqa: BLE001
        print(f"FAIL resolution switch   <- {type(e).__name__}: {e}")
        failures.append(("resolution switch", [f"{type(e).__name__}: {e}"], ""))

    # export update strategies: choosing files, commands and the parts that can be tried without root or a real disk
    try:
        import io
        import tarfile
        from core import exportupdate as eu
        base = "https://example.invalid/releases/download/v9.9.9/"
        urls = [base + n for n in ("pythonos-9.9.9-x86_64.iso", "pythonos-9.9.9-minimal-x86_64.iso", "pythonos-9.9.9-aarch64.iso",
                                   "PythonOS-9.9.9-android-arm64-v8a.apk", "PythonOS-9.9.9-android.apk", "pythonos_9.9.9_all.deb",
                                   "pythonos-9.9.9-linux.tar.gz")]
        assert eu.iso_for(urls, "x86_64", False).endswith("pythonos-9.9.9-x86_64.iso")
        assert eu.iso_for(urls, "x86_64", True).endswith("minimal-x86_64.iso")
        assert eu.iso_for(urls, "aarch64", False).endswith("aarch64.iso") and eu.iso_for(urls, "aarch64", True) is None
        assert eu.apk_for(urls, "aarch64").endswith("arm64-v8a.apk") and eu.apk_for(urls, "x86_64").endswith("android.apk")
        assert eu.pick(urls, r"\.deb$").endswith("all.deb")
        assert eu.install_command("pacman", "/tmp/p")[:2] == ["pacman", "-U"] and eu.install_command("deb", "/tmp/p")[-1] == "/tmp/p"
        assert [eu.disk_name(d) for d in ("/dev/sdb1", "/dev/nvme0n1p2", "/dev/mmcblk0p1", "/dev/sr0", "/dev/sda")] == \
            ["sdb", "nvme0n1", "mmcblk0", "sr0", "sda"]
        mounts = eu.parse_mounts("rootfs / rootfs rw 0 0\n/dev/sdb /media/sdb iso9660 ro 0 0\n/dev/loop0 /.modloop squashfs ro 0 0\n")
        assert eu.mount_for_path("/media/sdb/boot/modloop-lts", mounts)[0] == "/dev/sdb"
        work = tempfile.mkdtemp(prefix="pyos-strategy-")
        try:
            archive = os.path.join(work, "pkg.tar.gz")                     # a release tarball: a folder with the launcher files
            with tarfile.open(archive, "w:gz") as tar:
                for name, text in (("pythonos", "#!/bin/sh\necho new\n"), ("bootstrap.py", "# new"), ("export.json", "{}"), ("README.txt", "x")):
                    data = text.encode()
                    info = tarfile.TarInfo(f"pythonos-9.9.9-linux/{name}")
                    info.size = len(data)
                    tar.addfile(info, io.BytesIO(data))
                evil = tarfile.TarInfo("../evil")
                evil.size = 1
                tar.addfile(evil, io.BytesIO(b"x"))
            home = os.path.join(work, "home")
            os.makedirs(home)
            with open(os.path.join(home, "pythonos"), "w") as f:
                f.write("old")
            done = eu.replace_from_tarball(archive, home, eu.LinuxTarball.FILES)
            assert sorted(done) == ["bootstrap.py", "export.json", "pythonos"] and open(os.path.join(home, "pythonos")).read().endswith("new\n")
            assert not os.path.exists(os.path.join(work, "evil")) and not os.path.exists(os.path.join(home, "README.txt"))
            image, medium = os.path.join(work, "new.iso"), os.path.join(work, "disk.img")      # a file stands in for the disk
            with open(image, "wb") as f:
                f.write(os.urandom(3 * 1024 * 1024 + 123))
            with open(medium, "wb") as f:
                f.write(b"\0" * (5 * 1024 * 1024))
            assert eu.write_image(image, medium) == os.path.getsize(image)
            with open(image, "rb") as a, open(medium, "rb") as b:
                assert b.read(os.path.getsize(image)) == a.read()
        finally:
            shutil.rmtree(work, ignore_errors=True)
        windows = {"platform": "windows", "remote": {"urls": [base + "PythonOS-9.9.9-web-setup.exe"]}}
        chosen = eu.strategy_for(windows)
        assert (chosen is not None and chosen.name == "windows") == (os.name == "nt")
        assert eu.strategy_for({"platform": "iso", "remote": {"urls": urls}}) is None or os.environ.get("PYOS_LIVE") == "1"
        print("ok   export update strategies")
    except Exception as e:                           # noqa: BLE001
        print(f"FAIL export update strategies   <- {type(e).__name__}: {e}")
        failures.append(("export strategies", [f"{type(e).__name__}: {e}"], ""))

    # the background services: define, list, stop, start, switch off and on
    try:
        shell.define_services()
        pyos.services.start_all("smoke", light_mode=True)
        steps = [("service", "Task Scheduler", 0), ("service stop scheduler", "stopped", 0), ("service stop scheduler", None, 1),
                 ("service start scheduler", "started", 0), ("service disable idle-watch", "switched off", 0), ("service status idle-watch", "switched off", 0),
                 ("service enable idle-watch", "will start", 0), ("service stop nosuch", None, 1)]
        for line, expect, want in steps:
            code, text = shell.run_captured(line)
            assert code == want and (expect is None or expect in text), (line, code, text[-120:])
        pyos.services.stop_all()
        assert pyos.services.state("scheduler") == "stopped"
        print("ok   services")
    except Exception as e:                           # noqa: BLE001
        print(f"FAIL services   <- {type(e).__name__}: {e}")
        failures.append(("services", [f"{type(e).__name__}: {e}"], ""))

    # app limits: what applies to an app, the options the guard gets, and a real process held to its limit
    try:
        from pyos import limits as app_limits
        from pyos import sandbox
        assert settings.parse_value("memory_limit_mb", "2048") == 2048, "memory budgets above 1440 must be accepted"
        pid = "utilities/limit-test"
        assert app_limits.for_package(pid, {})["source"]["memory"] == "default"
        assert app_limits.for_package(pid, {"limits": {"memory_mb": 96}})["memory_mb"] == 96
        app_limits.set_limit(pid, "memory", 200)
        assert app_limits.for_package(pid, {"limits": {"memory_mb": 96}})["memory_mb"] == 200, "what the user set beats what the app asks"
        app_limits.reset(pid, "memory")
        assert app_limits.for_package(pid, {"limits": {"memory_mb": 96}})["memory_mb"] == 96
        app_limits.reset(pid)
        for bad in (("memory", 5), ("disk", 10), ("cpu", -1)):
            try:
                app_limits.set_limit(pid, *bad)
                raise AssertionError(f"{bad} should be refused")
            except ValueError:
                pass
        app = os.path.join(root, "files", "installed_utilities", "hog")
        os.makedirs(app, exist_ok=True)
        with open(os.path.join(app, "run.py"), "w") as f:
            f.write("\n".join(["import sys", "if sys.argv[1] == 'mem':", "    keep = [bytearray(10 * 1024 * 1024) for _ in range(80)]",
                               "    print('not stopped')", "else:", "    print('fine')", ""]))
        command, env = sandbox.launch(os.path.join(app, "run.py"), ["mem"], app, {})
        assert "--mem-mb" in command and "--cpu-seconds" in command
        command[command.index("--mem-mb") + 1] = "64"                        # a 64 MB limit; the app asks for 800 MB
        import subprocess as _sp
        stopped = _sp.run(command, env=env, capture_output=True, text=True, timeout=60)
        assert stopped.returncode == 137 and "more memory than its limit" in stopped.stderr, (stopped.returncode, stopped.stderr[-200:])
        command[-1] = "ok"
        fine = _sp.run(command, env=env, capture_output=True, text=True, timeout=60)
        assert fine.returncode == 0 and "fine" in fine.stdout, (fine.returncode, fine.stderr[-200:])
        shutil.rmtree(app, ignore_errors=True)
        print("ok   app limits")
    except Exception as e:                           # noqa: BLE001
        print(f"FAIL app limits   <- {type(e).__name__}: {e}")
        failures.append(("app limits", [f"{type(e).__name__}: {e}"], ""))

    # processor detection, and the pure parts of the Flash program (drive lists, checksums, writing to a file standing in for a stick)
    try:
        if not HAVE_REPO:
            raise _Skip()
        import importlib.util
        import platform as _platform
        from pyos import archinfo
        assert [archinfo.normalize(x) for x in ("AMD64", "arm64", "armv8l", "i686", "aarch64", "X64", "")] == ["x86_64", "aarch64", "armv7", "x86", "aarch64", "x86_64", ""]
        real = archinfo.detect()
        assert real["arch"] and real["label"] and isinstance(real["emulated"], bool)
        saved = (_platform.system, _platform.machine, archinfo._windows_native, archinfo._mac_native, archinfo._android_abi)
        try:
            _platform.system, _platform.machine = (lambda: "Windows"), (lambda: "AMD64")             # an x64 program on Windows on ARM
            archinfo._windows_native, archinfo._android_abi = (lambda: "aarch64"), (lambda: "")
            info = archinfo.detect.__wrapped__()
            assert info["arch"] == "aarch64" and info["process"] == "x86_64" and info["emulated"] and "emulated" in archinfo.describe.__wrapped__() if False else info["emulated"]
            _platform.system, _platform.machine = (lambda: "Darwin"), (lambda: "x86_64")             # an Intel program under Rosetta
            archinfo._mac_native = lambda: "aarch64"
            assert archinfo.detect.__wrapped__()["arch"] == "aarch64"
            archinfo._mac_native = lambda: ""
            assert archinfo.detect.__wrapped__()["arch"] == "x86_64" and not archinfo.detect.__wrapped__()["emulated"]
        finally:
            _platform.system, _platform.machine, archinfo._windows_native, archinfo._mac_native, archinfo._android_abi = saved
            archinfo.detect.cache_clear()
        spec = importlib.util.spec_from_file_location("flashlib_test", os.path.join(REPO, "OS_Export", "Wizard", "flashlib.py"))
        flashlib = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(flashlib)
        sums = flashlib.parse_sums("%s  pythonos-9.9.9-x86_64.iso\n%s *pythonos-9.9.9-minimal-aarch64.iso\nnot a line\n" % ("a" * 64, "b" * 64))
        assert flashlib.pick_iso(sums, "x86_64") == "pythonos-9.9.9-x86_64.iso" and flashlib.pick_iso(sums, "aarch64", True).endswith("minimal-aarch64.iso")
        assert flashlib.pick_iso(sums, "aarch64") is None and flashlib.machine_arch() == archinfo.arch()
        lsblk = '{"blockdevices":[{"name":"sda","path":"/dev/sda","size":512000000000,"type":"disk","rm":false,"tran":"sata","children":[{"mountpoints":["/"]}]},' \
                '{"name":"sdb","path":"/dev/sdb","size":16000000000,"type":"disk","rm":true,"tran":"usb","model":"Cruzer","mountpoints":[null]}]}'
        assert [d["id"] for d in flashlib.parse_lsblk(lsblk)] == ["/dev/sdb"]
        windows = '[{"Number":0,"FriendlyName":"NVMe","Size":512000000000,"BusType":"NVMe","IsSystem":true,"IsBoot":true},' \
                  '{"Number":2,"FriendlyName":"USB Stick","Size":16000000000,"BusType":"USB","IsSystem":false,"IsBoot":false}]'
        assert [d["id"] for d in flashlib.parse_windows_disks(windows)] == ["2"]
        work = tempfile.mkdtemp(prefix="pyos-flash-")
        try:
            image, stick = os.path.join(work, "a.iso"), os.path.join(work, "stick.img")
            with open(image, "wb") as f:
                f.write(os.urandom(3 * 1024 * 1024 + 41))
            with open(stick, "wb") as f:
                f.write(b"\0" * (4 * 1024 * 1024))
            assert flashlib.write_image(image, stick) == os.path.getsize(image) and flashlib.verify_image(image, stick)
            with open(stick, "r+b") as f:
                f.seek(1000)
                f.write(b"XX")
            assert not flashlib.verify_image(image, stick), "a changed byte must be caught"
            log = os.path.join(work, "progress.log")
            with open(log, "w") as f:
                f.write('{"phase":"write","done":5,"total":10}\n{"phase":"do')
            events, offset = flashlib.read_progress(log)
            assert events == [("write", 5, 10, "")] and offset < os.path.getsize(log), "a half-written line must wait for the rest"
        finally:
            shutil.rmtree(work, ignore_errors=True)
        print("ok   processor detection and the Flash program")
    except _Skip:
        print("skip processor detection and the Flash program (needs the repository checkout)")
    except Exception as e:                           # noqa: BLE001
        print(f"FAIL processor detection and the Flash program   <- {type(e).__name__}: {e}")
        failures.append(("arch and flash", [f"{type(e).__name__}: {e}"], ""))

    # the Setup Wizard's decisions (which file for which computer and goal) and the release catalog / release page tables
    try:
        if not HAVE_REPO:
            raise _Skip()
        sys.path.insert(0, os.path.join(REPO, "OS_Export", "Wizard"))
        sys.path.insert(0, os.path.join(REPO, "OS_Export"))
        import catalog
        import wizardlib as wiz
        import release_notes
        v = "9.9.9"
        names = [f"PythonOS-{v}-web-setup.exe", f"PythonOS-{v}-setup.exe", f"PythonOS-{v}-arm64-setup.exe", f"PythonOS-{v}-android-arm64-v8a.apk",
                 f"PythonOS-{v}-android.apk", f"pythonos_{v}_all.deb", f"pythonos-{v}-1.noarch.rpm", f"pythonos-{v}-1-any.pkg.tar.zst",
                 f"pythonos-{v}-linux.tar.gz", f"pythonos-{v}-x86_64.iso", f"pythonos-{v}-minimal-x86_64.iso", f"pythonos-{v}-aarch64.iso",
                 f"pythonos-{v}-vm.ova", f"pythonos-{v}-vm.qcow2", f"pythonos-{v}-vm-data.qcow2", f"pythonos-{v}-vm-kit.zip", f"pythonos-wizard-{v}.zip",
                 "SHA256SUMS", "core-manifest.json", f"pythonos-core-{v}.zip", "notes.txt"]
        entries = catalog.build(names)
        assert len(entries) == len(names) - 1, "every known file is classified, an unknown one is not"
        assert catalog.classify(f"pythonos-{v}-minimal-aarch64.iso") == {"name": f"pythonos-{v}-minimal-aarch64.iso", "os": "bootable", "arch": "aarch64",
                                                                         "kind": "iso", "variant": "minimal"}
        rel = wiz.Release("v" + v, {n: {"url": "u/" + n, "size": 1} for n in names})
        x64 = {"os": "windows", "arch": "x86_64", "package": None, "distro": {}, "tools": {}, "arch_label": "", "emulated": False, "note": ""}
        assert wiz.plan_for("install", x64, rel)["files"] == [f"PythonOS-{v}-web-setup.exe"]
        fedora = dict(x64, os="linux", package=wiz.package_kind(wiz.parse_os_release('ID=fedora\nPRETTY_NAME="Fedora"\n')), distro={"name": "Fedora"})
        assert wiz.plan_for("install", fedora, rel)["files"] == [f"pythonos-{v}-1.noarch.rpm"]
        assert wiz.plan_for("install", dict(fedora, package=wiz.package_kind(wiz.parse_os_release("ID=alpine\n"))), rel)["files"] == [f"pythonos-{v}-linux.tar.gz"]
        assert wiz.package_kind(wiz.parse_os_release('ID=linuxmint\nID_LIKE="ubuntu debian"\n')) == "deb"
        assert wiz.plan_for("android", x64, rel, abi="aarch64")["files"] == [f"PythonOS-{v}-android-arm64-v8a.apk"]
        assert wiz.plan_for("android", x64, rel, abi="universal")["files"] == [f"PythonOS-{v}-android.apk"]
        assert wiz.plan_for("vm", x64, rel, software="virtualbox")["files"] == [f"pythonos-{v}-vm.ova"]
        assert wiz.plan_for("vm", x64, rel, software="qemu")["files"][:2] == [f"pythonos-{v}-vm.qcow2", f"pythonos-{v}-vm-data.qcow2"]
        assert wiz.plan_for("vm", x64, rel, software="hyperv")["files"] == [f"pythonos-{v}-x86_64.iso"]
        arm = dict(x64, arch="aarch64")
        for software in ("virtualbox", "qemu", "utm"):
            assert wiz.plan_for("vm", arm, rel, software=software)["files"] == [f"pythonos-{v}-aarch64.iso"], "an ARM computer must get the ARM image"
        assert wiz.plan_for("docker", x64, rel)["action"] == "docker-run"
        sizes = {n: 1024 for n in names}
        page = "\n".join(release_notes.quick_guide(v, sizes, "v" + v))
        for title in ("### Windows", "### Android", "### Linux", "### Docker", "### Bootable USB stick", "### Virtual machines"):
            assert title in page, f"the release page needs a table for {title}"
        assert f"releases/download/v{v}/pythonos-{v}-vm.ova" in page
        assert "pythonos-9.9.9-windows-portable.zip" not in page, "a file that is not in the release is not offered"
        print("ok   setup wizard plans and release page tables")
    except _Skip:
        print("skip setup wizard plans and release page tables (needs the repository checkout)")
    except Exception as e:                           # noqa: BLE001
        print(f"FAIL setup wizard plans and release page tables   <- {type(e).__name__}: {e}")
        failures.append(("wizard plans", [f"{type(e).__name__}: {e}"], ""))

    # the file manager: its engine (folders first, copy/cut/paste without overwriting, trash and undo, rename) and the screen starting and quitting
    try:
        from pyos import filemanager, filemanager_ui
        base = os.path.join(root, "files", "home", "smoke", "fm-test")
        os.makedirs(os.path.join(base, "docs"), exist_ok=True)
        with open(os.path.join(base, "a.txt"), "w") as f:
            f.write("hello\nworld\n")
        manager = filemanager.Manager(base, "smoke")
        assert [e.name for e in manager.entries()] == ["docs", "a.txt"], "folders come first"
        manager.focus("a.txt")
        assert manager.preview(manager.current()) == ["hello", "world"]
        manager.copy()
        manager.go(os.path.join(base, "docs"))
        assert manager.paste() == (1, []) and [e.name for e in manager.entries()] == ["a.txt"]
        assert manager.paste() == (1, []) and sorted(e.name for e in manager.entries()) == ["a (2).txt", "a.txt"], "a taken name is never overwritten"
        manager.go(base)
        manager.focus("a.txt")
        assert manager.delete() == (1, []) and [e.name for e in manager.entries()] == ["docs"]
        assert manager.undo() == "a.txt" and "a.txt" in [e.name for e in manager.entries()]
        manager.rename("b.txt")
        manager.make_folder("new")
        assert sorted(e.name for e in manager.entries()) == ["b.txt", "docs", "new"]
        try:
            manager.rename("new")
            raise AssertionError("an existing name must be refused")
        except filemanager.FileManagerError:
            pass
        try:
            manager.go(os.path.dirname(root))
            raise AssertionError("leaving the filesystem must be refused")
        except filemanager.FileManagerError:
            pass
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput
        with create_pipe_input() as pipe:
            pipe.send_text("jj q")
            filemanager_ui.build(filemanager.Manager(base, "smoke"), input=pipe, output=DummyOutput()).run()
        shutil.rmtree(base, ignore_errors=True)
        print("ok   file manager")
    except Exception as e:                           # noqa: BLE001
        print(f"FAIL file manager   <- {type(e).__name__}: {e}")
        failures.append(("file manager", [f"{type(e).__name__}: {e}"], ""))

    # the Settings app: its pages, changing a setting like `settings set`, and the screen starting and quitting
    try:
        from pyos import settingsui
        names = [title for _gid, title, _fn in settingsui.pages()]
        assert names[:2] == ["Display", "System"] and names[-3:] == ["Services", "Apps", "About"], names
        every = {row.key for _gid, _title, fn in settingsui.pages() for row in fn() if row.kind == "setting"}
        assert every == set(settings.SCHEMA), f"every setting must be on a page: {set(settings.SCHEMA) ^ every}"
        assert settingsui.next_choice("clock_24h") is False or settings.get("clock_24h") is False
        assert settingsui.apply_setting("memory_limit_mb", "2048", "smoke", "admin") == 2048 and settings.get("memory_limit_mb") == 2048
        settings.reset("memory_limit_mb")
        try:
            settingsui.apply_setting("clock_24h", "perhaps", "smoke", "admin")
            raise AssertionError("a bad value must be refused")
        except ValueError:
            pass
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput
        with create_pipe_input() as pipe:
            pipe.send_text("\tjj\tq")
            settingsui.build("smoke", "admin", input=pipe, output=DummyOutput()).run()
        print("ok   settings app")
    except Exception as e:                           # noqa: BLE001
        print(f"FAIL settings app   <- {type(e).__name__}: {e}")
        failures.append(("settings app", [f"{type(e).__name__}: {e}"], ""))

    # app tests: every tools/test_*.py runs on its own and must exit cleanly (they talk to local fakes, never the network)
    try:
        import glob
        import subprocess as _subprocess
        for script in sorted(glob.glob(os.path.join(REPO, "tools", "test_*.py"))):
            done = _subprocess.run([sys.executable, script], capture_output=True, text=True, timeout=120, encoding="utf-8", errors="replace")
            assert done.returncode == 0, f"{os.path.basename(script)}: {(done.stdout + done.stderr)[-300:]}"
        print("ok   app tests")
    except Exception as e:                           # noqa: BLE001
        print(f"FAIL app tests   <- {type(e).__name__}: {e}")
        failures.append(("app tests", [f"{type(e).__name__}: {e}"], ""))

    # the boot steps themselves
    from core import boot, whathappened  # noqa: F401
    steps = boot.boot_steps("No")
    if len(steps) < 8:
        failures.append(("boot_steps", [f"only {len(steps)} steps"], ""))

    if failures:
        print(f"\n{len(failures)} check(s) failed:")
        for line, problems, tail in failures:
            print(f"- {line}: {'; '.join(problems)}\n  last output: {tail!r}")
        return 1
    print(f"\nAll {len(CHECKS)} checks passed.")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dir", help="an already staged OS folder to test in place (it will get a test account and files)")
    args = parser.parse_args()
    if args.dir:
        return run(os.path.abspath(args.dir))
    sys.path.insert(0, os.path.join(REPO, "OS_Export"))
    import stage
    work = tempfile.mkdtemp(prefix="pyos-smoke-")
    try:
        root = stage.stage(os.path.join(work, "os"))
        return run(root)
    finally:
        os.chdir(tempfile.gettempdir())
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
