# pyos/safemode.py - safe mode: PythonOS starts with only the system itself.
#
# Safe mode leaves out everything that is not part of PythonOS: apps from the marketplace, the startup commands of a user, the background
# checks (updates, app updates) and the long animations. It is for getting back in when something that was added breaks the start.
# Switch it on from the boot menu, with `main.py --safe`, or with `safe on` in the emergency console (which sets it for the next start).
import os


def enabled():
    return os.environ.get("PYOS_SAFE") == "1"


def turn_on():
    os.environ["PYOS_SAFE"] = "1"


BANNER = "Safe mode: apps from the marketplace, startup commands and background checks are off. Restart normally to get them back."
