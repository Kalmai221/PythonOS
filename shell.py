import os
import io
import contextlib
import sys
import difflib
import shlex
import inspect
import subprocess
import importlib.util
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markup import escape
from rich.prompt import Prompt
import json
import pyos
import pyos.fs as fs
try:
    import readline
except ImportError:
    try:
        import pyreadline3 as readline
    except ImportError:
        from pyos import readline_stub as readline

# Initialize the console for rich output
console = Console()

# Metadata dictionary for commands
commands_config = {}

HISTORY_FILE = os.path.join(".OSData", "history")

def load_installed_packages(base_path="files"):
    """Load commands from all data.json files under 'files/installed_*' recursively."""
    installed = {}

    # Loop over directories like files/installed_developer, files/installed_games, etc.
    for entry in os.listdir(base_path):
        full_dir_path = os.path.join(base_path, entry)
        if os.path.isdir(full_dir_path) and entry.startswith("installed_"):
            for root, dirs, files in os.walk(full_dir_path):
                if "data.json" in files:
                    data_json_path = os.path.join(root, "data.json")
                    try:
                        with open(data_json_path, "r") as f:
                            data = json.load(f)
                        command_name = data.get("command")
                        if command_name:
                            description = data.get("description", "No description available.")
                            run_script = data.get("scripts", {}).get("run")
                            if run_script:
                                run_script_path = os.path.join(root, run_script)

                                def make_execute_func(script_path):
                                    def execute():
                                        if os.path.exists(script_path):
                                            subprocess.call([sys.executable, script_path])
                                        else:
                                            console.print(f"[bold red]Run script not found:[/bold red] {script_path}")
                                    return execute

                                installed[command_name] = {
                                    "module": type("DynamicModule", (), {"execute": make_execute_func(run_script_path)}),
                                    "description": description,
                                    "aliases": data.get("alias", [])
                                }
                            else:
                                console.print(f"[bold yellow]Warning:[/bold yellow] 'run' script not found in {data_json_path}, skipping.")
                    except Exception as e:
                        console.print(f"[bold red]Error loading {data_json_path}: {e}[/bold red]")
    return installed


def make_prompt(username, role=None):
    """user@host:path$ (# for admins); coloured where readline handles ANSI escapes."""
    host = fs.hostname()
    path = fs.display(fs.current_dir(), tilde=True)
    sign = "#" if role == "admin" else "$"
    if os.name == "nt" or not sys.stdout.isatty():
        return f"{username}@{host}:{path}{sign} "
    # \001 / \002 tell readline the escape codes take up no screen width
    return (f"\001\033[1;32m\002{username}@{host}\001\033[0m\002:"
            f"\001\033[1;34m\002{path}\001\033[0m\002{sign} ")


def invoke(module, args=None):
    """Call module.execute, passing the argument list only if it accepts one."""
    try:
        takes_args = len(inspect.signature(module.execute).parameters) > 0
    except (TypeError, ValueError):
        takes_args = False
    if takes_args:
        return module.execute(args or [])
    return module.execute()


def split_command(line):
    """Split a command line into tokens (quotes honoured; | > >> ; are separate tokens)."""
    if os.name == "nt":
        line = line.replace("\\", "/")  # allow Windows-style paths
    try:
        lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError as e:
        console.print(f"[bold red]Parse error:[/bold red] {e}")
        return []


OPERATORS = {"|", ">", ">>", ";"}
UNSUPPORTED = {"&&", "||", "&", "<", "(", ")", "<<", ">&"}


def parse_line(tokens):
    """Turn tokens into a list of pipelines; each stage is (argv, redirect) with
    redirect = None or (">" | ">>", filename). Returns None on a syntax error."""
    pipelines, stages, argv, redirect = [], [], [], None
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in UNSUPPORTED:
            console.print(f"[bold red]syntax error:[/bold red] '{tok}' is not supported (use ';' to run commands in order)")
            return None
        if tok in (">", ">>"):
            if i + 1 >= len(tokens) or tokens[i + 1] in OPERATORS:
                console.print("[bold red]syntax error:[/bold red] missing file name after redirect")
                return None
            redirect = (tok, tokens[i + 1])
            i += 2
            continue
        if tok in ("|", ";"):
            if not argv:
                if tok == ";" and not stages:
                    i += 1
                    continue
                console.print(f"[bold red]syntax error:[/bold red] nothing before '{tok}'")
                return None
            stages.append((argv, redirect))
            argv, redirect = [], None
            if tok == ";":
                pipelines.append(stages)
                stages = []
            i += 1
            continue
        argv.append(tok)
        i += 1
    if argv:
        stages.append((argv, redirect))
    elif stages:
        console.print("[bold red]syntax error:[/bold red] nothing after '|'")
        return None
    if stages:
        pipelines.append(stages)
    return pipelines


