# pyos/helpview.py - the `help` command: categories first, details on request, search, and paging.
#
# One table of every command stops working once there are dozens of commands and apps, so help shows a short list of
# categories and lets you drill in:  help | help <number or category> | help <command> | help <what you want to do> | help all
import difflib

from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from . import theme

# category -> (blurb, command names). A command that is not listed lands in "Other" until it is added here.
CATEGORIES = {
    "Files": ("Look at and change files and folders",
              ["ls", "cd", "pwd", "cat", "head", "tail", "wc", "grep", "find", "tree", "touch", "mkdir", "cp", "mv", "rm", "trash", "undo", "edit", "fm",
               "zip", "unzip", "tar", "du", "stat", "less", "tee", "which", "basename", "dirname"]),
    "Text and shell": ("Print, repeat and organise what you type",
                       ["echo", "history", "clear", "man", "tutorial", "sort", "uniq", "cut", "tr", "diff", "xargs", "tee", "less",
                        "alias", "unalias", "export", "env", "watch", "time", "rev", "tac", "nl", "seq", "cal", "cowsay", "fortune", "rainbow"]),
    "Jobs and scheduling": ("Run things in the background or later",
                            ["jobs", "fg", "kill", "sleep", "schedule", "notifications", "taskman", "ps", "service"]),
    "Accounts and security": ("Who you are and how the system protects itself",
                              ["whoami", "id", "who", "passwd", "su", "lock", "last", "logout", "manageusers", "logs", "doctor"]),
    "System": ("About this computer and its settings",
               ["sysinfo", "uname", "hostname", "uptime", "free", "df", "date", "version", "settings", "bootlog", "whathappened", "report", "diag", "quickstart", "arch", "nproc", "lscpu", "pgrep"]),
    "Network and hardware": ("Connect, share and set up hardware",
                             ["ping", "tracert", "nslookup", "whois", "curl", "wget", "netstat", "ifconfig", "ipinfo", "share", "hwsetup", "display", "persist", "print"]),
    "Updates and apps": ("Keep PythonOS current and add apps",
                         ["updatecheck", "rollback", "whatsnew", "pkg", "backup", "limits"]),
    "Power": ("Turn off, restart or reset", ["shutdown", "restart", "wipe", "installos"]),
}


# "I want to ..." -> what to type. Shown on the first help screen, so a newcomer does not need to know a command name.
TASKS = [
    ("See what is in a folder", "ls", "ls -l"),
    ("Read or edit a file", "cat <file>, edit <file>", "less <file>"),
    ("Copy, move or delete", "cp, mv, rm", "undo brings a deleted file back"),
    ("Find a file or some text", "find <name>, grep <text> <file>", "help search find"),
    ("Check the internet", "ping <host>, tracert <host>", "nslookup <name>"),
    ("Add apps and games", "market", "pkg install <name>"),
    ("Update PythonOS", "updatecheck", "whatsnew"),
    ("Change how it looks or works", "settings", "settings theme ocean"),
    ("See what is running", "taskman, ps", "kill <id>"),
    ("Turn off or restart", "shutdown, restart", ""),
]

