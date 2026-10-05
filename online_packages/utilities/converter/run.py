#!/usr/bin/env python3
"""Converter: units (length, mass, volume, time, speed, area, data, energy, pressure, temperature, fuel economy), currencies with
rates that work offline, number bases, cooking measures (cups to grams), oven gas marks, favourites, copying the result, and a calculator
that remembers its history. Nothing is ever evaluated as code.  Examples: convert 5 km to mi | 40 mpg to l/100km | 100 usd to eur |
convert 2 cups flour to g | convert ff hex to dec | convert gas 4"""
import os
import sys
import ast
import math
import operator
import re

from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt
from rich.table import Table

import time

try:
    import requests
except ImportError:
    requests = None
try:
    from pyos import appdata, fs
except ImportError:
    appdata = fs = None

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
    "fuel": {"mpg": None, "mpguk": None, "l/100km": None, "km/l": None},
    "currency": {c: None for c in ("usd", "eur", "gbp", "jpy", "cad", "aud", "chf", "cny", "inr", "mxn", "brl", "krw", "sek", "nok",
                                   "dkk", "nzd", "sgd", "hkd", "zar", "try", "pln", "czk", "huf", "ils", "thb", "idr", "php", "myr")},
}
# Approximate rates (units per 1 US dollar) used until real ones can be fetched; the app says so whenever it uses them
FALLBACK_RATES = {"usd": 1.0, "eur": 0.92, "gbp": 0.79, "jpy": 150.0, "cad": 1.36, "aud": 1.52, "chf": 0.88, "cny": 7.2, "inr": 83.0,
                  "mxn": 17.0, "brl": 5.0, "krw": 1330.0, "sek": 10.5, "nok": 10.7, "dkk": 6.9, "nzd": 1.65, "sgd": 1.34, "hkd": 7.8,
                  "zar": 18.5, "try": 32.0, "pln": 4.0, "czk": 23.0, "huf": 360.0, "ils": 3.7, "thb": 35.5, "idr": 15700.0, "php": 56.0, "myr": 4.7}
RATES_URL = "https://api.frankfurter.dev/v1/latest?base=USD"
RATES_MAX_AGE = 24 * 3600
# grams in one US cup of common ingredients
INGREDIENTS = {"flour": 125, "sugar": 200, "brown sugar": 213, "icing sugar": 120, "butter": 227, "water": 237, "milk": 245, "honey": 340,
               "rice": 185, "oats": 90, "cocoa": 85, "salt": 288, "oil": 218, "yogurt": 245, "cream": 238, "syrup": 322, "breadcrumbs": 108,
               "cheese": 113, "nuts": 140, "raisins": 150, "cornflour": 128, "baking powder": 192, "peanut butter": 258}
GAS_MARKS = {1: (140, 275), 2: (150, 300), 3: (170, 325), 4: (180, 350), 5: (190, 375), 6: (200, 400), 7: (220, 425), 8: (230, 450), 9: (240, 475)}
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
    if a == "fuel":
        return from_l100(to_l100(value, src), dst)
    if a == "currency":
        table, _source = rates()
        return value / table[src] * table[dst]
    return value * UNITS[a][src] / UNITS[a][dst]


def to_l100(value, unit):
    """Fuel economy to litres per 100 km (the figure that adds up: miles per gallon is its inverse)."""
    if value <= 0:
        raise ValueError("fuel economy must be more than zero")
    return {"l/100km": value, "km/l": 100 / value, "mpg": 235.2146 / value, "mpguk": 282.4809 / value}[unit]


def from_l100(l100, unit):
    return {"l/100km": l100, "km/l": 100 / l100, "mpg": 235.2146 / l100, "mpguk": 282.4809 / l100}[unit]


# ------------------------------------------------------------- currency
def rates():
    """(units per 1 USD, description of where they came from). Uses fresh saved rates, fetches new ones when they are over a day
    old and the internet is reachable, and otherwise the saved or built-in approximate ones."""
    saved = appdata.load("converter_rates", {}) if appdata else {}
    age = time.time() - saved.get("fetched", 0)
    if (not saved or age > RATES_MAX_AGE) and requests is not None:
        fetched = fetch_rates()
        if fetched:
            saved = fetched
            age = 0
    if saved.get("rates"):
        table = {k.lower(): v for k, v in saved["rates"].items()}
        table["usd"] = 1.0
        return table, f"rates from {saved.get('date', '?')}" + (f" (saved {int(age // 3600)} h ago)" if age > 3600 else "")
    return dict(FALLBACK_RATES), "approximate built-in rates (connect to the internet for today's)"


