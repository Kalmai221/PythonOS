# pyos/optional.py - optional libraries (requirements-extra.txt). PythonOS uses each one when it is installed and works without it.
import importlib

_cache = {}


def get(name):
    """The module `name` if it can be imported and is switched on, else None (remembered). In the Android app every optional library is inside,
    and the person's choice (the extras command, the first start) switches them on and off: see pyos/extras.py."""
    if _switched_off(name):
        return None
    if name not in _cache:
        try:
            _cache[name] = importlib.import_module(name)
        except Exception:                                  # noqa: BLE001 - missing, or broken on this system: just not available
            _cache[name] = None
    return _cache[name]


def _switched_off(name):
    try:
        from . import extras
        return extras.switched_off(name)
    except Exception:                                      # noqa: BLE001 - the switch never gets in the way of a library
        return False


def have(name):
    return get(name) is not None
