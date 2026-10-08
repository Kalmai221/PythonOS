# pyos/sandbox.py - package permissions: what an app says it needs, what the user allowed, and the guard that enforces it.
#
# A marketplace package declares permissions in its data.json ("permissions": ["network", "files"]). The marketplace shows
# them before installing and records what the user allowed (.OSData/package_perms.json). When the package runs, it is started
# through pyos/sandbox_run.py, which installs a guard in that process: network access, file access outside the app's own
# folder, and starting other programs are refused unless the matching permission was granted.
#
# A permission an app asked for but has not been given is not simply refused: the first time the app tries to use it, the guard asks the
# person on the terminal - allow this time, always allow, not now, or never allow. "Always" and "never" are remembered (`pkg permissions`
# shows and changes them); the guard in the app's process writes the answers to a small file in files/tmp and the shell applies them when
# the app ends (apply_decisions). Where nobody can be asked (output captured, a script, the locked-down live system) it is refused as before.
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
DENIED_FILE = os.path.join(".OSData", "package_denied.json")       # permissions the person said "never" to: {package id: [permission]}


NAMES = {"network": "Internet", "files": "Your files", "notifications": "Notifications", "schedule": "Schedule", "system": "System info",
         "exec": "Other programs"}


def describe(perms):
    """['network', 'files'] -> 'connect to the internet ..., read and change your files ...' (empty list -> 'nothing special')."""
    from .i18n import tr
    return ", ".join(tr(PERMISSIONS.get(p, p)) for p in perms) or tr("nothing special (it only keeps its own settings)")


def prompt_texts():
    """The words of the question the guard asks while an app runs, in the person's language (the guard itself is plain standard-library
    code and does not know the language, so the shell hands the words over)."""
    from .i18n import tr
    return {"wants": tr("{name} wants to {what}."), "permission": tr("Permission: {perm}."),
            "choices": tr("(a) allow this time   (A) always allow   (n) not now   (N) never allow"), "prompt": tr("Allow? [n] "),
            "names": {p: tr(n) for p, n in NAMES.items()}, "whats": {p: tr(t) for p, t in PERMISSIONS.items()}}


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
    set_denied(pkg_id, [])


def _read_denied():
    try:
        with open(DENIED_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def denied(pkg_id):
    """The permissions the person said "never" to for this package."""
    return [p for p in _read_denied().get(pkg_id, []) if p in PERMISSIONS]


def set_denied(pkg_id, perms):
    data = _read_denied()
    perms = sorted({p for p in perms if p in PERMISSIONS})
    if perms:
        data[pkg_id] = perms
    elif pkg_id in data:
        del data[pkg_id]
    else:
        return
    os.makedirs(os.path.dirname(DENIED_FILE), exist_ok=True)
    tmp = DENIED_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, DENIED_FILE)


def state(pkg_id, perm, declared_list, allowed_list):
    """'allowed', 'never', 'ask' (asked for but not given: asked about on first use) or '' (not asked for)."""
    if perm in allowed_list:
        return "allowed"
    if perm in denied(pkg_id):
        return "never"
    return "ask" if perm in declared_list else ""


def askable(folder, meta):
    """The permissions the app asked for, has not been given and has not been told "never": the ones it may be asked about while it runs."""
    pid = package_id(folder)
    want = declared(meta) or []
    have = effective(folder, meta)
    return [p for p in want if p not in have and p not in denied(pid)]


def apply_decisions(env):
    """After an app ended: apply the "always" and "never" answers its guard recorded (the file named in env) and delete the file. Only
    permissions the app was allowed to be asked about can change, so an app cannot give itself more than it asked for."""
    path = (env or {}).get("PYOS_PERM_DECISIONS")
    pid = (env or {}).get("PYOS_PERM_PACKAGE")
    if not path or not pid:
        return []
    applied = []
    try:
        with open(path, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        return []
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    allowed_to_change = set((env.get("PYOS_PERM_ASK") or "").split(","))
    now_granted = list(granted(pid) or [])
    now_denied = denied(pid)
    for line in lines:
        try:
            item = json.loads(line)
        except ValueError:
            continue
        perm, decision = item.get("perm"), item.get("decision")
        if perm not in PERMISSIONS or perm not in allowed_to_change:
            continue
        if decision == "always":
            if perm not in now_granted:
                now_granted.append(perm)
            now_denied = [p for p in now_denied if p != perm]
        elif decision == "never":
            now_granted = [p for p in now_granted if p != perm]
            if perm not in now_denied:
                now_denied.append(perm)
        else:
            continue
        applied.append((perm, decision))
    if applied:
        set_granted(pid, now_granted)
        set_denied(pid, now_denied)
    return applied


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
    pid = package_id(folder)
    ask = []
    try:
        from . import lockdown
        if not lockdown.enabled():                          # on a locked-down system nothing is ever asked: what is not allowed is refused
            ask = askable(folder, meta)
    except Exception:                                      # noqa: BLE001
        ask = []
    decisions = None
    if ask:
        os.makedirs(os.path.join("files", "tmp"), exist_ok=True)
        decisions = os.path.abspath(os.path.join("files", "tmp", f".perm-{os.getpid()}-{abs(hash(pid)) % 100000}.json"))
        try:
            os.remove(decisions)                            # an answer left over from a run that never reached apply_decisions
        except OSError:
            pass
        env["PYOS_PERM_DECISIONS"], env["PYOS_PERM_PACKAGE"], env["PYOS_PERM_ASK"] = decisions, pid, ",".join(ask)
    try:
        from . import limits
        held = limits.for_package(package_id(folder), meta)
    except Exception:
        held = {"memory_mb": 0, "cpu_seconds": 0}
    cmd = [sys.executable, runner, "--perms", ",".join(effective(folder, meta)), "--dir", os.path.abspath(folder),
           "--id", pid, "--mem-mb", str(held["memory_mb"]), "--cpu-seconds", str(held["cpu_seconds"])]
    if ask:
        cmd += ["--ask", ",".join(ask), "--decisions", decisions, "--texts", json.dumps(prompt_texts(), ensure_ascii=False)]
    cmd += ["--", os.path.abspath(script_path), *(args or [])]
    return cmd, env
