from rich.console import Console
from rich.markup import escape
from rich.prompt import IntPrompt, Prompt
from rich.table import Table
from pyos import settings, theme

console = Console()
config = {
    "name": "settings",
    "description": "Themes and options: settings [list|get|set|reset|theme|themes]. Run it alone for a menu.",
    "alias": ["prefs"],
}

HELP = """[bold]settings[/bold] - change how PythonOS looks and behaves

  settings                        open the menu
  settings list                   show every setting
  settings get <name>             show one setting
  settings set <name> <value>     change one      (for example: settings set theme ocean)
  settings reset [name]           back to the default (everything if no name)
  settings themes                 preview the colour themes
  settings theme <name>           switch theme"""


def _show(value):
    return "on" if value is True else "off" if value is False else str(value)


def list_settings():
    current = settings.load()
    table = Table(header_style="bold blue", expand=True)
    table.add_column("#", justify="right")
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value", style="bold")
    table.add_column("Options")
    table.add_column("What it does")
    for i, (key, (default, allowed, description)) in enumerate(settings.SCHEMA.items(), 1):
        options = "on / off" if allowed is bool else "minutes" if allowed is int else " / ".join(allowed)
        mark = "" if current[key] == default else " [dim](changed)[/dim]"
        table.add_row(str(i), key, _show(current[key]) + mark, escape(options), escape(description))
    console.print(table)


def preview_themes():
    current = theme.name()
    for name, roles in theme.THEMES.items():
        marker = "  [bold]<- in use[/bold]" if name == current else ""
        console.print(f"[{roles['title']}]{name}[/{roles['title']}]{marker}")
        console.print(f"  [{roles['prompt_user']}]user@pyOS[/{roles['prompt_user']}]:[{roles['prompt_path']}]~[/{roles['prompt_path']}]$  "
                      f"[{roles['success']}]success[/{roles['success']}]  [{roles['warning']}]warning[/{roles['warning']}]  "
                      f"[{roles['error']}]error[/{roles['error']}]  [{roles['accent']}]accent[/{roles['accent']}]  "
                      f"[{roles['border']}]border[/{roles['border']}]")


def change(key, text):
    """Set one setting from what the user typed. Returns True on success."""
    try:
        value = settings.parse_value(key, text)
        settings.set(key, value)
    except ValueError as e:
        console.print(f"[bold red]settings: {escape(str(e))}[/bold red]")
        return False
    console.print(f"[green]{key} = {_show(value)}[/green]")
    if key == "theme":
        preview_themes()
    return True


def menu():
    keys = list(settings.SCHEMA)
    while True:
        list_settings()
        choice = IntPrompt.ask("Number of the setting to change (0 to finish)", default=0)
        if not 1 <= choice <= len(keys):
            return True
        key = keys[choice - 1]
        allowed = settings.SCHEMA[key][1]
        if key == "theme":
            preview_themes()
        if allowed is bool:
            text = Prompt.ask(f"{key}", choices=["on", "off"], default=_show(settings.get(key)))
        elif allowed is int:
            text = Prompt.ask(f"{key} (minutes, 0 = never)", default=str(settings.get(key)))
        else:
            text = Prompt.ask(f"{key}", choices=list(allowed), default=settings.get(key))
        change(key, text)


def execute(args=None):
    args = list(args or [])
    if not args:
        return menu()
    sub, rest = args[0].lower(), args[1:]
    if sub in ("help", "-h", "--help"):
        console.print(HELP)
        return True
    if sub in ("list", "ls", "show"):
        list_settings()
        return True
    if sub == "get":
        if not rest or rest[0] not in settings.SCHEMA:
            console.print(f"[bold red]Usage:[/bold red] settings get <{'|'.join(settings.SCHEMA)}>")
            return False
        console.print(_show(settings.get(rest[0])), markup=False)
        return True
    if sub == "set":
        if len(rest) != 2:
            console.print("[bold red]Usage:[/bold red] settings set <name> <value>")
            return False
        return change(rest[0], rest[1])
    if sub == "reset":
        if rest and rest[0] not in settings.SCHEMA:
            console.print(f"[bold red]settings: unknown setting '{escape(rest[0])}'[/bold red]")
            return False
        settings.reset(rest[0] if rest else None)
        console.print("[green]Back to the default.[/green]")
        return True
    if sub == "themes":
        preview_themes()
        return True
    if sub == "theme":
        if not rest:
            console.print(f"Theme: [bold]{theme.name()}[/bold]  (available: {', '.join(theme.THEMES)})")
            return True
        return change("theme", rest[0])
    console.print(f"[bold red]settings: unknown subcommand '{escape(sub)}'[/bold red]")
    console.print(HELP)
    return False
