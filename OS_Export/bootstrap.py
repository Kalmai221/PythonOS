#!/usr/bin/env python3
"""Download the PythonOS core from the latest GitHub release and install it.

The Linux, Windows and Android packages do not contain the OS itself - just this script. On
first run they use it to fetch the current core (the same files the in-OS updater installs),
so a fresh install is always the latest release.

    python bootstrap.py --dest <folder> [--url <core-manifest.json URL>] [--force]

Uses only the standard library, so it runs before any dependency is installed.
Exit status: 0 = installed or already up to date, 1 = failed (nothing half-installed is left
behind that the next attempt cannot repair).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.request
import zipfile
from urllib.parse import urljoin

RELEASES_URL = "https://github.com/Kalmai221/PythonOS/releases"
CODE_DIRS = ("commands", "core", "programs", "pyos")
TIMEOUT = 30


def manifest_url(override=None):
    return override or os.environ.get("PYOS_UPDATE_URL") or f"{RELEASES_URL}/latest/download/core-manifest.json"


def version_key(text):
    numbers = [int(n) for n in re.findall(r"\d+", str(text).split("-")[0])]
    numbers += [0] * (4 - len(numbers))
    return tuple(numbers), 0 if "dev" in str(text).lower() else 1


def fetch(url, progress=None):
    request = urllib.request.Request(url, headers={"User-Agent": "PythonOS-bootstrap"})
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        total = int(response.headers.get("Content-Length") or 0)
        chunks, done = [], 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            chunks.append(chunk)
            done += len(chunk)
            if progress and total:
                progress(done, total)
        return b"".join(chunks)


# What a complete PythonOS folder holds. Every launcher checks this before starting and downloads again when something is missing.
REQUIRED_FILES = ["main.py", "shell.py", "users.py", "VERSION", "requirements.txt", "boot-requirements.txt"]
REQUIRED_DIRS = ["commands", "core", "programs", "pyos"]
# the libraries PythonOS imports at start-up (the same list as requirements.txt, by module name)
REQUIRED_MODULES = "rich psutil requests yaspin ping3 prompt_toolkit pygments"


def missing(dest):
    """Names of the files and folders a complete install has that are not in `dest` (empty list: nothing to download)."""
    gone = [n for n in REQUIRED_FILES if not os.path.isfile(os.path.join(dest, n))]
    gone += [n for n in REQUIRED_DIRS if not os.path.isdir(os.path.join(dest, n))]
    return gone


def safe_member(path):
    return bool(path) and not os.path.isabs(path) and ".." not in path.replace("\\", "/").split("/") and not path.startswith("/")


def sync_config_version(dest, version):
    """config.json is never overwritten (it holds the person's settings), but the version PythonOS shows comes from it: keep it in step."""
    path = os.path.join(dest, "config.json")
    try:
        with open(path, encoding="utf-8") as f:
            config = json.load(f)
        if isinstance(config, dict) and config.get("version") != version:
            config["version"] = version
            with open(path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4)
    except (OSError, ValueError):
        pass


def install(dest, url=None, force=False, log=print):
    """Install (or update) the core into `dest`. Returns True on success."""
    dest = os.path.abspath(dest)
    os.makedirs(dest, exist_ok=True)
    murl = manifest_url(url)

    try:
        manifest = json.loads(fetch(murl).decode("utf-8"))
        for key in ("version", "asset", "sha256", "files"):
            if key not in manifest:
                raise ValueError(f"the release manifest is missing '{key}'")
    except Exception as e:
        log(f"Could not read the latest PythonOS release ({e}).")
        return False

    latest = str(manifest["version"])
    version_file = os.path.join(dest, "VERSION")
    if not force and os.path.isfile(os.path.join(dest, "main.py")) and os.path.isfile(version_file):
        with open(version_file, encoding="utf-8") as f:
            installed = f.read().strip()
        gone = missing(dest)
        if gone:
            log("Some PythonOS files are missing (" + ", ".join(gone) + "): downloading them again.")
        elif version_key(installed) >= version_key(latest):
            log(f"PythonOS {installed} is already installed.")
            return True

    if manifest.get("url"):
        zip_url = manifest["url"]
    elif os.environ.get("PYOS_UPDATE_URL") or url:
        zip_url = urljoin(murl, manifest["asset"])
    else:
        zip_url = f"{RELEASES_URL}/download/{manifest.get('tag', 'v' + latest)}/{manifest['asset']}"

    stage = os.path.join(dest, ".bootstrap")
    shutil.rmtree(stage, ignore_errors=True)
    try:
        log(f"Downloading PythonOS {latest}...")
        last = [-1]

        def progress(done, total):
            percent = done * 100 // total
            if percent // 10 != last[0] // 10:
                last[0] = percent
                log(f"  {percent}%")

        data = fetch(zip_url, progress)
        if hashlib.sha256(data).hexdigest() != manifest["sha256"]:
            raise ValueError("the download is corrupted (checksum mismatch)")

        os.makedirs(stage)
        archive = os.path.join(stage, "core.zip")
        with open(archive, "wb") as f:
            f.write(data)
        files = os.path.join(stage, "files")
        with zipfile.ZipFile(archive) as z:
            for entry in manifest["files"]:
                rel = entry["path"]
                if not safe_member(rel):
                    raise ValueError(f"unsafe path in the download: {rel}")
                content = z.read(rel)
                if hashlib.sha256(content).hexdigest() != entry["sha256"]:
                    raise ValueError(f"checksum mismatch for {rel}")
                target = os.path.join(files, *rel.split("/"))
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with open(target, "wb") as f:
                    f.write(content)

        # Everything verified - now put it in place (user data in `dest` is never touched)
        for name in CODE_DIRS:
            new = os.path.join(files, name)
            if os.path.isdir(new):
                shutil.rmtree(os.path.join(dest, name), ignore_errors=True)
                shutil.move(new, os.path.join(dest, name))
        for name in os.listdir(files):
            path = os.path.join(files, name)
            if os.path.isfile(path):
                shutil.copy2(path, os.path.join(dest, name))
        sync_config_version(dest, latest)
        log(f"Installed PythonOS {latest}.")
        return True
    except Exception as e:
        log(f"Could not install PythonOS: {e}")
        return False
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dest", default=".", help="folder to install into (default: current folder)")
    parser.add_argument("--url", help="core-manifest.json URL (default: the latest GitHub release)")
    parser.add_argument("--force", action="store_true", help="reinstall even if the version is current")
    args = parser.parse_args()
    sys.exit(0 if install(args.dest, args.url, args.force) else 1)


if __name__ == "__main__":
    main()
