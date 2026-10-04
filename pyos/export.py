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
