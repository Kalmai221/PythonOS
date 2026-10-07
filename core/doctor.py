"""`doctor`: check that the install is healthy and offer to fix what it can.

Each check returns Findings. A Finding has a level (ok / warn / error), an area, a message and, when the problem can be fixed
safely, a fix() callable plus a one-line description of what the fix does. When it cannot be fixed by itself, `hint` says what the
person can do. Nothing is changed unless the user agrees. Checks that need the internet only run with online=True.
"""
import ast
import json
import os
import platform
import re
import shutil
import socket
import sys
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
    hint: str = ""                   # what to do when there is no automatic fix
    check: str = ""                  # which check produced it (filled in by run_all)


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


def check_environment():
    out = []
    version = ".".join(str(n) for n in sys.version_info[:3])
    if sys.version_info < (3, 9):
        out.append(Finding("error", "Python", f"Python {version} is older than the 3.9 PythonOS needs",
                           hint="install a newer Python, or use a packaged export"))
    else:
        out.append(Finding("ok", "Python", f"{version} ({platform.python_implementation()}) on {platform.system()} {platform.machine()}"))
    year = time.localtime().tm_year
    if year < 2024:
        out.append(Finding("warn", "Clock", f"the computer's clock says {year}; updates and secure connections can fail",
                           hint="set the date and time"))
    try:
        size = shutil.get_terminal_size(fallback=(0, 0))
        if sys.stdout.isatty() and 0 < size.columns < 60:
            out.append(Finding("warn", "Terminal", f"only {size.columns} columns wide; tables and menus will wrap", hint="make the window wider"))
    except (OSError, ValueError):
        pass
    try:
        from pyos import export
        found = export.info()
        if found:
            out.append(Finding("ok", "Package", f"{export.title(found['platform'])}, package version {found['version']}"))
    except Exception:                                      # noqa: BLE001 - informational only
        pass
    return out


def _optional(name):
    try:
        from pyos import optional
        return optional.get(name)
    except Exception:                                      # noqa: BLE001
        return None


def check_memory():
    """Memory and swap. Each is skipped on its own where the system does not allow reading it (Android restricts /proc): never an error."""
    from pyos import sysmem
    out = []
    mem = sysmem.memory()
    if mem is not None:
        if mem.percent >= 95:
            out.append(Finding("warn", "Memory", f"{mem.percent:.0f}% of {_human(mem.total)} in use", hint="close other programs"))
        else:
            out.append(Finding("ok", "Memory", f"{_human(mem.available)} available of {_human(mem.total)}"))
    swap = sysmem.swap()
    if swap is not None and swap.total and swap.percent >= 90:
        out.append(Finding("warn", "Swap", f"{swap.percent:.0f}% of the swap space is in use; the computer is short of memory"))
    return out


# the import name of each optional library, where it is not the package name
IMPORT_NAMES = {"python-dateutil": "dateutil", "beautifulsoup4": "bs4", "pyyaml": "yaml", "pillow": "PIL", "pypdf2": "PyPDF2",
                "python-docx": "docx", "opencv-python": "cv2", "scikit-learn": "sklearn", "python-magic": "magic"}


def check_libraries():
    """Which optional libraries (requirements-extra.txt) are installed. Missing ones are only a loss of features."""
    try:
        with open("requirements-extra.txt", encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    import importlib.util
    names = []
    for line in lines:
        line = line.split("#")[0].strip()
        if line:
            names.append(re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0])
    if not names:
        return []
    missing = []
    for name in names:
        module = IMPORT_NAMES.get(name.lower(), name.lower().replace("-", "_"))
        try:
            if importlib.util.find_spec(module) is None:
                missing.append(name)
        except (ImportError, ValueError):
            missing.append(name)
    if missing:
        return [Finding("warn", "Libraries", f"{len(names) - len(missing)} of {len(names)} optional libraries installed; missing: "
                        + ", ".join(missing[:8]) + (", ..." if len(missing) > 8 else ""),
                        hint="python -m pip install -r requirements-extra.txt (what uses them still works, in a simpler way)")]
    return [Finding("ok", "Libraries", f"all {len(names)} optional libraries are installed")]


