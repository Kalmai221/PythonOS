#!/usr/bin/env python3
"""Theme designer: make your own colour theme for PythonOS. Start from an existing theme, change the colours of each part (accent,
titles, success/warning/error messages, borders, the prompt), see a live sample, give it a name and save it. Then switch to it with
  settings set theme custom:<name>
Themes are saved in your own ~/.config/themes.json, so each person can have their own. Usage: themedesigner  |  themedesigner list |
themedesigner delete <name>"""
import re
import sys

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from pyos import appdata, theme

console = Console()
ROLES = [("accent", "Accent colour (highlights)"), ("title", "Titles and headings"), ("success", "Success messages"),
         ("warning", "Warnings"), ("error", "Errors"), ("border", "Boxes and tables"), ("dim", "Quiet text"),
         ("prompt_user", "Prompt: your name"), ("prompt_path", "Prompt: the folder")]
COLOURS = ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white", "bright_black", "bright_red", "bright_green",
           "bright_yellow", "bright_blue", "bright_magenta", "bright_cyan", "bright_white", "orange1", "dark_orange", "pink1", "purple", "gold1",
           "chartreuse1", "turquoise2", "deep_sky_blue1", "grey50"]
STYLES = ["", "bold", "dim", "italic", "underline"]
NAME_RE = re.compile(r"[a-z0-9_-]{1,20}")


def load():
    return appdata.load("themes", {}) or {}


def sample(roles):
    """A little screen drawn in the theme's colours."""
    r = roles
    lines = [f"[{r['title']}]My PythonOS[/{r['title']}]  [{r['dim']}]a quiet detail[/{r['dim']}]",
             f"[{r['prompt_user']}]you@pyOS[/{r['prompt_user']}]:[{r['prompt_path']}]~/docs[/{r['prompt_path']}]$ backup create",
             f"[{r['success']}]Backup finished[/{r['success']}]   [{r['warning']}]Disk almost full[/{r['warning']}]   [{r['error']}]Something failed[/{r['error']}]",
             f"[{r['accent']}]An accent colour for highlights[/{r['accent']}]"]
    console.print(Panel("\n".join(lines), border_style=r["border"], expand=False, title=f"[{r['title']}]Preview[/{r['title']}]"))


def valid_style(text):
    """Is this a rich style made only of colours/attributes we know? (stops markup tricks)"""
    words = text.split()
    allowed = set(COLOURS) | {"bold", "dim", "italic", "underline"}
    return bool(words) and all(w in allowed for w in words)


def edit(roles):
    while True:
        sample(roles)
        table = Table(header_style="bold blue")
        for col in ("#", "Part", "Now"):
            table.add_column(col)
        for i, (key, label) in enumerate(ROLES, 1):
            table.add_row(str(i), label, f"[{roles[key]}]{roles[key]}[/{roles[key]}]")
        console.print(table)
        n = IntPrompt.ask("Change which part? (0 when done)", default=0)
        if n == 0:
            return roles
        if not 1 <= n <= len(ROLES):
            continue
        key = ROLES[n - 1][0]
        console.print("Colours: " + ", ".join(f"[{c}]{c}[/{c}]" for c in COLOURS))
        text = Prompt.ask(f"New style for '{ROLES[n - 1][1]}' (a colour, optionally with bold/dim/italic/underline, like  bold bright_green)",
                          default=roles[key]).strip()
        if valid_style(text):
            roles[key] = text
        else:
            console.print("[red]I only know the colours listed above, plus bold, dim, italic and underline.[/red]")


def main(args):
    saved = load()
    if args and args[0] == "list":
        for name in saved:
            console.print(f"custom:{escape(name)}")
        if not saved:
            console.print("[dim]No custom themes yet.[/dim]")
        return
    if args and args[0] == "delete" and len(args) > 1:
        if saved.pop(args[1], None) is not None:
            appdata.save("themes", saved)
            console.print("[green]Deleted.[/green]")
        else:
            console.print("[red]No such theme.[/red]")
        return
    names = list(theme.THEMES) + [f"custom:{n}" for n in saved]
    base = Prompt.ask("Start from", choices=names, default="default")
    roles = dict(theme.THEMES["default"])
    roles.update(theme.THEMES.get(base) or saved.get(base[len("custom:"):], {}))
    roles = edit(roles)
    name = Prompt.ask("Name your theme (letters, digits, - and _)", default="mine").strip().lower()
    if not NAME_RE.fullmatch(name):
        console.print("[red]Use 1-20 letters, digits, - or _.[/red]")
        return
    if name in saved and not Confirm.ask(f"Replace your theme '{name}'?", default=True):
        return
    saved[name] = {k: v for k, v in roles.items() if k in dict(ROLES)}
    appdata.save("themes", saved)
    console.print(f"[green]Saved.[/green] Use it with:  [bold]settings set theme custom:{name}[/bold]")


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
