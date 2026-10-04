# pyos/appdata.py - small per-user JSON storage for apps and features.
#
# Data lives in the user's home as ~/.config/<name>.json, so it is visible, easy to back up (see the
# `backup` command) and private to each user. Apps that may also run outside PythonOS should import
# this with a fallback to a local file.
import json
import os

BASE_DIR = os.path.abspath("files")


def _user():
    try:
        with open("current_user.json", encoding="utf-8") as f:
            return json.load(f).get("username")
    except (OSError, ValueError):
        return None


def path(name, user=None):
    user = user or _user()
    folder = os.path.join(BASE_DIR, "home", user, ".config") if user else os.path.join(BASE_DIR, ".config")
    return os.path.join(folder, f"{name}.json")


def load(name, default=None, user=None):
    try:
        with open(path(name, user), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save(name, data, user=None):
    target = path(name, user)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    tmp = target + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, target)
