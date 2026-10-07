# pyos/settings.py - system settings (theme, prompt, boot speed, ...) stored in .OSData/settings.json
import json
import os
import re
import threading

SETTINGS_FILE = os.path.join(".OSData", "settings.json")
USER_FILE = os.path.join(".OSData", "user_settings.json")     # per-user overrides of PER_USER settings
PER_USER = ("auto_lock_minutes", "idle_logout_minutes")
_lock = threading.Lock()
_cache = {"mtime": None, "data": None}

# key -> (default, allowed values or type, description)
SCHEMA = {
    "language": ("auto", ("auto", "en", "es", "fr", "de"), "Language of the system's own messages (auto = follow the computer; commands stay in English)"),
    "theme": ("default", ("default", "ocean", "forest", "sunset", "mono", "contrast"), "Colour theme"),
    "prompt_style": ("full", ("full", "short", "minimal"), "Prompt: full user@host:path$, short path$, or minimal $"),
    "clock_24h": (True, bool, "Show times as 24-hour (off = 12-hour)"),
    "notifications": (True, bool, "Show notifications before the prompt"),
    "update_check": (True, bool, "Check for PythonOS updates in the background after login"),
    "market_update_check": (True, bool, "Check once a day for updates to installed apps and tell you (a notification)"),
    "auto_lock_minutes": (0, int, "Ask for the password again after this many idle minutes (0 = never)"),
    "idle_logout_minutes": (0, int, "Log out (back to the login screen) after this many idle minutes (0 = never)"),
    "clear_screens": (True, bool, "Clear the screen when a full-screen program or menu starts, and tidy it after one that printed a lot"),
    "clear_style": ("overflow", ("off", "overflow", "always"), "Clear the screen before a command: off, overflow (when the last output filled the screen) or always (every command)"),
    "auto_page": (True, bool, "Show long output of listing commands (ls, cat, man, history...) one screen at a time, so nothing scrolls out of sight (the Linux console has no scrollback)"),
    "fancy_prompt": (True, bool, "The enhanced prompt: Ctrl+R searches your history, suggestions from your history appear in grey (Right arrow accepts), Tab shows a menu, commands are coloured (off = the plain prompt)"),
    "prompt_keys": ("emacs", ("emacs", "vi"), "Keys of the prompt: emacs (Ctrl+A, Ctrl+E, Ctrl+R...) or vi"),
    "auto_clear_lines": (300, int, "Tidy the screen before a prompt once this many lines have piled up (0 = never)"),
    "confirm_delete": (True, bool, "Ask before rm removes a folder"),
    "report_relay": ("", str, "https:// address of a relay that files problem reports as GitHub issues (empty = no relay; GitHub and Discord are separate ways)"),
    "memory_limit_mb": (1024, int, "Memory PythonOS owns, in MB: it is the whole computer as far as PythonOS is concerned (0 = all of the machine's memory; applies right away; the live ISO always uses all of it)"),
    "app_memory_percent": (25, int, "How much of PythonOS's memory one app may use, in percent (0 = no limit); an app over its limit is stopped. Per-app: limits"),
    "light_mode": (False, bool, "Light mode: skip background checks and long animations (switched on by itself on computers with little memory)"),
    "low_battery_percent": (15, int, "Warn when the battery falls to this percent and is not charging (0 = never)"),
    "critical_battery_percent": (5, int, "Shut down cleanly when the battery falls to this percent and is not charging (0 = never)"),
    "admin_reauth": (True, bool, "Ask administrators for their password again before risky actions (delete account, change role, wipe)"),
    "use_trash": (True, bool, "rm moves things to the trash (restore with undo or trash restore) instead of deleting them"),
    "trash_days": (30, int, "Empty items from the trash after this many days (0 = keep until emptied)"),
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


def is_set(key):
    """True when the setting was chosen explicitly (by the user or by an installer), not just the default."""
    return key in _read()


def _custom_theme_name(value):
    """'custom:name' - one of the user's own themes (made with the Theme Designer app)."""
    return isinstance(value, str) and value.startswith("custom:") and re.fullmatch(r"[A-Za-z0-9_-]{1,20}", value[7:]) is not None


INT_RANGE = {"memory_limit_mb": (0, 1 << 20)}          # every other whole-number setting is a number of minutes (0 to 1440)


def int_range(key):
    return INT_RANGE.get(key, (0, 24 * 60))


def _valid(key, value):
    allowed = SCHEMA[key][1]
    if allowed is bool:
        return isinstance(value, bool)
    if allowed is str:
        return isinstance(value, str) and len(value) <= 300 and (value == "" or value.startswith("https://"))
    if allowed is int:
        low, high = int_range(key)
        return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high
    if key == "theme" and _custom_theme_name(value):
        return True
    return value in allowed


def parse_value(key, text):
    """Turn what the user typed into a value for `key`. Raises ValueError with a helpful message."""
    if key not in SCHEMA:
        raise ValueError(f"unknown setting '{key}' (try: {', '.join(SCHEMA)})")
    allowed = SCHEMA[key][1]
    if allowed is str:
        text = str(text).strip()
        if text.lower() in ("none", "off", "-"):
            return ""
        if text and not text.startswith("https://"):
            raise ValueError(f"{key} must start with https:// (or be 'none')")
        return text
    text = str(text).strip().lower()
    if allowed is bool:
        if text in ("on", "true", "yes", "1"):
            return True
        if text in ("off", "false", "no", "0"):
            return False
        raise ValueError(f"{key} must be on or off")
    if allowed is int:
        low, high = int_range(key)
        if not text.isdigit() or not low <= int(text) <= high:
            raise ValueError(f"{key} must be a whole number of {'MB' if key.endswith('_mb') else 'minutes'} ({low} to {high})")
        return int(text)
    if key == "theme" and _custom_theme_name(text):
        return text
    if text not in allowed:
        raise ValueError(f"{key} must be one of: {', '.join(allowed)}" + (" (or custom:<name> for a theme you made)" if key == "theme" else ""))
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


def _read_users():
    try:
        with open(USER_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def get_for(key, user):
    """The value of a setting for one user: their own override if they have one (PER_USER settings), else the system value."""
    if key in PER_USER and user:
        mine = _read_users().get(user, {})
        if key in mine and _valid(key, mine[key]):
            return mine[key]
    return get(key)


def set_for(key, value, user):
    """Give one user their own value of a PER_USER setting."""
    if key not in PER_USER:
        raise ValueError(f"{key} is a system-wide setting (per-user: {', '.join(PER_USER)})")
    if not _valid(key, value):
        raise ValueError(f"invalid value for {key}: {value!r}")
    with _lock:
        data = _read_users()
        data.setdefault(user, {})[key] = value
        os.makedirs(os.path.dirname(USER_FILE), exist_ok=True)
        with open(USER_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)


def reset_for(key, user):
    with _lock:
        data = _read_users()
        if user in data:
            data[user].pop(key, None)
            if not data[user]:
                data.pop(user)
            with open(USER_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)


BOOT_PAUSE = 0.1


def boot_pause():
    """Seconds to pause between boot steps (a fixed, short pause so the log can be read as it goes)."""
    if get("light_mode") or os.environ.get("PYOS_LIGHT") == "1":
        return 0.0                                    # light mode: no animation delays
    return BOOT_PAUSE


def format_time(dt):
    """Format a datetime as 24-hour or 12-hour according to the clock setting."""
    return dt.strftime("%H:%M:%S") if get("clock_24h") else dt.strftime("%I:%M:%S %p").lstrip("0")
