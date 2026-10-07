#!/usr/bin/env python3
"""Memory figures on a system that restricts /proc (Android): doctor and free must not fail or print a warning when swap (or memory)
cannot be read. psutil is faked."""
import io
import os
import sys
import types
import warnings

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)


class Mem:
    total, available, percent, used, free = 4 * 1024 ** 3, 2 * 1024 ** 3, 50.0, 2 * 1024 ** 3, 2 * 1024 ** 3


def fake_psutil(swap, memory=lambda: Mem()):
    module = types.ModuleType("psutil")
    module.swap_memory = swap
    module.virtual_memory = memory
    return module


def deny(*_a):
    raise PermissionError(13, "Permission denied: '/proc/vmstat'")


def warn_then_answer():
    warnings.warn("'sin' and 'sout' swap memory stats couldn't be determined and were set to 0", RuntimeWarning)
    return types.SimpleNamespace(total=0, used=0, free=0, percent=0.0)


def main():
    real = sys.modules.get("psutil")
    warnings.simplefilter("error")                           # a leaked warning would become an exception here
    try:
        from core import doctor
        from pyos import sysmem
        from commands import free

        # swap is denied: memory is still reported, there is no swap finding, and nothing is raised
        sys.modules["psutil"] = fake_psutil(deny)
        assert sysmem.swap() is None and sysmem.memory().percent == 50.0
        found = doctor.check_memory()
        assert [f.area for f in found] == ["Memory"] and found[0].level == "ok", found

        # psutil's own warning about swap it could not determine: swallowed, and the figures still come back
        sys.modules["psutil"] = fake_psutil(warn_then_answer)
        assert sysmem.swap().total == 0
        assert [f.area for f in doctor.check_memory()] == ["Memory"]

        # memory itself denied: nothing to report, still no error
        sys.modules["psutil"] = fake_psutil(deny, deny)
        assert sysmem.memory() is None and doctor.check_memory() == []

        # a swap that really is nearly full is still reported
        sys.modules["psutil"] = fake_psutil(lambda: types.SimpleNamespace(total=1024 ** 3, used=1000 ** 3, free=24 * 1024 ** 2, percent=95.0))
        assert [f.area for f in doctor.check_memory()] == ["Memory", "Swap"]

        # free: says swap is not readable instead of failing (the figures come from resources.snapshot, faked here)
        from pyos import resources
        real_snapshot, real_limit = resources.snapshot, resources.limit_mb
        resources.snapshot = lambda: (4 * 1024 ** 3, 2 * 1024 ** 3, 2 * 1024 ** 3, 50.0)
        resources.limit_mb = lambda: 0
        sys.modules["psutil"] = fake_psutil(deny)
        buffer = io.StringIO()
        from rich.console import Console
        free.console = Console(file=buffer, width=80, force_terminal=False)
        try:
            free.execute()
        finally:
            resources.snapshot, resources.limit_mb = real_snapshot, real_limit
        assert "Swap:" in buffer.getvalue() and "not readable" in buffer.getvalue(), buffer.getvalue()
    finally:
        warnings.resetwarnings()
        if real is not None:
            sys.modules["psutil"] = real
        else:
            sys.modules.pop("psutil", None)
    print("memory figures: all checks passed")


if __name__ == "__main__":
    main()
