#!/usr/bin/env python3
"""Log viewer: read the system log (and any text log file you point it at) with filters, colours and a live 'follow' mode.
Filters: level, user, a word, a time range. Commands: level warn | user bob | find word | since 2h | clear | follow | top | bottom | page N |
export file | q.   Usage: logviewer [file]   (default: the system log, /var/log/system.log)"""
import datetime
import os
import re
import sys
import time

from rich.console import Console
from rich.markup import escape
from rich.text import Text

from pyos import fs

console = Console()
LINE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\](?: (\S+?):)? (.*)$")
LEVELS = {"debug": 0, "info": 1, "warn": 2, "warning": 2, "error": 3}
PAGE = 20


def parse(lines):
    """Parsed entries: {time, level, user, message, raw}; lines that are not in the system-log format are kept as plain text."""
    out = []
    for raw in lines:
        raw = raw.rstrip("\n")
        m = LINE.match(raw)
        if m:
            out.append({"time": datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"), "level": m.group(2).upper(),
                        "user": m.group(3) or "", "message": m.group(4), "raw": raw})
        elif raw.strip():
            out.append({"time": None, "level": "", "user": "", "message": raw, "raw": raw})
    return out


def parse_since(text, now=None):
    now = now or datetime.datetime.now()
    m = re.fullmatch(r"(\d+)([mhd])", text.strip().lower())
    if m:
        return now - datetime.timedelta(**{{"m": "minutes", "h": "hours", "d": "days"}[m.group(2)]: int(m.group(1))})
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text.strip(), fmt)
        except ValueError:
            pass
    raise ValueError("Use 2h, 3d, 2026-10-05 or '2026-10-05 14:30'.")


class Filters:
    def __init__(self):
        self.level = self.user = self.word = self.since = None

    def describe(self):
        parts = [f"level>={self.level}" if self.level else "", f"user={self.user}" if self.user else "",
                 f"contains '{self.word}'" if self.word else "", f"since {self.since:%Y-%m-%d %H:%M}" if self.since else ""]
        return ", ".join(p for p in parts if p) or "no filters"

    def apply(self, entries):
        floor = LEVELS.get(self.level) if self.level else None
        out = []
        for e in entries:
            if floor is not None and LEVELS.get(e["level"].lower(), 1) < floor:
                continue
            if self.user and e["user"] != self.user:
                continue
            if self.word and self.word.lower() not in e["raw"].lower():
                continue
            if self.since and (e["time"] is None or e["time"] < self.since):
                continue
            out.append(e)
        return out


def styled(entry, word=None):
    colour = {"ERROR": "bold red", "WARN": "yellow", "WARNING": "yellow", "DEBUG": "dim"}.get(entry["level"], "")
    text = Text(entry["raw"], style=colour)
    if word:
        text.highlight_words([re.escape(word)], style="black on yellow", case_sensitive=False)
    return text


def read_log(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return parse(f.readlines())


def follow(path, filters):
    console.print("[dim]Following the log. Press Ctrl+C to stop.[/dim]")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for e in filters.apply(parse(f.readlines()[-10:])):
                console.print(styled(e, filters.word))
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.4)
                    continue
                for e in filters.apply(parse([line])):
                    console.print(styled(e, filters.word))
    except KeyboardInterrupt:
        console.print()


def main(args):
    path = fs.resolve(args[0]) if args else os.path.join(fs.BASE_DIR, "var", "log", "system.log")
    shown_name = fs.display(path)
    if not os.path.isfile(path):
        console.print(f"[yellow]{escape(shown_name)} does not exist (yet).[/yellow]")
        return
    me, role = fs.current_user()
    filters = Filters()
    entries = read_log(path)
    page_from = None
    console.print(f"[bold]Log viewer[/bold]  {escape(shown_name)}  ({len(entries)} lines)   level warn | user NAME | find WORD | since 2h | clear | follow | top | bottom | page N | export FILE | q")
    while True:
        view = filters.apply(entries)
        if role != "admin" and path.endswith("system.log"):
            view = [e for e in view if e["user"] in ("", me)]
        start = len(view) - PAGE if page_from is None else page_from
        start = max(0, min(start, max(0, len(view) - 1)))
        for e in view[start:start + PAGE]:
            console.print(styled(e, filters.word))
        console.print(f"[dim]{len(view)} line(s) match ({filters.describe()}); showing {start + 1 if view else 0}-{min(len(view), start + PAGE)}[/dim]")
        try:
            parts = input("log> ").strip().split(None, 1)
        except EOFError:
            return
        if not parts:
            page_from = start + PAGE if start + PAGE < len(view) else None
            continue
        cmd, rest = parts[0].lower(), parts[1].strip() if len(parts) > 1 else ""
        page_from = None
        try:
            if cmd in ("q", "quit"):
                return
            if cmd == "level":
                if rest.lower() not in LEVELS:
                    raise ValueError("level must be info, warn or error")
                filters.level = rest.lower()
            elif cmd == "user":
                filters.user = rest or None
            elif cmd in ("find", "grep"):
                filters.word = rest or None
            elif cmd == "since":
                filters.since = parse_since(rest)
            elif cmd == "clear":
                filters = Filters()
            elif cmd == "follow":
                follow(path, filters)
                entries = read_log(path)
            elif cmd == "top":
                page_from = 0
            elif cmd == "bottom":
                page_from = None
            elif cmd == "page" and rest.isdigit():
                page_from = (int(rest) - 1) * PAGE
            elif cmd == "export" and rest:
                with open(fs.resolve(rest, write=True), "w", encoding="utf-8") as out:
                    out.writelines(e["raw"] + "\n" for e in view)
                console.print(f"[green]Wrote {len(view)} line(s) to {escape(rest)}[/green]")
            elif cmd == "reload":
                entries = read_log(path)
            else:
                console.print("[yellow]Commands: level, user, find, since, clear, follow, top, bottom, page N, export FILE, reload, q[/yellow]")
        except (ValueError, OSError, PermissionError) as e:
            console.print(f"[red]{escape(fs.errtext(e) if isinstance(e, OSError) else str(e))}[/red]")


def execute(args=None):
    try:
        main(list(args or []))
    except PermissionError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
