#!/usr/bin/env python3
"""Build the PythonOS Setup Wizard for the computer this runs on, as one file that needs no Python.

    python OS_Export/Wizard/build.py --out dist/wizard-bin

Produces PythonOS-Wizard.exe (Windows), pythonos-wizard-linux-<x86_64|aarch64> or pythonos-wizard-macos-<arm64|x86_64>. CI runs it once per system and pack.py puts the results in one zip. Needs: pip install pyinstaller
(and Tk, which comes with Python on Windows and macOS; on Linux: python3-tk).
"""
import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def target_name():
    system = platform.system()
    machine = platform.machine().lower()
    if system == "Windows":
        return "PythonOS-Wizard.exe"
    if system == "Linux":
        return "pythonos-wizard-linux-" + ("aarch64" if machine in ("aarch64", "arm64") else "x86_64")
    if system == "Darwin":
        return "pythonos-wizard-macos-" + ("arm64" if machine in ("arm64", "aarch64") else "x86_64")
    raise SystemExit(f"{system} is not supported")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.path.join(HERE, os.pardir, os.pardir, "dist", "wizard-bin"))
    args = parser.parse_args()
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)
    name = target_name()
    work = tempfile.mkdtemp(prefix="pyos-wizard-build-")
    command = [sys.executable, "-m", "PyInstaller", "--onefile", "--clean", "--noconfirm", "--name", os.path.splitext(name)[0] if name.endswith(".exe") else name,
               "--distpath", work, "--workpath", os.path.join(work, "build"), "--specpath", work, "--paths", HERE,
               "--paths", os.path.join(HERE, os.pardir, os.pardir, "pyos"), "--paths", os.path.join(HERE, os.pardir),
               "--hidden-import", "archinfo", "--hidden-import", "catalog", "--hidden-import", "flashlib", "--hidden-import", "wizardlib",
               "--hidden-import", "wizardgui", "--hidden-import", "wizardcli", "--hidden-import", "flashgui", "--hidden-import", "tkinter", "--hidden-import", "tkinter.ttk",
               "--hidden-import", "tkinter.filedialog", "--hidden-import", "tkinter.messagebox"]
    # No administrator manifest: the wizard installs for the signed-in user. Only the part that writes a drive is started elevated.
    command.append(os.path.join(HERE, "main.py"))
    try:
        subprocess.check_call(command)
        built = os.path.join(work, name)
        if not os.path.isfile(built):
            raise SystemExit(f"PyInstaller did not make {built}")
        shutil.copy2(built, os.path.join(out, name))
        print(f"Built {os.path.join(out, name)} ({os.path.getsize(built) // 1024 // 1024} MB)")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
