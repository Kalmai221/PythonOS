# pyos/appsettings.py - options an installed app offers, shown together under `settings app`
#
# An app lists its options in data.json:
#   "settings": [{"key": "units", "label": "Units", "type": "choice", "choices": ["metric", "imperial"], "default": "metric"},
#                {"key": "show_hints", "label": "Show hints", "type": "bool", "default": true},
#                {"key": "seconds", "label": "Round length", "type": "int", "min": 10, "max": 300, "default": 60},
#                {"key": "city", "label": "Home city", "type": "text", "default": ""}]
# Values are saved per user in ~/.config/appsettings.json. An app reads its own with get("games/tetris", "key", default):
# the OS's own copy of `settings app` and the app therefore always agree, and the app never has to build a settings screen.
import json
import os

FILE = "appsettings"
TYPES = ("bool", "int", "choice", "text")


def schema(meta):
    """The valid option entries of a package's data.json (bad ones are ignored)."""
    result = []
    for entry in (meta or {}).get("settings") or []:
        if not isinstance(entry, dict) or not isinstance(entry.get("key"), str) or entry.get("type") not in TYPES:
            continue
        if entry["type"] == "choice" and not entry.get("choices"):
            continue
        result.append(entry)
    return result


def _load(user=None):
    from pyos import appdata
    data = appdata.load(FILE, {}, user=user)
    return data if isinstance(data, dict) else {}


def _save(data, user=None):
    from pyos import appdata
    appdata.save(FILE, data, user=user)


def parse(entry, text):
    """The value a user typed for an option, checked against its type. Raises ValueError with a readable message."""
    text = str(text).strip()
    kind = entry["type"]
    if kind == "bool":
        if text.lower() in ("on", "true", "yes", "1"):
            return True
        if text.lower() in ("off", "false", "no", "0"):
            return False
        raise ValueError("use on or off")
    if kind == "int":
        try:
            number = int(text)
        except ValueError:
            raise ValueError("use a whole number") from None
        low, high = entry.get("min"), entry.get("max")
        if (low is not None and number < low) or (high is not None and number > high):
            raise ValueError(f"use a number from {low if low is not None else 'any'} to {high if high is not None else 'any'}")
        return number
    if kind == "choice":
        for choice in entry["choices"]:
            if str(choice).lower() == text.lower():
                return choice
        raise ValueError("choose one of: " + ", ".join(str(c) for c in entry["choices"]))
    return text[:200]


def values(pkg_id, meta, user=None):
    """{key: value} for every option of the package: what the user chose, else the app's default."""
    saved = _load(user).get(pkg_id, {})
    result = {}
    for entry in schema(meta):
        result[entry["key"]] = saved.get(entry["key"], entry.get("default"))
    return result


def set_value(pkg_id, entry, text, user=None):
    value = parse(entry, text)
    data = _load(user)
    data.setdefault(pkg_id, {})[entry["key"]] = value
    _save(data, user)
    return value


def reset(pkg_id, key=None, user=None):
    data = _load(user)
    if key:
        data.get(pkg_id, {}).pop(key, None)
    else:
        data.pop(pkg_id, None)
    _save(data, user)


def get(pkg_id, key, default=None, user=None):
    """For apps: the user's value of one of the app's options (or `default` when none was chosen)."""
    try:
        return _load(user).get(pkg_id, {}).get(key, default)
    except Exception:
        return default
