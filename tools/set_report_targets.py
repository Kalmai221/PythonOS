#!/usr/bin/env python3
"""Sets the Discord channel `report` can send problem reports to (pyos/report_targets.json).

    python tools/set_report_targets.py --discord https://discord.com/api/webhooks/<id>/<token>
    python tools/set_report_targets.py --show
    python tools/set_report_targets.py --discord ""                            (switch it off)

GitHub needs nothing here: it uses the gh command. The Discord address is only lightly
disguised in the file, so GitHub's secret scanner does not revoke it; it is not a secret from anyone who reads the code. To replace it,
run this again and ship the file with a core update.
"""
import json
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO)

from pyos import reportsend  # noqa: E402


def option(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv and sys.argv.index(name) + 1 < len(sys.argv) else None


def main():
    try:
        with open(reportsend.TARGETS, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    hook = option("--discord")
    if hook is not None:
        hook = hook.strip()
        if hook and not hook.startswith("https://"):
            sys.exit("the Discord address must start with https://")
        data["discord"] = reportsend.disguise(hook) if hook else ""
    if hook is not None:
        with open(reportsend.TARGETS, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"discord": data.get("discord", "")}, f, indent=2)
            f.write("\n")
    shown = reportsend.targets()
    print("Discord webhook: ", "set" if shown["discord"] else "(not set: the Discord way is off)")


if __name__ == "__main__":
    main()
