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


def _look_and_feel():
    names = list(theme.THEMES)
    console.print("Colour themes: " + ", ".join(f"[{theme.THEMES[n]['accent']}]{n}[/{theme.THEMES[n]['accent']}]" for n in names))
    choice = Prompt.ask("Theme", choices=names, default=settings.get("theme"))
    settings.set("theme", choice)
    speed = Prompt.ask("Boot speed (how long the start-up animation takes)", choices=["normal", "fast", "instant"],
                       default=settings.get("boot_speed"))
    settings.set("boot_speed", speed)


def _persistent_storage():
    from core import persist, hardware
    if persist.active() or hardware.unavailable_reason():
        return
    console.print(Panel("The live system forgets everything when it is switched off. A USB stick or spare disk can keep your "
                        "account, files and settings. (You can also do this later with [bold]persist create[/bold].)",
                        border_style=theme.style("border"), expand=False))
    if Confirm.ask("Set up persistent storage now?", default=False):
        try:
            persist.create()
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


def firsttimeuse():
    live = os.environ.get("PYOS_LIVE") == "1"
    total = 5 if live else 3
    console.clear()
    console.print(Panel(Text("Welcome to PythonOS", style="bold white on dark_green", justify="center")))
    console.print("Let's set things up. It takes a minute, and you can change everything later.\n")
    number = 0

    if live:
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
