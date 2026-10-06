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
    settings.set("boot_speed", "instant")
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
