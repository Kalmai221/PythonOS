"""The memory PythonOS owns.

Everywhere except the live ISO PythonOS is given a fixed amount of memory (setting memory_limit_mb, 1024 MB by default). That amount
is "the computer" as far as PythonOS is concerned: free, sysinfo and the task manager report it as the total, and everything PythonOS
runs (its own process and the programs it starts) counts as used. On Windows the limit is also enforced by the system (a job object),
so PythonOS really cannot grow past it. On the live ISO PythonOS is the whole machine, so it gets all the memory there is.
"""
import os
import sys
import threading
import time

MB = 1024 ** 2
DEFAULT_MB = 1024
_applied = {"limit": 0, "enforced": False}


def live():
    return os.environ.get("PYOS_LIVE") == "1"


def physical_total():
    try:
        import psutil
        return int(psutil.virtual_memory().total)
    except Exception:
        return 0


def limit_mb():
    """The configured limit in MB; 0 means no limit (the whole machine)."""
    if live():
        return 0
    try:
        from pyos import settings
        value = int(settings.get("memory_limit_mb"))
    except Exception:
        value = DEFAULT_MB
    return max(0, value)


def budget():
    """Bytes of memory PythonOS owns: the limit, but never more than the machine has."""
    physical = physical_total()
    mb = limit_mb()
    if not mb:
        return physical
    return min(mb * MB, physical) if physical else mb * MB


def used():
    """Bytes in use by PythonOS and the programs it started."""
    try:
        import psutil
        me = psutil.Process(os.getpid())
        total = me.memory_info().rss
        for child in me.children(recursive=True):
            try:
                total += child.memory_info().rss
            except psutil.Error:
                continue
        return int(total)
    except Exception:
        return 0


def snapshot():
    """(total, used, available, percent) of PythonOS's own memory. On the live ISO (no limit) this is the machine's: what the
    whole system is using, since there PythonOS is the system."""
    total = budget()
    if live() or not limit_mb():
        try:
            import psutil
            vm = psutil.virtual_memory()
            return int(vm.total), int(vm.used), int(vm.available), float(vm.percent)
        except Exception:
            pass
    spent = min(used(), total) if total else used()
    available = max(0, total - spent)
    return total, spent, available, (spent * 100.0 / total if total else 0.0)


def percent_of_budget(rss):
    total = budget()
    return rss * 100.0 / total if total else 0.0


# ------------------------------------------------------------------------------------------- enforcement
def _enforce_windows(limit):
    """Put this process (and everything it starts) in a job object with a memory cap."""
    import ctypes
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64), ("PerJobUserTimeLimit", ctypes.c_int64),
                    ("LimitFlags", wintypes.DWORD), ("MinimumWorkingSetSize", ctypes.c_size_t),
                    ("MaximumWorkingSetSize", ctypes.c_size_t), ("ActiveProcessLimit", wintypes.DWORD),
                    ("Affinity", ctypes.c_size_t), ("PriorityClass", wintypes.DWORD), ("SchedulingClass", wintypes.DWORD)]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]

    class Extended(ctypes.Structure):
        _fields_ = [("Basic", Basic), ("Io", IoCounters), ("ProcessMemoryLimit", ctypes.c_size_t),
                    ("JobMemoryLimit", ctypes.c_size_t), ("PeakProcessMemoryUsed", ctypes.c_size_t),
                    ("PeakJobMemoryUsed", ctypes.c_size_t)]

    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateJobObjectW.restype = wintypes.HANDLE
    k32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    k32.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    k32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    k32.GetCurrentProcess.restype = wintypes.HANDLE

    job = k32.CreateJobObjectW(None, None)
    if not job:
        return False
    info = Extended()
    info.Basic.LimitFlags = 0x200                       # JOB_OBJECT_LIMIT_JOB_MEMORY
    info.JobMemoryLimit = limit
    if not k32.SetInformationJobObject(job, 9, ctypes.byref(info), ctypes.sizeof(info)):    # JobObjectExtendedLimitInformation
        return False
    return bool(k32.AssignProcessToJobObject(job, k32.GetCurrentProcess()))


def apply():
    """Called once at start-up. Returns a short description of what is in force."""
    mb = limit_mb()
    if not mb:
        return "all memory"
    limit = budget()
    _applied["limit"] = limit
    if sys.platform == "win32":
        try:
            _applied["enforced"] = _enforce_windows(limit)
        except Exception:
            _applied["enforced"] = False
    return f"{limit // MB} MB" + (" (enforced)" if _applied["enforced"] else "")


def describe():
    mb = limit_mb()
    if not mb:
        return "all of the machine's memory" if live() else "no limit"
    return f"{budget() // MB} MB" + (", enforced by the system" if _applied["enforced"] else "")


class Guard(threading.Thread):
    """Tells the user once when PythonOS is nearly out of its own memory (and again if it goes over)."""

    def __init__(self, notify, interval=20):
        super().__init__(name="memory-guard", daemon=True)
        self.notify, self.interval, self._said = notify, interval, 0
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        if not limit_mb():
            return
        while not self._stop_event.wait(self.interval):
            percent = snapshot()[3]
            level = 2 if percent >= 100 else 1 if percent >= 90 else 0
            if level > self._said:
                self.notify("PythonOS is using all of its memory. Close programs or raise memory_limit_mb in settings." if level == 2
                            else f"PythonOS memory is {percent:.0f}% full.", "warn")
            self._said = level