# words people use for things, mapped to command words, so `help copy a file` finds cp
SYNONYMS = {
    "copy": "cp", "duplicate": "cp", "move": "mv", "rename": "mv", "delete": "rm trash", "remove": "rm", "erase": "rm wipe", "folder": "ls cd mkdir",
    "directory": "ls cd mkdir", "list": "ls", "show": "cat ls", "read": "cat less", "open": "cat edit", "write": "edit echo", "search": "find grep",
    "internet": "ping curl nslookup", "network": "ping ifconfig netstat", "website": "curl wget", "download": "wget curl", "dns": "nslookup",
    "route": "tracert", "speed": "ping", "password": "passwd", "user": "manageusers su whoami", "account": "manageusers passwd", "quit": "exit shutdown logout",
    "exit": "logout shutdown", "reboot": "restart", "poweroff": "shutdown", "update": "updatecheck pkg", "upgrade": "updatecheck", "install": "pkg market installos",
    "app": "market pkg run", "game": "market run", "memory": "free taskman", "disk": "df du", "space": "df du", "process": "ps taskman kill", "kill": "kill",
    "time": "date uptime", "clock": "date", "calendar": "cal", "backup": "backup", "restore": "undo backup rollback", "clear": "clear", "screen": "clear display",
    "resolution": "display", "sound": "hwsetup", "audio": "hwsetup", "wifi": "hwsetup", "keyboard": "hwsetup", "print": "print", "count": "wc", "sort": "sort",
    "zip": "zip unzip tar", "archive": "zip tar", "permission": "limits", "limit": "limits", "theme": "settings", "setting": "settings",
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


FOOTER = ("[dim]help <number> opens a group  |  help <command> explains one  |  help <what you want to do>, for example help copy a file  |  "
          "help all  |  man <name> for the full manual  |  Tab completes[/dim]")


def show_tasks(console):
    """The "I want to ..." block of the first help screen."""
    if _narrow(console):
        console.print("[bold]I want to...[/bold]")
        for task, commands, _more in TASKS[:6]:
            console.print(f"  {escape(task)}: [bold]{escape(commands)}[/bold]")
        console.print()
        return
    table = Table(title=theme.tag("title", "I want to..."), title_justify="left", border_style=theme.style("border"), header_style="bold", expand=True)
    table.add_column("Task")
    table.add_column("Type", style="bold")
    table.add_column("Also", style="dim")
    for task, commands, more in TASKS:
        table.add_row(escape(task), escape(commands), escape(more))
    console.print(table)


def overview(console, commands, programs):
    groups = grouped(commands)
    console.print(f"[bold]Help[/bold]  [dim]{len(commands)} commands" + (f", {len(programs)} apps" if programs else "") + "[/dim]\n")
    rows = list(groups.items())
    if programs:
        rows.append(("Apps", sorted(programs)))
    if _narrow(console):
        for number, (category, names) in enumerate(rows, 1):
            blurb = CATEGORIES.get(category, ("",))[0]
            console.print(f"[bold]{number}[/bold] [bold]{escape(category)}[/bold] ({len(names)}) [dim]{escape(blurb)}[/dim]")
        console.print()
    else:
        table = Table(border_style=theme.style("border"), header_style="bold", expand=True)
        table.add_column("No.", justify="right", style="bold")
        table.add_column("Category", style="bold " + (theme.style("success") or "green"), no_wrap=True)
        table.add_column("Commands")
        table.add_column("#", justify="right", style="dim")
        for number, (category, names) in enumerate(rows, 1):
            shown = ", ".join(names[:7]) + (f", ... +{len(names) - 7}" if len(names) > 7 else "")
            table.add_row(str(number), escape(category), escape(shown), str(len(names)))
        console.print(table)
    show_tasks(console)
    console.print("[dim]New here?[/dim] [bold]tutorial[/bold] [dim]walks you through it.[/dim]")
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
        return False
    hits = search_hits(word, commands, programs)
    if not hits:
        console.print(f"[yellow]Nothing matches '{escape(word)}'.[/yellow] Try [bold]help[/bold] for the groups, or another word for the same thing.")
        return False
    console.print(f"[bold]Matches for '{escape(word)}'[/bold] [dim](best first)[/dim]")
    for name, kind, text in hits[:15]:
        console.print(f"  [bold]{escape(name)}[/bold] [dim]({kind})[/dim] - {escape(text)}")
    if len(hits) > 15:
        console.print(f"[dim]... and {len(hits) - 15} more. Add a word to narrow it down.[/dim]")
    console.print("[dim]help <name> explains one of them.[/dim]")
    return True


def search_hits(phrase, commands, programs):
    """[(name, kind, text)] best first: every word of the phrase counts (with synonyms), names count more than descriptions."""
    words = [w for w in phrase.lower().replace("?", " ").split() if w not in STOP_WORDS]
    if not words:
        return []
    extra = []
    for w in words:
        extra += SYNONYMS.get(w, SYNONYMS.get(w.rstrip("s"), "")).split()
    scores = {}
    kinds = {}
    texts = {}
    for kind, data in (("command", commands), ("app", programs)):
        for name, info in data.items():
            hay = " ".join([info["description"], *info["aliases"]]).lower()
            score = 0
            for w in words:
                if w == name or w in info["aliases"]:
                    score += 6
                elif w in name:
                    score += 3
                if w in hay:
                    score += 2
            if name in extra:
                score += 4
            if score:
                scores[name], kinds[name], texts[name] = score, kind, info["description"]
    try:
        from . import manpages
        for name, page in manpages.PAGES.items():
            if name in scores:
                continue
            body = (page["summary"] + " " + page["description"]).lower()
            score = sum(1 for w in words if w in body) + (3 if name in extra else 0)
            if score:
                scores[name], kinds[name], texts[name] = score, "manual", page["summary"]
    except Exception:
        pass
    if len(words) > 1:                                  # several words: keep what matches most of them
        best = max(scores.values(), default=0)
        scores = {n: s for n, s in scores.items() if s >= max(1, best // 3)}
    return [(n, kinds[n], texts[n]) for n in sorted(scores, key=lambda n: (-scores[n], n))]


STOP_WORDS = {"a", "an", "the", "to", "how", "do", "i", "can", "my", "is", "of", "and", "or", "for", "in", "on", "it", "me", "what", "where", "want", "need", "file", "files"}


def show_one(console, key, kind, info):
    usage = f"run {key}" if kind == "program" else key
    aliases = ", ".join(info["aliases"]) or "none"
    where = "App" if kind == "program" else category_of(key)
    page = None
    try:
        from . import manpages
        page = manpages.PAGES.get(key)
    except Exception:
        pass
    lines = [escape(info["description"]), ""]
    if page and page.get("synopsis"):
        lines.append("[bold]Usage:[/bold]")
        lines += [f"  {escape(s)}" for s in page["synopsis"][:5]]
    else:
        lines.append(f"[bold]Usage:[/bold] {escape(usage)}")
    if page and page.get("examples"):
        lines.append("[bold]Examples:[/bold]")
        for example, note in page["examples"][:4]:
            lines.append(f"  [green]{escape(example)}[/green]" + (f"  [dim]{escape(note)}[/dim]" if note else ""))
    lines.append(f"[bold]Aliases:[/bold] {escape(aliases)}    [bold]Group:[/bold] {escape(where)}")
    if page and page.get("see"):
        lines.append("[bold]Related:[/bold] " + ", ".join(escape(s) for s in page["see"]))
    lines.append(f"[dim]The full manual: man {escape(key)}[/dim]")
    console.print(Panel("\n".join(lines), title=f"{theme.tag('title', key)} [dim]({kind})[/dim]", border_style=theme.style("border"), expand=False))


def show(console, commands, programs, words, find_entry):
    """Entry point for `help [words]`."""
    if not words:
        overview(console, commands, programs)
        return
    first = words[0].lower()
    if first in ("all", "everything"):
        show_all(console, commands, programs)
        return
    if first in ("search", "-s"):
        show_search(console, " ".join(words[1:]), commands, programs)
        return
    # an exact command or app wins over a category of the same name
    for kind, data in (("command", commands), ("program", programs)):
        key = find_entry(data, words[0])
        if key:
            show_one(console, key, kind, data[key])
            return
    names = [c for c in list(CATEGORIES) + ["Other", "Apps"]]
    if first.isdigit():
        ordered = list(grouped(commands)) + (["Apps"] if programs else [])
        number = int(first)
        if 1 <= number <= len(ordered):
            show_category(console, ordered[number - 1], commands, programs)
        else:
            console.print(f"[bold red]There is no group {number}.[/bold red] help shows the numbered groups (1 to {len(ordered)}).")
        return
    for category in names:
        if category.lower() == " ".join(words).lower() or category.lower().startswith(first):
            show_category(console, category, commands, programs)
            return
    close = difflib.get_close_matches(first, list(commands) + list(programs) + [c.lower() for c in names], n=3, cutoff=0.6)
    if search_hits(" ".join(words), commands, programs):
        show_search(console, " ".join(words), commands, programs)         # not a command name: treat it as "what I want to do"
        return
    console.print(f"[bold red]No help entry for '{escape(words[0])}'.[/bold red]"
                  + (f" Did you mean: {', '.join(close)}?" if close else "") + " Try [bold]help[/bold] for the groups.")
