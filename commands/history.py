from rich.console import Console

try:
    import readline
except ImportError:
    try:
        import pyreadline3 as readline
    except ImportError:
        from pyos import readline_stub as readline

console = Console()
config = {"name": "history", "description": "Show previously entered commands."}


def execute(args=None):
    try:
        total = readline.get_current_history_length()
        for i in range(1, total + 1):
            console.print(f"{i:>5}  {readline.get_history_item(i)}", markup=False, highlight=False)
    except Exception:
        console.print("[bold yellow]History is not available on this system.[/bold yellow]")