def check_commands():
    """Every command file must define `config` and `execute`, and no two may claim the same name."""
    if not os.path.isdir("commands"):
        return []
    broken, seen, dupes = [], {}, []
    for name in sorted(os.listdir("commands")):
        if not name.endswith(".py") or name.startswith("_"):
            continue
        try:
            with open(os.path.join("commands", name), encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except (SyntaxError, ValueError, OSError):
            continue                                       # check_core reports these
        config = None
        has_execute = False
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "config" for t in node.targets):
                config = node.value
            elif isinstance(node, ast.FunctionDef) and node.name == "execute":
                has_execute = True
        if config is None or not has_execute:
            broken.append(name)
            continue
        if isinstance(config, ast.Dict):
            for key, value in zip(config.keys, config.values):
                if isinstance(key, ast.Constant) and key.value == "name" and isinstance(value, ast.Constant):
                    if value.value in seen:
                        dupes.append(f"{value.value} ({seen[value.value]} and {name})")
                    seen[value.value] = name
    out = []
    if broken:
        out.append(Finding("error", "Commands", "not valid commands (no config or execute): " + ", ".join(broken[:6]),
                           hint="updatecheck repairs the installation"))
    if dupes:
        out.append(Finding("warn", "Commands", "the same command name is defined twice: " + ", ".join(dupes[:4])))
    if not out:
        out.append(Finding("ok", "Commands", f"{len(seen)} commands, each with a name and a handler"))
    return out


def check_shell():
    """Aliases (per account) that point at a command that does not exist."""
    try:
        known = {n[:-3] for n in os.listdir("commands") if n.endswith(".py")}
    except OSError:
        return []
    problems, total = [], 0
    for user in _users():
        try:
            with open(os.path.join(fs.home_dir(user), ".pyos_aliases"), encoding="utf-8") as f:
                data = json.load(f)
        except OSError:
            continue
        except ValueError:
            problems.append(f"{user}: the alias file is damaged")
            continue
        if not isinstance(data, dict):
            continue
        for alias, value in data.items():
            total += 1
            words = str(value).split()
            if words and words[0] not in known and words[0] not in data and not re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[0]):
                problems.append(f"{user}: {alias} -> {words[0]}")
    if problems:
        return [Finding("warn", "Aliases", "pointing at nothing: " + "; ".join(problems[:5]), hint="remove them with unalias <name>")]
    return [Finding("ok", "Aliases", f"{total} alias(es), all pointing at real commands")] if total else []


def _size(path):
    total = 0
    for base, _dirs, names in os.walk(path):
        for name in names:
            try:
                total += os.path.getsize(os.path.join(base, name))
            except OSError:
                pass
    return total


def check_storage():
    out = []
    parts = {}
    for label, folder in (("files", fs.BASE_DIR), ("system data", ".OSData")):
        if os.path.isdir(folder):
            parts[label] = _size(folder)
    if parts:
        out.append(Finding("ok", "Storage", ", ".join(f"{label} {_human(n)}" for label, n in parts.items())))
    log_dir = os.path.dirname(pyos.log.LOG_FILE) or "."
    old = []
    try:
        for name in os.listdir(log_dir):
            p = os.path.join(log_dir, name)
            if name.startswith("crash-") and os.path.isfile(p) and time.time() - os.path.getmtime(p) > 30 * 86400:
                old.append(p)
    except OSError:
        pass

    def clean():
        for p in old:
            try:
                os.remove(p)
            except OSError:
                pass
        return f"removed {len(old)} old crash report(s)"

    if old:
        out.append(Finding("warn", "Crash reports", f"{len(old)} crash report(s) older than 30 days", clean, "delete them"))
    try:
        big = os.path.getsize(pyos.log.LOG_FILE)
        if big > 50 * 1024 ** 2:
            out.append(Finding("warn", "Log", f"the log is {_human(big)}", hint="it is safe to delete it after reading what you need"))
    except OSError:
        pass
    return out