def fetch_rates():
    try:
        data = requests.get(RATES_URL, timeout=4).json()
        saved = {"fetched": time.time(), "date": data.get("date", ""), "rates": data["rates"]}
        if appdata:
            appdata.save("converter_rates", saved)
        return saved
    except Exception:  # offline or the service is down: fall back quietly
        return None


# --------------------------------------------------------- number bases
BASE_NAMES = {"bin": 2, "binary": 2, "oct": 8, "octal": 8, "dec": 10, "decimal": 10, "hex": 16, "hexadecimal": 16}


def base_of(word):
    word = word.lower()
    if word in BASE_NAMES:
        return BASE_NAMES[word]
    if word.startswith("base") and word[4:].isdigit() and 2 <= int(word[4:]) <= 36:
        return int(word[4:])
    return None


def to_base(number, base):
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    if number == 0:
        return "0"
    sign, number, out = ("-" if number < 0 else ""), abs(number), ""
    while number:
        number, rem = divmod(number, base)
        out = digits[rem] + out
    return sign + out


def parse_base(text):
    """'ff hex to dec', '1010 bin dec', '255 dec hex' -> (number as int, from base, to base) or None if it is not a base conversion."""
    m = re.fullmatch(r"\s*(-?[0-9a-zA-Z]+)\s+(\w+)\s+(?:to|in|into|as)?\s*(\w+)\s*", text)
    if not m or base_of(m.group(2)) is None or base_of(m.group(3)) is None:
        return None
    src, dst = base_of(m.group(2)), base_of(m.group(3))
    try:
        return int(m.group(1), src), src, dst
    except ValueError:
        raise ValueError(f"'{m.group(1)}' is not a base-{src} number") from None


# -------------------------------------------------------------- cooking
def parse_cooking(text):
    """'2 cups flour to g', '1 tbsp butter in g', '100 g sugar to cup' -> (value, unit, ingredient, target unit) or None."""
    m = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s+([a-zA-Z ]+?)\s+(?:to|in|into)\s+([a-zA-Z]+)\s*", text)
    if not m or m.group(3).lower() not in INGREDIENTS:
        return None
    return float(m.group(1)), m.group(2), m.group(3).lower(), m.group(4)


def cooking_convert(value, unit, ingredient, target):
    """Volume <-> weight for an ingredient, using its grams per cup."""
    unit, target = unit_key(unit), unit_key(target)
    grams_per_litre = INGREDIENTS[ingredient] / UNITS["volume"]["cup"]
    if category_of(unit) == "volume" and category_of(target) == "mass":
        litres = value * UNITS["volume"][unit]
        return litres * grams_per_litre / 1000 / UNITS["mass"][target]
    if category_of(unit) == "mass" and category_of(target) == "volume":
        litres = value * UNITS["mass"][unit] * 1000 / grams_per_litre
        return litres / UNITS["volume"][target]
    if category_of(unit) == category_of(target) == "volume":
        return convert(value, unit, target)
    raise ValueError("Convert between a volume (cup, tbsp, tsp, ml) and a weight (g, kg, oz, lb).")


def parse_gas(text):
    m = re.fullmatch(r"\s*gas\s*(?:mark)?\s*(\d)\s*(?:to|in)?\s*(c|f)?\s*", text, re.I)
    if m and int(m.group(1)) in GAS_MARKS:
        c, f = GAS_MARKS[int(m.group(1))]
        return f"gas mark {m.group(1)} = {c} C = {f} F"
    return None


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


