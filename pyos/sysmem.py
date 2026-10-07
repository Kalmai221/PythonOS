# pyos/sysmem.py - memory figures that never raise and never print a warning
#
# On Android (and some containers) /proc is restricted: psutil then either raises PermissionError or prints a RuntimeWarning about swap
# figures it "couldn't determine". Anything that shows memory (doctor, free) asks here, and gets None when the system will not say.
import warnings


def _ask(name):
    try:
        import psutil
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return getattr(psutil, name)()
    except Exception:                                      # noqa: BLE001 - PermissionError, OSError, a missing or broken psutil
        return None


def swap():
    """psutil.swap_memory(), or None if this system does not allow reading it."""
    return _ask("swap_memory")


def memory():
    """psutil.virtual_memory(), or None if this system does not allow reading it."""
    return _ask("virtual_memory")
