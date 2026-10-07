#!/usr/bin/env python3
"""Contacts: a small private address book in your home folder.

    contacts                              list everyone
    contacts add "Ada Lovelace" --phone 555-0100 --email ada@example.com --note "met at the fair"
    contacts show ada                     everything about the first match
    contacts search 555                   look in every field
    contacts edit ada --phone 555-0199    change fields (--name, --phone, --email, --note)
    contacts remove ada                   delete (asks first)
    contacts export                       write ~/contacts.csv
"""
import csv
import json
import os
import sys

from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm
from rich.table import Table

console = Console()
FIELDS = ("name", "phone", "email", "note")


def data_file(name):
    """Per-user storage inside the PyOS home directory (falls back to files/)."""
    try:
        with open("current_user.json") as f:
            user = json.load(f)["username"]
    except Exception:
        user = None
    folder = os.path.join("files", "home", user) if user else "files"
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, name)


def load():
    try:
        with open(data_file(".contacts.json"), encoding="utf-8") as f:
            data = json.load(f)
        return [c for c in data if isinstance(c, dict) and c.get("name")] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save(people):
    with open(data_file(".contacts.json"), "w", encoding="utf-8") as f:
        json.dump(sorted(people, key=lambda c: c["name"].lower()), f, indent=2, ensure_ascii=False)


def make(name, phone="", email="", note=""):
    return {"name": " ".join(name.split()), "phone": phone.strip(), "email": email.strip(), "note": note.strip()}


def search(people, text):
    """Contacts with `text` in any field (case-insensitive); a name that starts with it comes first."""
    needle = text.lower()
    hits = [c for c in people if any(needle in str(c.get(f, "")).lower() for f in FIELDS)]
    return sorted(hits, key=lambda c: (not c["name"].lower().startswith(needle), c["name"].lower()))


def to_csv(people):
    import io
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for c in people:
        writer.writerow({f: c.get(f, "") for f in FIELDS})
    return out.getvalue()


def options(args):
    """Split ['Ada', '--phone', '1'] into the leading words and {phone: '1'}."""
    words, found, i = [], {}, 0
    while i < len(args):
        if args[i].startswith("--") and args[i][2:] in FIELDS and i + 1 < len(args):
            found[args[i][2:]] = args[i + 1]
            i += 2
        else:
            words.append(args[i])
            i += 1
    return words, found


def show_table(people):
    table = Table(header_style="bold blue")
    for col in ("Name", "Phone", "Email", "Note"):
        table.add_column(col)
    for c in people:
        table.add_row(escape(c["name"]), escape(c.get("phone", "")), escape(c.get("email", "")), escape(c.get("note", "")))
    console.print(table)


def main(args):
    people = load()
    command = args[0].lower() if args else "list"
    rest = args[1:]
    if command == "list":
        if not people:
            console.print("No contacts yet. Add one: contacts add \"Ada Lovelace\" --phone 555-0100")
            return 0
        show_table(people)
        return 0
    if command == "add":
        words, found = options(rest)
        if not words:
            console.print("[red]Usage:[/red] contacts add \"Name\" [--phone ..] [--email ..] [--note ..]")
            return 1
        person = make(" ".join(words), **found)
        if any(c["name"].lower() == person["name"].lower() for c in people):
            console.print(f"[yellow]{escape(person['name'])} is already in your contacts; use contacts edit.[/yellow]")
            return 1
        people.append(person)
        save(people)
        console.print(f"[green]Added {escape(person['name'])}.[/green]")
        return 0
    if command in ("search", "find"):
        hits = search(people, " ".join(rest))
        show_table(hits) if hits else console.print("Nobody matches.")
        return 0 if hits else 1
    if command in ("show", "edit", "remove", "rm"):
        words, found = options(rest)
        hits = search(people, " ".join(words)) if words else []
        if not hits:
            console.print("[red]Nobody matches.[/red]")
            return 1
        person = hits[0]
        if command == "show":
            for field in FIELDS:
                console.print(f"[bold]{field.capitalize():6}[/bold] {escape(person.get(field, ''))}")
            return 0
        if command == "edit":
            if not found:
                console.print("[red]Say what to change, for example --phone 555-0199[/red]")
                return 1
            person.update({k: v.strip() for k, v in found.items()})
            save(people)
            console.print(f"[green]Updated {escape(person['name'])}.[/green]")
            return 0
        if Confirm.ask(f"Remove {person['name']}?", default=False):
            people.remove(person)
            save(people)
            console.print("[green]Removed.[/green]")
        return 0
    if command == "export":
        path = os.path.join(os.path.dirname(data_file("x")), "contacts.csv")
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(to_csv(people))
        console.print(f"Wrote [bold]~/contacts.csv[/bold] ({len(people)} contacts).")
        return 0
    console.print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
