import re
from rich.console import Console
import pyos.fs as fs
import pyos.stdio as stdio

console = Console()
config = {"name": "grep", "description": "Search files or piped input for a pattern (grep [-i] <pattern> [file...]). Fails if nothing matched."}


def execute(args=None):
    args = list(args or [])
    ignore = "-i" in args
    args = [a for a in args if a != "-i"]
    piped = stdio.read_stdin()
    if len(args) < 1 or (len(args) < 2 and piped is None):
        console.print("[bold red]Usage:[/bold red] grep \\[-i] <pattern> <file>...")
        return False
    try:
        regex = re.compile(args[0], re.IGNORECASE if ignore else 0)
    except re.error as e:
        console.print(f"[bold red]grep: invalid pattern: {e}[/bold red]")
        return False

    matched, errors = False, False
    if len(args) == 1:
        for line in piped.splitlines():
            if regex.search(line):
                console.print(line, markup=False, highlight=False)
                matched = True
        return matched
    multi = len(args) > 2
    for name in args[1:]:
        try:
            with open(fs.resolve(name), "r", encoding="utf-8", errors="replace") as f:
                for n, line in enumerate(f, 1):
                    if regex.search(line):
                        prefix = f"{name}:" if multi else ""
                        console.print(f"{prefix}{n}: {line.rstrip()}", markup=False, highlight=False)
                        matched = True
        except Exception as e:
            console.print(f"[bold red]grep: {name}: {e}[/bold red]")
            errors = True
    return matched and not errors
