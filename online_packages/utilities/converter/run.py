#!/usr/bin/env python3
"""Converter: unit conversions and a calculator that remembers its history. Nothing is ever evaluated as code."""
import sys
import ast
import math
import operator
import re

from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt
from rich.table import Table

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
HISTORY = "calc_history"
MAX_HISTORY = 200

# ------------------------------------------------------------------ units
# each category: unit -> factor to the base unit (temperature is special-cased)
UNITS = {
    "length": {"m": 1, "km": 1000, "cm": 0.01, "mm": 0.001, "mi": 1609.344, "yd": 0.9144, "ft": 0.3048, "in": 0.0254, "nmi": 1852},
    "mass": {"kg": 1, "g": 0.001, "mg": 1e-6, "t": 1000, "lb": 0.45359237, "oz": 0.028349523125, "st": 6.35029318},
    "volume": {"l": 1, "ml": 0.001, "m3": 1000, "gal": 3.785411784, "qt": 0.946352946, "pt": 0.473176473, "cup": 0.2365882365,
               "floz": 0.0295735295625, "tbsp": 0.01478676478125, "tsp": 0.00492892159375, "ukgal": 4.54609},
    "time": {"s": 1, "ms": 0.001, "min": 60, "h": 3600, "d": 86400, "wk": 604800, "yr": 31557600},
    "speed": {"m/s": 1, "km/h": 1 / 3.6, "mph": 0.44704, "kn": 0.514444, "ft/s": 0.3048},
    "area": {"m2": 1, "km2": 1e6, "cm2": 1e-4, "ha": 1e4, "acre": 4046.8564224, "ft2": 0.09290304, "mi2": 2589988.110336},
    "data": {"b": 1, "kb": 1000, "mb": 1e6, "gb": 1e9, "tb": 1e12, "kib": 1024, "mib": 1024 ** 2, "gib": 1024 ** 3, "tib": 1024 ** 4,
             "bit": 0.125},
    "energy": {"j": 1, "kj": 1000, "cal": 4.184, "kcal": 4184, "wh": 3600, "kwh": 3.6e6},
    "pressure": {"pa": 1, "kpa": 1000, "bar": 1e5, "psi": 6894.757293168, "atm": 101325, "mmhg": 133.322387415},
    "temperature": {"c": None, "f": None, "k": None},
}
ALIASES = {"meter": "m", "metre": "m", "meters": "m", "kilometer": "km", "kilometers": "km", "mile": "mi", "miles": "mi",
           "feet": "ft", "foot": "ft", "inch": "in", "inches": "in", "kilogram": "kg", "kilograms": "kg", "gram": "g",
           "pound": "lb", "pounds": "lb", "lbs": "lb", "ounce": "oz", "ounces": "oz", "liter": "l", "litre": "l",
           "liters": "l", "litres": "l", "gallon": "gal", "gallons": "gal", "second": "s", "seconds": "s", "sec": "s",
           "minute": "min", "minutes": "min", "hour": "h", "hours": "h", "hr": "h", "day": "d", "days": "d", "week": "wk",
           "weeks": "wk", "year": "yr", "years": "yr", "kph": "km/h", "kmh": "km/h", "knot": "kn", "knots": "kn",
           "celsius": "c", "fahrenheit": "f", "kelvin": "k", "°c": "c", "°f": "f", "megabyte": "mb", "gigabyte": "gb",
           "terabyte": "tb", "kilobyte": "kb", "byte": "b", "bytes": "b", "km2": "km2", "sqm": "m2", "sqft": "ft2",
           "hectare": "ha", "acres": "acre", "calorie": "cal", "calories": "cal", "joule": "j", "joules": "j",
           "tonne": "t", "stone": "st", "teaspoon": "tsp", "tablespoon": "tbsp", "cups": "cup"}


def unit_key(text):
    text = text.strip().lower()
    return ALIASES.get(text, text)


def category_of(unit):
    for cat, table in UNITS.items():
        if unit in table:
            return cat
    return None


def to_celsius(value, unit):
    return value if unit == "c" else (value - 32) * 5 / 9 if unit == "f" else value - 273.15


def from_celsius(value, unit):
    return value if unit == "c" else value * 9 / 5 + 32 if unit == "f" else value + 273.15


def convert(value, src, dst):
    src, dst = unit_key(src), unit_key(dst)
    a, b = category_of(src), category_of(dst)
    if a is None:
        raise ValueError(f"I do not know the unit '{src}'")
    if b is None:
        raise ValueError(f"I do not know the unit '{dst}'")
    if a != b:
        raise ValueError(f"You cannot convert {src} ({a}) to {dst} ({b})")
    if a == "temperature":
        return from_celsius(to_celsius(value, src), dst)
    return value * UNITS[a][src] / UNITS[a][dst]


def pretty(x):
    if x == 0:
        return "0"
    if abs(x) >= 1e12 or abs(x) < 1e-4:
        return f"{x:.6g}"
    return f"{x:,.6f}".rstrip("0").rstrip(".")


def parse_conversion(text):
    """'5 km to mi', '100f in c', '12 inches mm' -> (value, from, to)."""
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*([^\s\d][^\s]*)\s+(?:to|in|into|as)?\s*([^\s]+)\s*", text, re.I)
    if not m:
        raise ValueError("Write it like: 5 km to mi")
    return float(m.group(1)), m.group(2), m.group(3)


