# pyos/screenlog.py - what the person saw on the screen, kept in memory for problem reports (optional)
#
# The text PythonOS prints to the screen and the command lines that were typed are kept in a small buffer in memory (setting `terminal_log`,
# on by default; off = nothing is kept): the last stretch only, never written to disk, gone when PythonOS ends. `report` then asks the
# person whether to include the last lines "as the screen showed them", which often explains a problem better than a description can.
# Nothing of it is used unless they say yes; they see it with the rest of the report, and it is redacted (names, addresses, tokens).
#
# Passwords are not echoed to the screen, so they are not here; text that looks like a secret is replaced anyway (see pyos.log.scrub).
import collections
import re
import threading
import time

from pyos import log

MAX_CHARS = 60000                      # about 700 lines of screen: the oldest text is dropped beyond this
_chunks = collections.deque()
_size = 0
_lock = threading.Lock()
_state = {"on": False, "checked": 0.0}
_ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][A-Za-z0-9]|[\x00-\x08\x0b\x0c\x0e-\x1f]")


def enabled():
    """Whether the setting is on. Looked up at most once a second: this is called for every write to the screen."""
    now = time.monotonic()
    if now - _state["checked"] > 1.0:
        _state["checked"] = now
        try:
            from pyos import settings
            _state["on"] = bool(settings.get("terminal_log"))
        except Exception:                                  # noqa: BLE001
            _state["on"] = False
        if not _state["on"]:
            clear()
    return _state["on"]


def feed(text):
    """Called with everything printed to the screen (and the command lines typed). Does nothing unless the setting is on. Never raises."""
    global _size
    try:
        if not text or not enabled():
            return
        with _lock:
            _chunks.append(text)
            _size += len(text)
            while _size > MAX_CHARS and len(_chunks) > 1:
                _size -= len(_chunks.popleft())
    except Exception:                                      # noqa: BLE001 - recording must never break the screen
        pass


def clear():
    global _size
    with _lock:
        _chunks.clear()
        _size = 0


def text(max_lines=60):
    """The last `max_lines` lines as the screen showed them: colour codes removed, progress lines that redrew in place reduced to their
    last version, secrets replaced. '' when nothing is recorded."""
    with _lock:
        raw = "".join(_chunks)
    out = []
    for line in _ANSI.sub("", raw.replace("\r\n", "\n")).split("\n"):
        if "\r" in line:                                   # a progress bar redrawn in place: only its last version was visible
            shown = [part for part in line.split("\r") if part.strip()]
            line = shown[-1] if shown else ""
        out.append(line.rstrip())
    while out and not out[-1]:
        out.pop()
    return log.scrub("\n".join(out[-max_lines:]))


def available():
    """True when the setting is on and there is something to include."""
    return enabled() and bool(_chunks)
