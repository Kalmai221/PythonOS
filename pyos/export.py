# pyos/export.py - which export (APK, Windows app, Linux package, ISO) this copy of PythonOS runs in.
#
# PythonOS updates its own core, but not the package around it (the APK and its terminal screen, the
# Windows launcher and bundled Python, the Linux launcher, the ISO's kernel and boot setup). Each export
# embeds a small identity: {"platform": ..., "version": ..., "api": ...}. The updater compares it with the
# latest release to tell the user when a new package must be installed by hand (core/sysupdate.py).
import json
import os

TITLES = {"android": "Android app (APK)", "windows": "Windows app", "linux": "Linux package", "iso": "bootable ISO"}


def _guess_platform():
    """Older packages (v1.0.0) shipped without an identity file; work out what they must be."""
    if os.environ.get("PYOS_LIVE") == "1":
        return "iso"
    if "ANDROID_DATA" in os.environ or "ANDROID_ROOT" in os.environ:
        return "android"
    return "windows" if os.name == "nt" else "linux"


def info():
    """{"platform", "version", "api"} for a packaged build, or None for a plain source checkout."""
    raw = os.environ.get("PYOS_EXPORT")
    if raw:
        try:
            data = json.loads(raw)
            if data.get("platform"):
                return _clean(data)
        except ValueError:
            pass
    path = os.environ.get("PYOS_EXPORT_INFO") or "export.json"
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("platform"):
            return _clean(data)
    except (OSError, ValueError):
        pass
    if os.path.isfile("VERSION"):      # packaged, but built before identities existed (v1.0.0)
        return {"platform": _guess_platform(), "version": "1.0.0", "api": 1}
    return None


def _clean(data):
    return {"platform": str(data["platform"]), "version": str(data.get("version", "1.0.0")), "api": int(data.get("api", 1))}


def title(platform):
    return TITLES.get(platform, platform)


def current():
    """The export this copy runs in ("android", "windows", "linux" or "iso"), or None from a source checkout (nothing is restricted there)."""
    found = info()
    return found["platform"] if found else None


def valid_exports(value):
    """A list of export names, or None for "all of them". Raises ValueError for anything else."""
    if value is None:
        return None
    if not isinstance(value, list) or not value or any(x not in TITLES for x in value):
        raise ValueError("'exports' must be a list made of: " + ", ".join(TITLES))
    return list(value)


def runs_here(exports, platform=None):
    """Whether something limited to `exports` (None = every export) works in this export. A source checkout runs everything."""
    platform = platform or current()
    return exports is None or platform is None or platform in exports


def where(exports):
    """"the Windows app and the bootable ISO" for a list of exports ("every export" for None)."""
    if not exports:
        return "every export"
    names = [TITLES[x] for x in exports]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
