"""PythonOS.exe - a tiny launcher, frozen with PyInstaller (see build.ps1).

PythonOS loads commands and marketplace packages from disk and installs packages with
pip, so the OS itself runs on the bundled Python in the "python" folder. This launcher
starts it from the right folder, which gives users a normal double-clickable .exe.

The package does not contain the OS: on first start this runs bootstrap.py, which downloads
the latest core from GitHub releases. After that PythonOS updates its own files.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
PYTHON = os.path.join(HERE, "python", "python.exe")


def _numbers(text):
    return tuple(int(p) for p in re.findall(r"\d+", str(text).split("-")[0])[:4])


def core_is_older():
    """True when the installer is newer than the OS files on disk (re-installing over an old version keeps the old files)."""
    try:
        with open(os.path.join(HERE, "export.json"), encoding="utf-8") as f:
            packaged = json.load(f)["version"]
        with open(os.path.join(HERE, "VERSION"), encoding="utf-8") as f:
            installed = f.read().strip()
        return _numbers(installed) < _numbers(packaged)
    except (OSError, ValueError, KeyError):
        return False


def main():
    if not os.path.isfile(PYTHON):
        print(f"PythonOS cannot start: {PYTHON} is missing.")
        print("Re-install PythonOS, or keep PythonOS.exe in the same folder as its 'python' folder.")
        input("Press Enter to close...")
        return 1
    os.chdir(HERE)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8",
               PYOS_EXPORT_INFO=os.path.join(HERE, "export.json"), COLORTERM="truecolor")
    env.pop("NO_COLOR", None)         # PythonOS shows colour (the mono theme is a PythonOS setting)
    sys.path.insert(0, HERE)
    try:
        import bootstrap
        missing = bool(bootstrap.missing(HERE))
    except ImportError:
        missing = not os.path.isfile(os.path.join(HERE, "main.py"))
    if missing or core_is_older():
        print("Downloading PythonOS (first start only)..." if missing else "Updating PythonOS to the version you just installed...")
        if subprocess.call([PYTHON, "bootstrap.py", "--dest", HERE], env=env) != 0:
            print("\nCould not download PythonOS. Check your internet connection and start it again.")
            input("Press Enter to close...")
            return 1
    try:
        code = subprocess.call([PYTHON, "main.py", *sys.argv[1:]], env=env)
    except KeyboardInterrupt:
        code = 0
    if code != 0:
        print(f"\nPythonOS stopped with exit code {code}.")
        input("Press Enter to close...")
    return code


if __name__ == "__main__":
    sys.exit(main())
