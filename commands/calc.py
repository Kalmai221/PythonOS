from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt

import pyos.stdio as stdio
from pyos import calc as calculator
from pyos import textcmd

console = Console()
config = {"name": "calc", "description": "Calculate (calc 2 + 3 * 4, calc \"sqrt(2) * pi\"); with nothing to calculate it opens a calculator.", "alias": ["bc"]}


def calculate(text):
    """Print the answer to each line of `text`. True when every line worked."""
    ok = True
    for line in [l for l in text.splitlines() if l.strip()] or [text]:
        try:
            textcmd.emit(calculator.show(calculator.evaluate(line)))
        except calculator.CalcError as e:
            console.print(f"[bold red]calc: {escape(str(e))}[/bold red]")
            ok = False
    return ok


def interactive():
    """The calculator: one calculation per line, exit (or an empty line twice, or Ctrl+D) to leave."""
    console.print("[bold cyan]Calculator[/bold cyan] [dim](numbers, + - * / // % ** ^, brackets, sqrt() sin() log() fact() ...; 'exit' to leave)[/dim]")
    while True:
        try:
            line = Prompt.ask("[bold yellow]calc>[/bold yellow]", default="")
        except (EOFError, KeyboardInterrupt):
            console.print()
            return True
        if line.strip().lower() in ("exit", "quit", "q"):
            return True
        if line.strip():
            try:
                console.print(f"[bold green]{escape(calculator.show(calculator.evaluate(line)))}[/bold green]")
            except calculator.CalcError as e:
                console.print(f"[bold red]{escape(str(e))}[/bold red]")


def execute(args=None):
    text = " ".join(args or [])
    if text.strip():
        return calculate(text)
    piped = stdio.read_stdin()
    if piped is not None:
        return calculate(piped)
    return interactive()
