"""PythonOS.exe - a tiny launcher, frozen with PyInstaller (see build.ps1).

PythonOS loads commands and marketplace packages from disk and installs packages with
pip, so the OS itself runs on the bundled Python in the "python" folder. This launcher
just starts it from the right folder, which gives users a normal double-clickable .exe.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))
PYTHON = os.path.join(HERE, "python", "python.exe")


def main():
    if not os.path.isfile(PYTHON):
        print(f"PythonOS cannot start: {PYTHON} is missing.")
        print("Re-install PythonOS, or keep PythonOS.exe in the same folder as its 'python' folder.")
        input("Press Enter to close...")
        return 1
    os.chdir(HERE)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
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
