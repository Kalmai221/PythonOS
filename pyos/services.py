"""PythonOS's background services: what runs while someone is signed in, and a way to stop, start and switch them off.

The shell defines each service (scheduler, idle watch, battery watch, memory guard, update checks, startup programs) when a user signs
in and starts the ones that are not switched off. They appear in the task list (taskman, ps) as services. `service` is the command that
manages them; this module is what it uses.

A service is a thread object with start() and, for one that keeps running, stop(). A "one-shot" service runs once and finishes (the
marketplace update check); it shows as "done" and can be run again with `service restart`.
"""
import json
import os
import threading

from . import tasks

STATE_FILE = os.path.join(".OSData", "services.json")
_defs = {}
_running = {}                 # name -> thread
_lock = threading.RLock()


class Service:
    def __init__(self, name, description, factory, oneshot=False, skip_in_light_mode=False, critical=False):
        self.name, self.description, self.factory = name, description, factory
        self.oneshot, self.skip_in_light_mode, self.critical = oneshot, skip_in_light_mode, critical


def define(name, description, factory, oneshot=False, skip_in_light_mode=False, critical=False):
    """Register a service. factory(user) returns a thread-like object (start() and, if it keeps running, stop()). critical ones ask for the
    administrator's password before they are stopped or switched off."""
    with _lock:
        _defs[name] = Service(name, description, factory, oneshot, skip_in_light_mode, critical)


def names():
    return list(_defs)


def get(name):
    return _defs.get(name)


# ---------------------------------------------------------------------------------------------- which are switched off
def _read():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def disabled():
    return [n for n in _read().get("disabled", []) if isinstance(n, str)]


def is_disabled(name):
    return name in disabled()


def set_disabled(name, off):
    """Switch a service off (it will not start at the next sign-in) or back on."""
    with _lock:
        data = _read()
        current = set(disabled())
        (current.add if off else current.discard)(name)
        data["disabled"] = sorted(current)
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, STATE_FILE)


# ---------------------------------------------------------------------------------------------- running
def instance(name):
    """The thread object of a running service, else None."""
    thread = _running.get(name)
    return thread if thread is not None and thread.is_alive() else None


def _task_of(thread):
    for task in tasks.services():
        if task.thread is thread:
            return task
    return None


def state(name):
    """'running', 'done' (a one-shot that finished), 'stopped' or 'disabled' (also stopped: it will not start at sign-in)."""
    if name not in _defs:
        return "unknown"
    if instance(name) is not None:
        return "running"
    if is_disabled(name):
        return "disabled"
    return "done" if _defs[name].oneshot and name in _running else "stopped"


def pid_of(name):
    thread = _running.get(name)
    task = _task_of(thread) if thread is not None else None
    return task.pid if task else None


def start(name, user):
    """Start a service now. Returns (ok, message)."""
    service = _defs.get(name)
    if service is None:
        return False, f"no such service: {name}"
    with _lock:
        if instance(name) is not None:
            return False, f"{name} is already running"
        try:
            thread = service.factory(user)
            thread.start()
        except Exception as e:
            from pyos import log
            log.log(f"service {name} could not start: {log.describe_exception(e)}", "ERROR", user=user)
            return False, f"{name} could not start: {e}"
        _running[name] = thread
        tasks.service(name, thread, user, getattr(thread, "stop", None))
    return True, f"started {service.description}"


def stop(name):
    """Stop a service now (it starts again at the next sign-in unless it is also switched off). Returns (ok, message)."""
    service = _defs.get(name)
    if service is None:
        return False, f"no such service: {name}"
    with _lock:
        thread = instance(name)
        if thread is None:
            _running.pop(name, None)
            return False, f"{name} is not running"
        task = _task_of(thread)
        note = tasks.stop_service(task) if task is not None else ""
        if task is None and hasattr(thread, "stop"):
            thread.stop()
        _running.pop(name, None)
    return True, f"stopped {service.description}" + (f" ({note})" if note else "")


def restart(name, user):
    if instance(name) is not None:
        ok, message = stop(name)
        if not ok:
            return ok, message
    return start(name, user)


def start_all(user, light_mode=False):
    """Start every service that is not switched off (called when someone signs in). Returns the names that were started."""
    started = []
    off = set(disabled())
    for name, service in list(_defs.items()):
        if name in off or (light_mode and service.skip_in_light_mode):
            continue
        if service.oneshot and os.environ.get("PYOS_SAFE") == "1":
            continue                                    # safe mode: no update checks, no startup commands
        if start(name, user)[0]:
            started.append(name)
    return started


def stop_all():
    """Stop every running service, newest first (sign-out)."""
    for name in reversed(list(_running)):
        if instance(name) is not None:
            stop(name)


def rows():
    """One dict per service for the list: name, description, state, pid, on at sign-in."""
    out = []
    for name, service in _defs.items():
        out.append({"name": name, "description": service.description, "state": state(name), "pid": pid_of(name),
                    "autostart": not is_disabled(name), "oneshot": service.oneshot, "critical": service.critical})
    return out
