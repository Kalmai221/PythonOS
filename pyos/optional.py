# pyos/optional.py - optional libraries (requirements-extra.txt). PythonOS uses each one when it is installed and works without it.
import importlib

_cache = {}


def get(name):
    """The module `name` if it can be imported, else None (remembered)."""
    if name not in _cache:
        try:
            _cache[name] = importlib.import_module(name)
        except Exception:                                  # noqa: BLE001 - missing, or broken on this system: just not available
            _cache[name] = None
    return _cache[name]


def have(name):
    return get(name) is not None
