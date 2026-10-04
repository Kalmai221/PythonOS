# pyos/settings.py - system settings (theme, prompt, boot speed, ...) stored in .OSData/settings.json
import json
import os
import threading

SETTINGS_FILE = os.path.join(".OSData", "settings.json")
_lock = threading.Lock()
_cache = {"mtime": None, "data": None}

# key -> (default, allowed values or type, description)
SCHEMA = {
    "theme": ("default", ("default", "ocean", "forest", "sunset", "mono", "contrast"), "Colour theme"),
    "prompt_style": ("full", ("full", "short", "minimal"), "Prompt: full user@host:path$, short path$, or minimal $"),
    "boot_speed": ("normal", ("normal", "fast", "instant"), "How long the boot animation takes"),
    "clock_24h": (True, bool, "Show times as 24-hour (off = 12-hour)"),
    "notifications": (True, bool, "Show notifications before the prompt"),
    "update_check": (True, bool, "Check for PythonOS updates in the background after login"),
    "auto_lock_minutes": (0, int, "Ask for the password again after this many idle minutes (0 = never)"),
    "confirm_delete": (True, bool, "Ask before rm removes a folder"),
}


def defaults():
    return {key: spec[0] for key, spec in SCHEMA.items()}


def _read():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            stored = json.load(f)
        return stored if isinstance(stored, dict) else {}
    except (OSError, ValueError):
        return {}


def load():
    """All settings (stored values over the defaults)."""
    with _lock:
        try:
            mtime = os.path.getmtime(SETTINGS_FILE)
        except OSError:
            mtime = None
        if _cache["data"] is None or _cache["mtime"] != mtime:
            data = defaults()
            for key, value in _read().items():
                if key in SCHEMA and _valid(key, value):
                    data[key] = value
            _cache.update(mtime=mtime, data=data)
        return dict(_cache["data"])


def get(key):
    return load()[key]


def _valid(key, value):
    allowed = SCHEMA[key][1]
    if allowed is bool:
        return isinstance(value, bool)
    if allowed is int:
        return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 24 * 60
    return value in allowed


def parse_value(key, text):
    """Turn what the user typed into a value for `key`. Raises ValueError with a helpful message."""
    if key not in SCHEMA:
        raise ValueError(f"unknown setting '{key}' (try: {', '.join(SCHEMA)})")
    allowed = SCHEMA[key][1]
    text = str(text).strip().lower()
    if allowed is bool:
        if text in ("on", "true", "yes", "1"):
            return True
        if text in ("off", "false", "no", "0"):
            return False
        raise ValueError(f"{key} must be on or off")
    if allowed is int:
        if not text.isdigit() or int(text) > 24 * 60:
            raise ValueError(f"{key} must be a whole number of minutes (0 to 1440)")
        return int(text)
    if text not in allowed:
        raise ValueError(f"{key} must be one of: {', '.join(allowed)}")
    return text


def set(key, value):  # noqa: A001 - mirrors dict-style API
    """Validate and save one setting."""
    if key not in SCHEMA:
        raise ValueError(f"unknown setting '{key}'")
    if not _valid(key, value):
        raise ValueError(f"invalid value for {key}: {value!r}")
    with _lock:
        stored = _read()
        stored[key] = value
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        tmp = SETTINGS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(stored, f, indent=2)
        os.replace(tmp, SETTINGS_FILE)
        _cache["data"] = None


def reset(key=None):
    with _lock:
        stored = _read()
        if key is None:
            stored = {}
        else:
            stored.pop(key, None)
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(stored, f, indent=2)
        _cache["data"] = None


def boot_pause():
    """Seconds to pause between boot steps for the chosen boot speed."""
    return {"normal": 0.35, "fast": 0.1, "instant": 0.0}[get("boot_speed")]


def format_time(dt):
    """Format a datetime as 24-hour or 12-hour according to the clock setting."""
    return dt.strftime("%H:%M:%S") if get("clock_24h") else dt.strftime("%I:%M:%S %p").lstrip("0")
