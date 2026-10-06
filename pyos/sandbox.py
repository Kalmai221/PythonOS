# pyos/sandbox.py - package permissions: what an app says it needs, what the user allowed, and the guard that enforces it.
#
# A marketplace package declares permissions in its data.json ("permissions": ["network", "files"]). The marketplace shows
# them before installing and records what the user allowed (.OSData/package_perms.json). When the package runs, it is started
# through pyos/sandbox_run.py, which installs a guard in that process: network access, file access outside the app's own
# folder, and starting other programs are refused unless the matching permission was granted.
#
# Be clear about what this is: a guard inside the Python process that stops an honest app doing more than it declared and
# catches mistakes. It is not a security boundary against deliberately malicious code (that is what the marketplace review and
# the lockdown_safe audit are for).
import json
import os
import sys

# permission -> what it lets the app do, in words a person understands
PERMISSIONS = {
    "network": "connect to the internet and your network",
    "files": "read and change your files and folders",
    "notifications": "show you notifications",
    "schedule": "schedule tasks that run later (alarms, reminders)",
    "system": "read information about this computer (processes, memory, disk)",
    "exec": "start other programs and run code on this computer",
}
# an app that declares nothing needs nothing; an app installed before permissions existed keeps working with these
LEGACY_DEFAULT = ("network", "files", "notifications", "schedule", "system")
GRANTS_FILE = os.path.join(".OSData", "package_perms.json")


def describe(perms):
    """['network', 'files'] -> 'connect to the internet ..., read and change your files ...' (empty list -> 'nothing special')."""
    return ", ".join(PERMISSIONS.get(p, p) for p in perms) or "nothing special (it only keeps its own settings)"


def declared(meta):
    """The permissions a data.json asks for, or None if it does not say (an older package)."""
    value = (meta or {}).get("permissions")
    if value is None:
        return None
    return [p for p in value if p in PERMISSIONS]


def _read():
    try:
        with open(GRANTS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def granted(pkg_id):
    """What the user allowed for this package id, or None if nothing was recorded."""
    value = _read().get(pkg_id)
    return None if value is None else [p for p in value if p in PERMISSIONS]


def set_granted(pkg_id, perms):
    data = _read()
    data[pkg_id] = [p for p in perms if p in PERMISSIONS]
    os.makedirs(os.path.dirname(GRANTS_FILE), exist_ok=True)
    tmp = GRANTS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, GRANTS_FILE)


def forget(pkg_id):
    data = _read()
    if data.pop(pkg_id, None) is not None:
        with open(GRANTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def package_id(folder):
    """files/installed_games/chess -> games/chess"""
    folder = os.path.normpath(folder)
    parent, name = os.path.split(folder)
    category = os.path.basename(parent)
    return f"{category[len('installed_'):]}/{name}" if category.startswith("installed_") else name


def effective(folder, meta):
    """The permissions an installed package actually runs with: what was granted; for a package from before permissions
    existed (nothing recorded, nothing declared) the legacy set; otherwise what it declares and the user was shown."""
    pid = package_id(folder)
    got = granted(pid)
    if got is not None:
        want = declared(meta)
        return got if want is None else [p for p in got if p in want]
    want = declared(meta)
    return list(LEGACY_DEFAULT) if want is None else want


def launch(script_path, args, folder, meta):
    """(command, environment) to run a package script under the guard. The guard is told its permissions on the command line
    (not the environment) so it also works where scripts are run inside the host process (the Android app)."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")
    from . import marketapi
    libs = os.path.join(os.path.abspath(folder), ".libs")                # Python libraries the marketplace installed for this app (API 2)
    if os.path.isdir(libs):
        env["PYTHONPATH"] = libs + os.pathsep + env["PYTHONPATH"]
    env["PYOS_PACKAGE_API"] = str(marketapi.package_api(meta))      # the marketplace API the app was written for (the app can branch on it)
    runner = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sandbox_run.py")
    try:
        from . import limits
        held = limits.for_package(package_id(folder), meta)
    except Exception:
        held = {"memory_mb": 0, "cpu_seconds": 0}
    cmd = [sys.executable, runner, "--perms", ",".join(effective(folder, meta)), "--dir", os.path.abspath(folder),
           "--id", package_id(folder), "--mem-mb", str(held["memory_mb"]), "--cpu-seconds", str(held["cpu_seconds"]),
           "--", os.path.abspath(script_path), *(args or [])]
    return cmd, env