def evaluate(text):
    """Work out one conversion typed as text. Returns (line to show, history text, result text to copy) or raises ValueError."""
    gas = parse_gas(text)
    if gas:
        return gas, text.strip(), gas
    based = parse_base(text)
    if based:
        number, src, dst = based
        result = to_base(number, dst)
        return f"{text.split()[0]} (base {src}) = [bold green]{result}[/bold green] (base {dst})", text.strip(), result
    cooking = parse_cooking(text)
    if cooking:
        value, unit, ingredient, target = cooking
        result = cooking_convert(value, unit, ingredient, target)
        shown = f"{pretty(result)} {unit_key(target)}"
        return f"{pretty(value)} {unit_key(unit)} {ingredient} = [bold green]{shown}[/bold green]  [dim]({INGREDIENTS[ingredient]} g per cup)[/dim]", text.strip(), shown
    value, src, dst = parse_conversion(text)
    result = convert(value, src, dst)
    shown = f"{pretty(result)} {unit_key(dst)}"
    note = ""
    if category_of(unit_key(src)) == "currency":
        note = f"  [dim]({rates()[1]})[/dim]"
    return f"{pretty(value)} {unit_key(src)} = [bold green]{shown}[/bold green]{note}", f"{pretty(value)} {unit_key(src)} to {unit_key(dst)}", shown


def favourites():
    return (appdata.load("converter_favs", []) if appdata else []) or []


def copy_result(text):
    """Put a result on the clipboard (~/.clipboard) so it can be pasted with 'snippets paste' or read with cat."""
    if not fs:
        console.print("[yellow]The clipboard needs PythonOS.[/yellow]")
        return
    name = fs.current_user()[0]
    base = fs.home_dir(name) if name else fs.BASE_DIR
    os.makedirs(base, exist_ok=True)
    with open(os.path.join(base, ".clipboard"), "w", encoding="utf-8") as f:
        f.write(re.sub(r"\[.*?\]", "", text))
    if appdata:
        history = [h for h in (appdata.load("clip_history", []) or []) if h.get("text") != text]
        history.insert(0, {"t": int(time.time()), "text": text})
        appdata.save("clip_history", history[:50])
    console.print("[green]Copied to the clipboard.[/green]")


def converter():
    cats = ", ".join(c for c in UNITS)
    console.print(f"[bold]Converter[/bold]  [dim]for example: 5 km to mi, 100 f to c, 2 gb to mb, 40 mpg to l/100km, 100 usd to eur, 2 cups flour to g, "
                  f"ff hex to dec, gas 4. Categories: {cats}. 'list <category>' shows units; 'fav' saves the last one; 'favs' runs your favourites; "
                  f"'copy' copies the last result; blank to leave[/dim]")
    last = None
    while True:
        text = Prompt.ask("[cyan]convert[/cyan]", default="").strip()
        if not text:
            return
        low = text.lower()
        if low.startswith("list"):
            cat = text[4:].strip().lower()
            console.print(f"{cat}: " + ", ".join(UNITS[cat]) if cat in UNITS else "Categories: " + cats)
            continue
        if low == "copy":
            copy_result(last[2]) if last else console.print("[yellow]Convert something first.[/yellow]")
            continue
        if low == "fav":
            if last and appdata:
                favs = favourites()
                if last[1] not in favs:
                    favs.append(last[1])
                    appdata.save("converter_favs", favs[:30])
                console.print("[green]Saved to your favourites.[/green]")
            else:
                console.print("[yellow]Convert something first.[/yellow]")
            continue
        if low == "favs":
            for fav in favourites() or ["(none yet - type 'fav' after a conversion)"]:
                try:
                    console.print("  " + evaluate(fav)[0])
                except ValueError:
                    console.print(f"  {fav}")
            continue
        try:
            last = evaluate(text)
        except (ValueError, KeyError) as e:
            console.print(f"[red]{escape(str(e)) if str(e) else 'I did not understand that.'}[/red]")
            continue
        console.print("  " + last[0])
        remember(last[1], last[2])


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
        elif args and args[0] == "favs":
            for fav in favourites():
                console.print("  " + evaluate(fav)[0])
        elif args and args[0] == "rates":
            table, source = rates()
            console.print(f"[bold]{source}[/bold] (units per 1 USD)")
            console.print(", ".join(f"{k.upper()} {v:g}" for k, v in sorted(table.items())))
        elif args:
            console.print(evaluate(" ".join(args))[0])
        else:
            while True:
                choice = Prompt.ask("[bold](c)[/bold]alculator  [bold](u)[/bold]nit converter  [bold](h)[/bold]istory  [bold](q)[/bold]uit",
                                    choices=["c", "u", "h", "q"], default="q")
                if choice == "q":
                    return
                {"c": calculator, "u": converter, "h": show_history}[choice]()
    except (ValueError, KeyError, SyntaxError, ZeroDivisionError, OverflowError) as e:
        console.print(f"[red]{escape(str(e))}[/red]")
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
