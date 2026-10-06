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
