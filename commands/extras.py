"""extras: choose which optional libraries this PythonOS has.

    extras                     what is available, what is installed, what you chose
    extras choose              pick them from a list
    extras install <name>...   install some (or: all)
    extras remove <name>...    remove some
    extras none                have none of them
PythonOS works without any of them; each adds something (see the list). The choice is kept, so updates install what you chose.
"""
from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm, Prompt
from rich.table import Table

from pyos import extras, lockdown
from pyos.i18n import tr

console = Console()
config = {"name": "extras", "description": "Choose which optional libraries to have (extras [choose|install|remove|none])."}


def _say(text):
    console.print(f"[dim]{escape(tr(text))}[/dim]")


def status(extra, chosen):
    if extras.backend() == "bundled":                          # the Android app: every library is inside, the choice is a switch
        return "[green]" + tr("on") + "[/green]" if extra.name in chosen else "[dim]" + tr("off") + "[/dim]"
    if extra.installed():
        return "[green]" + tr("installed") + "[/green]"
    if extra.name in chosen:
        return "[yellow]" + tr("chosen, not installed yet") + "[/yellow]"
    return "[dim]" + tr("not installed") + "[/dim]"


def show(items):
    chosen = set(extras.wanted(items))
    table = Table(title=tr("Optional libraries"))
    for column in ("#", tr("Library"), tr("What it adds"), tr("Status")):
        table.add_column(column)
    for number, extra in enumerate(items, 1):
        table.add_row(str(number), escape(extra.name), escape(extra.description), status(extra, chosen))
    console.print(table)
    choice = extras.load_choice()
    mode = {"all": tr("all of them"), "none": tr("none of them"), "custom": tr("the ones you picked")}.get(choice["mode"]) if choice else tr("not chosen yet")
    console.print(f"[dim]{escape(tr('Your choice: {mode}', mode=mode))}[/dim]")
    fresh = extras.new_since_choice(items)
    if fresh:
        console.print(f"[yellow]{escape(tr('New since you chose: {names}. Run: extras install <name>', names=', '.join(e.name for e in fresh)))}[/yellow]")


def _report(results, why):
    if why:
        console.print(f"[bold red]{escape(tr('extras:'))} {escape(tr(why))}[/bold red]")
        return False
    ok = True
    for name, done in results.items():
        console.print((f"[green]{escape(tr('installed'))}[/green] " if done else f"[red]{escape(tr('could not install'))}[/red] ") + escape(name))
        ok = ok and done
    return ok


def choose(items):
    """Ask which to have; remember the answer and install it. True when done."""
    if not items:
        console.print(tr("There are no optional libraries."))
        return True
    show(items)
    here = set(extras.wanted(items))
    console.print("\n" + escape(tr("Type the numbers you want (for example 1 3 5), a for all, n for none, or Enter to keep the current choice.")))
    try:
        answer = Prompt.ask(tr("Your choice"), default="").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print()
        return False
    if not answer:
        return True
    if answer in ("a", "all"):
        extras.save_choice("all")
        picked = [e.name for e in items]
    elif answer in ("n", "none", "no"):
        extras.save_choice("none")
        picked = []
    else:
        try:
            numbers = sorted({int(x) for x in answer.replace(",", " ").split()})
            picked = [items[n - 1].name for n in numbers if n >= 1]
            if len(picked) != len(numbers):
                raise IndexError
        except (ValueError, IndexError):
            console.print(f"[red]{escape(tr('Those are not numbers from the list.'))}[/red]")
            return False
        every = {e.name for e in items}
        extras.save_choice("all" if set(picked) == every else "none" if not picked else "custom", picked)
    bundled = extras.backend() == "bundled"
    gone = [] if bundled else sorted(n for n in here if n not in picked and any(e.name == n and e.installed() for e in items))
    if gone and Confirm.ask(tr("Remove the ones you did not pick? ({names})", names=", ".join(gone)), default=False):
        _report(*extras.remove(gone, _say))
    if bundled:
        console.print("[green]" + escape(tr("Saved. Switched on: {names}", names=", ".join(picked) or tr("none"))) + "[/green]")
        return True
    todo = [n for n in picked if not any(e.name == n and e.installed() for e in items)]
    return _report(*extras.install(todo, _say)) if todo else True


def first_time():
    """The question of the first-time setup: install the optional libraries? Remembers the answer. Does nothing when it was answered or cannot apply."""
    items = extras.catalog()
    if not items or not extras.undecided(items):
        return
    missing = items if extras.backend() == "bundled" else [e for e in items if not e.installed()]
    console.print(escape(tr("PythonOS has optional libraries. Each adds something (better search, more archive types, ...) and none is needed.")))
    for e in missing:
        console.print(f"  [bold]{escape(e.name)}[/bold]  [dim]{escape(e.description)}[/dim]")
    bundled = extras.backend() == "bundled"
    if bundled:
        console.print("[dim]" + escape(tr("They all come with this app. Switch on the ones you want; nothing is downloaded.")) + "[/dim]")
    elif extras.backend() == "apk":
        console.print("[dim]" + escape(tr("They are downloaded when you install them, so this computer needs the internet.")) + "[/dim]")
    try:
        question = tr("Switch them on: (a)ll, (c)hoose, or (n)one") if bundled else tr("Install them: (a)ll, (c)hoose, or (n)one")
        answer = Prompt.ask("\n" + question, choices=["a", "c", "n"], default="n" if extras.backend() == "apk" else "a")
    except (EOFError, KeyboardInterrupt):
        console.print()
        return
    if answer == "c":
        choose(items)
    elif answer == "a":
        extras.save_choice("all")
        if not bundled:
            _report(*extras.install([e.name for e in missing], _say))
    else:
        extras.save_choice("none")
    console.print()


def execute(args=None):
    args = list(args or [])
    if lockdown.enabled() and extras.backend() != "apk" and args and args[0] not in ("list", "ls"):
        console.print(f"[bold red]{escape(tr('extras: not while lockdown is on'))}[/bold red]")
        return False
    items = extras.catalog()
    if not args or args[0] in ("list", "ls"):
        show(items)
        return True
    action, names = args[0], args[1:]
    if action == "choose":
        return choose(items)
    if action == "none":
        extras.save_choice("none")
        console.print(escape(tr("Chosen: none. Libraries that are installed stay until you run: extras remove <name>")))
        return True
    if action in ("install", "add", "remove", "uninstall", "rm"):
        known = {e.name for e in items}
        installing = action in ("install", "add")
        if names == ["all"] or (not names and installing):
            names = sorted(known)
        unknown = [n for n in names if n not in known]
        if unknown or not names:
            console.print(f"[bold red]{escape(tr('Unknown: {names}. See: extras', names=', '.join(unknown) or '-'))}[/bold red]")
            return False
        choice = extras.load_choice()
        current = set(choice["selected"]) if choice and choice["mode"] == "custom" else set(extras.wanted(items))
        if installing:
            keep = current | set(names)
            extras.save_choice("all" if keep >= known else "custom", keep)
            return _report(*extras.install(names, _say))
        keep = current - set(names)
        extras.save_choice("custom" if keep else "none", keep)
        return _report(*extras.remove(names, _say))
    console.print(f"[bold red]{escape(tr('Usage:'))}[/bold red] extras [choose | install <name>... | remove <name>... | none]")
    return False
