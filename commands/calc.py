from rich.console import Console

import pyos.stdio as stdio
from pyos import calc as calculator
from pyos import textcmd

console = Console()
config = {"name": "calc", "description": "Calculate (calc 2 + 3 * 4, calc \"sqrt(2) * pi\"); numbers, + - * / // % ** ^, brackets and functions.", "alias": ["bc"]}


def execute(args=None):
    text = " ".join(args or [])
    if not text.strip():
        piped = stdio.read_stdin()
        if piped is None:
            console.print("[bold red]Usage:[/bold red] calc <expression>   for example  calc 2 + 3 * 4   or   calc \"sqrt(144) + 10 % 3\"")
            return False
        text = piped
    ok = True
    for line in [l for l in text.splitlines() if l.strip()] or [text]:
        try:
            textcmd.emit(calculator.show(calculator.evaluate(line)))
        except calculator.CalcError as e:
            console.print(f"[bold red]calc: {e}[/bold red]")
            ok = False
    return ok