def check_schedule():
    try:
        with open(os.path.join(".OSData", "schedule.json"), encoding="utf-8") as f:
            tasks = json.load(f)
    except FileNotFoundError:
        return []
    except (OSError, ValueError):
        return [Finding("error", "Schedule", "the schedule file is damaged",
                        hint="move .OSData/schedule.json away; tasks then have to be added again")]
    if not isinstance(tasks, list):
        return [Finding("error", "Schedule", "the schedule file has the wrong shape")]
    bad = [t for t in tasks if not isinstance(t, dict) or "id" not in t or "user" not in t]
    if bad:
        return [Finding("warn", "Schedule", f"{len(bad)} scheduled task(s) are incomplete")]
    return [Finding("ok", "Schedule", f"{len(tasks)} scheduled task(s)")] if tasks else []


def _latest_release():
    import urllib.request
    req = urllib.request.Request("https://api.github.com/repos/Kalmai221/PythonOS/releases/latest",
                                 headers={"User-Agent": "PythonOS-doctor", "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=6) as resp:                    # nosec - fixed https URL
        return json.load(resp)


def _numbers(text):
    return tuple(int(n) for n in re.findall(r"\d+", str(text))[:3])


def check_network():
    """Internet, name lookups and the update server. Only runs with --online (it needs the network and takes a moment)."""
    started = time.time()
    try:
        socket.setdefaulttimeout(5)
        socket.getaddrinfo("github.com", 443)
    except OSError as e:
        return [Finding("warn", "Network", f"cannot look up github.com ({e.__class__.__name__}); updates and the marketplace need the internet",
                        hint="check the connection, DNS and any proxy")]
    try:
        data = _latest_release()
    except Exception as e:                                 # noqa: BLE001 - any failure is "cannot reach"
        return [Finding("warn", "Network", f"github.com resolves but the release server did not answer ({e.__class__.__name__})",
                        hint="try again later, or check a proxy or firewall")]
    out = [Finding("ok", "Network", f"the release server answered in {time.time() - started:.1f} s")]
    try:
        with open("config.json", encoding="utf-8") as f:
            have = json.load(f).get("version", "")
        latest = str(data.get("tag_name", "")).lstrip("v")
        if _numbers(have) and _numbers(latest) and _numbers(have) < _numbers(latest):
            out.append(Finding("warn", "Updates", f"PythonOS {have} is installed; {latest} is the latest release", hint="run updatecheck"))
        else:
            out.append(Finding("ok", "Updates", f"PythonOS {have} is the latest release"))
    except (OSError, ValueError):
        pass
    return out


CHECKS = [check_environment, check_disk, check_memory, check_core, check_commands, check_layout, check_accounts, check_permissions,
          check_packages, check_libraries, check_locks, check_settings, check_shell, check_schedule, check_storage, check_log]
ONLINE_CHECKS = [check_network]


def names():
    return [c.__name__[6:] for c in CHECKS + ONLINE_CHECKS]


def score(findings):
    """0-100: each problem costs 20, each warning 5."""
    return max(0, 100 - 20 * sum(1 for f in findings if f.level == "error") - 5 * sum(1 for f in findings if f.level == "warn"))


REPORT = os.path.join(".OSData", "doctor.json")


def last_report():
    try:
        with open(REPORT, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def save_report(findings):
    try:
        with open(REPORT, "w", encoding="utf-8") as f:
            json.dump({"time": time.time(), "score": score(findings),
                       "findings": [[x.level, x.area, x.message] for x in findings if x.level != "ok"]}, f)
    except OSError:
        pass


def run_all(only=None, online=False, timings=None):
    """Run the checks (all, or just those whose name is in `only`). `timings`, if given, collects {check: seconds}."""
    findings = []
    for check in CHECKS + (ONLINE_CHECKS if online else []):
        key = check.__name__[6:]
        if only and key not in only:
            continue
        began = time.time()
        try:
            found = check()
        except Exception as e:  # a broken check must not hide the others
            found = [Finding("warn", key.title(), f"could not run this check ({e.__class__.__name__}: {e})")]
        for f in found:
            f.check = key
        findings.extend(found)
        if timings is not None:
            timings[key] = time.time() - began
    return findings
