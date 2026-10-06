#!/usr/bin/env python3
"""Put the Setup Wizard programs built on each system (build.py) and their launchers into one zip.

    python OS_Export/Wizard/pack.py --bin dist/wizard-bin --version 1.2.0 --out dist/wizard

Writes pythonos-wizard-<version>.zip: README.txt, wizard.bat, wizard.sh, wizard.command and every program that was built. The scripts and the
Linux/macOS programs are stored as executable. A program that is not there (a system that could not be built) is left out; the zip still
needs at least the Windows program or one Linux or macOS one.
"""
import argparse
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PROGRAMS = ("PythonOS-Wizard.exe", "pythonos-wizard-linux-x86_64", "pythonos-wizard-linux-aarch64", "pythonos-wizard-macos-arm64",
            "pythonos-wizard-macos-x86_64")
LAUNCHERS = ("wizard.bat", "wizard.sh", "wizard.command")


def add(archive, path, name, mode):
    info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3                                   # Unix: lets the file keep its executable bit
    info.external_attr = (0o100000 | mode) << 16
    with open(path, "rb") as f:
        data = f.read()
    if name.endswith((".sh", ".command", ".bat", ".txt")):
        data = data.replace(b"\r\n", b"\n") if not name.endswith(".bat") else data.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
    archive.writestr(info, data)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--bin", required=True, help="the folder with the programs build.py made (from every system)")
    parser.add_argument("--version", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    os.makedirs(args.out, exist_ok=True)
    present = [p for p in PROGRAMS if os.path.isfile(os.path.join(args.bin, p))]
    if not present:
        sys.exit(f"no Setup Wizard program found in {args.bin}")
    folder = f"pythonos-wizard-{args.version}"
    target = os.path.join(args.out, f"{folder}.zip")
    with zipfile.ZipFile(target, "w") as z:
        readme = os.path.join(HERE, "launchers", "README.txt")
        with open(readme, encoding="utf-8") as f:
            text = f.read().replace("{version}", args.version)
        info = zipfile.ZipInfo(f"{folder}/README.txt", date_time=(2026, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = (0o100000 | 0o644) << 16
        z.writestr(info, text.replace("\r\n", "\n").replace("\n", "\r\n"))
        for name in LAUNCHERS:
            add(z, os.path.join(HERE, "launchers", name), f"{folder}/{name}", 0o755)
        for name in present:
            add(z, os.path.join(args.bin, name), f"{folder}/{name}", 0o755)
    print(f"Wrote {target} with {', '.join(present)}")


if __name__ == "__main__":
    main()