class ExitShell(Exception):
    pass


def run_stage(argv):
    """Run one command. Returns False if it reported failure."""
    name, args = argv[0], argv[1:]
    user = pyos.userinfo()[0]

    if name == "exit":
        raise ExitShell
    if name == "help":
        show_help(available_commands, available_programs, args[0] if args else None)
        return True
    if name == "reload":
        reload_all()
        return True
    if name == "run":
        if not args:
            console.print("[bold red]Usage:[/bold red] run <program>")
            return False
        matched = find_entry(available_programs, args[0])
        if not matched:
            console.print(f"[bold red]Program '{args[0]}' not found.[/bold red]")
            return False
        readline.parse_and_bind("set editing-mode emacs")
        try:
            return invoke(available_programs[matched]["module"], args[1:]) is not False
        except Exception as e:
            console.print(f"[bold red]Program '{args[0]}' crashed: {e}[/bold red]")
            pyos.log.log(f"program {args[0]} crashed: {e}", "ERROR", user=user)
            return False
        finally:
            readline.parse_and_bind("set editing-mode vi")

    matched = find_entry(available_commands, name)
    if not matched:
        names = list(available_commands) + ["help", "run", "reload", "exit"]
        close = difflib.get_close_matches(name, names, n=1)
        hint = f" Did you mean [bold]{close[0]}[/bold]?" if close else " Type 'help' for a list of commands."
        console.print(f"[bold red]{escape(name)}: command not found.[/bold red]{hint}")
        return False
    try:
        return invoke(available_commands[matched]["module"], args) is not False
    except ExitShell:
        raise
    except Exception as e:
        console.print(f"[bold red]Command '{name}' failed: {e}[/bold red]")
        pyos.log.log(f"command {name} failed: {e}", "ERROR", user=user)
        return False


def run_pipeline(stages):
    """Run `a | b > file`: each stage's output is captured and fed to the next."""
    data = None
    for i, (argv, redirect) in enumerate(stages):
        last = i == len(stages) - 1
        pyos.stdio.stdin = data
        try:
            if last and redirect is None:
                run_stage(argv)
                return
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                run_stage(argv)
            data = buf.getvalue()
        finally:
            pyos.stdio.stdin = None
        if last and redirect:
            op, target = redirect
            try:
                path = fs.resolve(target, write=True)
                with open(path, "a" if op == ">>" else "w", encoding="utf-8") as f:
                    f.write(data)
            except Exception as e:
                console.print(f"[bold red]{escape(target)}: {e}[/bold red]")


def run_line(line):
    tokens = split_command(line)
    if not tokens:
        return
    pipelines = parse_line(tokens)
    for stages in pipelines or []:
        run_pipeline(stages)


def find_entry(table, name):
    return next((k for k, info in table.items() if name == k or name in info["aliases"]), None)


def setup_readline():
    """History + tab completion for commands, programs and paths."""
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        readline.read_history_file(HISTORY_FILE)
    except Exception:
        pass

    def completer(text, state):
        try:
            line = readline.get_line_buffer()
            parts = line.lstrip().split(" ")
            if len(parts) <= 1:
                options = ["exit", "help", "reload", "run"] + list(available_commands)
            elif parts[0] == "run" and len(parts) == 2:
                options = list(available_programs)
            else:
                directory, _, prefix = text.rpartition("/")
                base = fs.resolve(directory + "/" if directory else ".")
                options = [(directory + "/" if directory else "") + n + ("/" if os.path.isdir(os.path.join(base, n)) else "")
                           for n in os.listdir(base)]
                text = directory + "/" + prefix if directory else prefix
            matches = sorted(o for o in options if o.startswith(text))
            return matches[state] if state < len(matches) else None
        except Exception:
            return None

    try:
        readline.set_completer(completer)
        readline.set_completer_delims(" \t\n")
    except Exception:
        pass


