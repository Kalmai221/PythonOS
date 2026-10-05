from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

import pyos
from pyos import appdata, stdio

console = Console()
config = {"name": "quickstart", "description": "A two-minute tour of what PythonOS can do (skip any time with q).", "alias": ["try"]}

# (title, text, a command to show live or None, a hint for what to try next)
STEPS = [
    ("Welcome", "PythonOS is a small operating system you drive with typed commands. It has files, accounts, apps, games and a "
                "network, and it runs on a PC, a USB stick, a phone and more. This tour takes about two minutes.", None, None),
    ("Finding your way", "help lists every command in groups. help files shows just one group, help search <word> looks for a command, "
                         "and man <command> is the full manual with examples.", "help", "Try: help files"),
    ("Apps and games", "The marketplace has games, tools and utilities. pkg search finds one, pkg install adds it, run <name> starts it.",
     "pkg search chess", "Try: pkg install tictactoe   then   run tictactoe"),
    ("Make it yours", "settings changes colours, the prompt, the language and more. Themes: default, ocean, forest, sunset, mono, contrast.",
     "settings themes", "Try: settings theme ocean"),
    ("Keep your data", "On the live USB everything is forgotten at power off unless you set up storage. persist create makes a place on a "
                       "disk or USB stick (it can be encrypted) for your accounts, files and settings.", "persist status", "Try: persist create"),
    ("Safe and undoable", "rm sends things to the trash and undo brings the last one back. doctor checks the system for problems, and "
                          "report prepares a problem report you can read before anything is sent.", None, "Try: rm file   then   undo"),
    ("Switching off", "Use the shutdown command (or restart) instead of unplugging: it closes everything properly. If the power does get "
                      "cut, PythonOS notices at the next start (whathappened).", None, "Type: shutdown when you are done"),
]


def execute(args=None):
    import shell
    total = len(STEPS)
    try:
        for number, (title, text, command, hint) in enumerate(STEPS, 1):
            stdio.clear_screen(scrollback=False)
            console.print(f"[bold cyan]PythonOS quick start[/bold cyan]  [dim]{number}/{total}[/dim]\n")
            console.print(Panel(escape(text), title=f"[bold]{escape(title)}[/bold]", border_style="blue", expand=False))
            if command:
                console.print(f"\n[dim]$ {escape(command)}[/dim]")
                shell.run_line(command)
            if hint:
                console.print(f"\n[bold]{escape(hint)}[/bold]")
            if Prompt.ask("\n[dim]Enter for the next step, q to stop[/dim]", default="").strip().lower() in ("q", "quit", "stop"):
                break
        else:
            console.print("\n[bold green]That's the tour.[/bold green] For a hands-on lesson, type [bold]tutorial[/bold].")
    except (KeyboardInterrupt, EOFError):
        console.print()
    appdata.save("quickstart", {"done": True})
    return True


def offer():
    """After first-time setup on the live ISO: ask once whether to take the tour."""
    try:
        if (appdata.load("quickstart", {}) or {}).get("done"):
            return
        if Confirm.ask("Take a two-minute quick start now?", default=True):
            execute([])
        else:
            appdata.save("quickstart", {"done": True})
            console.print("[dim]Any time later: quickstart (or tutorial for a hands-on lesson).[/dim]")
    except (KeyboardInterrupt, EOFError):
        pass
