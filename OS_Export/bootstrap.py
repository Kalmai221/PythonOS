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
import time
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


class Look:
    """What the first-start download looks like: a short heading, numbered steps with ticks, and a live progress bar with the size, speed and
    time left. Standard library only (this runs before anything is installed). On a terminal it uses colour and redraws the bar in place;
    with NO_COLOR, a dumb terminal or output that is not a terminal it falls back to plain lines, and it uses plain characters where the
    terminal cannot show the nicer ones. `log` is where plain text goes when something other than print is given."""

    def __init__(self, log=print, stream=None, steps=4):
        self.log = log
        self.stream = stream or sys.stdout
        self.plain = log is not print
        # a real terminal, or a screen that says it draws like one (the PythonOS window and the Android app set COLORTERM / FORCE_COLOR)
        terminal = bool(getattr(self.stream, "isatty", lambda: False)()) or bool(os.environ.get("COLORTERM") or os.environ.get("FORCE_COLOR"))
        self.live = terminal and not self.plain
        self.color = self.live and "NO_COLOR" not in os.environ and os.environ.get("TERM") != "dumb"
        self.unicode = "utf" in str(getattr(self.stream, "encoding", "") or "").lower()
        self.steps = steps
        self.width = 0                                   # length of the progress line on screen, to wipe it when it shrinks
        self.last_quarter = -1
        if self.color and os.name == "nt":
            os.system("")                                # switches an older Windows console into colour mode

    def paint(self, code, text):
        return f"\x1b[{code}m{text}\x1b[0m" if self.color else text

    def _write(self, text):
        if self.plain:
            self.log(text)
        else:
            self.stream.write(text + "\n")
            self.stream.flush()

    def heading(self, title, detail=""):
        """The banner: the prompt mark, the name and what is happening, in a box (plain dashes where the terminal cannot draw one)."""
        dot = "·" if self.unicode else "-"
        inside = f">_  {title}" + (f"  {dot}  {detail}" if detail else "")
        width = len(inside) + 4
        self._write("")
        if self.unicode:
            coloured = f"{self.paint('1;36', '>_')}  {self.paint('1', title)}" + (f"  {self.paint('2', dot)}  {self.paint('2', detail)}" if detail else "")
            self._write("  " + self.paint("2", "╭" + "─" * (width - 2) + "╮"))
            self._write("  " + self.paint("2", "│") + "  " + coloured + "  " + self.paint("2", "│"))
            self._write("  " + self.paint("2", "╰" + "─" * (width - 2) + "╯"))
        else:
            self._write("  " + self.paint("1;36", inside))
            self._write("  " + self.paint("2", "-" * width))

    def step(self, number, text):
        self.end_bar()
        self._write(f"  {self.paint('2', f'[{number}/{self.steps}]')} {text}")

    def done(self, text, detail=""):
        self.end_bar()
        tick = "✓" if self.unicode else "ok"
        self._write(f"        {self.paint('1;32', tick)} {text}" + (f"  {self.paint('2', detail)}" if detail else ""))

    def info(self, text):
        self._write(f"        {self.paint('2', text)}")

    def fail(self, text, hint=""):
        self.end_bar()
        cross = "✗" if self.unicode else "x"
        self._write(f"        {self.paint('1;31', cross)} {text}")
        if hint:
            self._write(f"          {self.paint('2', hint)}")

    def ready(self, text):
        self._write("")
        self._write("  " + self.paint("1;32", text))
        self._write("")

    @staticmethod
    def size(count):
        return f"{count / 1048576:.1f} MB" if count >= 104858 else f"{count / 1024:.0f} KB"

    @staticmethod
    def clock(seconds):
        seconds = int(seconds + 0.5)
        return f"{seconds}s" if seconds < 60 else f"{seconds // 60}m {seconds % 60:02d}s"

    def bar(self, done, total, started):
        """The download's progress. Redrawn in place on a terminal; a line for every quarter otherwise."""
        if not total:
            return
        fraction = min(done / total, 1.0)
        elapsed = max(time.monotonic() - started, 0.001)
        speed = done / elapsed
        left = (total - done) / speed if speed else 0
        columns = shutil.get_terminal_size((80, 24)).columns
        width = max(8, min(28, columns - 58))
        filled = int(width * fraction)
        full, empty = ("█", "░") if self.unicode else ("#", "-")
        text = (f"        {self.paint('36', full * filled)}{self.paint('2', empty * (width - filled))} {int(fraction * 100):3d}%  "
                f"{self.size(done)} of {self.size(total)}  {speed / 1048576:.1f} MB/s" + (f"  {self.clock(left)} left" if done < total else ""))
        if self.live:
            visible = len(text) - (len(text) - len(re.sub(r"\x1b\[[0-9;]*m", "", text)))
            self.stream.write("\r" + text + " " * max(0, self.width - visible))
            self.stream.flush()
            self.width = visible
        elif int(fraction * 4) != self.last_quarter:
            self.last_quarter = int(fraction * 4)
            self._write(text)

    def end_bar(self):
        if self.live and self.width:
            self.stream.write("\n")
            self.stream.flush()
            self.width = 0


def install(dest, url=None, force=False, log=print):
    """Install (or update) the core into `dest`. Returns True on success."""
    dest = os.path.abspath(dest)
    os.makedirs(dest, exist_ok=True)
    murl = manifest_url(url)
    ui = Look(log)

    ui.heading("PythonOS", "setting up")
    ui.step(1, "Finding the latest release")
    try:
        manifest = json.loads(fetch(murl).decode("utf-8"))
        for key in ("version", "asset", "sha256", "files"):
            if key not in manifest:
                raise ValueError(f"the release manifest is missing '{key}'")
    except Exception as e:
        ui.fail(f"Could not read the latest PythonOS release: {e}", "Check the internet connection, then start the app again.")
        return False

    latest = str(manifest["version"])
    ui.done(f"PythonOS {latest}", f"{len(manifest['files'])} files, {Look.size(int(manifest.get('size', 0)))}" if manifest.get("size") else "")
    version_file = os.path.join(dest, "VERSION")
    if not force and os.path.isfile(os.path.join(dest, "main.py")) and os.path.isfile(version_file):
        with open(version_file, encoding="utf-8") as f:
            installed = f.read().strip()
        gone = missing(dest)
        if gone:
            ui.info("Some PythonOS files are missing (" + ", ".join(gone) + "): downloading them again.")
        elif version_key(installed) >= version_key(latest):
            sync_config_version(dest, installed)             # an older launcher never wrote it: the version shown must match the files
            ui.done(f"PythonOS {installed} is already installed")
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
        ui.step(2, f"Downloading PythonOS {latest}")
        started = time.monotonic()
        data = fetch(zip_url, lambda done, total: ui.bar(done, total, started))
        ui.done("Downloaded", f"{Look.size(len(data))} in {ui.clock(time.monotonic() - started)}")

        ui.step(3, "Checking that nothing is damaged")
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
        ui.done("Every file matches its checksum", f"{len(manifest['files'])} files")

        # Everything verified - now put it in place (user data in `dest` is never touched)
        ui.step(4, "Installing")
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
        ui.done("Installed")
        ui.ready(f"PythonOS {latest} is ready.")
        return True
    except Exception as e:
        ui.fail(f"Could not install PythonOS: {e}", "Nothing was changed. Check the internet connection, then start the app again.")
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
