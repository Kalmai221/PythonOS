# pyos/extras.py - the optional libraries (requirements-extra.txt), and which of them this copy of PythonOS has
#
# PythonOS works without any of them; each one adds something (a better "did you mean", .7z archives, the name of the Linux distribution, ...).
# The person chooses which to have:
#   * the Windows installers and the first-time setup ask (everything ticked by default), and the `extras` command changes the choice any time
#   * the choice is kept in .OSData/extras.json:  {"mode": "all" | "custom" | "none", "selected": [names]}
#       all     every library in the list, including ones a later update adds
#       custom  exactly the ones in "selected"; a library a later update adds is offered (extras) but not installed
#       none    none
#     with no file the old behaviour holds: the exports that install libraries themselves (Windows, Linux, Docker) have all of them, and the live
#     ISO has only what is on the disc until the person is asked
#   * how a library is installed depends on the system: pip (Windows, Linux, Docker, a source checkout) or Alpine's apk (the ISO and virtual
#     machines, which have no pip). The Android app carries its libraries inside and cannot add more.
# Nothing here starts a program itself: it asks core.hardware.run, and nothing is done while lockdown is on.
import importlib.util
import json
import os
import re
import sys

from . import export, lockdown

LIST_FILE = "requirements-extra.txt"
CHOICE_FILE = os.path.join(".OSData", "extras.json")            # for the whole system: the installers write it before any account exists
IMPORT_NAMES = {"python-dateutil": "dateutil", "beautifulsoup4": "bs4", "pyyaml": "yaml", "pillow": "PIL", "pypdf2": "PyPDF2",
                "python-docx": "docx", "opencv-python": "cv2", "scikit-learn": "sklearn", "python-magic": "magic",
                "py-cpuinfo": "cpuinfo", "dnspython": "dns", "charset-normalizer": "charset_normalizer"}
# the package names Alpine uses for the libraries (the ISO and virtual machines); one that Alpine does not have is simply not offered there
APK_NAMES = {"python-dateutil": "py3-dateutil", "humanize": "py3-humanize", "zxcvbn": "py3-zxcvbn", "filetype": "py3-filetype",
             "beautifulsoup4": "py3-beautifulsoup4", "pyyaml": "py3-yaml", "rapidfuzz": "py3-rapidfuzz", "feedparser": "py3-feedparser",
             "charset-normalizer": "py3-charset-normalizer", "py7zr": "py3-py7zr", "distro": "py3-distro", "py-cpuinfo": "py3-cpuinfo",
             "watchfiles": "py3-watchfiles", "dnspython": "py3-dnspython"}
MODES = ("all", "custom", "none")


class Extra:
    def __init__(self, name, requirement, marker, description):
        self.name, self.requirement, self.marker, self.description = name, requirement, marker, description

    @property
    def module(self):
        return IMPORT_NAMES.get(self.name.lower(), self.name.lower().replace("-", "_"))

    def installed(self):
        try:
            return importlib.util.find_spec(self.module) is not None
        except (ImportError, ValueError):
            return False

    def applies(self, version=None):
        """False when the list says this library is not for this Python (a marker such as python_version < "3.14")."""
        if not self.marker:
            return True
        found = re.fullmatch(r'\s*python_version\s*(<=|>=|<|>|==|!=)\s*["\']([\d.]+)["\']\s*', self.marker)
        if not found:
            return True                                             # a marker this reader does not know: leave the decision to pip
        here = tuple(version or sys.version_info[:2])[:2]
        parts = [int(x) for x in found.group(2).split(".")][:2]
        there = tuple(parts + [0] * (2 - len(parts)))
        return {"<": here < there, "<=": here <= there, ">": here > there, ">=": here >= there, "==": here == there, "!=": here != there}[found.group(1)]


def list_path():
    for base in (os.getcwd(), os.path.dirname(os.path.dirname(os.path.abspath(__file__)))):
        path = os.path.join(base, LIST_FILE)
        if os.path.isfile(path):
            return path
    return None


def parse(text):
    """[Extra] from the text of requirements-extra.txt: 'name; marker  # what it adds'."""
    found = []
    for line in text.splitlines():
        body, _hash, comment = line.partition("#")
        body = body.strip()
        if not body:
            continue
        requirement, _semi, marker = body.partition(";")
        name = re.split(r"[<>=!~\[ ]", requirement.strip(), maxsplit=1)[0]
        if name:
            found.append(Extra(name, body, marker.strip(), comment.strip()))
    return found


def catalog():
    """Every optional library in the list that applies to this Python."""
    path = list_path()
    if not path:
        return []
    try:
        with open(path, encoding="utf-8") as f:
            return [e for e in parse(f.read()) if e.applies()]
    except OSError:
        return []


def backend():
    """'pip', 'apk' (the ISO and virtual machines) or None (the Android app cannot add libraries)."""
    here = export.current()
    if here == "android":
        return None
    if here == "iso" or os.environ.get("PYOS_LIVE") == "1" or os.environ.get("PYOS_INSTALLED") == "1":
        return "apk"
    return "pip"


