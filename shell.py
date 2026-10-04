import os
import sys
import difflib
import shlex
import inspect
import subprocess
import importlib.util
import threading
import time
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markup import escape
import json
import pyos
import pyos.fs as fs
from pyos import jobs, notify, scheduler, settings, stdio, theme
try:
    import readline
except ImportError:
    try:
        import pyreadline3 as readline
    except ImportError:
        from pyos import readline_stub as readline

# Initialize the console for rich output
console = Console()

HISTORY_FILE = os.path.join(".OSData", "history")
BUILTINS = ["exit", "help", "reload", "run"]

available_commands = {}
available_programs = {}

_state = threading.local()   # per-thread: $? of the last command


def last_status():
    return getattr(_state, "status", 0)


def _set_status(code):
    _state.status = code


# ---------------------------------------------------------------- packages
def load_installed_packages(base_path="files"):
    """Load commands from all data.json files under 'files/installed_*' recursively."""
    installed = {}
    if not os.path.isdir(base_path):
        return installed

    # Loop over directories like files/installed_developer, files/installed_games, etc.
    for entry in os.listdir(base_path):
        full_dir_path = os.path.join(base_path, entry)
        if os.path.isdir(full_dir_path) and entry.startswith("installed_"):
            for root, dirs, files in os.walk(full_dir_path):
                if "data.json" in files:
                    data_json_path = os.path.join(root, "data.json")
                    try:
                        with open(data_json_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        command_name = data.get("command")
                        if command_name and not pyos.lockdown.may_run(root):
                            pyos.log.log(f"package {root} not trusted - not loaded (lockdown)", "WARN")
                            continue
                        if command_name:
                            description = data.get("description", "No description available.")
                            run_script = data.get("scripts", {}).get("run")
                            if run_script:
                                run_script_path = os.path.join(root, run_script)
                                installed[command_name] = {
                                    "module": type("DynamicModule", (), {"execute": staticmethod(make_execute_func(run_script_path))}),
                                    "description": description,
                                    "aliases": data.get("alias", [])
                                }
                            else:
                                console.print(f"[bold yellow]Warning:[/bold yellow] 'run' script not found in {data_json_path}, skipping.")
                    except Exception as e:
                        console.print(f"[bold red]Error loading {data_json_path}: {e}[/bold red]")
    return installed


def make_execute_func(script_path):
    """Run a marketplace package's script. Returns False if it failed."""
    def execute(args=None):
        if not os.path.exists(script_path):
            console.print(f"[bold red]Run script not found:[/bold red] {script_path}")
            return False
        # Packages can `import pyos` (settings, notifications, the sandboxed filesystem, ...)
        env = dict(os.environ)
        env["PYTHONPATH"] = os.getcwd() + os.pathsep + env.get("PYTHONPATH", "")
        cmd = [sys.executable, script_path, *(args or [])]
        if sys.stdout.isatty():
            return subprocess.call(cmd, env=env) == 0
        # output is being piped or captured: collect it instead of letting it go to the terminal
        result = subprocess.run(cmd, env=env, capture_output=True, text=True,
                                stdin=subprocess.DEVNULL if stdio.read_stdin() is None else None,
                                input=stdio.read_stdin())
        sys.stdout.write(result.stdout)
        sys.stdout.write(result.stderr)
        return result.returncode == 0
    return execute


# ------------------------------------------------------------------ prompt
def make_prompt(username, role=None):
    """user@host:path$ (# for admins), shortened by the prompt style; coloured via the theme."""
    host = fs.hostname()
    path = fs.display(fs.current_dir(), tilde=True)
    sign = "#" if role == "admin" else "$"
    style = settings.get("prompt_style")
    colour = os.name != "nt" and sys.stdout.isatty()
    if style == "minimal":
        return f"{sign} "
    if style == "short":
        if not colour:
            return f"{path}{sign} "
        return f"\001{theme.ansi('prompt_path')}\002{path}\001\033[0m\002{sign} "
    if not colour:
        return f"{username}@{host}:{path}{sign} "
    # \001 / \002 tell readline the escape codes take up no screen width
    return (f"\001{theme.ansi('prompt_user')}\002{username}@{host}\001\033[0m\002:"
            f"\001{theme.ansi('prompt_path')}\002{path}\001\033[0m\002{sign} ")


def invoke(module, args=None):
    """Call module.execute, passing the argument list only if it accepts one."""
    try:
        takes_args = len(inspect.signature(module.execute).parameters) > 0
    except (TypeError, ValueError):
        takes_args = False
    if takes_args:
        return module.execute(args or [])
    return module.execute()


# ------------------------------------------------------------------ parsing
def split_command(line):
    """Split a command line into tokens (quotes honoured; | > >> ; && || & are separate tokens)."""
    if os.name == "nt":
        line = line.replace("\\", "/")  # allow Windows-style paths
    try:
        lexer = shlex.shlex(line, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError as e:
        console.print(f"[bold red]Parse error:[/bold red] {e}")
        return []


UNSUPPORTED = {"<", "(", ")", "<<", ">&", "|&"}


def parse_line(tokens):
    """Turn tokens into a list of command lists: [{"bg": bool, "items": [{"op", "stages"}, ...]}].

    Lists are separated by ';' or '&'. Inside a list, pipelines are joined by '&&' / '||'; each item's
    op says how it relates to the one before it (None for the first). A list ending in '&' runs
    entirely in the background, as in a real shell. stages is a list of (argv, redirect) with
    redirect = None or ('>' | '>>', filename). Returns None (after printing why) on a syntax error.
    """
    lists, items, stages, argv, redirect = [], [], [], [], None
    pending = None
    i = 0

    def finish_stage():
        nonlocal argv, redirect
        if not argv:
            return False
        stages.append((argv, redirect))
        argv, redirect = [], None
        return True

    def finish_pipeline():
        nonlocal stages
        items.append({"op": pending, "stages": stages})
        stages = []

    while i < len(tokens):
        tok = tokens[i]
        if tok in UNSUPPORTED:
            console.print(f"[bold red]syntax error:[/bold red] '{tok}' is not supported")
            return None
        if tok in (">", ">>"):
            if i + 1 >= len(tokens) or tokens[i + 1] in ("|", ">", ">>", ";", "&&", "||", "&"):
                console.print("[bold red]syntax error:[/bold red] missing file name after redirect")
                return None
            redirect = (tok, tokens[i + 1])
            i += 2
            continue
        if tok == "|":
            if not finish_stage():
                console.print("[bold red]syntax error:[/bold red] nothing before '|'")
                return None
        elif tok in (";", "&&", "||", "&"):
            if not finish_stage():
                if tok == ";" and not stages and not items:
                    i += 1
                    continue
                console.print(f"[bold red]syntax error:[/bold red] nothing before '{tok}'")
                return None
            finish_pipeline()
            if tok in ("&&", "||"):
                pending = tok
            else:
                lists.append({"bg": tok == "&", "items": items})
                items, pending = [], None
        else:
            argv.append(tok)
        i += 1

    if argv:
        finish_stage()
    elif stages:
        console.print("[bold red]syntax error:[/bold red] nothing after '|'")
        return None
    if stages:
        finish_pipeline()
    elif pending in ("&&", "||"):
        console.print(f"[bold red]syntax error:[/bold red] nothing after '{pending}'")
        return None
    if items:
        lists.append({"bg": False, "items": items})
    return lists


class ExitShell(Exception):
    pass


def expand(word):
    return word.replace("$?", str(last_status()))


# ---------------------------------------------------------------- running
def run_stage(argv):
    """Run one command. Returns its status: 0 ok, 1 failed, 127 not found."""
    argv = [expand(a) for a in argv]
    name, args = argv[0], argv[1:]
    user = pyos.userinfo()[0]
    main_thread = threading.current_thread() is threading.main_thread()

    if name == "exit":
        raise ExitShell
    if name == "help":
        show_help(available_commands, available_programs, args[0] if args else None)
        return 0
    if name == "reload":
        reload_all()
        return 0
    if name == "run":
        if not args:
            console.print("[bold red]Usage:[/bold red] run <program>")
            return 1
        matched = find_entry(available_programs, args[0])
        if not matched:
            console.print(f"[bold red]Program '{args[0]}' not found.[/bold red]")
            return 127
        if main_thread:
            readline.parse_and_bind("set editing-mode emacs")
        try:
            return 1 if invoke(available_programs[matched]["module"], args[1:]) is False else 0
        except ExitShell:
            raise
        except Exception as e:
            console.print(f"[bold red]Program '{args[0]}' crashed: {e}[/bold red]")
            pyos.log.log(f"program {args[0]} crashed: {e}", "ERROR", user=user)
            return 1
        finally:
            if main_thread:
                readline.parse_and_bind("set editing-mode vi")

    matched = find_entry(available_commands, name)
    if not matched:
        names = list(available_commands) + BUILTINS
        close = difflib.get_close_matches(name, names, n=1)
        hint = f" Did you mean [bold]{close[0]}[/bold]?" if close else " Type 'help' for a list of commands."
        console.print(f"[bold red]{escape(name)}: command not found.[/bold red]{hint}")
        return 127
    try:
        return 1 if invoke(available_commands[matched]["module"], args) is False else 0
    except ExitShell:
        raise
    except Exception as e:
        console.print(f"[bold red]Command '{name}' failed: {e}[/bold red]")
        pyos.log.log(f"command {name} failed: {e}", "ERROR", user=user)
        return 1


def run_pipeline(stages):
    """Run `a | b > file`: each stage's output is captured and fed to the next. Returns the last status."""
    data = None
    status = 0
    for i, (argv, redirect) in enumerate(stages):
        last = i == len(stages) - 1
        stdio.set_stdin(data)
        try:
            if last and redirect is None:
                return run_stage(argv)
            with stdio.capture() as buf:
                status = run_stage(argv)
            data = buf.getvalue()
        finally:
            stdio.set_stdin(None)
        if last and redirect:
            op, target = redirect
            try:
                path = fs.resolve(target, write=True)
                with open(path, "a" if op == ">>" else "w", encoding="utf-8") as f:
                    f.write(data)
            except Exception as e:
                console.print(f"[bold red]{escape(target)}: {e}[/bold red]")
                return 1
    return status


def describe(items):
    """Readable text for a list of pipelines, used to name background jobs."""
    out = []
    for item in items:
        parts = []
        for argv, redirect in item["stages"]:
            text = " ".join(argv)
            if redirect:
                text += f" {redirect[0]} {redirect[1]}"
            parts.append(text)
        out.append(((item["op"] + " ") if item["op"] else "") + " | ".join(parts))
    return " ".join(out)


def run_items(items):
    """Run pipelines joined by && / ||. Returns the status of the last one that ran."""
    for item in items:
        if item["op"] == "&&" and last_status() != 0:
            continue
        if item["op"] == "||" and last_status() == 0:
            continue
        _set_status(run_pipeline(item["stages"]))
    return last_status()


def run_line(line):
    """Run a command line (pipes, redirects, ;, &&, ||, &). Returns the status of the last command run."""
    tokens = split_command(line)
    if not tokens:
        return getattr(_state, "status", 0)
    lists = parse_line(tokens)
    if lists is None:
        _set_status(2)
        return 2
    for entry in lists:
        if entry["bg"]:
            items = entry["items"]
            job = jobs.start(describe(items), lambda it=items: run_items(it), user=pyos.userinfo()[0])
            console.print(f"[dim][{job.id}] started in the background - `jobs` lists it, `fg {job.id}` shows its output[/dim]")
            _set_status(0)
        else:
            run_items(entry["items"])
    return last_status()


def run_captured(line):
    """Run a command line with its output captured (scheduler, tests). Returns (status, output)."""
    with stdio.capture() as buf:
        status = run_line(line)
    return status, buf.getvalue()


def find_entry(table, name):
    return next((k for k, info in table.items() if name == k or name in info["aliases"]), None)


# -------------------------------------------------------------- completion
def complete(line):
    """Completions for the last word of `line` (used by Tab, and by the Android keyboard row)."""
    parts = line.lstrip().split(" ")
    word = parts[-1]
    try:
        if len(parts) <= 1:
            options = BUILTINS + list(available_commands) + [a for c in available_commands.values() for a in c["aliases"]]
        elif parts[0] == "run" and len(parts) == 2:
            options = list(available_programs) + [a for p in available_programs.values() for a in p["aliases"]]
        elif parts[0] in ("help", "man") and len(parts) == 2:
            options = list(available_commands) + list(available_programs)
        elif parts[0] in ("settings", "set") and len(parts) == 2:
            options = ["list", "get", "set", "reset", "theme", "themes"]
        elif parts[0] == "settings" and len(parts) == 3 and parts[1] in ("get", "set", "reset"):
            options = list(settings.SCHEMA)
        else:
            directory, _, prefix = word.rpartition("/")
            base = fs.resolve(directory + "/" if directory else ".")
            options = [(directory + "/" if directory else "") + n + ("/" if os.path.isdir(os.path.join(base, n)) else "")
                       for n in os.listdir(base)]
        return sorted(set(o for o in options if o.startswith(word)))
    except Exception:
        return []


def setup_readline():
    """History + tab completion for commands, programs and paths."""
    try:
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        readline.read_history_file(HISTORY_FILE)
    except Exception:
        pass

    cache = {"line": None, "matches": []}

    def completer(text, state):
        try:
            line = readline.get_line_buffer()
            if cache["line"] != (line, text):
                cache["line"], cache["matches"] = (line, text), complete(line)
            matches = cache["matches"]
            return matches[state] if state < len(matches) else None
        except Exception:
            return None

    try:
        readline.set_completer(completer)
        readline.set_completer_delims(" \t\n")
    except Exception:
        pass


# ------------------------------------------------------------------ loading
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


# ----------------------------------------------------------- lock & session
def lock_session(username):
    """Ask for the password again. Returns True if the right one was entered (3 tries)."""
    import getpass
    import users
    console.print("[bold yellow]Session locked.[/bold yellow]")
    for attempt in range(3):
        try:
            password = getpass.getpass(f"Password for {username}: ")
        except (KeyboardInterrupt, EOFError):
            return False
        record = users.get_users().get(username)
        if record and users.verify_password(password, record["password"]):
            console.print("[green]Unlocked.[/green]")
            return True
        console.print("[red]Incorrect password.[/red]")
    return False


def show_notifications(username):
    for n in notify.take_pending(username):
        level = {"warn": "warning", "error": "error", "success": "success"}.get(n["level"], "accent")
        style = theme.style(level)
        message = escape(str(n["message"]))
        console.print(f"[{style}]* {escape(n['title'])}:[/{style}] {message}")


def start_shell(username):
    global available_commands, available_programs

    available_commands = load_all_modules("commands")
    available_programs = load_all_modules("programs")
    installed_programs = load_installed_packages("files")
    available_programs.update(installed_programs)

    stdio.install()

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

    sched = scheduler.Scheduler(run_captured, username)
    sched.start()
    try:
        from core import sysupdate
        sysupdate.check_in_background(username)
    except Exception:
        pass

    last_activity = time.time()
    while True:
        role = pyos.userinfo()[1]
        show_notifications(username)
        try:
            line = input(make_prompt(username, role)).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold yellow]Exiting shell...[/bold yellow]")
            break

        limit = settings.get("auto_lock_minutes")
        if limit and time.time() - last_activity > limit * 60:
            if not lock_session(username):
                console.print("[bold red]Logging out.[/bold red]")
                break
        last_activity = time.time()

        if not line:
            continue

        try:
            run_line(line)
        except ExitShell:
            console.print("[bold green]Logging out...[/bold green]")
            break
        except KeyboardInterrupt:
            console.print("\n[bold yellow]^C[/bold yellow]")
        last_activity = time.time()

    sched.stop()
    pyos.log.log("logout", user=username)
    try:
        readline.write_history_file(HISTORY_FILE)
    except Exception:
        pass


# --------------------------------------------------------------------- help
def _help_table(title, data):
    table = Table(title=theme.tag("title", title), title_justify="left", header_style="bold",
                  border_style=theme.style("border"), expand=True)
    table.add_column("Name", style="bold " + (theme.style("success") or "green"), no_wrap=True)
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
                    f"{escape(info['description'])}\n\n[bold]Usage:[/bold] {escape(usage)}\n[bold]Aliases:[/bold] {aliases}"
                    f"\n[dim]More: man {escape(key)}[/dim]",
                    title=f"{theme.tag('title', key)} [dim]({kind})[/dim]", border_style=theme.style("border"), expand=False))
                return
        console.print(f"[bold red]No help entry for '{topic}'.[/bold red]")
        return

    console.print(_help_table("Commands", available_commands))
    if available_programs:
        console.print(_help_table("Programs  (start with: run <name>)", available_programs))
    console.print("[dim]Built in: help " + escape("[name]") + ", run <program>, reload, exit  |  Tab completes names and paths"
                  "  |  man <name> for the manual  |  tutorial for a guided tour[/dim]")
