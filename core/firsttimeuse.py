"""First-time setup: one guided flow instead of several separate screens.

    1. (live ISO) keyboard layout, time zone, network and audio - first, so a password is typed on the right keyboard
    2. your account (the first one is the administrator)
    3. computer name, colour theme and boot speed
    4. (live ISO) optional persistent storage, so the account and files survive a power-off
    5. updates and a few starter apps, if you are online
"""
import importlib.util
import os

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.text import Text

from pyos import fs, settings, theme

console = Console()
STARTER_APPS = [("utilities/notes", "Notes"), ("utilities/todo", "To-do"), ("utilities/clock", "Clock"),
                ("utilities/calendar", "Calendar"), ("utilities/files", "File Manager")]


def _step(number, total, title):
    console.print(f"\n[bold cyan]Step {number} of {total}[/bold cyan]  [bold]{title}[/bold]")


def _online():
    from core import sysupdate
    return sysupdate.check_internet_connection()


def _hardware_steps():
    """Keyboard, time zone, network, audio - each optional."""
    from core import hardware
    if hardware.unavailable_reason():
        return
    console.print("[dim]Each of these can be skipped and done later with 'hwsetup'.[/dim]")
    for label, action in (("keyboard layout", hardware.keyboard_setup), ("time zone", hardware.timezone_setup),
                          ("network and internet", hardware.network_setup), ("audio", hardware.audio_setup)):
        try:
            if Confirm.ask(f"Set up the {label} now?", default=label != "audio"):
                action()
        except (KeyboardInterrupt, EOFError):
            console.print(f"\n[yellow]Skipped the {label}.[/yellow]")
        except Exception as e:  # a missing tool must never stop the setup
            console.print(f"[yellow]Could not set up the {label}: {escape(str(e))}[/yellow]")


def _create_account():
    import users
    console.print(Panel("Create your account. The first account is the [bold]administrator[/bold]: it can manage "
                        "other accounts and the system.", border_style=theme.style("border"), expand=False))
    while not users.get_users():
        if users.register_and_login():
            break
        console.print("[yellow]Let's try again.[/yellow]")
    name = pyos_user()
    return name


def pyos_user():
    from pyos import userinfo
    return userinfo()[0]


def _computer_name():
    current = fs.hostname()
    name = Prompt.ask("Name this computer", default=current).strip()
    clean = "".join(c for c in name if c.isalnum() or c in "-_")[:30]
    if clean and clean != current:
        try:
            with open(os.path.join(fs.BASE_DIR, "etc", "hostname"), "w", encoding="utf-8") as f:
                f.write(clean + "\n")
        except OSError:
            console.print("[yellow]Could not save the name; it stays " + escape(current) + ".[/yellow]")


def _theme_sample(name):
    """A little screen drawn in the theme's own colours, so it can be judged before it is chosen."""
    roles = theme.THEMES[name]
    lines = [f"[{roles['title']}]{name}[/{roles['title']}]  [{roles['dim']}]a sample of this theme[/{roles['dim']}]",
             f"[{roles['prompt_user']}]you@pyOS[/{roles['prompt_user']}]:[{roles['prompt_path']}]~[/{roles['prompt_path']}]$ ls",
             f"[{roles['success']}]Backup finished[/{roles['success']}]   [{roles['warning']}]Disk almost full[/{roles['warning']}]   "
             f"[{roles['error']}]Something went wrong[/{roles['error']}]",
             f"[{roles['accent']}]accent colour[/{roles['accent']}]"]
    console.print(Panel(chr(10).join(lines), border_style=roles["border"], expand=False))


def _look_and_feel():
    names = list(theme.THEMES)
    original = settings.get("theme")
    console.print("[bold]Pick a colour theme.[/bold] Type a name to try it on a sample; you decide afterwards.")
    for n in names:
        _theme_sample(n)
    chosen = original
    while True:
        pick = Prompt.ask("Theme to try", choices=names, default=chosen)
        settings.set("theme", pick)             # applied right now, so everything after this is drawn in it
        _theme_sample(pick)
        if Confirm.ask(f"Keep the {pick} theme?", default=True):
            chosen = pick
            break
        chosen = pick


def _memory_budget():
    """How much of the computer's memory PythonOS owns. Skipped when an installer already asked (the setting is stored)."""
    from pyos import resources
    if resources.live() or settings.is_set("memory_limit_mb"):
        return
    options = resources.choices()
    physical = resources.physical_total() // resources.MB
    console.print("\n[bold]How much memory should PythonOS use?[/bold] This is the whole computer as far as PythonOS is concerned "
                  "(the machine has " + (f"{physical / 1024:.1f} GB" if physical else "an unknown amount") + "). "
                  "You can change it later: [bold]settings set memory_limit_mb 2048[/bold].")
    names = {str(o): ("all of it" if o == 0 else f"{o} MB") for o in options}
    for option in options:
        console.print(f"  [bold]{option if option else 'all'}[/bold]  {names[str(option)]}")
    default = "1024" if 1024 in options else str(options[0])
    answer = Prompt.ask("Memory in MB (or 'all')", choices=[str(o) if o else "all" for o in options], default=default)
    settings.set("memory_limit_mb", 0 if answer == "all" else int(answer))
    console.print(f"[dim]PythonOS now owns {resources.apply()}.[/dim]")


