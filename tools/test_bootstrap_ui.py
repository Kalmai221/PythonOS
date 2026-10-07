#!/usr/bin/env python3
"""The first-start download screen of bootstrap.py: the steps, the progress bar (in place on a terminal, a line per quarter otherwise),
colour only where it is wanted, plain characters where the terminal cannot show the nicer ones, and a failure that says what to do.
The release is faked; nothing is downloaded."""
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import tempfile
import zipfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def load():
    spec = importlib.util.spec_from_file_location("bootstrap_ui_test", os.path.join(REPO_ROOT, "OS_Export", "bootstrap.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Screen:
    """A fake screen: it says whether it is a terminal and what it can encode, and keeps what was written."""

    def __init__(self, tty, encoding="utf-8"):
        self._tty, self.encoding, self._buffer = tty, encoding, io.StringIO()

    def isatty(self):
        return self._tty

    def write(self, text):
        return self._buffer.write(text)

    def flush(self):
        pass

    def getvalue(self):
        return self._buffer.getvalue()


def release(files):
    """A fake release: the core zip, its manifest, and a fetch() that serves them (in chunks, calling the progress callback)."""
    blob = io.BytesIO()
    with zipfile.ZipFile(blob, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    zip_bytes = blob.getvalue()
    manifest = {"version": "9.9.9", "tag": "v9.9.9", "asset": "core.zip", "sha256": hashlib.sha256(zip_bytes).hexdigest(), "size": len(zip_bytes),
                "files": [{"path": n, "sha256": hashlib.sha256(d.encode()).hexdigest()} for n, d in files.items()]}

    def fetch(url, progress=None):
        data = json.dumps(manifest).encode() if url.endswith(".json") else zip_bytes
        if progress and not url.endswith(".json"):
            for done in range(0, len(data), max(1, len(data) // 8)):
                progress(done, len(data))
            progress(len(data), len(data))
        return data
    return manifest, fetch


def main():
    bootstrap = load()
    saved = {k: os.environ.pop(k, None) for k in ("NO_COLOR", "COLORTERM", "FORCE_COLOR", "TERM")}
    files = {"main.py": "print('hi')\n", "shell.py": "", "users.py": "", "VERSION": "9.9.9\n", "requirements.txt": "", "boot-requirements.txt": "",
             "commands/a.py": "x = 1\n", "core/b.py": "", "programs/c.py": "", "pyos/d.py": ""}
    manifest, fetch = release(files)
    bootstrap.fetch = fetch
    tmp = tempfile.mkdtemp()
    try:
        # on a real terminal: colour, a bar redrawn in place, every step, a tick for each, and the result
        screen = Screen(True)
        look = bootstrap.Look(print, screen)
        assert look.live and look.color and look.unicode
        old = bootstrap.sys.stdout
        bootstrap.sys.stdout = screen
        try:
            assert bootstrap.install(os.path.join(tmp, "a"), url="https://example.invalid/core-manifest.json") is True
        finally:
            bootstrap.sys.stdout = old
        text = screen.getvalue()
        plain = ANSI.sub("", text)
        for want in ("PythonOS", "[1/4] Finding the latest release", "[2/4] Downloading PythonOS 9.9.9", "[3/4] Checking", "[4/4] Installing",
                     "PythonOS 9.9.9 is ready.", "✓", "█", "MB/s"):
            assert want in plain, (want, plain)
        assert "\r" in text and "\x1b[" in text, "on a terminal the bar is redrawn in place and coloured"
        assert "100%" in plain
        assert os.path.isfile(os.path.join(tmp, "a", "commands", "a.py")) and open(os.path.join(tmp, "a", "VERSION")).read().strip() == "9.9.9"

        # not a terminal (a pipe, a log file): no colour, no redrawing, a line per quarter, plain words
        screen = Screen(False)
        old = bootstrap.sys.stdout
        bootstrap.sys.stdout = screen
        try:
            assert bootstrap.install(os.path.join(tmp, "b"), url="https://example.invalid/core-manifest.json") is True
        finally:
            bootstrap.sys.stdout = old
        text = screen.getvalue()
        assert "\x1b" not in text and "\r" not in text, "no escape codes into a log"
        assert text.count("%") >= 4 and "[4/4] Installing" in text

        # NO_COLOR is honoured even on a terminal; a terminal that cannot show the nicer characters gets plain ones
        os.environ["NO_COLOR"] = "1"
        assert not bootstrap.Look(print, Screen(True)).color
        del os.environ["NO_COLOR"]
        legacy = Screen(True, "cp1252")
        look = bootstrap.Look(print, legacy)
        old = bootstrap.sys.stdout
        bootstrap.sys.stdout = legacy
        try:
            look.step(2, "x")
            look.bar(5, 10, bootstrap.time.monotonic() - 1)
            look.done("fine")
        finally:
            bootstrap.sys.stdout = old
        shown = ANSI.sub("", legacy.getvalue())
        assert "█" not in shown and "✓" not in shown and "#" in shown and " ok " in shown, shown
        os.environ["TERM"] = "dumb"
        assert not bootstrap.Look(print, Screen(True)).color
        del os.environ["TERM"]

        # a custom log (the app's own) gets plain lines, one call each
        lines = []
        bootstrap.install(os.path.join(tmp, "c"), url="https://example.invalid/core-manifest.json", log=lines.append)
        assert any("Downloading PythonOS 9.9.9" in l for l in lines) and not any("\x1b" in l or "\r" in l for l in lines)

        # already up to date: says so, downloads nothing
        downloads = []
        real_fetch = bootstrap.fetch
        bootstrap.fetch = lambda url, progress=None: (downloads.append(url), real_fetch(url, progress))[1]
        lines.clear()
        assert bootstrap.install(os.path.join(tmp, "a"), url="https://example.invalid/core-manifest.json", log=lines.append) is True
        assert any("already installed" in l for l in lines) and all(u.endswith(".json") for u in downloads), (lines, downloads)
        bootstrap.fetch = real_fetch

        # a failure: red cross, the reason, what to do, and nothing half installed
        def broken(url, progress=None):
            if url.endswith(".json"):
                return real_fetch(url)
            raise OSError("connection lost")
        bootstrap.fetch = broken
        screen = Screen(False)
        old = bootstrap.sys.stdout
        bootstrap.sys.stdout = screen
        try:
            assert bootstrap.install(os.path.join(tmp, "d"), url="https://example.invalid/core-manifest.json") is False
        finally:
            bootstrap.sys.stdout = old
        assert "Could not install PythonOS: connection lost" in screen.getvalue() and "Nothing was changed" in screen.getvalue()
        assert not os.path.exists(os.path.join(tmp, "d", ".bootstrap")) and not os.path.exists(os.path.join(tmp, "d", "main.py"))
        bootstrap.fetch = lambda url, progress=None: (_ for _ in ()).throw(OSError("offline"))
        screen = Screen(False)
        old = bootstrap.sys.stdout
        bootstrap.sys.stdout = screen
        try:
            assert bootstrap.install(os.path.join(tmp, "e"), url="https://example.invalid/core-manifest.json") is False
        finally:
            bootstrap.sys.stdout = old
        assert "Could not read the latest PythonOS release" in screen.getvalue() and "internet connection" in screen.getvalue()
    finally:
        for key, value in saved.items():
            if value is not None:
                os.environ[key] = value
        shutil.rmtree(tmp, ignore_errors=True)
    print("first-start screen: all checks passed")


if __name__ == "__main__":
    main()