def load_module(file_path, module_name):
    """Dynamically loads a Python module from a given file path."""
    try:
        if os.path.exists(file_path):
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        else:
            console.print(f"[bold red]Error:[/bold red] File '{file_path}' not found.")
            return None
    except Exception as e:
        console.print(f"[bold red]Error loading '{module_name}': {e}[/bold red]")
        return None

def list_available(directory):
    """Returns a list of Python files (without extensions) in a given directory."""
    if os.path.exists(directory):
        return [f[:-3] for f in os.listdir(directory) if f.endswith(".py")]
    return []

def load_all_modules(directory):
    """Loads all Python modules from a specified directory."""
    available = {}
    for file_name in list_available(directory):
        module = load_module(os.path.join(directory, file_name + ".py"), file_name)
        if module and hasattr(module, "config"):
            available[file_name] = {
                "module": module,
                "description": module.config.get("description", "No description available."),
                "aliases": module.config.get("alias", [])
            }
    return available

def reload_all():
    global available_commands, available_programs

    console.print("[bold yellow]Reloading commands and programs...[/bold yellow]")

    # Reload commands and programs from disk (fresh imports)
    available_commands = load_all_modules("commands")

    installed_programs = load_installed_packages("files")
    available_programs = load_all_modules("programs")
    available_programs.update(installed_programs)

    console.print("[bold green]Reload complete![/bold green]")


def start_shell(username):
    global available_commands, available_programs

    available_commands = load_all_modules("commands")
    available_programs = load_all_modules("programs")
    installed_programs = load_installed_packages("files")
    available_programs.update(installed_programs)

    # Every login starts in the user's home directory
    fs.ensure_layout()
    fs.save_current_dir(fs.ensure_home(username))

    readline.parse_and_bind("tab: complete")
    readline.parse_and_bind("set editing-mode vi")
    setup_readline()

    try:
        with open(os.path.join(fs.BASE_DIR, "etc", "motd")) as f:
            motd = f.read().strip()
        if motd:
            console.print(f"[dim]{escape(motd)}[/dim]")
    except OSError:
        pass

    while True:
        role = pyos.userinfo()[1]
        try:
            line = input(make_prompt(username, role)).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold yellow]Exiting shell...[/bold yellow]")
            break

        if not line:
            continue

        try:
            run_line(line)
        except ExitShell:
            console.print("[bold green]Logging out...[/bold green]")
            break
        except KeyboardInterrupt:
            console.print("\n[bold yellow]^C[/bold yellow]")

    pyos.log.log("logout", user=username)
    try:
        readline.write_history_file(HISTORY_FILE)
    except Exception:
        pass


def _help_table(title, data):
    table = Table(title=f"[bold cyan]{title}[/bold cyan]", title_justify="left", header_style="bold",
                  border_style="blue", expand=True)
    table.add_column("Name", style="bold green", no_wrap=True)
    table.add_column("Description", style="white")
    table.add_column("Aliases", style="dim", no_wrap=True)
    for name in sorted(data):
        info = data[name]
        table.add_row(escape(name), escape(info["description"]), escape(", ".join(info["aliases"])) if info["aliases"] else "")
    return table


def show_help(available_commands, available_programs, topic=None):
    """Print all commands and programs, or details for one (help <name>)."""
    if topic:
        for kind, data in (("command", available_commands), ("program", available_programs)):
            key = find_entry(data, topic)
            if key:
                info = data[key]
                usage = f"run {key}" if kind == "program" else key
                aliases = ", ".join(info["aliases"]) or "none"
                console.print(Panel(
                    f"{escape(info['description'])}\n\n[bold]Usage:[/bold] {escape(usage)}\n[bold]Aliases:[/bold] {aliases}",
                    title=f"[bold cyan]{key}[/bold cyan] [dim]({kind})[/dim]", border_style="blue", expand=False))
                return
        console.print(f"[bold red]No help entry for '{topic}'.[/bold red]")
        return

    console.print(_help_table("Commands", available_commands))
    if available_programs:
        console.print(_help_table("Programs  (start with: run <name>)", available_programs))
    console.print("[dim]Built in: help " + escape("[name]") + ", run <program>, reload, exit  |  Tab completes names and paths[/dim]")
