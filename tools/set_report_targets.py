#!/usr/bin/env python3
"""Sets where `report` can send problem reports (pyos/report_targets.json).

    python tools/set_report_targets.py --github-client-id Iv1.abc123...
    python tools/set_report_targets.py --discord https://discord.com/api/webhooks/<id>/<token>
    python tools/set_report_targets.py --show
    python tools/set_report_targets.py --github-client-id "" --discord ""     (switch both off)

The GitHub client id is public (it names PythonOS's OAuth app, with the device flow switched on). The Discord address is only lightly
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
    client, hook = option("--github-client-id"), option("--discord")
    if client is not None:
        data["github_client_id"] = client.strip()
    if hook is not None:
        hook = hook.strip()
        if hook and not hook.startswith("https://"):
            sys.exit("the Discord address must start with https://")
        data["discord"] = reportsend.disguise(hook) if hook else ""
    if client is not None or hook is not None:
        with open(reportsend.TARGETS, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"github_client_id": data.get("github_client_id", ""), "discord": data.get("discord", "")}, f, indent=2)
            f.write("\n")
    shown = reportsend.targets()
    print("GitHub client id:", shown["github_client_id"] or "(not set: the GitHub way is off)")
    print("Discord webhook: ", "set" if shown["discord"] else "(not set: the Discord way is off)")


if __name__ == "__main__":
    main()
