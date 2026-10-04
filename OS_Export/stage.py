#!/usr/bin/env python3
"""Copy the PythonOS runtime into a folder so a platform build can package it.

Every platform build (Linux, Windows, Android, ISO) starts from this, so the list of
files that make up the OS lives in exactly one place.

    python OS_Export/stage.py <dest> [--vendor pkg ...]
    python OS_Export/stage.py --print-version

--vendor pip-installs the named (pure Python) packages into <dest>/site-packages,
for builds that cannot run pip at runtime. main.py adds that folder to sys.path.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))

PAYLOAD_FILES = [
    "main.py", "shell.py", "users.py", "config.json",
    "requirements.txt", "boot-requirements.txt", "readme.md",
]
PAYLOAD_DIRS = ["commands", "core", "programs", "pyos"]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def version():
    """VERSION env var (a tag like v1.2.0 is fine) or the version in config.json."""
    env = os.environ.get("VERSION", "").strip()
    if env and env != "dev":
        return env.lstrip("v")
    try:
        with open(os.path.join(REPO, "config.json"), encoding="utf-8") as f:
            base = str(json.load(f).get("version", "1.0"))
    except (OSError, ValueError):
        base = "1.0"
    return base if not env else f"{base}-dev"


def stage(dest, vendor=()):
    dest = os.path.abspath(dest)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    os.makedirs(dest)
    for name in PAYLOAD_FILES:
        src = os.path.join(REPO, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(dest, name))
    for name in PAYLOAD_DIRS:
        shutil.copytree(os.path.join(REPO, name), os.path.join(dest, name), ignore=IGNORE)
    with open(os.path.join(dest, "VERSION"), "w", encoding="utf-8", newline="\n") as f:
        f.write(version() + "\n")
    if vendor:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", "--no-compile",
                               "--target", os.path.join(dest, "site-packages"), *vendor])
    return dest


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dest", nargs="?", help="folder to create (replaced if it exists)")
    parser.add_argument("--vendor", nargs="*", default=[], metavar="PKG", help="pure-Python packages to bundle")
    parser.add_argument("--print-version", action="store_true", help="print the version and exit")
    args = parser.parse_args()
    if args.print_version:
        print(version())
        return
    if not args.dest:
        parser.error("dest is required")
    print(f"Staged PythonOS {version()} in {stage(args.dest, args.vendor)}")


if __name__ == "__main__":
    main()
