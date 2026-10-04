#!/usr/bin/env python3
"""Python: run a .py file from your PythonOS folders, or open an interactive Python prompt. Nothing to install:
it uses the Python PythonOS itself runs on. (This is code execution, so locked-down systems do not allow it.)"""
import code
import os
import runpy
import subprocess
import sys

from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt

try:
    from pyos import fs
except ImportError:
    fs = None

console = Console()


def workdir():
    """The shell's current folder (a real path on this device), or the PythonOS root."""
    if fs:
        return fs.current_dir()
    try:
        with open("current_directory.txt") as f:
            path = f.read().strip()
        if os.path.isdir(path):
            return path
    except OSError:
        pass
    return os.getcwd()


def separate_python():
    """True when we can start a separate Python process (not on every device, for example Android)."""
    return bool(sys.executable) and os.path.exists(sys.executable) and not os.environ.get("PYOS_NO_SUBPROCESS")


def resolve_file(name):
    path = fs.resolve(name) if fs else os.path.abspath(os.path.join(workdir(), name))
    if os.path.isdir(path) or not os.path.isfile(path):
        raise FileNotFoundError(name)
    return path


def run_file(name, args=()):
    try:
        path = resolve_file(name)
    except (FileNotFoundError, PermissionError) as e:
        console.print(f"[bold red]Cannot run '{escape(name)}': {escape(str(e) or 'no such file')}[/bold red]")
        listing = sorted(f for f in os.listdir(workdir()) if f.endswith(".py"))
        if listing:
            console.print("[yellow]Python files here:[/yellow] " + ", ".join(listing))
        return False
    console.print(f"[bold green]Running {escape(os.path.basename(path))}[/bold green]\n")
    try:
        if separate_python():
            return subprocess.call([sys.executable, path, *args], cwd=os.path.dirname(path)) == 0
        old = (os.getcwd(), sys.argv)
        os.chdir(os.path.dirname(path))
        sys.argv = [path, *args]
        try:
            runpy.run_path(path, run_name="__main__")
            return True
        finally:
            os.chdir(old[0])
            sys.argv = old[1]
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Interrupted.[/bold yellow]")
    except SystemExit as e:
        return not e.code
    except Exception as e:  # the program's own error: show it, do not crash PythonOS
        console.print(f"[bold red]{type(e).__name__}: {escape(str(e))}[/bold red]")
    return False


def repl():
    console.print("[bold green]Python[/bold green] " + sys.version.split()[0] + "  [dim](exit() or Ctrl+D to leave)[/dim]")
    if separate_python():
        try:
            subprocess.call([sys.executable, "-q"], cwd=workdir())
            return
        except KeyboardInterrupt:
            return
    old = os.getcwd()
    os.chdir(workdir())
    try:
        code.interact(banner="", local={"__name__": "__console__"}, exitmsg="")
    except (SystemExit, KeyboardInterrupt, EOFError):
        pass
    finally:
        os.chdir(old)


def main():
    console.print("[bold green]Python[/bold green]\n  1. Run a Python file\n  2. Interactive Python prompt")
    choice = Prompt.ask("Choose", choices=["1", "2"], default="2")
    if choice == "1":
        run_file(Prompt.ask("File name (for example test.py)").strip())
    else:
        repl()


def execute(args=None):
    args = list(args or [])
    try:
        if not args:
            main()
        elif args[0] in ("-i", "repl"):
            repl()
        elif args[0] == "-c" and len(args) > 1:
            exec(compile(" ".join(args[1:]), "<python -c>", "exec"), {"__name__": "__main__"})
        else:
            run_file(args[0], args[1:])
    except (KeyboardInterrupt, EOFError):
        console.print()
    except Exception as e:
        console.print(f"[bold red]{type(e).__name__}: {escape(str(e))}[/bold red]")


if __name__ == "__main__":
    execute(sys.argv[1:])
