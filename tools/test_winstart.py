#!/usr/bin/env python3
"""Windows start.py: the plain console fallback (python.exe start.py --pause) keeps its window open when PythonOS stops with an error, and never
passes --pause on to PythonOS. main() is replaced by a fake, so nothing starts."""
import importlib.util
import os
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def main():
    spec = importlib.util.spec_from_file_location("win_start", os.path.join(REPO_ROOT, "OS_Export", "Windows", "start.py"))
    start = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(start)
    asked = []
    seen = []

    def fake_main(code):
        def run():
            seen.append(list(sys.argv))
            return code
        return run

    real_argv = sys.argv
    try:
        # the fallback with an error: the window waits, and PythonOS never sees --pause
        start.main = fake_main(1)
        sys.argv = ["start.py", "--pause", "--other"]
        assert start.entry(sys.argv, asked.append) == 1 and len(asked) == 1 and "exit code 1" in asked[0]
        assert seen[-1] == ["start.py", "--other"], seen
        # the fallback with a clean exit: nothing to read, the window closes
        asked.clear()
        start.main = fake_main(0)
        sys.argv = ["start.py", "--pause"]
        assert start.entry(sys.argv, asked.append) == 0 and asked == []
        # the PythonOS window (no --pause): never waits
        start.main = fake_main(1)
        sys.argv = ["start.py"]
        assert start.entry(sys.argv, asked.append) == 1 and asked == []
    finally:
        sys.argv = real_argv
    # the host starts the fallback through python.exe, and no console program is built or shipped any more
    with open(os.path.join(REPO_ROOT, "OS_Export", "Windows", "native", "host", "Host.cs"), encoding="utf-8") as f:
        host = f.read()
    assert "PythonOS-console" not in host and "--pause" in host and "Fallback.Available(dir)" in host
    with open(os.path.join(REPO_ROOT, "OS_Export", "Windows", "build.ps1"), encoding="utf-8") as f:
        build = f.read()
    assert "python -m PyInstaller" not in build and "launcher.py" not in build
    assert not os.path.exists(os.path.join(REPO_ROOT, "OS_Export", "Windows", "launcher.py"))
    print("windows start: all checks passed")


if __name__ == "__main__":
    main()
