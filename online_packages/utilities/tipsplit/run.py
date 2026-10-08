#!/usr/bin/env python3
"""Tip and split: add a tip to a bill and share it out.

    tipsplit 84.50                   a 15% tip, one person
    tipsplit 84.50 20 4              a 20% tip split between 4 people
    tipsplit 84.50 18 3 --tax 6.5    tip on the bill before the 6.5% tax (the tax is added after)
    tipsplit 84.50 18 4 --round      round what each person pays up to a whole amount
Amounts are in whatever money you are using; nothing is converted.
"""
import sys
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation

from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()
CENT = Decimal("0.01")


def money(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def number(text, what, low=Decimal(0), high=None):
    try:
        value = Decimal(text.replace(",", "."))
    except InvalidOperation:
        raise ValueError(f"{what} must be a number, not '{text}'") from None
    if value < low or (high is not None and value > high):
        raise ValueError(f"{what} must be {'at least ' + str(low) if high is None else 'between ' + str(low) + ' and ' + str(high)}")
    return value


def calculate(bill, tip_percent=Decimal(15), people=1, tax_percent=Decimal(0), round_up=False):
    """A dict with the tip, the total and what each person pays. The tip is worked out on the bill before tax, and tax is added to the bill.
    Each person's share is rounded up to the cent (or to a whole amount with round_up), so the shares always add up to at least the total."""
    if people < 1:
        raise ValueError("there must be at least one person")
    tax = money(bill * tax_percent / 100)
    tip = money(bill * tip_percent / 100)
    total = bill + tax + tip
    share = total / people
    each = share.quantize(Decimal(1), rounding=ROUND_CEILING) if round_up else share.quantize(CENT, rounding=ROUND_CEILING)
    paid = each * people
    return {"bill": money(bill), "tax": tax, "tip": tip + (paid - total if round_up else Decimal(0)), "tip_plain": tip, "total": total,
            "each": each, "paid": paid, "extra": paid - total}


def parse(argv):
    argv = list(argv)
    tax = Decimal(0)
    round_up = "--round" in argv
    argv = [a for a in argv if a != "--round"]
    if "--tax" in argv:
        i = argv.index("--tax")
        try:
            tax = number(argv[i + 1], "the tax", high=Decimal(100))
        except IndexError:
            raise ValueError("--tax needs a percentage") from None
        del argv[i:i + 2]
    if not argv or len(argv) > 3:
        raise ValueError("")
    bill = number(argv[0], "the bill", low=Decimal("0.01"))
    tip = number(argv[1], "the tip", high=Decimal(100)) if len(argv) > 1 else Decimal(15)
    people = int(number(argv[2], "the number of people", low=Decimal(1), high=Decimal(100))) if len(argv) > 2 else 1
    return bill, tip, people, tax, round_up


def main(argv):
    try:
        bill, tip_percent, people, tax_percent, round_up = parse(argv)
        result = calculate(bill, tip_percent, people, tax_percent, round_up)
    except ValueError as e:
        console.print(__doc__)
        if str(e):
            console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    table = Table(show_header=False, box=None)
    table.add_column(style="dim")
    table.add_column(justify="right")
    table.add_row("Bill", f"{result['bill']:,.2f}")
    if tax_percent:
        table.add_row(f"Tax ({tax_percent:g}%)", f"{result['tax']:,.2f}")
    table.add_row(f"Tip ({tip_percent:g}%)", f"{result['tip_plain']:,.2f}")
    table.add_row("[bold]Total[/bold]", f"[bold]{result['total']:,.2f}[/bold]")
    if people > 1:
        table.add_row(f"[bold]Each of {people}[/bold]", f"[bold green]{result['each']:,.2f}[/bold green]")
        if result["extra"]:
            table.add_row("[dim]rounded up by[/dim]", f"[dim]{result['extra']:,.2f}[/dim]")
    console.print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
