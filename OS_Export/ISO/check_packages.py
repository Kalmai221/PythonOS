#!/usr/bin/env python3
"""Fail early if a package name in the ISO profile does not exist in Alpine's repositories.

    python OS_Export/ISO/check_packages.py [alpine version, default 3.19]

A misspelt or removed package name only shows up deep inside mkimage, after minutes of work ("fbset: unable to select package").
This reads the package names from mkimg.pythonos.sh and genapkovl-pythonos.sh and compares them with the repository indexes (main and
community) over the network.
"""
import io
import os
import re
import sys
import tarfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
MIRROR = "https://dl-cdn.alpinelinux.org/alpine"


X86_ONLY = {"syslinux", "grub-bios", "open-vm-tools", "open-vm-tools-openrc", "virtualbox-guest-additions", "virtualbox-guest-additions-openrc"}


def repository_names(version, repos=("main", "community"), arch="x86_64"):
    names = set()
    for repo in repos:
        url = f"{MIRROR}/v{version}/{repo}/{arch}/APKINDEX.tar.gz"
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "PythonOS-ci"}), timeout=60) as response:
            data = response.read()
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
            index = tar.extractfile("APKINDEX").read().decode("utf-8", "replace")
        names.update(line[2:] for line in index.splitlines() if line.startswith("P:"))
    return names


def wanted_from_profile(text):
    """Names added with apks="$apks ..." lines in mkimg.pythonos.sh."""
    names = set()
    for match in re.finditer(r'apks="\$apks ([^"]+)"', text):
        names.update(match.group(1).split())
    return names


def wanted_from_overlay(text):
    """Names in the heredocs that make up the world file in genapkovl-pythonos.sh (lines of a single package name)."""
    names = set()
    inside = False
    for line in text.splitlines():
        if "etc/apk/world" in line and ("<<" in line):
            inside = True
            continue
        if inside:
            if line.strip() == "EOF":
                inside = False
            elif re.fullmatch(r"[a-z0-9][a-z0-9._+-]*", line.strip()):
                names.add(line.strip())
    return names


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ALPINE_VERSION", "3.19")
    with open(os.path.join(HERE, "mkimg.pythonos.sh"), encoding="utf-8") as f:
        wanted = wanted_from_profile(f.read())
    with open(os.path.join(HERE, "genapkovl-pythonos.sh"), encoding="utf-8") as f:
        wanted |= wanted_from_overlay(f.read())
    failed = False
    for arch in ("x86_64", "aarch64"):
        names = wanted if arch == "x86_64" else wanted - X86_ONLY       # the ARM image leaves the PC-only packages out
        available = repository_names(version, arch=arch)
        missing = sorted(n for n in names if n not in available)
        print(f"{len(names)} package names checked against Alpine {version} {arch}.")
        if missing:
            print("Not in the repositories: " + ", ".join(missing))
            failed = True
    if failed:
        return 1
    print("All package names exist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
