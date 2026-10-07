# pyos/bugs.py - the "bug-detection" background service
#
# PythonOS writes a line at level ERROR to the system log when something fails that the person did not cause: a command or a program that
# crashed with an exception (named with its file and line), an app that ended with a traceback, a service that could not start, a scheduled
# task that failed. This service reads the new lines of the log as they appear. When it finds one it has not told you about, the shell asks,
# before the next prompt: "An unexpected bug has been found, would you like to report it?" - and if you say yes, `report` starts with the
# bug already described. Nothing is sent without the usual choices and the usual look at the whole report.
#
# What is NOT a bug here: a mistake in what you typed, a network that is down, a failed update or install, a wrong password. Those are logged
# at a lower level or are listed in IGNORE.
#
# The same bug is only offered once per session, never more than once every two minutes, and never more than five times per session.
import collections
import os
import re
import threading
import time

from pyos import log

POLL_SECONDS = 2.0
MIN_GAP = 120.0
MAX_OFFERS = 5
QUEUE = 10
IGNORE = re.compile(r"(?i)^(update|installos|report|compat)\b|\b(login failed|could not reach|timed out|timeout|connection|network|no space left|"
                    r"could not be installed|could not be removed|checksum|offline|dns)\b")

_pending = collections.deque(maxlen=QUEUE)
_seen = set()
_state = {"offers": 0, "last": 0.0}
_lock = threading.Lock()


def signature(message):
    """The same bug looks the same each time: the message without numbers, times, paths and quoted values."""
    text = re.sub(r"\d+", "#", message)
    text = re.sub(r"(['\"]).*?\1", "'_'", text)
    return re.sub(r"\s+", " ", text)[:160]


def classify(level, message):
    """A short description when this log line is an unexpected bug, else None."""
    if level != "ERROR" or IGNORE.search(message):
        return None
    return message[:300]


def note(level, message, user=""):
    """Consider one log line. Returns True if it was queued as a new bug."""
    summary = classify(level, message)
    if summary is None:
        return False
    sig = signature(message)
    with _lock:
        if sig in _seen:
            return False
        _seen.add(sig)
        _pending.append({"summary": summary, "user": user, "time": time.time()})
    return True


def take(now=None):
    """The next bug to ask about, or None (nothing new, asked too recently, or asked enough times)."""
    now = now if now is not None else time.time()
    with _lock:
        if not _pending or _state["offers"] >= MAX_OFFERS or now - _state["last"] < MIN_GAP:
            return None
        _state["offers"] += 1
        _state["last"] = now
        return _pending.popleft()


def waiting():
    with _lock:
        return len(_pending)


def forget():
    """Clear everything (a new session, and the tests)."""
    with _lock:
        _pending.clear()
        _seen.clear()
        _state.update(offers=0, last=0.0)


def description(bug):
    """What `report` starts with: the bug in a sentence a developer can use."""
    return "Unexpected bug found by bug-detection: " + bug["summary"]


def offer(ask, run_report, show=print, now=None):
    """Called by the shell before it shows a prompt. If a new bug is waiting, say so and ask; if the answer is yes, start the report.
    `ask(question)` returns True or False; `run_report(text)` starts `report` with that description. Returns True when it asked."""
    from pyos import services
    if services.instance("bug-detection") is None:
        return False
    bug = take(now)
    if bug is None:
        return False
    show(bug["summary"])
    if ask("An unexpected bug has been found, would you like to report it?"):
        run_report(description(bug))
    else:
        show("Not reported. You can run report at any time.")
    return True


class Detector(threading.Thread):
    """The service: reads what is added to the system log and queues the bugs among it."""

    def __init__(self, user=None, path=None):
        super().__init__(name="bug-detection", daemon=True)
        self.user = user
        self.path = path or log.LOG_FILE
        self._stop_event = threading.Event()
        self.offset = self._size()

    def _size(self):
        try:
            return os.path.getsize(self.path)
        except OSError:
            return 0

    def scan(self):
        """Look at the lines added since the last scan. Returns how many new bugs were queued."""
        size = self._size()
        if size < self.offset:                              # the log was trimmed (it keeps its newest half): start again from its beginning
            self.offset = 0
        found = 0
        if size > self.offset:
            try:
                with open(self.path, "rb") as f:
                    f.seek(self.offset)
                    chunk = f.read(size - self.offset)
            except OSError:
                return 0
            self.offset = size
            for raw in chunk.decode("utf-8", "replace").splitlines():
                match = log._LINE.match(raw)
                if match and note(match.group(2).upper(), match.group(4), match.group(3) or ""):
                    found += 1
        return found

    def run(self):
        while not self._stop_event.wait(POLL_SECONDS):
            try:
                self.scan()
            except Exception:                               # noqa: BLE001 - the detector must never be the bug
                pass

    def stop(self):
        self._stop_event.set()
