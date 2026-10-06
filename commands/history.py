from rich.console import Console

from pyos import prompt

console = Console()
config = {"name": "history", "description": "Show what you typed (history [n | word | -c]); !! repeats the last command, !n number n, !word the last one starting with word."}


def execute(args=None):
    args = list(args or [])
    items = prompt.history_lines()
    if args == ["-c"]:
        try:
            open(prompt.HISTORY_FILE, "w", encoding="utf-8").close()
            import readline
            readline.clear_history()
        except Exception:                                  # noqa: BLE001 - the file is the part that matters
            pass
        console.print("[green]History cleared.[/green]")
        return True
    if not items:
        console.print("[dim]Nothing in the history yet.[/dim]")
        return True
    if len(args) == 1 and args[0].isdigit():
        shown = list(enumerate(items, 1))[-int(args[0]):]
    elif args:
        shown = prompt.search_history(items, " ".join(args))
        if not shown:
            console.print(f"[yellow]Nothing in the history contains '{' '.join(args)}'.[/yellow]", highlight=False)
            return True
    else:
        shown = list(enumerate(items, 1))
    for number, line in shown:
        console.print(f"{number:>5}  {line}", markup=False, highlight=False)
    return True
