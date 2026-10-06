#!/usr/bin/env python3
"""Expenses: write down what you spend and see where it goes.

    expenses                          the menu
    expenses add 12.50 food lunch     add an expense (amount, category, note)
    expenses month                    this month by category
    expenses list                     the latest expenses
Amounts are kept in whole cents, so the totals are exact.
"""
import datetime
import json
import os
import re
import sys

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

console = Console()


def data_file():
    """Per-user storage inside the PyOS home directory (falls back to files/)."""
    try:
        with open("current_user.json") as f:
            user = json.load(f)["username"]
    except Exception:
        user = None
    folder = os.path.join("files", "home", user) if user else "files"
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, ".expenses.json")


def load():
    try:
        with open(data_file()) as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save(items):
    with open(data_file(), "w") as f:
        json.dump(items, f, indent=2)


def parse_amount(text):
    """'12.5', '12,50' or '1 200.00' -> cents (1250, 1250, 120000). None if it is not an amount above zero."""
    text = str(text).strip().replace(" ", "")
    if re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d{1,2})?", text):
        text = text.replace(",", "")
    text = text.replace(",", ".")
    if not re.fullmatch(r"\d+(\.\d{1,2})?", text):
        return None
    whole, _, cents = text.partition(".")
    value = int(whole) * 100 + int((cents + "00")[:2])
    return value or None


def money(cents):
    return f"{cents // 100:,}.{cents % 100:02d}"


def add(items, cents, category, note="", on=None):
    items.append({"date": (on or datetime.date.today()).isoformat(), "cents": cents, "category": category.strip().lower() or "other", "note": note.strip()})
    return items[-1]


def month_totals(items, month):
    """({category: cents}, total) for the month 'YYYY-MM'."""
    totals = {}
    for item in items:
        if item["date"].startswith(month):
            totals[item["category"]] = totals.get(item["category"], 0) + item["cents"]
    return totals, sum(totals.values())


def show_month(items, month=None):
    month = month or datetime.date.today().strftime("%Y-%m")
    totals, total = month_totals(items, month)
    if not totals:
        console.print(f"[yellow]Nothing spent in {month}.[/yellow]")
        return
    table = Table(title=month, header_style="bold blue")
    for column in ("Category", "Spent", "Share"):
        table.add_column(column, justify="left" if column == "Category" else "right")
    for category, cents in sorted(totals.items(), key=lambda kv: -kv[1]):
        table.add_row(category, money(cents), f"{cents * 100 // total}%")
    table.add_row("[bold]Total[/bold]", f"[bold]{money(total)}[/bold]", "")
    console.print(table)


def show_list(items, count=15):
    if not items:
        console.print("[yellow]No expenses yet. Add one with 'a'.[/yellow]")
        return
    table = Table(header_style="bold blue")
    for column in ("#", "Date", "Amount", "Category", "Note"):
        table.add_column(column, justify="right" if column in ("#", "Amount") else "left")
    start = max(0, len(items) - count)
    for number, item in enumerate(items[start:], start + 1):
        table.add_row(str(number), item["date"], money(item["cents"]), item["category"], item["note"])
    console.print(table)


def cli(args):
    items = load()
    if args[0] == "add" and len(args) >= 3 and parse_amount(args[1]):
        item = add(items, parse_amount(args[1]), args[2], " ".join(args[3:]))
        save(items)
        console.print(f"[green]Added {money(item['cents'])} to {item['category']}.[/green]")
    elif args[0] == "month":
        show_month(items, args[1] if len(args) > 1 else None)
    elif args[0] in ("list", "ls"):
        show_list(items)
    else:
        console.print("expenses [add <amount> <category> [note] | month [YYYY-MM] | list]   (no arguments opens the menu)")


def menu():
    items = load()
    while True:
        console.print("\n[bold]Expenses[/bold]")
        show_month(items)
        action = Prompt.ask("(a)dd  (l)ist  (m)onth  (r)emove  (q)uit", choices=["a", "l", "m", "r", "q"], default="q")
        if action == "q":
            break
        if action == "a":
            cents = parse_amount(Prompt.ask("Amount"))
            if not cents:
                console.print("[red]That is not an amount.[/red]")
                continue
            add(items, cents, Prompt.ask("Category", default="other"), Prompt.ask("Note", default=""))
        elif action == "l":
            show_list(items)
        elif action == "m":
            show_month(items, Prompt.ask("Month (YYYY-MM)", default=datetime.date.today().strftime("%Y-%m")))
        elif action == "r" and items:
            show_list(items)
            number = Prompt.ask("Number to remove")
            if number.isdigit() and 1 <= int(number) <= len(items):
                items.pop(int(number) - 1)
        save(items)


def execute(args=None):
    try:
        if args:
            cli(list(args))
        else:
            menu()
    except (KeyboardInterrupt, EOFError):
        console.print()
    return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
