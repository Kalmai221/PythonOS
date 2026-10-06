#!/usr/bin/env python3
"""Units: convert between thousands of units and do sums with them, with the pint library.

    units 5 miles to km
    units 100 km/h to mph
    units 20 degC to degF
    units 3 cups to ml
    units 2 hours + 30 minutes to minutes
    units                          the prompt: type conversions one after another
    units list [word]              find a unit by name
"""
import sys

from rich.console import Console
from rich.markup import escape

console = Console()
SEPARATORS = (" to ", " in ", " into ", " -> ")
_registry = []


def registry():
    """The pint unit registry (made once; it takes a moment to load)."""
    if not _registry:
        import pint
        _registry.append(pint.UnitRegistry(autoconvert_offset_to_baseunit=True))
    return _registry[0]


def split(text):
    """('5 miles', 'km') from '5 miles to km', or (text, None) when there is no target."""
    lowered = text.lower()
    for sep in SEPARATORS:
        if sep in lowered:
            i = lowered.index(sep)
            return text[:i].strip(), text[i + len(sep):].strip()
    return text.strip(), None


def number(value):
    """A readable number: up to 6 significant digits, no trailing zeros."""
    text = f"{value:.6g}"
    return text.replace("e+", "e").replace("e-0", "e-") if "e" in text else text


def convert(text):
    """(result text, None) or (None, message) for 'N unit to unit'. Without 'to' it simplifies the expression."""
    ureg = registry()
    source, target = split(text)
    if not source:
        return None, "type something like: 5 miles to km"
    try:
        quantity = ureg.Quantity(ureg.parse_expression(source)) if not hasattr(ureg.parse_expression(source), "to") else ureg.parse_expression(source)
        if target:
            quantity = quantity.to(target)
        elif hasattr(quantity, "to_reduced_units"):
            quantity = quantity.to_reduced_units()
    except Exception as e:                                 # noqa: BLE001 - pint raises many kinds of errors; all mean "I could not do that"
        return None, explain(e, source, target)
    magnitude = quantity.magnitude
    unit = f"{quantity.units:~}" or str(quantity.units)
    shown = number(magnitude) if isinstance(magnitude, (int, float)) else str(magnitude)
    return f"{shown} {unit}".strip(), None


def explain(error, source, target):
    name = type(error).__name__
    if name == "DimensionalityError":
        return f"Those do not match: {source} and {target} measure different things."
    if name in ("UndefinedUnitError", "AttributeError"):
        word = str(error).replace("'", "").replace("is not defined in the unit registry", "").strip()
        return f"I do not know the unit {word or 'you wrote'}. Try: units list {word.split()[-1] if word else 'metre'}"
    return f"I could not work that out ({str(error)[:80]})."


def find(word, limit=25):
    """Unit names containing `word`."""
    ureg = registry()
    word = word.lower()
    names = sorted({n for n in dir(ureg) if word in n.lower() and not n.startswith("_") and n.isalpha()})
    return names[:limit], max(0, len(names) - limit)


def run(text):
    result, problem = convert(text)
    if problem:
        console.print(f"[yellow]{escape(problem)}[/yellow]")
        return False
    console.print(f"[bold]{escape(result)}[/bold]")
    return True


def execute(args=None):
    args = list(args or [])
    try:
        import pint  # noqa: F401
    except ImportError:
        console.print("[bold red]units needs the pint library, which is not installed. Install the app again: pkg install units[/bold red]")
        return False
    try:
        if args[:1] == ["list"]:
            names, more = find(" ".join(args[1:]) or "metre")
            console.print(", ".join(names) + (f"  ... and {more} more" if more else ""), markup=False)
            return True
        if args:
            return run(" ".join(args))
        console.print("[dim]Type a conversion like 5 miles to km. Empty line to leave.[/dim]")
        while True:
            line = input("units> ").strip()
            if not line or line in ("q", "quit", "exit"):
                return True
            run(line)
    except (KeyboardInterrupt, EOFError):
        console.print()
    return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
