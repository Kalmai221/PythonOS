import getpass
import shlex

from rich.console import Console
from rich.markup import escape

import pyos
import users
from pyos import audit
from pyos.i18n import tr

console = Console()
config = {"name": "sudo", "description": "Run one command as an administrator: sudo <command> [arguments]  (sudo -k forgets the password)"}


def _admins():
    return sorted(name for name, info in users.get_users().items() if isinstance(info, dict) and info.get("role") == "admin")


def _ask_admin(me):
    """A standard user must give an administrator's name and password. Returns the administrator, or None."""
    admins = _admins()
    if not admins:
        console.print("[bold red]" + escape(tr("sudo: there is no administrator account.")) + "[/bold red]")
        return None
    try:
        name = admins[0] if len(admins) == 1 else input(tr("Administrator ({names}): ", names=", ".join(admins))).strip()
        if name not in admins:
            console.print("[bold red]" + escape(tr("sudo: {name} is not an administrator.", name=name)) + "[/bold red]")
            return None
        for _attempt in range(3):
            ok, message = users.authenticate(name, getpass.getpass(tr("Password for {name}: ", name=name)))
            if ok:
                return name
            console.print(f"[bold red]{escape(message)}[/bold red]")
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]" + escape(tr("Cancelled.")) + "[/yellow]")
        return None
    audit.record("sudo refused: wrong password three times", f"(asked by {me})", "WARN", me)
    return None


def execute(args=None):
    args = list(args or [])
    me, role = pyos.userinfo()
    if not me:
        console.print("[bold red]" + escape(tr("sudo: you are not logged in.")) + "[/bold red]")
        return False
    if args[:1] == ["-k"]:
        audit.forget(me)
        console.print("[dim]" + escape(tr("The remembered password was forgotten; the next sudo asks again.")) + "[/dim]")
        return True
    if not args:
        console.print("[bold red]" + escape(tr("Usage:")) + "[/bold red] " + escape(tr("sudo <command> [arguments]   (sudo -k forgets the password)")))
        return False

    line = shlex.join(args)
    if role == "admin":
        if not audit.elevate(tr("run '{command}' with sudo", command=line)):
            return False
        return _run(line, me, role, me)
    admin = _ask_admin(me)
    if not admin:
        return False
    audit.remember(admin)
    audit.record(f"sudo: {me} ran '{line}' as an administrator", user=admin)
    return _run(line, me, role, admin)


def _run(line, me, role, admin):
    """Run the command line with the rights of `admin`, then put the person's own session back."""
    import shell
    switch = admin != me
    if switch:
        users.save_session(admin, "admin")
    try:
        status = shell.run_line(line)
    finally:
        if switch:
            users.save_session(me, role)
    return status in (0, None)
