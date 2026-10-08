#!/usr/bin/env python3
"""Which marketplace apps do work that a PythonOS command already does, or would be better for being able to ask for one (pyos.corecmd)?

    python tools/audit_apps_core.py              one block per command: the apps that could use it, and why
    python tools/audit_apps_core.py --apps       one block per app: the commands it could use
    python tools/audit_apps_core.py --json       the same as data

It reads each app's run.py for the Python modules and calls that stand for a job a command does (requests -> curl and wget, zipfile -> zip and unzip,
hashlib -> sha256sum, ...). It is a pointer for a person to read, not a verdict: an app that already does the job well has little to gain.
"""
import collections
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
# (what the app does, the pattern in its code, the commands that do it, what it would gain)
RULES = [
    ("downloads from the web", r"requests\.(get|post)|urlopen|urllib\.request", ["curl", "wget"], "the size limits, progress and file rules of the commands; saving what it fetched with wget"),
    ("saves a web file", r"iter_content|\.content\b", ["wget"], "one tested download with a size limit, instead of writing the bytes by hand"),
    ("works with zip or tar files", r"zipfile|tarfile", ["zip", "unzip", "tar"], "the same safety checks as the commands (no files outside the folder, no bombs)"),
    ("hashes or checks files", r"hashlib", ["sha256sum", "md5sum", "sha1sum", "sha512sum"], "checking a download against a list with -c"),
    ("encodes text", r"base64", ["base64"], "the same behaviour as the command, including unpadded input"),
    ("compares text", r"difflib", ["diff", "cmp"], "a diff that matches what people know"),
    ("looks for files", r"os\.walk|glob\.|rglob|scandir", ["find", "tree", "du"], "one definition of what hidden and system files are"),
    ("copies, moves or deletes", r"shutil\.|os\.remove|os\.rename|os\.replace", ["cp", "mv", "rm"], "the trash and undo of the commands, so a mistake can be taken back"),
    ("tests connections", r"socket\.|ping3", ["ping", "nslookup", "whois", "tracert", "ipinfo"], "the commands' timeouts and error messages"),
    ("reads system facts", r"psutil", ["ps", "free", "df", "uptime", "lscpu", "sysinfo"], "the same numbers the rest of PythonOS shows"),
    ("reads the person's text files", r"open\(\s*(path|name|file|filename|target)[^)]*encoding", ["cat", "head", "tail"], "files in other encodings (Windows-1252, UTF-16) read correctly"),
    ("compresses", r"import gzip|import bz2|import lzma", ["gzip", "gunzip", "zcat"], "the size limit against compression bombs"),
]
# jobs an app could do that none of them do yet, found by what the app is for (its tags and category), not its code
IDEAS = [
    ({"notes", "journal", "todo", "snippets", "expenses", "contacts", "habits", "flashcards"}, ["zip", "gzip", "sha256sum"], "a backup or export of its data in one archive, checked with a checksum"),
    ({"weather", "iss", "quake", "hn", "xkcd", "rss", "rates", "countries"}, ["schedule"], "a regular check (every morning, every hour) set with schedule instead of a loop that has to stay open"),
    ({"pomodoro", "countdown", "alarm", "habits", "flashcards"}, ["schedule"], "a reminder that fires when the app is closed (with the notifications permission)"),
    ({"mdview", "readability", "pdfread", "epub", "wiki", "define", "books"}, ["column", "fold", "grep"], "wrapping and searching long text the way the rest of the system does"),
    ({"logviewer", "csvview", "jsonfmt"}, ["tail", "grep", "column", "sed"], "following, filtering and tabulating without re-implementing them"),
    ({"hashtool", "dupes", "diskusage", "bulkrename"}, ["sha256sum", "du", "find", "mv"], "the commands' own checks, trash and undo"),
    ({"lanscan", "portscan", "nettools", "speedtest", "wifimeter"}, ["ping", "nslookup", "whois", "tracert", "ipinfo"], "name lookups and owner details for the devices and hosts it finds"),
    ({"sysmon", "procs", "battery"}, ["ps", "free", "df", "uptime"], "the same figures `sysinfo` and `taskman` show"),
]


def apps():
    found = []
    base = os.path.join(ROOT, "online_packages")
    for kind in sorted(os.listdir(base)):
        folder = os.path.join(base, kind)
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            run = os.path.join(folder, name, "run.py")
            if os.path.isfile(run):
                with open(run, encoding="utf-8") as f:
                    found.append((name, f.read()))
    return found


def audit():
    """{app: [(job, [commands], gain)]} for every app."""
    result = collections.OrderedDict()
    for name, text in apps():
        hits = [(job, commands, gain) for job, pattern, commands, gain in RULES if re.search(pattern, text)]
        hits += [("could offer", commands, gain) for tags, commands, gain in IDEAS if name in tags]
        if "corecmd" in text:
            hits = [h for h in hits if h[0] != "could offer"] + [("already asks for commands", [], "")]
        result[name] = hits
    return result


def by_command(result):
    table = collections.defaultdict(list)
    for name, hits in result.items():
        for job, commands, gain in hits:
            for command in commands:
                table[command].append((name, job, gain))
    return table


def main(argv):
    result = audit()
    if "--json" in argv:
        print(json.dumps(result, indent=2))
        return 0
    if "--apps" in argv:
        for name, hits in result.items():
            if hits:
                print(f"{name}")
                for job, commands, gain in hits:
                    print(f"    {job}: {', '.join(commands)}" + (f"  - {gain}" if gain else ""))
        return 0
    for command, rows in sorted(by_command(result).items()):
        print(f"{command}  ({len(rows)} app(s))")
        for name, job, gain in rows:
            print(f"    {name}: {job}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
