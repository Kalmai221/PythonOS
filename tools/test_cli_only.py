#!/usr/bin/env python3
"""PythonOS is a command line system: it cannot open or click links. Nothing in the system may try to open a browser or print a clickable
(hyperlinked) address; an address is shown as plain text for the person to type on another device. This scans the OS code for the ways
of doing that, and checks that `report` offers no link."""
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
FOLDERS = ("commands", "core", "pyos", "programs", "online_packages")
FILES = ("shell.py", "main.py", "users.py")
FORBIDDEN = [
    (re.compile(r"\bimport webbrowser\b|\bwebbrowser\.open"), "opens a browser"),
    (re.compile(r"xdg-open|\bos\.startfile\b|gnome-open"), "launches the desktop's opener"),
    (re.compile(r"\[link="), "a clickable Rich link"),
    (re.compile(r"\\x1b\]8;|\\033\]8;"), "a terminal hyperlink (OSC 8)"),
]
ALLOWED = {os.path.join("tools", "test_cli_only.py")}


def scan():
    found = []
    paths = [os.path.join(REPO, f) for f in FILES]
    for folder in FOLDERS:
        for base, _dirs, names in os.walk(os.path.join(REPO, folder)):
            paths += [os.path.join(base, n) for n in names if n.endswith(".py")]
    for path in paths:
        rel = os.path.relpath(path, REPO)
        if rel in ALLOWED or not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            for number, line in enumerate(f, 1):
                for pattern, what in FORBIDDEN:
                    if pattern.search(line):
                        found.append(f"{rel}:{number}: {what}")
    return found


def main():
    problems = scan()
    assert not problems, "PythonOS is a CLI and cannot handle links:\n  " + "\n  ".join(problems)
    sys.path.insert(0, REPO)
    os.chdir(REPO)
    from pyos import report
    assert not hasattr(report, "issue_link"), "report must not build long pre-filled links"
    source = open(os.path.join(REPO, "commands", "report.py"), encoding="utf-8").read()
    assert "(l)ink" not in source and "browser" not in source.replace("into a browser on any device", "")
    print("cli only: all checks passed")


if __name__ == "__main__":
    main()
