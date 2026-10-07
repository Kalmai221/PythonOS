#!/usr/bin/env python3
"""Loan: what a loan or mortgage really costs.

    loan 250000 5.5 30                  amount, yearly interest in %, years
    loan 250000 5.5 30 --extra 200      with 200 extra paid every month: how much sooner, how much saved
    loan 250000 5.5 30 --table          the first year, month by month
    loan 250000 5.5 30 --years          the balance and interest at the end of every year
"""
import sys

from rich.console import Console
from rich.table import Table

console = Console()


def payment(principal, yearly_percent, years):
    """The fixed monthly payment."""
    n = round(years * 12)
    r = yearly_percent / 100 / 12
    if n <= 0:
        raise ValueError("the loan must last at least a month")
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def schedule(principal, yearly_percent, years, extra=0.0):
    """[(month, payment, interest, principal_paid, balance)]: every month until the loan is paid off."""
    r = yearly_percent / 100 / 12
    pay = payment(principal, yearly_percent, years)
    balance, rows, month = principal, [], 0
    while balance > 0.005 and month < 12 * 100:
        month += 1
        interest = balance * r
        due = min(pay + extra, balance + interest)
        paid = due - interest
        balance -= paid
        rows.append((month, due, interest, paid, max(balance, 0.0)))
    return rows


def money(x):
    return f"{x:,.2f}"


def totals(rows):
    return sum(r[1] for r in rows), sum(r[2] for r in rows)


def main(argv):
    flags = {a for a in argv if a.startswith("--") and a != "--extra"}
    extra = 0.0
    args = []
    i = 0
    while i < len(argv):
        if argv[i] == "--extra" and i + 1 < len(argv):
            try:
                extra = float(argv[i + 1])
            except ValueError:
                console.print("[red]--extra needs a number[/red]")
                return 1
            i += 2
        elif argv[i].startswith("--"):
            i += 1
        else:
            args.append(argv[i])
            i += 1
    if len(args) != 3:
        console.print(__doc__)
        return 1
    try:
        principal, rate, years = (float(a.replace(",", "")) for a in args)
        if principal <= 0 or rate < 0 or years <= 0:
            raise ValueError("amount and years must be above zero, and the rate cannot be negative")
        base = schedule(principal, rate, years)
        pay = payment(principal, rate, years)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        return 1
    paid, interest = totals(base)
    console.print(f"[bold]Monthly payment:[/bold] {money(pay)}")
    console.print(f"[bold]Total paid:[/bold] {money(paid)}   [bold]of which interest:[/bold] {money(interest)} ({interest / principal * 100:.0f}% of the amount)")
    if extra > 0:
        quick = schedule(principal, rate, years, extra)
        q_paid, q_interest = totals(quick)
        saved_months = len(base) - len(quick)
        console.print(f"[green]With {money(extra)} extra a month: paid off in {len(quick) // 12} years {len(quick) % 12} months "
                      f"({saved_months} months sooner), interest {money(q_interest)} - you save {money(interest - q_interest)}.[/green]")
    if "--table" in flags or "--years" in flags:
        table = Table(header_style="bold blue")
        for col in ("Month" if "--table" in flags else "Year", "Payment", "Interest", "Principal", "Balance"):
            table.add_column(col, justify="right")
        if "--table" in flags:
            for m, p, i_, pr, b in base[:12]:
                table.add_row(str(m), money(p), money(i_), money(pr), money(b))
        else:
            for year in range(1, (len(base) + 11) // 12 + 1):
                chunk = base[(year - 1) * 12:year * 12]
                table.add_row(str(year), money(sum(c[1] for c in chunk)), money(sum(c[2] for c in chunk)), money(sum(c[3] for c in chunk)), money(chunk[-1][4]))
        console.print(table)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
