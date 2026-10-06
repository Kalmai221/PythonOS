"""`doctor`: check that the install is healthy and offer to fix what it can.

Each check returns Findings. A Finding has a level (ok / warn / error), an area, a message and, when the problem can be fixed
safely, a fix() callable plus a one-line description of what the fix does. Nothing is changed unless the user agrees.
"""
import ast
import json
import os
import shutil
import time
from dataclasses import dataclass
from typing import Callable, Optional

import pyos
from pyos import fs, paths, settings


@dataclass
class Finding:
    level: str                       # ok | warn | error
    area: str
    message: str
    fix: Optional[Callable[[], str]] = None
    fix_text: str = ""


ROOT = os.getcwd()
MIN_FREE_WARN = 200 * 1024 ** 2
MIN_FREE_ERROR = 50 * 1024 ** 2
OS_FOLDERS = ("commands", "core", "pyos", "programs")


def _human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


# ------------------------------------------------------------------ checks
def check_disk():
    try:
        free = shutil.disk_usage(os.path.abspath("files") if os.path.isdir("files") else ".").free
    except OSError:
        return [Finding("warn", "Disk space", "could not read the free space")]
    if free < MIN_FREE_ERROR:
        return [Finding("error", "Disk space", f"only {_human(free)} free - PythonOS may fail to save files")]
    if free < MIN_FREE_WARN:
        return [Finding("warn", "Disk space", f"only {_human(free)} free")]
    return [Finding("ok", "Disk space", f"{_human(free)} free")]


def check_layout():
    found, missing = [], []
    for d in fs.LAYOUT:
        if not os.path.isdir(os.path.join(fs.BASE_DIR, *d.split("/"))):
            missing.append(d)
    users = _users()
    for name in users:
        if not os.path.isdir(fs.home_dir(name)):
            missing.append(f"home/{name}")

    def fix():
        fs.ensure_layout()
        for name in _users():
            fs.ensure_home(name)
        return f"created {len(missing)} folder(s)"

    if missing:
        found.append(Finding("warn", "Folders", "missing: " + ", ".join(missing), fix, "create the missing folders"))
    else:
        found.append(Finding("ok", "Folders", "standard folders and every home folder exist"))
    return found