def _persistent_storage():
    from core import persist, hardware
    if persist.active() or hardware.unavailable_reason():
        return
    device = persist.best_candidate()
    found = persist.describe(device) if device else None
    console.print(Panel("The live system forgets everything when it is switched off. A USB stick or spare disk can keep your "
                        "account, files and settings. (You can also do this later with [bold]persist create[/bold].)"
                        + (f"\n\n[bold]Found:[/bold] {escape(found)}" if found else
                           "\n\n[dim]No suitable disk was found. Plug in a USB stick (not the one PythonOS started from) to use this. "
                           "In a virtual machine, add a second (empty) virtual disk, then run [bold]persist create[/bold].[/dim]"),
                        border_style=theme.style("border"), expand=False))
    if not found:
        return
    blank = not device.get("fstype") and not device.get("label")        # an empty disk: nothing on it to lose, so yes is the sensible default
    if blank:
        console.print("[dim]It is empty, so nothing on it will be lost.[/dim]")
    if Confirm.ask("Set up persistent storage now?", default=blank):
        try:
            persist.create(device["path"] if device else None)
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Skipped.[/yellow]")


def _updates_and_apps():
    if not _online():
        console.print("[dim]No internet connection, so no updates or apps now. Connect later and run "
                      "'updatecheck' or the marketplace ('market').[/dim]")
        return
    from core import sysupdate
    try:
        console.print("[cyan]Checking for updates...[/cyan]")
        sysupdate.update_system(True)
    except Exception as e:
        console.print(f"[yellow]Update check failed: {escape(str(e))}[/yellow]")
    names = ", ".join(n for _, n in STARTER_APPS)
    if not Confirm.ask(f"Install some starter apps ({names})?", default=True):
        return
    try:
        spec = importlib.util.spec_from_file_location("marketplace", os.path.join("programs", "marketplace.py"))
        market = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(market)
        packages, _offline = market.load_index()
        if not packages:
            return
        by_id = {p["id"]: p for p in packages}
        installed = market.installed_packages()
        for pid, label in STARTER_APPS:
            if pid in by_id and pid not in installed:
                market.install_with_dependencies(by_id[pid], installed, packages, quiet=True)
    except Exception as e:
        console.print(f"[yellow]Could not install the starter apps: {escape(str(e))} (try 'market' later).[/yellow]")


def _choose_language():
    """The very first question, in every language at once: which language should the system speak?"""
    from pyos import i18n
    if settings.get("language") != "auto":
        return
    guess = i18n.language()
    console.print("[bold]Language / Idioma / Langue / Sprache[/bold]")
    for code, name in i18n.LANGUAGES.items():
        console.print(f"  [bold]{code}[/bold]  {name}")
    try:
        chosen = Prompt.ask("Language", choices=list(i18n.LANGUAGES), default=guess)
    except (EOFError, KeyboardInterrupt):
        chosen = guess
    settings.set("language", chosen)
    console.print()


def firsttimeuse():
    live = os.environ.get("PYOS_LIVE") == "1"
    installed = os.environ.get("PYOS_INSTALLED") == "1"       # an installed PythonOS: hardware setup, but no live-USB storage step
    total = 5 if live else 4 if installed else 3
    console.clear()
    _choose_language()
    from pyos.i18n import tr
    console.print(Panel(Text(tr("Welcome to PythonOS"), style="bold white on dark_green", justify="center")))
    console.print(tr("Let's set things up. It takes a minute, and you can change everything later.") + "\n")
    number = 0

    if live or installed:
        number += 1
        _step(number, total, "Your hardware")
        _hardware_steps()

    number += 1
    _step(number, total, "Your account")
    name = _create_account()

    number += 1
    _step(number, total, "This computer")
    _computer_name()
    _look_and_feel()
    _memory_budget()

    if live:
        number += 1
        _step(number, total, "Keeping your data")
        _persistent_storage()

    number += 1
    _step(number, total, "Updates and apps")
    _updates_and_apps()

    console.print(Panel(f"[bold green]All set{', ' + escape(name) if name else ''}![/bold green]\n\n"
                        "Try [bold]tutorial[/bold] for a short guided tour, [bold]help[/bold] for the commands, "
                        "or [bold]market[/bold] for more apps.",
                        border_style=theme.style("border"), expand=False))
