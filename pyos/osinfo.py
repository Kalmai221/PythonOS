# pyos/osinfo.py - what this computer is, in words: the operating system's name and the processor's model
#
# Two optional libraries make the answers better and neither is needed:
#   distro        the name and version of a Linux distribution ("Alpine Linux v3.19", "Ubuntu 24.04 LTS"); without it /etc/os-release is read,
#                 which every modern distribution (and the PythonOS ISO) has
#   py-cpuinfo    the brand of the processor on Windows and Android, where there is no /proc/cpuinfo; without it Linux reads /proc/cpuinfo
#                 and the other systems say what the platform module knows
# While lockdown is on nothing here starts a program (py-cpuinfo can), and a library that hangs is given a few seconds and then left alone.
import os
import platform
import threading

from . import lockdown, optional

_cache = {}


def _os_release():
    """The fields of /etc/os-release as a dict (empty when there is none)."""
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                fields = {}
                for line in f:
                    key, sep, value = line.strip().partition("=")
                    if sep and key:
                        fields[key] = value.strip().strip('"').strip("'")
                return fields
        except OSError:
            continue
    return {}


def distribution():
    """The operating system's name for people: 'Alpine Linux v3.19.4', 'Ubuntu 24.04 LTS', 'Windows 11', 'Android 14'."""
    if "distribution" in _cache:
        return _cache["distribution"]
    name = ""
    system = platform.system()
    if system == "Linux":
        library = optional.get("distro")
        if library is not None and not lockdown.enabled():
            try:
                name = library.name(pretty=True)
            except Exception:                                   # noqa: BLE001 - the library is a nicety
                name = ""
        if not name:
            fields = _os_release()
            name = fields.get("PRETTY_NAME") or " ".join(x for x in (fields.get("NAME"), fields.get("VERSION_ID")) if x)
        if (not name or name == "Linux") and (os.environ.get("ANDROID_ROOT") or os.path.exists("/system/build.prop")):
            name = "Android"
    elif system == "Windows":
        name = f"Windows {platform.release()}".strip()
    elif system == "Darwin":
        name = f"macOS {platform.mac_ver()[0]}".strip()
    _cache["distribution"] = name or system or "unknown"
    return _cache["distribution"]


def _proc_cpuinfo():
    """The processor model from /proc/cpuinfo ('' where there is none)."""
    try:
        with open("/proc/cpuinfo", encoding="utf-8", errors="replace") as f:
            for line in f:
                key, _sep, value = line.partition(":")
                if key.strip().lower() in ("model name", "hardware", "cpu model", "model") and value.strip():
                    return " ".join(value.split())
    except OSError:
        pass
    return ""


def _library_cpu():
    """py-cpuinfo's answer ({} if it is missing, locked out, slow or fails). It reads the registry or runs system tools, so it gets a few seconds."""
    library = optional.get("cpuinfo")
    if library is None or lockdown.enabled():
        return {}
    box = {}

    def work():
        try:
            box["info"] = library.get_cpu_info()
        except Exception:                                       # noqa: BLE001
            box["info"] = {}
    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(8)
    return box.get("info") or {}


def cpu():
    """{'model': brand text, 'vendor': ..., 'cache': ...} for this processor; missing facts are ''."""
    if "cpu" in _cache:
        return _cache["cpu"]
    model = _proc_cpuinfo() if platform.system() == "Linux" else ""
    info = {}
    if not model or platform.system() != "Linux":
        info = _library_cpu()
        model = info.get("brand_raw") or model or platform.processor() or ""
    _cache["cpu"] = {"model": " ".join(str(model).split()), "vendor": str(info.get("vendor_id_raw") or ""),
                     "cache": str(info.get("l3_cache_size") or info.get("l2_cache_size") or "")}
    return _cache["cpu"]
