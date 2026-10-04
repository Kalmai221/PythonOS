# pyos/notify.py - notifications shown before the next prompt and kept in a history.
#
# Anything can call notify(): background jobs, the scheduler, the updater, the marketplace.
# Notifications are stored in .OSData/notifications.json, so they also survive a restart.
import json
import os
import threading
import time

from . import settings

QUEUE_FILE = os.path.join(".OSData", "notifications.json")
MAX_KEPT = 200
_lock = threading.Lock()
_next_id = [0]


def _load():
    try:
        with open(QUEUE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(items):
    os.makedirs(os.path.dirname(QUEUE_FILE), exist_ok=True)
    tmp = QUEUE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items[-MAX_KEPT:], f)
    os.replace(tmp, QUEUE_FILE)


def notify(message, title="PythonOS", level="info", user=None):
    """Add a notification. user=None means everyone. level: info | success | warn | error."""
    with _lock:
        items = _load()
        _next_id[0] = max([_next_id[0]] + [i.get("id", 0) for i in items]) + 1
        items.append({"id": _next_id[0], "time": time.time(), "title": title, "message": message,
                      "level": level, "user": user, "shown": False})
        _save(items)
    return _next_id[0]


def _mine(item, user):
    return item.get("user") in (None, user)


def pending(user=None):
    """Notifications not shown yet for this user."""
    with _lock:
        return [i for i in _load() if not i.get("shown") and _mine(i, user)]


def take_pending(user=None):
    """Return the unshown notifications and mark them shown (nothing is shown if they are switched off)."""
    with _lock:
        items = _load()
        fresh = [i for i in items if not i.get("shown") and _mine(i, user)]
        for i in fresh:
            i["shown"] = True
        if fresh:
            _save(items)
    return fresh if settings.get("notifications") else []


def history(user=None, limit=50):
    with _lock:
        return [i for i in _load() if _mine(i, user)][-limit:]


def clear(user=None):
    with _lock:
        items = [i for i in _load() if not _mine(i, user)]
        _save(items)
