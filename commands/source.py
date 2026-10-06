from rich.console import Console

import pyos.fs as fs

console = Console()
config = {"name": "source", "description": "Run the commands of a file, one per line (source <file>); ~/.pyosrc runs like this at every login.", "alias": ["."]}


def execute(args=None):
    import shell
    if not args:
        console.print("[bold red]Usage:[/bold red] source <file>")
        return False
    try:
        with open(fs.resolve(args[0]), encoding="utf-8") as f:
            lines = f.read().splitlines()
    except Exception as e:                                             # noqa: BLE001
        console.print(f"[bold red]source: {args[0]}: {fs.errtext(e)}[/bold red]")
        return False
    status = 0
    for line in lines:
        if line.strip() and not line.strip().startswith("#"):
            status = shell.run_line(line)
    return status in (0, None)
