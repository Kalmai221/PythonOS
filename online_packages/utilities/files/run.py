#!/usr/bin/env python3
"""File manager: browse the PythonOS filesystem, open, copy, move, rename, delete and search. It uses the same
permission checks as the shell, so it can only touch what your account may touch."""
import datetime
import fnmatch
import os
import shutil

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table

from pyos import fs

console = Console()
TEXT_LIMIT = 200_000
HELP = """[bold]Commands[/bold]  (N is a number from the list)
  [cyan]N[/cyan]            open a folder or view a file        [cyan]u[/cyan]  go up        [cyan]~[/cyan]  go home
  [cyan]g <path>[/cyan]     go to a path                        [cyan]f <pattern>[/cyan]  find files (e.g. f *.txt)
  [cyan]c N <dest>[/cyan]   copy                                [cyan]m N <dest>[/cyan]  move
  [cyan]r N <name>[/cyan]   rename                              [cyan]d N[/cyan]  delete
  [cyan]n <name>[/cyan]     new folder                          [cyan]t <name>[/cyan]  new empty file
  [cyan]i N[/cyan]          details                             [cyan]a[/cyan]  show/hide hidden files
  [cyan]h[/cyan]  help      [cyan]q[/cyan]  quit"""


def size_text(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def folder_size(path, limit=50_000):
    total = count = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
            count += 1
            if count > limit:
                return total, True
    return total, False


class Manager:
    def __init__(self):
        self.cwd = fs.current_dir()
        name = fs.current_user()[0]
        if name and os.path.isdir(fs.home_dir(name)):
            self.cwd = fs.home_dir(name)
        self.hidden = False
        self.entries = []

    def target(self, text, write=False):
        """Full path for a typed path (relative to the folder being browsed)."""
        text = text.strip()
        if not text.startswith(("/", "~")):
            text = fs.display(self.cwd).rstrip("/") + "/" + text
        return fs.resolve(text, write=write)

    def pick(self, token):
        if token.isdigit() and 1 <= int(token) <= len(self.entries):
            return os.path.join(self.cwd, self.entries[int(token) - 1])
        raise ValueError(f"'{token}' is not a number in the list")

    def refresh(self):
        try:
            names = sorted(os.listdir(self.cwd), key=lambda n: (not os.path.isdir(os.path.join(self.cwd, n)), n.lower()))
        except OSError:
            names = []
        self.entries = [n for n in names if self.hidden or not n.startswith(".")]

    def show(self):
        self.refresh()
        table = Table(title=fs.display(self.cwd, tilde=True), header_style="bold blue", title_justify="left")
        table.add_column("#", justify="right", style="dim")
        table.add_column("Name")
        table.add_column("Size", justify="right")
        table.add_column("Modified", style="dim")
        for i, name in enumerate(self.entries, 1):
            full = os.path.join(self.cwd, name)
            is_dir = os.path.isdir(full)
            try:
                st = os.stat(full)
                when = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
                size = "" if is_dir else size_text(st.st_size)
            except OSError:
                when, size = "", ""
            table.add_row(str(i), f"[bold blue]{escape(name)}/[/bold blue]" if is_dir else escape(name), size, when)
        console.print(table if self.entries else "[dim](empty folder)[/dim]")

    # ------------------------------------------------------------ actions
    def go(self, path):
        if os.path.isdir(path):
            fs.resolve(fs.display(path))                    # permission check (raises PermissionError)
            self.cwd = path
        else:
            console.print("[red]That is not a folder.[/red]")

    def view(self, path):
        try:
            if os.path.getsize(path) > TEXT_LIMIT:
                console.print(f"[yellow]{escape(os.path.basename(path))} is large ({size_text(os.path.getsize(path))}); showing the first part.[/yellow]")
            with open(path, "rb") as f:
                raw = f.read(TEXT_LIMIT)
        except OSError as e:
            console.print(f"[red]{escape(str(e))}[/red]")
            return
        if b"\0" in raw:
            console.print(f"[yellow]{escape(os.path.basename(path))} is a binary file ({size_text(os.path.getsize(path))}).[/yellow]")
            return
        text = raw.decode("utf-8", errors="replace")
        lexer = {".py": "python", ".json": "json", ".md": "markdown", ".sh": "bash", ".html": "html", ".js": "javascript"}.get(
            os.path.splitext(path)[1].lower(), "text")
        console.print(Panel(Syntax(text, lexer, word_wrap=True, line_numbers=lexer != "text"), title=escape(os.path.basename(path)), border_style="blue"))

    def details(self, path):
        st = os.stat(path)
        lines = [f"[bold]Path:[/bold] {escape(fs.display(path))}", f"[bold]Type:[/bold] {'folder' if os.path.isdir(path) else 'file'}"]
        if os.path.isdir(path):
            total, truncated = folder_size(path)
            lines.append(f"[bold]Contents:[/bold] {size_text(total)}{'+' if truncated else ''} in {len(os.listdir(path))} item(s)")
        else:
            lines.append(f"[bold]Size:[/bold] {size_text(st.st_size)}")
        lines.append(f"[bold]Modified:[/bold] {datetime.datetime.fromtimestamp(st.st_mtime):%Y-%m-%d %H:%M:%S}")
        console.print(Panel("\n".join(lines), border_style="blue", expand=False))

    def copy(self, src, dest_text):
        dest = self.target(dest_text, write=True)
        if os.path.isdir(dest):
            dest = os.path.join(dest, os.path.basename(src))
        if os.path.exists(dest):
            console.print("[red]Something with that name is already there.[/red]")
            return
        shutil.copytree(src, dest) if os.path.isdir(src) else shutil.copy2(src, dest)
        console.print(f"[green]Copied to {escape(fs.display(dest))}.[/green]")

    def move(self, src, dest_text):
        fs.resolve(fs.display(src), write=True)
        dest = self.target(dest_text, write=True)
        if os.path.isdir(dest):
            dest = os.path.join(dest, os.path.basename(src))
        if os.path.exists(dest):
            console.print("[red]Something with that name is already there.[/red]")
            return
        shutil.move(src, dest)
        console.print(f"[green]Moved to {escape(fs.display(dest))}.[/green]")

    def rename(self, src, new):
        if not new or "/" in new or "\\" in new or new in (".", ".."):
            console.print("[red]A new name cannot contain slashes.[/red]")
            return
        fs.resolve(fs.display(src), write=True)
        dest = os.path.join(os.path.dirname(src), new)
        if os.path.exists(dest):
            console.print("[red]Something with that name is already there.[/red]")
            return
        os.rename(src, dest)
        console.print(f"[green]Renamed to {escape(new)}.[/green]")

    def delete(self, src):
        fs.resolve(fs.display(src), write=True)
        what = "folder and everything in it" if os.path.isdir(src) else "file"
        if not Confirm.ask(f"Delete the {what} [bold]{escape(os.path.basename(src))}[/bold]?", default=False):
            console.print("[yellow]Cancelled.[/yellow]")
            return
        shutil.rmtree(src) if os.path.isdir(src) else os.remove(src)
        console.print("[green]Deleted.[/green]")

    def make(self, name, folder):
        if not name or "/" in name or "\\" in name:
            console.print("[red]Give a plain name (no slashes).[/red]")
            return
        path = self.target(name, write=True)
        if os.path.exists(path):
            console.print("[red]Something with that name is already there.[/red]")
            return
        os.makedirs(path) if folder else open(path, "w").close()
        console.print(f"[green]Created {escape(name)}.[/green]")

    def find(self, pattern):
        hits = []
        for root, dirs, files in os.walk(self.cwd):
            dirs[:] = [d for d in dirs if self.hidden or not d.startswith(".")]
            for name in dirs + files:
                if fnmatch.fnmatch(name.lower(), pattern.lower()) or (("*" not in pattern) and pattern.lower() in name.lower()):
                    hits.append(os.path.join(root, name))
            if len(hits) > 200:
                break
        if not hits:
            console.print(f"[yellow]Nothing matches '{escape(pattern)}' in this folder or below.[/yellow]")
            return
        for h in hits[:200]:
            console.print(("[blue]" if os.path.isdir(h) else "") + escape(fs.display(h, tilde=True)) + ("/[/blue]" if os.path.isdir(h) else ""))
        console.print(f"[dim]{len(hits)} match(es){' (showing 200)' if len(hits) > 200 else ''}[/dim]")

    def handle(self, line):
        parts = line.split(None, 2)
        if not parts:
            return True
        cmd, args = parts[0], parts[1:]
        if cmd in ("q", "quit", "exit"):
            return False
        if cmd == "h":
            console.print(HELP)
        elif cmd == "u":
            parent = os.path.dirname(self.cwd)
            if os.path.normcase(self.cwd) != os.path.normcase(fs.BASE_DIR):
                self.go(parent)
        elif cmd == "~":
            name = fs.current_user()[0]
            self.go(fs.home_dir(name) if name else fs.BASE_DIR)
        elif cmd == "a":
            self.hidden = not self.hidden
        elif cmd == "g" and args:
            self.go(self.target(" ".join(parts[1:])))
        elif cmd == "f" and args:
            self.find(" ".join(parts[1:]))
        elif cmd == "n" and args:
            self.make(" ".join(parts[1:]), True)
        elif cmd == "t" and args:
            self.make(" ".join(parts[1:]), False)
        elif cmd.isdigit():
            path = self.pick(cmd)
            self.go(path) if os.path.isdir(path) else self.view(path)
        elif cmd in ("i", "d") and args:
            path = self.pick(args[0])
            self.details(path) if cmd == "i" else self.delete(path)
        elif cmd in ("c", "m", "r") and len(args) == 2:
            path = self.pick(args[0])
            {"c": self.copy, "m": self.move, "r": self.rename}[cmd](path, args[1])
        else:
            console.print("[yellow]I did not understand that. Type h for help.[/yellow]")
        return True


def main():
    manager = Manager()
    console.print("[dim]Type h for help.[/dim]")
    while True:
        manager.show()
        try:
            line = Prompt.ask("[cyan]files[/cyan]", default="").strip()
        except EOFError:
            return
        try:
            if not manager.handle(line):
                return
        except PermissionError as e:
            console.print(f"[bold red]{escape(str(e))}[/bold red]")
        except (OSError, ValueError, shutil.Error) as e:
            console.print(f"[red]{escape(str(e))}[/red]")


def execute():
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute()
