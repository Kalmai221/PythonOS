# pyos/scheduler.py - run commands later or repeatedly ("schedule add every 5m backup create")
#
#   in 10m <cmd>        once, after a delay            (s, m, h, d)
#   at 14:30 <cmd>      once, at the next 14:30
#   every 5m <cmd>      repeatedly
#   daily 08:00 <cmd>   every day at that time
#
# Tasks are saved in .OSData/schedule.json and belong to the user who created them; they run while
# that user is logged in (a task that came due while they were away runs once at the next login).
# Output is captured and delivered as a notification, so tasks must not need typed input.
import datetime
import json
import os
import re
import threading
import time

from . import notify, stdio

SCHEDULE_FILE = os.path.join(".OSData", "schedule.json")
_lock = threading.RLock()
_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}


def parse_duration(text):
    m = re.fullmatch(r"(\d+)([smhd])", str(text).strip().lower())
    if not m or int(m.group(1)) == 0:
        raise ValueError(f"'{text}' is not a duration - use a number and s, m, h or d (for example 90s, 5m, 2h)")
    return int(m.group(1)) * _UNITS[m.group(2)]


def parse_clock(text):
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", str(text).strip())
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
        raise ValueError(f"'{text}' is not a time - use HH:MM, for example 14:30")
    return int(m.group(1)), int(m.group(2))


def next_clock(hour, minute, now=None):
    """Timestamp of the next occurrence of HH:MM (today if still ahead, otherwise tomorrow)."""
    now_dt = datetime.datetime.fromtimestamp(now if now is not None else time.time())
    target = now_dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now_dt:
        target += datetime.timedelta(days=1)
    return target.timestamp()


def parse_spec(words, now=None):
    """Parse ['every', '5m', 'ls', ...] into (spec, command_words)."""
    now = now if now is not None else time.time()
    if len(words) < 3:
        raise ValueError("usage: schedule add <in|at|every|daily> <when> <command>")
    kind, when, command = words[0].lower(), words[1], words[2:]
    if kind == "in":
        seconds = parse_duration(when)
        return {"kind": "once", "next_run": now + seconds}, command
    if kind == "at":
        hour, minute = parse_clock(when)
        return {"kind": "once", "next_run": next_clock(hour, minute, now)}, command
    if kind == "every":
        seconds = parse_duration(when)
        return {"kind": "every", "interval": seconds, "next_run": now + seconds}, command
    if kind == "daily":
        hour, minute = parse_clock(when)
        return {"kind": "daily", "time": f"{hour:02d}:{minute:02d}", "next_run": next_clock(hour, minute, now)}, command
    raise ValueError("start with in, at, every or daily")


def _load():
    try:
        with open(SCHEDULE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(tasks):
    os.makedirs(os.path.dirname(SCHEDULE_FILE), exist_ok=True)
    tmp = SCHEDULE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(tasks, f, indent=2)
    os.replace(tmp, SCHEDULE_FILE)


def add(user, words, now=None):
    spec, command = parse_spec(words, now)
    with _lock:
        tasks = _load()
        task_id = max([t["id"] for t in tasks] + [0]) + 1
        task = {"id": task_id, "user": user, "command": " ".join(command), "last_run": None, "last_status": None, **spec}
        tasks.append(task)
        _save(tasks)
    return task


def tasks_for(user):
    with _lock:
        return [t for t in _load() if t["user"] == user]


def remove(user, task_id, admin=False):
    with _lock:
        tasks = _load()
        keep = [t for t in tasks if not (t["id"] == task_id and (admin or t["user"] == user))]
        if len(keep) == len(tasks):
            return False
        _save(keep)
        return True


def describe(task):
    if task["kind"] == "every":
        return f"every {task['interval']}s"
    if task["kind"] == "daily":
        return f"daily at {task['time']}"
    return "once at " + datetime.datetime.fromtimestamp(task["next_run"]).strftime("%Y-%m-%d %H:%M")


def run_due(runner, user, now=None):
    """Run this user's due tasks. runner(command) -> (status, output). Returns how many ran."""
    now = now if now is not None else time.time()
    with _lock:
        due = [t for t in _load() if t["user"] == user and t["next_run"] <= now]
    ran = 0
    for task in due:
        status, output = runner(task["command"])
        ran += 1
        with _lock:
            tasks = _load()
            for t in tasks:
                if t["id"] != task["id"]:
                    continue
                t["last_run"], t["last_status"] = now, status
                if t["kind"] == "once":
                    tasks.remove(t)
                elif t["kind"] == "every":
                    t["next_run"] = now + t["interval"]
                else:
                    hour, minute = parse_clock(t["time"])
                    t["next_run"] = next_clock(hour, minute, now)
                break
            _save(tasks)
        lines = [l for l in output.strip().splitlines() if l.strip()][:4]
        text = f"{task['command']}" + (" - failed" if status else "") + ("\n" + "\n".join(lines) if lines else "")
        if lines or status:                    # a task that worked and printed nothing needs no notification
            notify.notify(text, title=f"Scheduled task #{task['id']}", level="warn" if status else "info", user=user)
    return ran


class Scheduler(threading.Thread):
    """Checks for due tasks once a second while the user is logged in."""

    def __init__(self, runner, user):
        super().__init__(name="scheduler", daemon=True)
        self.runner, self.user = runner, user
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.wait(1.0):
            try:
                run_due(self.runner, self.user)
            except Exception as e:
                # a bad task must never kill the scheduler, but it should be in the log
                from pyos import log
                log.log(f"scheduler: a task failed: {log.describe_exception(e)}", "ERROR", user=self.user)

    def stop(self):
        self._stop_event.set()
