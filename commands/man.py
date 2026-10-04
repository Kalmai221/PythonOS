import difflib
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from pyos import manpages, theme

console = Console()
config = {
    "name": "man",
    "description": "Read the manual: man <command or topic>, man -k <word> to search, man alone lists everything.",
    "alias": ["manual"],
}

TOPICS = ["shell", "files", "users", "packages", "updates", "lockdown"]


def _heading(text):
    console.print(f"\n[bold {theme.style('accent') or 'cyan'}]{text}[/bold {theme.style('accent') or 'cyan'}]")


def show(page):
    accent = theme.style("accent") or "cyan"
    console.print(f"[bold {accent}]{escape(page['name'].upper())}[/bold {accent}]  {escape(page['summary'])}")
    _heading("USAGE")
    for line in page["synopsis"]:
        console.print(f"  {escape(line)}")
    _heading("ABOUT")
    for line in page["description"].split("\n"):
        console.print(f"  {escape(line)}")
    if page["options"]:
        _heading("OPTIONS")
        for flag, text in page["options"]:
            console.print(f"  [bold]{escape(flag)}[/bold]  {escape(text)}")
    if page["examples"]:
        _heading("EXAMPLES")
        for command, text in page["examples"]:
            console.print(f"  [bold green]$ {escape(command)}[/bold green]")
            console.print(f"      [dim]{escape(text)}[/dim]")
    if page["see"]:
        _heading("SEE ALSO")
        console.print("  " + ", ".join(escape(s) for s in page["see"]))
    console.print()


def listing():
    table = Table(header_style="bold blue", expand=True)
    table.add_column("Page", style="bold green", no_wrap=True)
    table.add_column("About")
    names = sorted(n for n in manpages.PAGES if n not in TOPICS)
    for name in names:
        table.add_row(name, escape(manpages.PAGES[name]["summary"]))
    console.print(table)
    console.print("[bold]Topics:[/bold] " + ", ".join(t for t in TOPICS if t in manpages.PAGES) + "   [dim](man <name> to read one)[/dim]")


def search(word):
    word = word.lower()
    hits = [p for p in manpages.PAGES.values()
            if word in p["name"] or word in p["summary"].lower() or word in p["description"].lower()]
    if not hits:
        console.print(f"[yellow]Nothing in the manual mentions '{escape(word)}'.[/yellow]")
        return False
    table = Table(header_style="bold blue")
    table.add_column("Page", style="bold green")
    table.add_column("About")
    for p in sorted(hits, key=lambda p: p["name"]):
        table.add_row(p["name"], escape(p["summary"]))
    console.print(table)
    return True


def execute(args=None):
    args = list(args or [])
    if not args:
        listing()
        return True
    if args[0] in ("-k", "--search"):
        if len(args) < 2:
            console.print("[bold red]Usage:[/bold red] man -k <word>")
            return False
        return search(" ".join(args[1:]))
    name = args[0].lower()
    if name in manpages.PAGES:
        show(manpages.PAGES[name])
        return True
    # a command with no page of its own: fall back to its one-line description
    try:
        import shell
        for table in (shell.available_commands, shell.available_programs):
            key = shell.find_entry(table, name)
            if key:
                if key in manpages.PAGES:
                    show(manpages.PAGES[key])
                else:
                    console.print(f"[bold]{escape(key)}[/bold] - {escape(table[key]['description'])}")
                    console.print("[dim]There is no longer manual page for it yet.[/dim]")
                return True
    except Exception:
        pass
    close = difflib.get_close_matches(name, manpages.PAGES, n=3)
    hint = f" Did you mean: {', '.join(close)}?" if close else " Try: man (to list pages) or man -k <word>."
    console.print(f"[bold red]man: no manual entry for '{escape(name)}'.[/bold red]{hint}")
    return False
