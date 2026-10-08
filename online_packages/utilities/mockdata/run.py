#!/usr/bin/env python3
"""Mock data: believable fake data for testing (the Faker library, offline).

    mockdata name 5                 five names
    mockdata person                 a whole fake person: name, email, phone, address, company, job
    mockdata email 3 --locale de_DE names and addresses in German style (fr_FR, es_ES, ja_JP, en_GB, ...)
    mockdata text 2                 two paragraphs of text
    mockdata person 3 --csv         several people as CSV
    mockdata name 3 --seed 7        the same seed always gives the same data
Kinds: name, email, user, phone, address, company, job, city, country, sentence, text, date, uuid, person.
"""
import csv
import io
import sys

from rich.console import Console
from rich.markup import escape

console = Console()

SIMPLE = {"name": "name", "email": "email", "user": "user_name", "phone": "phone_number", "address": "address", "company": "company", "job": "job",
          "city": "city", "country": "country", "sentence": "sentence", "text": "paragraph", "date": "date", "uuid": "uuid4"}
PERSON = [("name", "name"), ("email", "email"), ("phone", "phone_number"), ("address", "address"), ("company", "company"), ("job", "job")]


def make(fake, kind, count):
    """A list with `count` values for a kind; for 'person' a list of dicts. Raises ValueError for an unknown kind."""
    count = max(1, min(count, 200))
    if kind == "person":
        return [{label: str(getattr(fake, method)()).replace("\n", ", ") for label, method in PERSON} for _ in range(count)]
    if kind not in SIMPLE:
        raise ValueError(f"I do not know '{kind}'. Kinds: " + ", ".join(sorted(list(SIMPLE) + ["person"])))
    return [str(getattr(fake, SIMPLE[kind])()) for _ in range(count)]


def parse(argv):
    argv = list(argv)
    options = {"locale": "en_US", "seed": None, "csv": False}
    for flag in ("--locale", "--seed"):
        if flag in argv:
            i = argv.index(flag)
            try:
                options[flag[2:]] = argv[i + 1]
            except IndexError:
                raise ValueError(f"{flag} needs a value") from None
            del argv[i:i + 2]
    if "--csv" in argv:
        argv.remove("--csv")
        options["csv"] = True
    if not argv:
        raise ValueError("")
    kind, count = argv[0].lower(), 1
    if len(argv) > 1:
        try:
            count = int(argv[1])
        except ValueError:
            raise ValueError(f"'{argv[1]}' is not a number") from None
    if options["seed"] is not None:
        try:
            options["seed"] = int(options["seed"])
        except ValueError:
            raise ValueError("--seed needs a number") from None
    return kind, count, options


def to_csv(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def main(argv):
    try:
        kind, count, options = parse(argv)
    except ValueError as e:
        console.print(__doc__)
        if str(e):
            console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    try:
        from faker import Faker
    except ImportError:
        console.print("[red]The 'faker' library is not installed. Install this app again to get it.[/red]")
        return 1
    try:
        fake = Faker(options["locale"])
    except Exception:                                           # noqa: BLE001 - Faker raises AttributeError for an unknown locale
        console.print(f"[red]No data for the language '{escape(options['locale'])}' (try de_DE, fr_FR, es_ES, ja_JP, en_GB).[/red]")
        return 1
    if options["seed"] is not None:
        Faker.seed(options["seed"])
    try:
        rows = make(fake, kind, count)
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    if kind == "person" and options["csv"]:
        print(to_csv(rows), end="")
    elif kind == "person":
        for row in rows:
            for label, value in row.items():
                console.print(f"[dim]{label:8}[/dim] {escape(value)}")
            console.print()
    else:
        for value in rows:
            print(value)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
