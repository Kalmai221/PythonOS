# pyos/trail.py - what the person ran lately, kept in memory for problem reports
#
# Every command the shell runs leaves one entry here: its name and arguments, how it ended and how long it took. Only the last few dozen
# are kept, nothing is written to disk, and it is gone when PythonOS ends. A problem report can include it ("Recent commands"), which is
# often what a developer needs most: what led up to the problem. Arguments are scrubbed of tokens and passwords; the report is redacted
# again and the person reads it before anything is sent.
import collections
import threading
import time

from pyos import log

KEEP = 40
_entries = collections.deque(maxlen=KEEP)
_lock = threading.Lock()


def record(name, args, status, seconds, user=None):
    """Remember one finished command. Never raises."""
    try:
        text = log.scrub(" ".join([str(name)] + [str(a) for a in (args or [])]))
        with _lock:
            _entries.append({"time": time.time(), "line": text[:160], "status": status, "seconds": round(seconds, 2), "user": user or ""})
    except Exception:                                      # noqa: BLE001
        pass


def recent(count=15):
    """The last `count` entries, oldest first."""
    with _lock:
        return list(_entries)[-count:]


def lines(count=15):
    """Readable lines for a report: time, the command, and how it ended."""
    out = []
    for item in recent(count):
        ended = "ok" if item["status"] == 0 else f"exit {item['status']}"
        out.append(f"{time.strftime('%H:%M:%S', time.localtime(item['time']))}  {item['line']}  [{ended}, {item['seconds']}s]")
    return out


def clear():
    with _lock:
        _entries.clear()
