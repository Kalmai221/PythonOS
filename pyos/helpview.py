# pyos/helpview.py - the `help` command: categories first, details on request, search, and paging.
#
# One table of every command stops working once there are dozens of commands and apps, so help shows a short list of
# categories and lets you drill in:  help | help <category> | help <command> | help search <word> | help all
import difflib

from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from . import theme

# category -> (blurb, command names). A command that is not listed lands in "Other" until it is added here.
CATEGORIES = {
    "Files": ("Look at and change files and folders",
              ["ls", "cd", "pwd", "cat", "head", "tail", "wc", "grep", "find", "tree", "touch", "mkdir", "cp", "mv", "rm", "trash", "undo", "edit",
               "zip", "unzip", "tar", "du", "stat"]),
    "Text and shell": ("Print, repeat and organise what you type",
                       ["echo", "history", "clear", "man", "tutorial", "sort", "uniq", "cut", "tr", "diff", "xargs", "tee", "less",
                        "alias", "unalias", "export", "env", "watch", "time", "cowsay", "fortune", "rainbow"]),
    "Jobs and scheduling": ("Run things in the background or later",
                            ["jobs", "fg", "kill", "sleep", "schedule", "notifications", "taskman", "ps", "service"]),
    "Accounts and security": ("Who you are and how the system protects itself",
                              ["whoami", "passwd", "su", "lock", "last", "logout", "manageusers", "logs", "doctor"]),
    "System": ("About this computer and its settings",
               ["sysinfo", "uname", "hostname", "uptime", "free", "df", "date", "version", "settings", "bootlog", "whathappened", "report", "diag", "quickstart"]),
    "Network and hardware": ("Connect, share and set up hardware",
                             ["ping", "ipinfo", "share", "hwsetup", "persist", "print"]),
    "Updates and apps": ("Keep PythonOS current and add apps",
                         ["updatecheck", "rollback", "whatsnew", "pkg", "backup", "limits"]),
    "Power": ("Turn off, restart or reset", ["shutdown", "restart", "wipe", "installos"]),
}


def category_of(name):
    for category, (_blurb, names) in CATEGORIES.items():
        if name in names:
            return category
    return "Other"


def grouped(commands):
    """{category: [command names present]} in display order (empty categories left out)."""
    groups = {c: [] for c in CATEGORIES}
    groups["Other"] = []
    for name in sorted(commands):
        groups[category_of(name)].append(name)
    return {c: names for c, names in groups.items() if names}


def _narrow(console):
    return console.width < 72


def _entries(console, title, data, names, kind="command"):
    """A table of commands (or compact lines on a narrow screen such as a phone)."""
    if _narrow(console):
        console.print(theme.tag("title", title))
        for name in names:
            info = data[name]
            console.print(f"  [bold]{escape(name)}[/bold] - {escape(info['description'])}")
        return
    table = Table(title=theme.tag("title", title), title_justify="left", header_style="bold",
                  border_style=theme.style("border"), expand=True)
    table.add_column("Name", style="bold " + (theme.style("success") or "green"), no_wrap=True)
    table.add_column("Description")
    table.add_column("Aliases", style="dim", no_wrap=True)
    for name in names:
        info = data[name]
        table.add_row(escape(name), escape(info["description"]), escape(", ".join(info["aliases"])))
    console.print(table)


def _page(console, render):
    """Run render(); when the output is taller than the screen and this is a real terminal, show it in a pager."""
    if console.is_terminal:
        with console.capture() as captured:
            render()
        text = captured.get()
        if text.count("\n") > console.height - 3:
            with console.pager(styles=True):
                console.print(text, end="", markup=False, highlight=False)
            return
        console.print(text, end="", markup=False, highlight=False)
        return
    render()


FOOTER = ("[dim]help <category> lists one group  |  help <command> shows one  |  help search <word>  |  help all  |  "
          "man <name> for the manual  |  Tab completes[/dim]")


