# pyos/session.py - did the last run end properly?
#
# Boot writes .OSData/session.json saying "running". A normal shutdown or restart (and a crash screen) changes it to
# "clean" or "crashed". If the next boot finds "running", the power was cut, the window was closed or the process was killed:
# that is an unexpected shutdown. The boot log notes it, and `whathappened` (core/whathappened.py) tells the user what was
# going on, using the last lines of the system log.
import json
import os
import time

FILE = os.path.join(".OSData", "session.json")


def _read():
    try:
        with open(FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(data):
    try:
        os.makedirs(".OSData", exist_ok=True)
        tmp = FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, FILE)
    except OSError:
        pass


def begin():
    """Called once per boot. Returns what happened to the previous run: {"state": "first"|"clean"|"crashed"|"unexpected", ...}."""
    before = _read()
    if not before:
        state = "first"
    else:
        state = {"clean": "clean", "crashed": "crashed"}.get(before.get("state"), "unexpected")
    previous = dict(before, state=state)
    _write({"state": "running", "started": time.time(), "pid": os.getpid(), "previous": {"state": state, "started": before.get("started"),
                                                                                       "ended": before.get("ended"), "code": before.get("code")}})
    return previous


def previous():
    """What happened to the run before this one (as recorded at this boot), or {}."""
    return _read().get("previous") or {}


def end(state="clean", code=None):
    """Called when PythonOS stops on purpose (shutdown, restart) or after a crash screen."""
    data = _read()
    data.update(state=state, ended=time.time())
    if code:
        data["code"] = code
    _write(data)
