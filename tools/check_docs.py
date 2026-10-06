#!/usr/bin/env python3
"""Documentation checks that keep the manual honest:
  * every command in commands/ has a man page and a place in the help groups
  * every man page belongs to a real command or a documented topic
  * every command and app has a description, and the catalog's apps all say which exports they run on
    python tools/check_docs.py
"""
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, ROOT)
os.environ["PYOS_BUNDLED"] = "1"


def main():
    from pyos import helpview, manpages
    problems = []
    commands = sorted(f[:-3] for f in os.listdir(os.path.join(ROOT, "commands")) if f.endswith(".py"))
    for name in commands:
        if name not in manpages.PAGES:
            problems.append(f"command '{name}' has no man page (add one in pyos/manpages.py)")
        if helpview.category_of(name) == "Other":
            problems.append(f"command '{name}' is not in a help group (add it to CATEGORIES in pyos/helpview.py)")
    topics = {"shell", "files", "users", "packages", "updates", "lockdown", "help", "run", "reload", "exit"}      # topics and shell built-ins
    for name in manpages.PAGES:
        if name not in commands and name not in topics and not os.path.exists(os.path.join(ROOT, "programs", name + ".py")):
            problems.append(f"man page '{name}' does not match a command or program")
    with open(os.path.join(ROOT, "online_packages", "index-api2.json"), encoding="utf-8") as f:
        catalog = json.load(f)["packages"]
    for pkg in catalog:
        if not pkg.get("description"):
            problems.append(f"app {pkg['id']} has no description")
        if not pkg.get("exports"):
            problems.append(f"app {pkg['id']} does not say which exports it runs on")
    if problems:
        print("Documentation check FAILED:")
        for p in problems:
            print("  " + p)
        return 1
    print(f"Documentation check passed ({len(commands)} commands, {len(catalog)} apps).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
