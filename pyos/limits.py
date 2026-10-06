"""Resource limits for apps: how much memory and CPU time one marketplace app may use.

An app runs as a process of its own (see sandbox.py), so the system can hold it to a limit. What the limit is, most specific first:
  1. what the user set:                 limits set <app> memory 128      (stored in .OSData/app_limits.json)
  2. what the app declares:             "limits": {"memory_mb": 64, "cpu_seconds": 30} in its data.json
  3. the system default:                a share of PythonOS's own memory (setting app_memory_percent, 25% unless changed)
0 means no limit. An app that goes over its memory limit is stopped with a message that says so (sandbox_run.py enforces it: the system
caps the process on Windows and Linux, and a watchdog covers the rest). CPU time is the seconds of processor time the app has used, not
the time it has been open.
"""
import json
import os
import threading

FILE = os.path.join(".OSData", "app_limits.json")
KEYS = {"memory": "memory_mb", "cpu": "cpu_seconds"}
MIN_DEFAULT_MB = 64
_lock = threading.Lock()


def _read():
    try:
        with open(FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(data):
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    tmp = FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, FILE)


def default_memory_mb():
    """The system default: a share of the memory PythonOS owns (0 = no limit)."""
    try:
        from pyos import resources, settings
        share = int(settings.get("app_memory_percent"))
        if share <= 0:
            return 0
        budget_mb = resources.budget() // resources.MB
        return max(MIN_DEFAULT_MB, budget_mb * min(share, 100) // 100) if budget_mb else 0
    except Exception:
        return 0


def _number(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def for_package(pid, meta=None):
    """{'memory_mb', 'cpu_seconds', 'source': {'memory': 'you'|'app'|'default', 'cpu': ...}} for one app."""
    mine = _read().get(pid, {}) if isinstance(_read().get(pid, {}), dict) else {}
    declared = (meta or {}).get("limits") if isinstance((meta or {}).get("limits"), dict) else {}
    out = {"source": {}}
    for name, key in KEYS.items():
        value, source = _number(mine.get(key)), "you"
        if value is None:
            value, source = _number(declared.get(key)), "app"
        if value is None:
            value, source = (default_memory_mb() if name == "memory" else 0), "default"
        out[key], out["source"][name] = value, source
    return out


def set_limit(pid, kind, value):
    """Set one limit for one app (kind 'memory' or 'cpu'; value 0 = no limit). Raises ValueError for anything else."""
    if kind not in KEYS:
        raise ValueError("the limits are: memory (MB) and cpu (seconds)")
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("a limit is a whole number (0 = no limit)")
    if kind == "memory" and 0 < value < 16:
        raise ValueError("a memory limit under 16 MB would stop the app before it starts")
    with _lock:
        data = _read()
        data.setdefault(pid, {})[KEYS[kind]] = value
        _write(data)


def reset(pid, kind=None):
    """Back to the app's own limit or the system default (one limit, or both)."""
    with _lock:
        data = _read()
        if kind is None:
            data.pop(pid, None)
        else:
            data.get(pid, {}).pop(KEYS[kind], None)
        _write(data)


def overrides():
    return _read()