# ---- the choice

def _read():
    try:
        with open(CHOICE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def load_choice():
    """{'mode', 'selected'} as saved, or None when the person has not chosen (and no installer chose for them)."""
    data = _read()
    if data.get("mode") in MODES:
        return {"mode": data["mode"], "selected": [str(x) for x in data.get("selected") or []]}
    return None


def save_choice(mode, selected=(), declined=None):
    """Remember the choice. `declined` are libraries the person was offered after an update and said no to (so they are not offered again)."""
    if mode not in MODES:
        raise ValueError(mode)
    data = {"mode": mode, "selected": sorted(set(selected)) if mode == "custom" else []}
    old = _read().get("declined") or []
    data["declined"] = sorted(set(declined if declined is not None else old))
    os.makedirs(os.path.dirname(CHOICE_FILE), exist_ok=True)
    tmp = CHOICE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, CHOICE_FILE)


def wanted(extras=None):
    """The libraries this copy should have, by name."""
    extras = catalog() if extras is None else extras
    names = [e.name for e in extras]
    choice = load_choice()
    if choice is None:
        return names if backend() == "pip" else []
    if choice["mode"] == "all":
        return names
    if choice["mode"] == "none":
        return []
    return [n for n in names if n in choice["selected"]]


def undecided(extras=None):
    """True when the person should be asked: nothing chosen yet, something is missing, and it can be installed here."""
    extras = catalog() if extras is None else extras
    return load_choice() is None and backend() is not None and any(not e.installed() for e in extras)


def new_since_choice(extras=None):
    """Libraries the list has that a 'custom' choice does not include: offered by `extras`, never installed without being asked."""
    choice = load_choice()
    if choice is None or choice["mode"] != "custom":
        return []
    extras = catalog() if extras is None else extras
    seen = set(choice["selected"]) | set(_read().get("declined") or [])
    return [e for e in extras if e.name not in seen and not e.installed()]


# ---- installing

def _run(command, timeout=900):
    from core import hardware
    return hardware.run(command, timeout=timeout, merge=True)


def _apk_online(say):
    """Make sure Alpine's online repositories are in the list (the disc has only what it was built with)."""
    from core import installer
    code, _out = _run(["apk", "update"], 120)
    if code == 0:
        return True
    try:
        with open(installer.REPOSITORIES, encoding="utf-8") as f:
            lines = [l for l in f.read().splitlines() if l.strip()]
        branch = installer._alpine_branch()
        for repo in ("main", "community"):
            url = f"{installer.MIRROR}/{branch}/{repo}"
            if url not in lines:
                lines.append(url)
        with open(installer.REPOSITORIES, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except OSError:
        return False
    say("Using Alpine's online package repositories")
    return _run(["apk", "update"], 180)[0] == 0


def apk_available(extra):
    code, out = _run(["apk", "search", "-e", APK_NAMES.get(extra.name, "")], 60) if extra.name in APK_NAMES else (1, "")
    return code == 0 and bool(out.strip())


def install(names, say=print):
    """Install libraries by name. Returns ({name: True/False}, why-not text or ''). Never raises for a failed install."""
    if lockdown.enabled():
        return {}, "installing is switched off while lockdown is on"
    how = backend()
    if how is None:
        return {}, "this app carries its libraries inside and cannot add more"
    extras = {e.name: e for e in catalog()}
    wanted_list = [extras[n] for n in names if n in extras]
    results = {}
    if how == "apk":
        if not _apk_online(say):
            return {}, "the package repositories cannot be reached (connect to the internet first: hwsetup network)"
        for extra in wanted_list:
            if extra.installed():
                results[extra.name] = True
            elif not apk_available(extra):
                results[extra.name] = False
            else:
                say(f"Installing {extra.name}...")
                results[extra.name] = _run(["apk", "add", "--quiet", APK_NAMES[extra.name]], 600)[0] == 0
        return results, ""
    for extra in wanted_list:
        if extra.installed():
            results[extra.name] = True
            continue
        say(f"Installing {extra.name}...")
        code, _out = _run([sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--no-input", "--no-warn-script-location",
                           extra.requirement], 600)
        results[extra.name] = code == 0
    return results, ""


def remove(names, say=print):
    if lockdown.enabled():
        return {}, "removing is switched off while lockdown is on"
    how = backend()
    if how is None:
        return {}, "this app carries its libraries inside"
    extras = {e.name: e for e in catalog()}
    results = {}
    for name in names:
        extra = extras.get(name)
        if extra is None:
            continue
        say(f"Removing {name}...")
        command = ["apk", "del", "--quiet", APK_NAMES.get(name, "")] if how == "apk" else [sys.executable, "-m", "pip", "uninstall", "-y", name]
        results[name] = _run(command, 300)[0] == 0
    return results, ""


def sync(say=print):
    """Install what the choice says is missing (after an update, or after the choice changed). ({name: ok}, why-not)."""
    missing = [e.name for e in catalog() if e.name in wanted() and not e.installed()]
    return install(missing, say) if missing else ({}, "")
