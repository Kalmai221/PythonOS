#!/usr/bin/env python3
"""Phone numbers: is it valid, where is it from, what kind of line, and how to write it (the phonenumbers library, offline).

    phone +44 20 7946 0958          international numbers start with +
    phone 020 7946 0958 GB          a national number needs its country code (two letters)
    phone 415-555-2671 US --json
"""
import json
import sys

from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()


def load():
    try:
        import phonenumbers
        from phonenumbers import carrier, geocoder, timezone
    except ImportError:
        console.print("[red]The 'phonenumbers' library is not installed. Install this app again to get it.[/red]")
        sys.exit(1)
    return phonenumbers, carrier, geocoder, timezone


def split_args(argv):
    """(number text, region or None). A last argument of two letters is the country; --json is not part of the number."""
    argv = [a for a in argv if a != "--json"]
    region = None
    if len(argv) > 1 and len(argv[-1]) == 2 and argv[-1].isalpha():
        region = argv[-1].upper()
        argv = argv[:-1]
    return " ".join(argv).strip(), region


def describe(libs, text, region=None):
    """A dict about the number, or raises ValueError with a sentence for the person."""
    phonenumbers, carrier, geocoder, timezone = libs
    try:
        number = phonenumbers.parse(text, region)
    except phonenumbers.NumberParseException as e:
        raise ValueError({"INVALID_COUNTRY_CODE": "Start the number with + and its country code, or add the country as two letters (for example GB).",
                          "NOT_A_NUMBER": "That does not look like a phone number.",
                          "TOO_SHORT_NSN": "The number is too short.",
                          "TOO_LONG": "The number is too long."}.get(getattr(e.error_type, "name", str(e.error_type)), str(e))) from e
    kind = phonenumbers.number_type(number)
    return {
        "valid": phonenumbers.is_valid_number(number),
        "possible": phonenumbers.is_possible_number(number),
        "international": phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.INTERNATIONAL),
        "national": phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.NATIONAL),
        "e164": phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164),
        "country": phonenumbers.region_code_for_number(number) or "",
        "place": geocoder.description_for_number(number, "en"),
        "carrier": carrier.name_for_number(number, "en"),
        "type": getattr(kind, "name", str(kind)).replace("_", " ").lower(),
        "timezones": list(timezone.time_zones_for_number(number)),
    }


def main(argv):
    as_json = "--json" in argv
    text, region = split_args(argv)
    if not text:
        console.print(__doc__)
        return 1
    try:
        info = describe(load(), text, region)
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    if as_json:
        print(json.dumps(info, indent=2))
        return 0
    table = Table(show_header=False, box=None)
    table.add_column(style="dim")
    table.add_column()
    table.add_row("Valid", "[green]yes[/green]" if info["valid"] else ("[yellow]possible, but not a real number[/yellow]" if info["possible"] else "[red]no[/red]"))
    table.add_row("International", escape(info["international"]))
    table.add_row("National", escape(info["national"]))
    table.add_row("For storing (E.164)", escape(info["e164"]))
    table.add_row("Country", escape(info["country"] or "unknown"))
    if info["place"]:
        table.add_row("Area", escape(info["place"]))
    table.add_row("Line type", escape(info["type"]))
    if info["carrier"]:
        table.add_row("Carrier", escape(info["carrier"]))
    if info["timezones"] and info["timezones"] != ["Etc/Unknown"]:
        table.add_row("Time zones", escape(", ".join(info["timezones"])))
    console.print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
