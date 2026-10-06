#!/usr/bin/env python3
"""World clock: the time somewhere else.

    worldclock                         a set of big cities
    worldclock tokyo "new york"        just these
    worldclock 15:00 london to tokyo   what 15:00 in London is in Tokyo (today)
City names or zone names (Europe/Paris) both work.
"""
import datetime
import re
import sys

from rich.console import Console
from rich.table import Table

try:
    from zoneinfo import ZoneInfo
except ImportError:                                        # Python older than 3.9
    ZoneInfo = None

console = Console()
CITIES = {
    "london": "Europe/London", "paris": "Europe/Paris", "berlin": "Europe/Berlin", "madrid": "Europe/Madrid", "rome": "Europe/Rome", "amsterdam": "Europe/Amsterdam",
    "dublin": "Europe/Dublin", "lisbon": "Europe/Lisbon", "athens": "Europe/Athens", "moscow": "Europe/Moscow", "istanbul": "Europe/Istanbul", "stockholm": "Europe/Stockholm",
    "cairo": "Africa/Cairo", "lagos": "Africa/Lagos", "nairobi": "Africa/Nairobi", "johannesburg": "Africa/Johannesburg", "dubai": "Asia/Dubai", "tehran": "Asia/Tehran",
    "karachi": "Asia/Karachi", "delhi": "Asia/Kolkata", "mumbai": "Asia/Kolkata", "dhaka": "Asia/Dhaka", "bangkok": "Asia/Bangkok", "jakarta": "Asia/Jakarta",
    "singapore": "Asia/Singapore", "hong kong": "Asia/Hong_Kong", "shanghai": "Asia/Shanghai", "beijing": "Asia/Shanghai", "seoul": "Asia/Seoul", "tokyo": "Asia/Tokyo",
    "manila": "Asia/Manila", "sydney": "Australia/Sydney", "melbourne": "Australia/Melbourne", "perth": "Australia/Perth", "auckland": "Pacific/Auckland",
    "honolulu": "Pacific/Honolulu", "anchorage": "America/Anchorage", "los angeles": "America/Los_Angeles", "san francisco": "America/Los_Angeles", "vancouver": "America/Vancouver",
    "denver": "America/Denver", "chicago": "America/Chicago", "mexico city": "America/Mexico_City", "new york": "America/New_York", "toronto": "America/Toronto",
    "miami": "America/New_York", "bogota": "America/Bogota", "lima": "America/Lima", "santiago": "America/Santiago", "buenos aires": "America/Argentina/Buenos_Aires",
    "sao paulo": "America/Sao_Paulo", "reykjavik": "Atlantic/Reykjavik", "utc": "UTC", "gmt": "UTC",
}
DEFAULT = ["utc", "london", "paris", "dubai", "delhi", "singapore", "tokyo", "sydney", "los angeles", "new york"]


def zone_for(name):
    """The ZoneInfo for a city or zone name, or None."""
    if ZoneInfo is None:
        return None
    key = re.sub(r"\s+", " ", name.strip().lower().replace("_", " "))
    zone = CITIES.get(key) or name.strip()
    try:
        return ZoneInfo(zone)
    except Exception:                                      # noqa: BLE001 - unknown zone, or no time zone data on this system
        for known, value in CITIES.items():
            if key and key in known:
                return ZoneInfo(value)
        return None


def label(name, zone):
    return name.title() if name.lower() in CITIES else str(zone)


def offset_text(moment):
    delta = moment.utcoffset() or datetime.timedelta()
    minutes = int(delta.total_seconds() // 60)
    sign = "+" if minutes >= 0 else "-"
    return f"UTC{sign}{abs(minutes) // 60:02d}:{abs(minutes) % 60:02d}"


def convert(clock, source, target, today=None):
    """The datetime in `target` of `clock` ('15:00' or '3:30pm') in `source` today. Returns None for a time that cannot be read."""
    match = re.fullmatch(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", clock.strip().lower())
    if not match:
        return None
    hour, minute, ampm = int(match.group(1)), int(match.group(2) or 0), match.group(3)
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    day = today or datetime.datetime.now(source).date()
    return datetime.datetime(day.year, day.month, day.day, hour, minute, tzinfo=source).astimezone(target)


def execute(args=None):
    args = list(args or [])
    if ZoneInfo is None:
        console.print("[bold red]worldclock needs Python 3.9 or newer.[/bold red]")
        return False
    text = " ".join(args)
    match = re.fullmatch(r"(\S+)\s+(.+?)\s+(?:to|in)\s+(.+)", text, re.I)
    if match and re.match(r"\d", match.group(1)):
        source, target = zone_for(match.group(2)), zone_for(match.group(3))
        if source is None or target is None:
            console.print(f"[yellow]I do not know the place '{(match.group(2) if source is None else match.group(3))}'. Try a big city or a zone like Europe/Paris.[/yellow]")
            return False
        result = convert(match.group(1), source, target)
        if result is None:
            console.print("[yellow]Write the time like 15:00 or 3:30pm.[/yellow]")
            return False
        console.print(f"{match.group(1)} in {match.group(2).title()} is [bold]{result.strftime('%H:%M')}[/bold] in {match.group(3).title()} "
                      f"[dim]({result.strftime('%A %d %B')}, {offset_text(result)})[/dim]")
        return True
    names = [a for a in re.split(r",|\s{2,}", text) if a.strip()] if "," in text else args or DEFAULT
    table = Table(header_style="bold blue")
    for column in ("Place", "Time", "Date", "Offset"):
        table.add_column(column)
    missing = []
    for name in names:
        zone = zone_for(name)
        if zone is None:
            missing.append(name)
            continue
        moment = datetime.datetime.now(zone)
        table.add_row(label(name, zone), moment.strftime("%H:%M"), moment.strftime("%a %d %b"), offset_text(moment))
    if table.row_count:
        console.print(table)
    for name in missing:
        console.print(f"[yellow]I do not know the place '{name}'.[/yellow]")
    return not missing


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
