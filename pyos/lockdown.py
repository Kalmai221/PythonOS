# pyos/lockdown.py - "stay inside PythonOS" mode (the live ISO, kiosks, shared machines)
#
# PythonOS runs as root on the ISO, and Python code can do anything, so the guarantee that nobody can
# reach the Linux side rests on the OS never running code or commands the user controls. In lockdown:
#
#   * packages from the marketplace only run if they are catalog-approved ("lockdown_safe") and their
#     files still match the hashes recorded when they were installed (the record lives in .OSData,
#     which no PythonOS command can write to). A package an admin drops into files/ does not run.
#   * installer/uninstaller scripts of packages never run (they exist to pip-install things).
#   * no external editor, no process killing, no way to list the machine's other processes.
#
# Turn it on with PYOS_LOCKDOWN=1 (the ISO does) or "lockdown": true in config.json.
import hashlib
import json
import os
import threading
from pathlib import Path

RECORD_FILE = Path(".OSData") / "packages.json"
_lock = threading.Lock()


def enabled():
    if os.environ.get("PYOS_LOCKDOWN") == "1":
        return True
    try:
        with open("config.json", encoding="utf-8") as f:
            return bool(json.load(f).get("lockdown"))
    except (OSError, ValueError):
        return False


def deny(console, what):
    """Print the standard refusal. Returns False so callers can `return lockdown.deny(...)`."""
    console.print(f"[yellow]{what} is switched off on this locked-down system.[/yellow]")
    return False


# ------------------------------------------------------------ package records
def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _key(folder):
    """Stable key for an installed package folder: 'installed_games/hangman'."""
    parts = Path(os.path.abspath(folder)).parts
    for i, part in enumerate(parts):
        if part.startswith("installed_"):
            return "/".join(parts[i:i + 2])
    return Path(folder).name


def _files_of(folder):
    found = {}
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for name in filenames:
            if name.endswith((".pyc", ".pyo")):
                continue
            full = os.path.join(dirpath, name)
            found[os.path.relpath(full, folder).replace(os.sep, "/")] = full
    return found


def _read():
    try:
        with open(RECORD_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(data):
    RECORD_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(RECORD_FILE) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, RECORD_FILE)


def record_package(folder, safe):
    """Remember what a freshly installed package looks like (called by the marketplace after verifying it)."""
    with _lock:
        data = _read()
        data[_key(folder)] = {"safe": bool(safe), "files": {rel: _sha256(full) for rel, full in _files_of(folder).items()}}
        _write(data)


def forget_package(folder):
    with _lock:
        data = _read()
        if data.pop(_key(folder), None) is not None:
            _write(data)


def package_trusted(folder):
    """True if the package was installed from the catalog, is marked safe, and is byte-for-byte unchanged."""
    record = _read().get(_key(folder))
    if not record or not record.get("safe"):
        return False
    current = _files_of(folder)
    if set(current) != set(record["files"]):
        return False            # a file was added or removed - extra code must not slip in
    try:
        return all(_sha256(current[rel]) == digest for rel, digest in record["files"].items())
    except OSError:
        return False


def may_run(folder):
    """Whether a package folder may execute right now (always true outside lockdown)."""
    return (not enabled()) or package_trusted(folder)