def _users():
    try:
        with open(paths.USER_DB, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def check_accounts():
    try:
        with open(paths.USER_DB, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return [Finding("warn", "Accounts", "there is no account database yet (first-time setup has not run)")]
    except (OSError, ValueError) as e:
        return [Finding("error", "Accounts", f"the account database cannot be read: {e}")]
    out = []
    admins = [n for n, u in data.items() if isinstance(u, dict) and u.get("role") == "admin"]
    if not admins:
        out.append(Finding("error", "Accounts", "no administrator account exists"))
    bad = [n for n, u in data.items() if not isinstance(u, dict) or u.get("role") not in ("admin", "user") or "password" not in u]
    if bad:
        out.append(Finding("error", "Accounts", "damaged entries: " + ", ".join(bad)))
    legacy = [n for n, u in data.items() if isinstance(u, dict) and not str(u.get("password", "")).startswith("pbkdf2$")]
    if legacy:
        out.append(Finding("warn", "Accounts", "old-style password hash for: " + ", ".join(legacy)
                           + " (the account owner should run passwd to upgrade it)"))
    if not out:
        out.append(Finding("ok", "Accounts", f"{len(data)} account(s), {len(admins)} administrator(s)"))
    return out


def check_permissions():
    out = []
    for folder in ("files", ".OSData"):
        if os.path.isdir(folder) and not os.access(folder, os.W_OK):
            out.append(Finding("error", "Permissions", f"{folder}/ is not writable"))
    if os.name != "nt":
        loose = []
        for name in (paths.USER_DB, os.path.join(".OSData", "hardware.json"), os.path.join(".OSData", "lockout.json")):
            try:
                if os.path.isfile(name) and os.stat(name).st_mode & 0o077:
                    loose.append(name)
            except OSError:
                pass

        def fix():
            for name in loose:
                os.chmod(name, 0o600)
            return f"restricted {len(loose)} file(s) to the owner"

        if loose:
            out.append(Finding("warn", "Permissions", "readable by other users of this computer: " + ", ".join(loose), fix,
                               "make them readable only by the owner (chmod 600)"))
    if not out:
        out.append(Finding("ok", "Permissions", "data folders are writable and private files are protected"))
    return out


def check_core():
    broken = []
    for folder in OS_FOLDERS:
        if not os.path.isdir(folder):
            broken.append(f"{folder}/ is missing")
            continue
        for name in sorted(os.listdir(folder)):
            if name.endswith(".py"):
                try:
                    with open(os.path.join(folder, name), encoding="utf-8") as f:
                        ast.parse(f.read())
                except (SyntaxError, ValueError) as e:
                    broken.append(f"{folder}/{name}: {e.__class__.__name__}")
                except OSError:
                    broken.append(f"{folder}/{name}: unreadable")
    for name in ("main.py", "shell.py", "users.py", "config.json"):
        if not os.path.isfile(name):
            broken.append(f"{name} is missing")
    if broken:
        return [Finding("error", "System files", "; ".join(broken[:6]) + ("; ..." if len(broken) > 6 else "")
                        + " - run updatecheck to repair the installation")]
    try:
        with open("config.json", encoding="utf-8") as f:
            version = json.load(f).get("version", "?")
    except (OSError, ValueError):
        return [Finding("error", "System files", "config.json is damaged")]
    return [Finding("ok", "System files", f"all files parse (version {version})")]


def check_packages():
    out, bad, leftovers = [], [], []
    root = fs.BASE_DIR
    try:
        categories = [d for d in os.listdir(root) if d.startswith("installed_")]
    except OSError:
        categories = []
    count = 0
    for cat in categories:
        cat_dir = os.path.join(root, cat)
        for name in sorted(os.listdir(cat_dir)):
            full = os.path.join(cat_dir, name)
            if name.startswith((".tmp_", ".old_")):
                leftovers.append(full)
                continue
            if not os.path.isdir(full):
                continue
            count += 1
            try:
                with open(os.path.join(full, "data.json"), encoding="utf-8") as f:
                    meta = json.load(f)
            except (OSError, ValueError):
                bad.append(f"{cat[len('installed_'):]}/{name}: data.json is missing or damaged")
                continue
            for script in (meta.get("scripts") or {}).values():
                path = os.path.join(full, script)
                if not os.path.isfile(path):
                    bad.append(f"{name}: {script} is missing")
                    continue
                try:
                    with open(path, encoding="utf-8") as f:
                        ast.parse(f.read())
                except (SyntaxError, ValueError):
                    bad.append(f"{name}: {script} has a syntax error")
    if bad:
        out.append(Finding("error", "Packages", "; ".join(bad[:5]) + " - reinstall with: pkg install <name>"))

    def clean():
        for p in leftovers:
            shutil.rmtree(p, ignore_errors=True)
        return f"removed {len(leftovers)} leftover folder(s)"

    if leftovers:
        out.append(Finding("warn", "Packages", f"{len(leftovers)} half-finished install leftover(s)", clean, "delete them"))
    if not out:
        out.append(Finding("ok", "Packages", f"{count} installed package(s), all complete"))
    return out


def check_locks():
    """Leftover temporary files, and records that point at accounts that no longer exist."""
    stale = []
    if os.path.isdir(".OSData"):
        for name in os.listdir(".OSData"):
            p = os.path.join(".OSData", name)
            if name.endswith(".tmp") and os.path.isfile(p) and time.time() - os.path.getmtime(p) > 3600:
                stale.append(p)
    for name in (paths.USER_DB + ".tmp",):
        if os.path.isfile(name) and time.time() - os.path.getmtime(name) > 3600:
            stale.append(name)
    users = set(_users())
    orphan_lockouts = []
    try:
        with open(os.path.join(".OSData", "lockout.json"), encoding="utf-8") as f:
            lock = json.load(f)
        orphan_lockouts = [n for n in lock if users and n not in users]
    except (OSError, ValueError):
        lock = {}
    orphan_tasks = []
    try:
        with open(os.path.join(".OSData", "schedule.json"), encoding="utf-8") as f:
            tasks = json.load(f)
        orphan_tasks = [t["id"] for t in tasks if users and t.get("user") not in users]
    except (OSError, ValueError, TypeError, KeyError):
        tasks = []
    out = []

    def fix():
        for p in stale:
            try:
                os.remove(p)
            except OSError:
                pass
        if orphan_lockouts:
            for n in orphan_lockouts:
                lock.pop(n, None)
            with open(os.path.join(".OSData", "lockout.json"), "w", encoding="utf-8") as f:
                json.dump(lock, f)
        if orphan_tasks:
            keep = [t for t in tasks if t["id"] not in orphan_tasks]
            with open(os.path.join(".OSData", "schedule.json"), "w", encoding="utf-8") as f:
                json.dump(keep, f)
        return "cleaned up"

    problems = []
    if stale:
        problems.append(f"{len(stale)} stale temporary file(s)")
    if orphan_lockouts:
        problems.append(f"lockout records for removed accounts ({', '.join(orphan_lockouts)})")
    if orphan_tasks:
        problems.append(f"{len(orphan_tasks)} scheduled task(s) for removed accounts")
    if problems:
        out.append(Finding("warn", "Stale data", "; ".join(problems), fix, "remove them"))
    else:
        out.append(Finding("ok", "Stale data", "no stale locks, temporary files or orphaned records"))
    return out


def check_settings():
    try:
        with open(settings.SETTINGS_FILE, encoding="utf-8") as f:
            stored = json.load(f)
    except FileNotFoundError:
        return [Finding("ok", "Settings", "defaults in use")]
    except (OSError, ValueError):
        def fix():
            os.replace(settings.SETTINGS_FILE, settings.SETTINGS_FILE + ".damaged")
            settings._cache["data"] = None
            return "set the damaged file aside; defaults are in use"
        return [Finding("error", "Settings", "settings.json is damaged", fix, "set it aside and use the defaults")]
    invalid = [k for k, v in stored.items() if k in settings.SCHEMA and not settings._valid(k, v)]
    unknown = [k for k in stored if k not in settings.SCHEMA]
    if invalid or unknown:
        def fix():  # pylint: disable=function-redefined
            for k in invalid + unknown:
                settings.reset(k)
            return "removed the bad entries"
        return [Finding("warn", "Settings", "ignored entries: " + ", ".join(invalid + unknown), fix, "remove them")]
    return [Finding("ok", "Settings", "all values are valid")]


def check_log():
    try:
        size = os.path.getsize(pyos.log.LOG_FILE)
    except OSError:
        return [Finding("ok", "Log", "empty")]
    crashes = 0
    try:
        crashes = sum(1 for n in os.listdir(os.path.dirname(pyos.log.LOG_FILE)) if n.startswith("crash-"))
    except OSError:
        pass
    if crashes:
        return [Finding("warn", "Log", f"{crashes} saved crash report(s) - see: logs --crashes")]
    return [Finding("ok", "Log", f"{_human(size)}, no crash reports")]


CHECKS = [check_disk, check_core, check_layout, check_accounts, check_permissions, check_packages, check_locks, check_settings,
          check_log]


def run_all():
    findings = []
    for check in CHECKS:
        try:
            findings.extend(check())
        except Exception as e:  # a broken check must not hide the others
            findings.append(Finding("warn", check.__name__[6:].title(), f"could not run this check ({e.__class__.__name__}: {e})"))
    return findings
