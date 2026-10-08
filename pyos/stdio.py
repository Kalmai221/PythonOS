# pyos/stdio.py - per-thread output capture and piped input
#
# Pipelines ("ls | grep x"), background jobs and scheduled tasks all need to capture a command's
# output without disturbing what the foreground shell is printing. sys.stdout is process-wide, so it
# is replaced once by a router that sends each thread's writes to that thread's capture buffer (if it
# has one) and everything else to the real terminal.
import contextlib
import io
import os
import sys
import threading

from . import screenlog

_local = threading.local()
_targets = {}  # thread id -> buffer
_lock = threading.Lock()
_pager = {}               # {"active": a paging.Pager} while a listing command output is being paged
_screen = {"lines": 0}   # lines printed to the real terminal since the last clear (for the auto_clear_lines setting)


class _Router(io.TextIOBase):
    """File-like object that routes writes per thread. Everything else is delegated to the real stream."""

    def __init__(self, real):
        self._real = real

    # --- the captured case ---
    def _buffer(self):
        return _targets.get(threading.get_ident())

    def write(self, text):
        buf = self._buffer()
        if buf is not None:
            return buf.write(text)
        _screen["lines"] += text.count(chr(10))
        screenlog.feed(text)                                  # kept in memory only when the terminal_log setting is on
        pager = _pager.get("active")
        if pager is not None and threading.current_thread() is threading.main_thread():
            pager.write(text)
            return len(text)
        return self._real.write(text)

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def flush(self):
        if self._buffer() is None:
            self._real.flush()

    def isatty(self):
        # captured output must not get colour codes
        return False if self._buffer() is not None else self._real.isatty()

    def fileno(self):
        if self._buffer() is not None:
            raise io.UnsupportedOperation("captured output has no file descriptor")
        return self._real.fileno()

    def writable(self):
        return True

    @property
    def encoding(self):
        return getattr(self._real, "encoding", "utf-8")

    @property
    def errors(self):
        return getattr(self._real, "errors", "strict")

    def __getattr__(self, name):  # buffer, name, mode, ...
        return getattr(self._real, name)


def lines_on_screen():
    return _screen["lines"]


def clear_screen(scrollback=True):
    """Clear the terminal (and by default its scrollback) and reset the line counter. Works on Windows 10+, Linux,
    macOS and the Android terminal, which all understand the ANSI sequences; falls back to the OS command."""
    install()
    real = sys.stdout._real if isinstance(sys.stdout, _Router) else sys.stdout
    try:
        if os.name == "nt":
            os.system("")                        # switches the Windows console into ANSI mode
        real.write("\x1b[H\x1b[2J" + ("\x1b[3J" if scrollback else ""))
        real.flush()
    except (OSError, ValueError):
        os.system("cls" if os.name == "nt" else "clear")  # nosec B605 - fixed text, nothing from the user
    _screen["lines"] = 0


def fresh_screen():
    """Clear the screen (keeping the scrollback) before a full-screen program or menu takes over - only on a real terminal, not for
    captured output or background jobs, and not when the clear_screens setting is off. Returns True if it cleared."""
    try:
        from pyos import settings
        if not settings.get("clear_screens") or _targets.get(threading.get_ident()) is not None:
            return False
        real = sys.stdout._real if isinstance(sys.stdout, _Router) else sys.stdout
        if not real.isatty() or threading.current_thread() is not threading.main_thread():
            return False
    except Exception:
        return False
    clear_screen(scrollback=False)
    return True


def overflowed():
    """True if more lines were printed since the last clear than fit on the screen."""
    try:
        return _screen["lines"] > max(10, os.get_terminal_size().lines - 2)
    except OSError:
        return False


def install():
    """Install the router on sys.stdout (safe to call more than once)."""
    if not isinstance(sys.stdout, _Router):
        sys.stdout = _Router(sys.stdout)


@contextlib.contextmanager
def paged():
    """Page everything the main thread prints to the real terminal, a screen at a time (see pyos/paging.py)."""
    from pyos import paging
    install()
    real = sys.stdout._real
    _pager["active"] = paging.Pager(real.write, input)
    try:
        yield
    finally:
        _pager.pop("active", None)
        try:
            real.flush()
        except (OSError, ValueError):
            pass


@contextlib.contextmanager
def capture():
    """Capture everything the current thread prints into a StringIO."""
    install()
    buf = io.StringIO()
    ident = threading.get_ident()
    with _lock:
        previous = _targets.get(ident)
        _targets[ident] = buf
    try:
        yield buf
    finally:
        with _lock:
            if previous is None:
                _targets.pop(ident, None)
            else:
                _targets[ident] = previous


# --- piped input (thread local, so a background job's pipe cannot leak into the foreground) ---
def set_stdin(text):
    _local.stdin = text


def read_stdin():
    """Return piped text, or None when the command is not receiving a pipe."""
    return getattr(_local, "stdin", None)