def overview(console, commands, programs):
    groups = grouped(commands)
    console.print(f"[bold]Help[/bold]  [dim]{len(commands)} commands" + (f", {len(programs)} apps" if programs else "") + "[/dim]\n")
    rows = list(groups.items())
    if programs:
        rows.append(("Apps", sorted(programs)))
    if _narrow(console):
        for category, names in rows:
            blurb = CATEGORIES.get(category, ("",))[0]
            console.print(f"[bold]{escape(category)}[/bold] ({len(names)}) [dim]{escape(blurb)}[/dim]")
        console.print()
    else:
        table = Table(border_style=theme.style("border"), header_style="bold", expand=True)
        table.add_column("Category", style="bold " + (theme.style("success") or "green"), no_wrap=True)
        table.add_column("Commands")
        table.add_column("#", justify="right", style="dim")
        for category, names in rows:
            shown = ", ".join(names[:8]) + (f", ... +{len(names) - 8}" if len(names) > 8 else "")
            table.add_row(escape(category), escape(shown), str(len(names)))
        console.print(table)
    console.print("[dim]Start with:[/dim] [bold]tutorial[/bold]  [dim]|[/dim] [bold]help Files[/bold]  [dim]|[/dim] "
                  "[bold]market[/bold] [dim](more apps)[/dim]")
    console.print(FOOTER)


def show_category(console, category, commands, programs):
    if category == "Apps":
        names = sorted(programs)
        _page(console, lambda: _entries(console, "Apps  (start with: run <name>)", programs, names, "program"))
        return
    names = grouped(commands).get(category, [])
    blurb = CATEGORIES.get(category, ("Commands that are not in a group yet",))[0]
    _page(console, lambda: _entries(console, f"{category} - {blurb}", commands, names))


def show_all(console, commands, programs):
    def render():
        for category, names in grouped(commands).items():
            _entries(console, category, commands, names)
        if programs:
            _entries(console, "Apps  (start with: run <name>)", programs, sorted(programs), "program")
    _page(console, render)


def show_search(console, word, commands, programs):
    word = word.lower().strip()
    if not word:
        console.print("[bold red]Usage:[/bold red] help search <word>")
        return
    hits = []
    for kind, data in (("command", commands), ("app", programs)):
        for name, info in data.items():
            hay = " ".join([name, info["description"], *info["aliases"]]).lower()
            if word in hay:
                hits.append((name, kind, info["description"]))
    try:
        from . import manpages
        known = {h[0] for h in hits}
        for name, page in manpages.PAGES.items():
            if name not in known and word in (name + " " + page["summary"] + " " + page["description"]).lower():
                hits.append((name, "manual", page["summary"]))
    except Exception:
        pass
    if not hits:
        console.print(f"[yellow]Nothing matches '{escape(word)}'.[/yellow] Try [bold]help[/bold] for the categories.")
        return
    for name, kind, text in sorted(hits)[:40]:
        console.print(f"  [bold]{escape(name)}[/bold] [dim]({kind})[/dim] - {escape(text)}")
    if len(hits) > 40:
        console.print(f"[dim]... and {len(hits) - 40} more. Be more specific.[/dim]")


def show_one(console, key, kind, info):
    usage = f"run {key}" if kind == "program" else key
    aliases = ", ".join(info["aliases"]) or "none"
    where = "App" if kind == "program" else category_of(key)
    console.print(Panel(
        f"{escape(info['description'])}\n\n[bold]Usage:[/bold] {escape(usage)}\n[bold]Aliases:[/bold] {escape(aliases)}"
        f"\n[bold]Group:[/bold] {escape(where)}\n[dim]More: man {escape(key)}[/dim]",
        title=f"{theme.tag('title', key)} [dim]({kind})[/dim]", border_style=theme.style("border"), expand=False))


def show(console, commands, programs, words, find_entry):
    """Entry point for `help [words]`."""
    if not words:
        overview(console, commands, programs)
        return
    first = words[0].lower()
    if first in ("all", "everything"):
        show_all(console, commands, programs)
        return
    if first in ("search", "find", "-s"):
        show_search(console, " ".join(words[1:]), commands, programs)
        return
    # an exact command or app wins over a category of the same name
    for kind, data in (("command", commands), ("program", programs)):
        key = find_entry(data, words[0])
        if key:
            show_one(console, key, kind, data[key])
            return
    names = [c for c in list(CATEGORIES) + ["Other", "Apps"]]
    for category in names:
        if category.lower() == " ".join(words).lower() or category.lower().startswith(first):
            show_category(console, category, commands, programs)
            return
    close = difflib.get_close_matches(first, list(commands) + list(programs) + [c.lower() for c in names], n=3, cutoff=0.6)
    console.print(f"[bold red]No help entry for '{escape(words[0])}'.[/bold red]"
                  + (f" Did you mean: {', '.join(close)}?" if close else "") + " Try [bold]help search " + escape(first) + "[/bold].")
