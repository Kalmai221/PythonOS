# pyos/startup.py - commands that run by themselves each time a user logs in ("startup apps").
#
# The list is kept per user in ~/.config/startup.json:  {"items": [{"command": "date", "enabled": true, "note": "..."}]}
# The Startup Manager app edits it. At login the shell runs the enabled items one after another in the background, with their output
# captured and delivered as a notification (so they must not need typed input). A command that fails is reported, never fatal.
from . import appdata, notify

MAX_ITEMS = 12


def items(user=None):
    data = appdata.load("startup", {}, user=user) or {}
    found = data.get("items", []) if isinstance(data, dict) else []
    return [i for i in found if isinstance(i, dict) and isinstance(i.get("command"), str)][:MAX_ITEMS]


def run_all(runner, user):
    """runner(command) -> (status, output). Runs the user's enabled startup commands. Returns how many ran."""
    ran = 0
    for item in items(user):
        if not item.get("enabled", True):
            continue
        status, output = runner(item["command"])
        ran += 1
        lines = [line for line in output.strip().splitlines() if line.strip()][:3]
        if lines or status:
            notify.notify(item["command"] + (" - failed" if status else "") + ("\n" + "\n".join(lines) if lines else ""),
                          title="Startup", level="warn" if status else "info", user=user)
    return ran
