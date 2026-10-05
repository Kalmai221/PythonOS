"""start.py - what the PythonOS window runs (the same job as launcher.py, without a console launcher around it).

Downloads the OS on the first start, refreshes it when the installer is newer than the files on disk, then runs main.py.
Lives next to PythonOS.exe in the install folder; run by the bundled Python.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(HERE, "python", "python.exe")


def numbers(text):
    return tuple(int(p) for p in re.findall(r"\d+", str(text).split("-")[0])[:4])


def core_is_older():
    """True when the installer is newer than the OS files on disk (re-installing over an old version keeps the old files)."""
    try:
        with open(os.path.join(HERE, "export.json"), encoding="utf-8") as f:
            packaged = json.load(f)["version"]
        with open(os.path.join(HERE, "VERSION"), encoding="utf-8") as f:
            installed = f.read().strip()
        return numbers(installed) < numbers(packaged)
    except (OSError, ValueError, KeyError):
        return False


def main():
    os.chdir(HERE)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYOS_EXPORT_INFO=os.path.join(HERE, "export.json"))
    missing = not os.path.isfile(os.path.join(HERE, "main.py"))
    if missing or core_is_older():
        print("Downloading PythonOS (first start only)..." if missing else "Updating PythonOS to the version you just installed...")
        if subprocess.call([PYTHON, "bootstrap.py", "--dest", HERE], env=env) != 0:
            print("\nCould not download PythonOS. Check your internet connection and start it again.")
            return 1
    try:
        return subprocess.call([PYTHON, "main.py", *sys.argv[1:]], env=env)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
