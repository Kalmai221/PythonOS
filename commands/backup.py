import os
from rich.console import Console
from rich.markup import escape
from rich.prompt import Confirm
from rich.table import Table
import pyos
import pyos.fs as fs
from pyos import backup as engine

console = Console()
config = {
    "name": "backup",
    "description": "Back up and restore your files: backup create|list|restore <file> [--system]. Admins can back up everything.",
    "alias": [],
}

HELP = """[bold]backup[/bold] - keep your files safe, or move them to another PythonOS

  backup create \\[file]            zip up your home folder (saved in ~/backups unless you name a file)
  backup create --system \\[file]   admins: every user's files, accounts, settings and schedule
  backup list                     your backups
  backup restore <file> \\[-y]      put a backup back (asks before overwriting; -y skips the question)
  backup restore <file> --system  admins: restore a system backup

Backups are plain .zip files. Move one between devices with the share command, or copy it out of the app.
A system backup contains password hashes - keep it private."""


def _size(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def execute(args=None):
    args = list(args or [])
    user, role = pyos.userinfo()
    if not user:
        console.print("[bold red]backup: you are not logged in.[/bold red]")
        return False
    if not args or args[0] in ("help", "-h", "--help"):
        console.print(HELP)
        return True
    sub = args[0].lower()
    flags = {a for a in args[1:] if a.startswith("-")}
    rest = [a for a in args[1:] if not a.startswith("-")]
    system = "--system" in flags
    if system and role != "admin":
        console.print("[bold red]backup: only admins can use --system.[/bold red]")
        return False
    kind = "system" if system else "user"

    if sub == "create":
        try:
            if rest:
                dest = fs.resolve(rest[0], write=True)
            else:
                dest = os.path.join(fs.home_dir(user), engine.BACKUP_DIR, engine.default_name(kind, user))
            if not dest.endswith(".zip"):
                dest += ".zip"
            with console.status("Backing up..."):
                count, total = engine.create(kind, user, dest)
        except (PermissionError, OSError, ValueError) as e:
            console.print(f"[bold red]backup: {escape(str(e))}[/bold red]")
            return False
        console.print(f"[green]Backed up {count} file(s) ({_size(total)}).[/green] Saved as [bold]{escape(fs.display(dest, tilde=True))}[/bold]")
        if system:
            console.print("[yellow]This backup contains password hashes - keep it private.[/yellow]")
        return True

    if sub in ("list", "ls"):
        found = engine.list_backups(user)
        if not found:
            console.print("[dim]No backups yet. Make one with: backup create[/dim]")
            return True
        table = Table(header_style="bold blue")
        for col in ("Name", "Type", "Made", "Files", "Size"):
            table.add_column(col)
        for b in found:
            table.add_row(escape(b["name"]), b["kind"], b["created"].replace("T", " "), str(b["files"]), _size(b["size"]))
        console.print(table)
        return True

    if sub == "restore":
        if not rest:
            console.print("[bold red]Usage:[/bold red] backup restore <file> \\[-y]")
            return False
        try:
            path = fs.resolve(rest[0])
            if not os.path.isfile(path):
                raise ValueError(f"{rest[0]}: no such file")
            manifest, plan = engine.plan_restore(path, kind, user)
            if not plan:
                console.print("[yellow]That backup contains nothing to restore.[/yellow]")
                return False
            overwriting = sum(1 for _name, target in plan if os.path.exists(target))
            console.print(f"Backup from [bold]{manifest.get('created', '?').replace('T', ' ')}[/bold] ({manifest.get('user', '?')}), "
                          f"{len(plan)} file(s); {overwriting} would replace existing files.")
            if "-y" not in flags and not Confirm.ask("Restore it?", default=False):
                console.print("[yellow]Cancelled.[/yellow]")
                return False
            with console.status("Restoring..."):
                count = engine.restore(path, kind, user)
        except (PermissionError, OSError, ValueError) as e:
            console.print(f"[bold red]backup: {escape(str(e))}[/bold red]")
            return False
        console.print(f"[green]Restored {count} file(s).[/green]" + (" Restart PythonOS to use restored accounts and settings." if system else ""))
        return True

    console.print(f"[bold red]backup: unknown subcommand '{escape(sub)}'[/bold red]")
    console.print(HELP)
    return False
