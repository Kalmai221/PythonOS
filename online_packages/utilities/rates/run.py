#!/usr/bin/env python3
"""Exchange rates: the European Central Bank's reference rates through frankfurter.dev (no account or key). Rates are published on working days.

    rates 100 usd eur                100 US dollars in euros
    rates 250 gbp usd jpy            one amount, several currencies
    rates usd                        1 dollar in the main currencies
    rates 100 usd eur --date 2024-12-24    the rate on a day in the past
    rates list                       every currency it knows
These are reference rates, not what a bank or a card will give you. Nothing here is financial advice.
"""
import re
import sys
from decimal import Decimal, InvalidOperation

import requests
from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()
BASE = "https://api.frankfurter.dev/v1/"
HEADERS = {"User-Agent": "PythonOS-rates/1.0 (https://github.com/Kalmai221/PythonOS)"}
MAIN = ["EUR", "USD", "GBP", "JPY", "CHF", "CAD", "AUD", "CNY", "INR"]


def parse(argv):
    """(amount, base, targets, date, list?). Raises ValueError with a sentence (empty = show the help)."""
    argv, date = list(argv), None
    if "--date" in argv:
        i = argv.index("--date")
        date = argv[i + 1] if i + 1 < len(argv) else ""
        del argv[i:i + 2]
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise ValueError("--date needs a day like 2024-12-24")
    if argv == ["list"]:
        return Decimal(1), "", [], date, True
    amount = Decimal(1)
    if argv:
        try:
            amount = Decimal(argv[0].replace(",", "."))
            argv = argv[1:]
        except InvalidOperation:
            pass
    if amount <= 0 or amount > Decimal("1e12"):
        raise ValueError("The amount must be more than 0.")
    codes = [a.upper() for a in argv if a.lower() not in ("to", "in")]
    if not codes:
        raise ValueError("")
    if any(not re.fullmatch(r"[A-Z]{3}", c) for c in codes):
        raise ValueError("Currencies are three-letter codes like USD, EUR or GBP (see: rates list).")
    base, targets = codes[0], codes[1:] or [c for c in MAIN if c != codes[0]]
    return amount, base, targets[:12], date, False


def convert(amount, rates):
    """{currency: amount in it} from the service's rates for one unit."""
    return {code: amount * Decimal(str(rate)) for code, rate in rates.items()}


def digits(value):
    return f"{value:,.2f}" if abs(value) >= 1 else f"{value:,.4f}"


def main(argv):
    try:
        amount, base, targets, date, listing = parse(argv)
    except ValueError as e:
        console.print(__doc__)
        if str(e):
            console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    try:
        if listing:
            response = requests.get(BASE + "currencies", timeout=10, headers=HEADERS)
            response.raise_for_status()
            names = response.json()
            table = Table(title=f"{len(names)} currencies")
            table.add_column("Code")
            table.add_column("Name")
            for code in sorted(names):
                table.add_row(code, escape(str(names[code])))
            console.print(table)
            return 0
        response = requests.get(BASE + (date or "latest"), params={"base": base, "symbols": ",".join(targets)}, timeout=10, headers=HEADERS)
        if response.status_code in (404, 422):
            console.print(f"[red]I do not know those currencies{' on that day' if date else ''}. See: rates list[/red]")
            return 1
        response.raise_for_status()
        data = response.json()
        results = convert(amount, data.get("rates") or {})
    except (requests.RequestException, ValueError, InvalidOperation) as e:
        console.print(f"[red]Could not reach the rates service ({escape(type(e).__name__)}). Check the internet connection.[/red]")
        return 1
    if not results:
        console.print("No rates came back for those currencies.")
        return 1
    table = Table(title=f"{digits(amount)} {base} on {data.get('date', '?')}")
    table.add_column("Currency")
    table.add_column("Amount", justify="right")
    table.add_column("Rate for 1", justify="right", style="dim")
    for code, value in results.items():
        table.add_row(code, f"[bold]{digits(value)}[/bold]", f"{Decimal(str(data['rates'][code])):,.4f}")
    console.print(table)
    console.print("[dim]European Central Bank reference rates. Not what a bank or a card gives you.[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
