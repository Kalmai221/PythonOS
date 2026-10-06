#!/usr/bin/env python3
"""Algebra: a small computer algebra system (sympy).

    algebra solve x**2 - 4              the solutions of an equation (= 0), or write: solve x**2 = 9
    algebra solve x+y=10, x-y=2         several equations (comma separated)
    algebra simplify (x**2-1)/(x-1)
    algebra expand (x+1)**3
    algebra factor x**2 - 5*x + 6
    algebra diff sin(x)*x               the derivative (add a variable: diff x*y y)
    algebra integrate x**2              the integral; for a definite one: integrate x**2 0 3
    algebra eval 2**100 / 3             just calculate
Write ^ or ** for powers. Type algebra with nothing for a prompt.
"""
import re
import sys

from rich.console import Console
from rich.markup import escape

console = Console()
ALLOWED = re.compile(r"^[A-Za-z0-9_+\-*/^().,= ]+$")


def check(text):
    """The expression text, or raises ValueError. Only maths characters are allowed (no quotes, brackets, underscores in a row...)."""
    text = text.strip()
    if not text or not ALLOWED.match(text) or "__" in text:
        raise ValueError("write a maths expression like x**2 - 4 (letters, digits and + - * / ^ ( ) = only)")
    return text.replace("^", "**")


def parse(text):
    import sympy
    from sympy.parsing.sympy_parser import implicit_multiplication_application, parse_expr, standard_transformations, convert_xor
    transformations = standard_transformations + (implicit_multiplication_application, convert_xor)
    return parse_expr(check(text), transformations=transformations, evaluate=True, local_dict={"pi": sympy.pi, "e": sympy.E})


def equation(text):
    """A sympy equation (left - right = 0) from 'x**2 = 9' or just 'x**2 - 9'."""
    import sympy
    parts = check(text).split("=")
    if len(parts) == 1:
        return parse(parts[0])
    if len(parts) != 2:
        raise ValueError("an equation has one = sign")
    return sympy.Eq(parse(parts[0]), parse(parts[1]))


def show(value):
    import sympy
    return sympy.pretty(value, use_unicode=False)


def run(command, rest):
    """The result text for a command and its argument text, or raises ValueError."""
    import sympy
    command = command.lower()
    if command == "solve":
        equations = [equation(p) for p in rest.split(",") if p.strip()]
        if not equations:
            raise ValueError("solve what? For example: algebra solve x**2 - 4")
        symbols = sorted(set().union(*[getattr(q, "free_symbols", set()) for q in equations]), key=str)
        answer = sympy.solve(equations if len(equations) > 1 else equations[0], symbols if len(equations) > 1 else (symbols[0] if symbols else None), dict=True)
        if not answer:
            return "No solution."
        return "\n".join(", ".join(f"{k} = {v}" for k, v in sorted(a.items(), key=lambda kv: str(kv[0]))) for a in answer)
    if command in ("simplify", "expand", "factor"):
        return show(getattr(sympy, command)(parse(rest)))
    if command in ("diff", "integrate"):
        words = rest.split()
        bounds = None
        if command == "integrate" and len(words) >= 3 and all(re.fullmatch(r"-?[\d.]+", w) for w in words[-2:]):
            bounds, words = words[-2:], words[:-2]
        variable = None
        if len(words) >= 2 and re.fullmatch(r"[A-Za-z]", words[-1]):
            variable, words = sympy.Symbol(words[-1]), words[:-1]
        expression = parse(" ".join(words))
        variable = variable or (sorted(expression.free_symbols, key=str)[0] if expression.free_symbols else sympy.Symbol("x"))
        if command == "diff":
            return show(sympy.diff(expression, variable))
        if bounds:
            return show(sympy.integrate(expression, (variable, sympy.sympify(bounds[0]), sympy.sympify(bounds[1]))))
        return show(sympy.integrate(expression, variable)) + "  + C"
    if command in ("eval", "calc"):
        value = parse(rest)
        return str(value) if value.is_Integer else f"{value}  ~ {sympy.N(value, 12)}"
    raise ValueError(f"I do not know '{command}'. Try solve, simplify, expand, factor, diff, integrate or eval.")


def execute(args=None):
    args = list(args or [])
    try:
        import sympy  # noqa: F401
    except ImportError:
        console.print("[bold red]algebra needs the sympy library. Install the app again: pkg install algebra[/bold red]")
        return False
    try:
        if args:
            console.print(escape(run(args[0], " ".join(args[1:]))), highlight=False)
            return True
        console.print("[dim]Type: solve x**2-4 | simplify ... | expand ... | factor ... | diff ... | integrate ... | eval ...   (empty line to leave)[/dim]")
        while True:
            line = input("algebra> ").strip()
            if not line or line in ("q", "quit", "exit"):
                return True
            command, _, rest = line.partition(" ")
            try:
                console.print(escape(run(command, rest)), highlight=False)
            except Exception as e:                         # noqa: BLE001 - a bad expression must not end the prompt
                console.print(f"[yellow]{escape(str(e)[:150])}[/yellow]")
    except (KeyboardInterrupt, EOFError):
        console.print()
    except Exception as e:                                 # noqa: BLE001
        console.print(f"[yellow]{escape(str(e)[:150])}[/yellow]")
        return False
    return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
