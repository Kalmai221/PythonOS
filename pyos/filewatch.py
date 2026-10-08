# pyos/filewatch.py - wait for a file or folder to change
#
# changes(path) yields once for every burst of changes under `path`. With the watchfiles library (a fast native watcher) the operating system
# says when something changed; without it the folder is looked at once a second (names, sizes and modification times), which works everywhere and
# is plenty for "run this again when I save". Both wake up about once a second so that Ctrl+C always gets through.
import os
import time

from . import optional

MAX_FILES = 5000                 # a folder bigger than this is not polled completely (watchfiles has no such limit)


def snapshot(path):
    """{file: (modification time, size)} for a file or for the files under a folder."""
    state = {}
    if os.path.isfile(path):
        try:
            info = os.stat(path)
            state[path] = (info.st_mtime_ns, info.st_size)
        except OSError:
            pass
        return state
    for base, dirs, names in os.walk(path):
        dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
        for name in names:
            if name.startswith("."):
                continue
            full = os.path.join(base, name)
            try:
                info = os.stat(full)
            except OSError:
                continue
            state[full] = (info.st_mtime_ns, info.st_size)
            if len(state) >= MAX_FILES:
                return state
    return state


def changes(path, interval=1.0, sleep=time.sleep):
    """Yield (once per change) until the caller stops iterating or Ctrl+C is pressed."""
    library = optional.get("watchfiles")
    if library is not None:
        try:
            for found in library.watch(path, debounce=300, rust_timeout=int(interval * 1000), yield_on_timeout=True, raise_interrupt=True):
                if found:
                    yield True
            return
        except KeyboardInterrupt:
            raise
        except Exception:                                      # noqa: BLE001 - a watcher that cannot start (no inotify room): poll instead
            pass
    before = snapshot(path)
    while True:
        sleep(interval)
        now = snapshot(path)
        if now != before:
            before = now
            yield True