# ------------------------------------------------------------- calculator
_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
           ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "log": math.log10, "ln": math.log,
          "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil, "exp": math.exp, "fact": math.factorial}
_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def calculate(expression, last=0):
    """Evaluate arithmetic with numbers, + - * / // % ** ( ), a few functions and constants, and 'ans'."""
    consts = dict(_CONSTS, ans=last)
    tree = ast.parse(expression.replace("^", "**").replace("x", "*") if re.fullmatch(r"[\d\s.xX+\-*/()^%]+", expression) else
                     expression.replace("^", "**"), mode="eval")

    def ev(node, depth=0):
        if depth > 40:
            raise ValueError("too deeply nested")
        if isinstance(node, ast.Expression):
            return ev(node.body, depth + 1)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.Name) and node.id in consts:
            return consts[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
            left, right = ev(node.left, depth + 1), ev(node.right, depth + 1)
            if isinstance(node.op, ast.Pow) and (abs(right) > 1000 or abs(left) > 1e12):
                raise ValueError("that power is too large")
            return _BINARY[type(node.op)](left, right)
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _UNARY[type(node.op)](ev(node.operand, depth + 1))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCS and not node.keywords:
            return _FUNCS[node.func.id](*[ev(a, depth + 1) for a in node.args])
        raise ValueError("I can only do arithmetic here")

    return ev(tree)


# ---------------------------------------------------------------- history
def load_history():
    return (appdata.load(HISTORY, []) if appdata else []) or []


def remember(expression, result):
    if appdata:
        items = load_history()
        items.append({"expr": expression, "result": result})
        appdata.save(HISTORY, items[-MAX_HISTORY:])


def show_history(limit=15):
    items = load_history()[-limit:]
    if not items:
        console.print("[dim]No calculations yet.[/dim]")
        return
    table = Table(title="Calculator history", header_style="bold blue")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Calculation")
    table.add_column("Result", style="bold green")
    for i, item in enumerate(items, 1):
        table.add_row(str(i), escape(item["expr"]), pretty(item["result"]) if isinstance(item["result"], (int, float)) else str(item["result"]))
    console.print(table)


def calculator():
    console.print("[bold]Calculator[/bold]  [dim]type a sum; 'ans' is the last answer; 'history' to review; 'clear' to forget; blank to leave[/dim]")
    items = load_history()
    last = items[-1]["result"] if items and isinstance(items[-1]["result"], (int, float)) else 0
    while True:
        text = Prompt.ask("[cyan]calc[/cyan]", default="").strip()
        if not text:
            return
        if text == "history":
            show_history()
        elif text == "clear":
            if appdata:
                appdata.save(HISTORY, [])
            console.print("[green]History cleared.[/green]")
        else:
            try:
                result = calculate(text, last)
            except ZeroDivisionError:
                console.print("[red]You cannot divide by zero.[/red]")
                continue
            except (ValueError, SyntaxError, TypeError, OverflowError) as e:
                console.print(f"[red]{escape(str(e)) if not isinstance(e, SyntaxError) else 'That is not a sum I understand.'}[/red]")
                continue
            last = result
            remember(text, result)
            console.print(f"  = [bold green]{pretty(result)}[/bold green]")


def converter():
    cats = ", ".join(c for c in UNITS)
    console.print(f"[bold]Converter[/bold]  [dim]for example: 5 km to mi, 100 f to c, 2 gb to mb. Categories: {cats}. 'list <category>' shows units; blank to leave[/dim]")
    while True:
        text = Prompt.ask("[cyan]convert[/cyan]", default="").strip()
        if not text:
            return
        if text.lower().startswith("list"):
            cat = text[4:].strip().lower()
            if cat in UNITS:
                console.print(f"{cat}: " + ", ".join(UNITS[cat]))
            else:
                console.print("Categories: " + cats)
            continue
        try:
            value, src, dst = parse_conversion(text)
            result = convert(value, src, dst)
        except ValueError as e:
            console.print(f"[red]{escape(str(e))}[/red]")
            continue
        console.print(f"  {pretty(value)} {unit_key(src)} = [bold green]{pretty(result)} {unit_key(dst)}[/bold green]")
        remember(f"{pretty(value)} {unit_key(src)} to {unit_key(dst)}", f"{pretty(result)} {unit_key(dst)}")


def execute(args=None):
    args = list(args or [])
    try:
        if args and args[0] == "history":
            show_history(50)
        elif args and args[0] in ("calc", "calculator"):
            if len(args) > 1:
                console.print(pretty(calculate(" ".join(args[1:]))))
            else:
                calculator()
        elif args:
            value, src, dst = parse_conversion(" ".join(args))
            console.print(f"{pretty(value)} {unit_key(src)} = [bold green]{pretty(convert(value, src, dst))} {unit_key(dst)}[/bold green]")
        else:
            while True:
                choice = Prompt.ask("[bold](c)[/bold]alculator  [bold](u)[/bold]nit converter  [bold](h)[/bold]istory  [bold](q)[/bold]uit",
                                    choices=["c", "u", "h", "q"], default="q")
                if choice == "q":
                    return
                {"c": calculator, "u": converter, "h": show_history}[choice]()
    except (ValueError, SyntaxError, ZeroDivisionError, OverflowError) as e:
        console.print(f"[red]{escape(str(e))}[/red]")
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
