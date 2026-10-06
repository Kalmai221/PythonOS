import os
import json
import time
import subprocess
import sys
from rich.console import Console
from rich.markup import escape
import importlib.util
from yaspin import yaspin
from rich.panel import Panel
from rich.align import Align
from rich.console import Group
from rich.text import Text
from rich.table import Table
import datetime
import platform
import psutil
import socket
import importlib.metadata
from pyos import settings
from pyos.i18n import tr

# Initialize the console for rich output
console = Console()

CONFIG_FILE = "config.json"
from pyos.paths import USER_DB
PROGRAMS_DIR = "programs"
COMMANDS_DIR = "commands"
SYSTEM_FILES = [CONFIG_FILE, USER_DB]
REQUIREMENTS_FILE = "requirements.txt"
        
PACKAGE_JSON_FILE = "package.json"

def check_internet_connection(host="8.8.8.8", port=53, timeout=3):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
        return True
    except socket.error:
        return False


def install_requirements(debug, spinner):
    """Install packages from requirements.txt"""
    if os.path.exists(REQUIREMENTS_FILE):
        spinner.text = f"Installing required packages from {REQUIREMENTS_FILE}..."
        if platform.system() == "Windows":
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_FILE, "-U", "--quiet"] if not debug else 
                [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_FILE, "-U"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_FILE, "-U", "--quiet", "--break-system-packages"] if not debug else 
            [sys.executable, "-m", "pip", "install", "-r", REQUIREMENTS_FILE, "-U", "--break-system-packages"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if debug == "Yes":
            spinner.text = "All required packages have been installed."
    else:
        spinner.text = f"No {REQUIREMENTS_FILE} found. Skipping package installation." if debug == "Yes" else "Skipping package installation."

def get_packages_from_requirements(requirements_file="requirements.txt"):
    if not os.path.exists(requirements_file):
        return []
    with open(requirements_file, "r") as f:
        lines = f.readlines()
    packages = []
    for line in lines:
        line = line.strip()
        if line and not line.startswith("#"):
            # Extract package name only (ignoring versions)
            pkg_name = line.split("==")[0].split(">=")[0].split("<=")[0].strip()
            packages.append(pkg_name)
    return packages

def check_packages_installed(packages):
    missing = []
    for pkg in packages:
        try:
            importlib.metadata.version(pkg)
        except importlib.metadata.PackageNotFoundError:
            missing.append(pkg)
    return missing

def check_system_integrity(debug, spinner):
    spinner.text = "Checking system integrity..."
    missing_files = [file for file in SYSTEM_FILES if not os.path.exists(file)]

    if missing_files:
        spinner.text = f"Warning: Missing system files: {', '.join(missing_files)}"
        for file in missing_files:
            if file == CONFIG_FILE:
                with open(CONFIG_FILE, "w") as f:
                    json.dump({"os_name": "pyOS", "version": "1.0"}, f, indent=4)
            elif file == USER_DB:
                with open(USER_DB, "w") as f:
                    json.dump({}, f, indent=4)
        spinner.text = "Missing files have been recreated."
    else:
        if debug == "Yes":
            spinner.text = "All system files are intact."

def load_programs(debug, spinner):
    if os.path.exists(PROGRAMS_DIR):
        program_files = [f for f in os.listdir(PROGRAMS_DIR) if f.endswith(".py")]
        if program_files:
            for program in program_files:
                program_name = program[:-3]  # Remove the ".py" extension
                try:
                    program_module = __import__(f"programs.{program_name}", fromlist=[program_name])
                    if hasattr(program_module, "config"):
                        pass  # Removed the display of loaded programs
                    else:
                        spinner.text = f"Warning:[/bold red] {program_name} does not have a config attribute."
                except Exception as e:
                    spinner.text = f"Error loading program {program_name}: {e}"
        else:
            spinner.text = f"No programs available in {PROGRAMS_DIR}."
    else:
        os.makedirs(PROGRAMS_DIR)
        spinner.text = f"No programs found. Created programs directory at {PROGRAMS_DIR}."

def load_commands(debug, spinner):
    if os.path.exists(COMMANDS_DIR):
        command_files = [f for f in os.listdir(COMMANDS_DIR) if f.endswith(".py")]
        if command_files:
            for command in command_files:
                command_name = command[:-3]  # Remove the ".py" extension
                try:
                    command_module = __import__(f"commands.{command_name}", fromlist=[command_name])
                    if hasattr(command_module, "config"):
                        pass  # Removed the display of loaded commands
                    else:
                        if debug == "Yes":
                            spinner.text = f"Warning: {command_name} does not have a config attribute."
                except Exception as e:                    
                    spinner.text = f"Error loading command {command_name}: {e}"
        else:
            spinner.text = f"No commands available in {COMMANDS_DIR}."
    else:
        os.makedirs(COMMANDS_DIR)
        if debug == "Yes":
            spinner.text = f"No commands found. Created commands directory at {COMMANDS_DIR}."

PYOS_FOLDER = "pyos"

def check_pyos_files(debug, spinner):
    """Check all Python files in the pyos folder for errors, ignoring __init__.py."""
    if os.path.exists(PYOS_FOLDER):
        if debug == "Yes":
            spinner.text = f"Found the '{PYOS_FOLDER}' folder."
        py_files = [f for f in os.listdir(PYOS_FOLDER) if f.endswith(".py") and f != "__init__.py"]

        if not py_files:
            if debug == "Yes":
                spinner.text = f"No Python files found in '{PYOS_FOLDER}'"
            return

        error_files = []

        # Iterate over all .py files and try to import them
        for file_name in py_files:
            file_path = os.path.join(PYOS_FOLDER, file_name)
            try:
                spec = importlib.util.spec_from_file_location(file_name, file_path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)  # Try to execute the module
            except Exception as e:
                error_files.append(file_name)
                if debug == "Yes":
                    spinner.text = f"Error loading {file_name}: {e}"

        if error_files:
            if debug == "Yes":
                spinner.text = f"There were errors in the following files: {', '.join(error_files)}"
        else:
            if debug == "Yes":
                spinner.text = f"All Python files in '{PYOS_FOLDER}' loaded successfully."
    else:
        if debug == "Yes":
            spinner.text = f"Error: '{PYOS_FOLDER}' folder not found!"

def set_current_directory_to_files(debug, spinner):
    """Sets the current directory to the 'files' folder and writes it to current_directory.txt."""
    current_directory = os.getcwd()  # Get the current working directory
    files_directory = os.path.join(current_directory, "files")  # Define the 'files' folder within the current directory

    if not os.path.exists(files_directory):
        os.makedirs(files_directory)  # Create the 'files' folder if it doesn't exist

    # Write the path of the 'files' directory to the current_directory.txt file
    with open("current_directory.txt", "w") as f:
        f.write(files_directory)

    # Standard directory tree (/home, /etc, /tmp, /var/log), boot time and log entry
    import pyos
    pyos.fs.ensure_layout()
    os.makedirs(".OSData", exist_ok=True)
    with open(os.path.join(".OSData", "boot_time"), "w") as f:
        f.write(str(time.time()))
    pyos.log.log("System booted")
        
    if debug == "Yes":
        spinner.text = f"Current directory set to: {files_directory}"

def get_system_info():
    """Fetch system information like time and uptime."""
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        with open(os.path.join(".OSData", "boot_time")) as f:
            uptime_seconds = time.time() - float(f.read().strip())
    except (OSError, ValueError):
        uptime_seconds = 0

    uptime_str = time.strftime("%H:%M:%S", time.gmtime(uptime_seconds))

    return f"[bold magenta]Current Time:[/bold magenta] [cyan]{current_time}[/cyan]\n" \
           f"[bold magenta]System Uptime:[/bold magenta] [cyan]{uptime_str}[/cyan]"

def get_system_version():
    """Reads the system version from config.json"""
    try:
        with open(CONFIG_FILE, "r") as file:
            config = json.load(file)
        return config.get("version", "1.0")  # Default to "1.0" if missing
    except (FileNotFoundError, json.JSONDecodeError):
        return "1.0"  # Default version if config is missing/corrupt

def display_home_screen():
    """Displays the home screen after boot."""
    system_version = get_system_version()
    now = datetime.datetime.now()
    try:
        with open(os.path.join(".OSData", "boot_time")) as f:               # since PythonOS started, not since the computer did
            uptime = time.strftime("%H:%M:%S", time.gmtime(time.time() - float(f.read().strip())))
    except (OSError, ValueError):
        uptime = "00:00:00"

    info = Table.grid(padding=(0, 2))
    info.add_column(style="bold magenta", justify="right")
    info.add_column(style="cyan")
    info.add_row("Date", now.strftime("%A, %d %B %Y"))
    info.add_row("Time", now.strftime("%H:%M:%S"))
    info.add_row("Uptime", uptime)
    info.add_row("Platform", f"{platform.system()} {platform.release()}")

    body = Group(
        Align.center(Text(BANNER, style="bold cyan")),
        Align.center(Text(f"v{system_version}", style="dim")),
        Text(""),
        Align.center(info),
        Text(""),
        Align.center(Text(tr("Type 'help' once logged in to see what you can do."), style="dim italic")),
    )
    console.print(Panel(body, title="[bold green]Welcome[/bold green]", border_style="blue", padding=(1, 4)))


BANNER = r"""
 ____        ___  ____
|  _ \ _   _/ _ \/ ___|
| |_) | | | | | | \___ \
|  __/| |_| | |_| |___) |
|_|    \__, |\___/|____/
       |___/
""".strip("\n")


class _Sink:
    """Stands in for the old spinner: the boot helpers set .text, which is now only used for debug detail."""
    text = ""

    def write(self, text):
        console.print(text)


def _progress_bar(done, total, width=14):
    filled = int(width * done / total)
    return "[cyan]" + "#" * filled + "[/cyan][dim]" + "-" * (width - filled) + "[/dim]"


def _step_internet(debug, sink):
    """Dependencies: bundled builds ship them; otherwise check the connection and install what is missing."""
    packages = get_packages_from_requirements("requirements.txt")
    if os.environ.get("PYOS_BUNDLED") == "1":
        return "ok", "dependencies ship with this build"
    missing = check_packages_installed(packages) if packages else []
    if not missing:
        return "ok", tr("{n} packages present", n=len(packages))           # nothing to install: no network needed, no upgrade on every boot
    if check_internet_connection():
        try:
            install_requirements(debug, sink)
            return "ok", "installed " + ", ".join(missing)
        except Exception as e:
            return "warn", "could not update packages: " + (str(e).splitlines()[0] if str(e) else "")
    if missing:
        return "fail", "offline and missing: " + ", ".join(missing)
    return "warn", "offline - all required packages are installed"


def boot_steps(debug):
    """The real boot steps: (label, function(debug, sink) -> (status, detail))."""
    def config_step(debug, sink):
        os_name = get_system_version()
        return "ok", f"PythonOS {os_name}"

    def integrity_step(debug, sink):
        check_system_integrity(debug, sink)
        return "ok", ""

    def services_step(debug, sink):
        check_pyos_files(debug, sink)
        return "ok", ""

    def commands_step(debug, sink):
        load_commands(debug, sink)
        n = len([f for f in os.listdir(COMMANDS_DIR) if f.endswith(".py")]) if os.path.isdir(COMMANDS_DIR) else 0
        return "ok", tr("{n} commands", n=n)

    def programs_step(debug, sink):
        load_programs(debug, sink)
        n = len([f for f in os.listdir(PROGRAMS_DIR) if f.endswith(".py")]) if os.path.isdir(PROGRAMS_DIR) else 0
        return "ok", tr("{n} programs", n=n)

    def files_step(debug, sink):
        set_current_directory_to_files(debug, sink)
        return "ok", ""

    def memory_step(debug, sink):
        from core import liveboot
        state, text = liveboot.memory_state()
        if state in ("low", "very-low"):
            os.environ["PYOS_LIGHT"] = "1"               # the shell skips optional background work
            return "warn", text
        return "ok", text

    def session_step(debug, sink):
        from pyos import session
        import pyos
        before = session.begin()
        state = before.get("state")
        if state == "unexpected":
            pyos.log.log("Unexpected shutdown detected: the previous session did not end properly", "WARN")
            return "warn", tr("last session ended unexpectedly (type whathappened)")
        if state == "crashed":
            return "warn", f"last session stopped with {before.get('code') or 'an error'} (type whathappened)"
        return "ok", tr("last shutdown was clean") if state == "clean" else tr("first start")

    def hardware_step(debug, sink):
        from pyos import resources
        return "ok", f"{psutil.cpu_count() or 1} CPU(s), {platform.machine() or 'unknown'}, memory {resources.describe()}"

    def kernel_step(debug, sink):
        from pyos import tasks
        tasks.listing()                                  # the task table starts here: init (1) and the kernel (2)
        return "ok", "init (1), kernel (2)"

    def filesystem_step(debug, sink):
        import shutil
        import pyos
        pyos.fs.ensure_layout()
        base = pyos.fs.BASE_DIR
        missing = [d for d in ("home", "etc", "tmp", "var/log") if not os.path.isdir(os.path.join(base, d))]
        try:
            free = shutil.disk_usage(base).free
        except OSError:
            free = None
        if missing:
            return "warn", "missing " + ", ".join(missing)
        if free is not None and free < 100 * 1024 ** 2:
            return "warn", f"only {free // 1024 ** 2} MB free"
        return "ok", f"{free / 1024 ** 3:.1f} GB free" if free is not None else ""

    return [("Reading the configuration", config_step), ("Checking system files", integrity_step),
            ("Detecting hardware", hardware_step), ("Starting kernel services", kernel_step),
            ("Starting system services", services_step), ("Checking memory", memory_step), ("Checking dependencies", _step_internet),
            ("Loading commands", commands_step), ("Loading programs", programs_step),
            ("Preparing the file system", files_step), ("Checking the file system", filesystem_step),
            ("Checking the last shutdown", session_step)]


MARKS = {"ok": "[bold green][  OK  ][/bold green]", "warn": "[bold yellow][ WARN ][/bold yellow]",
         "fail": "[bold red][FAILED][/bold red]"}


# how each real step reads in the detailed boot log: (what happened, what it happened to)
UNITS = {
    "Reading the configuration": ("Loaded", "system configuration"),
    "Checking system files": ("Checked", "system files"),
    "Detecting hardware": ("Detected", "hardware"),
    "Starting kernel services": ("Started", "the kernel"),
    "Starting system services": ("Started", "system services"),
    "Checking memory": ("Checked", "memory"),
    "Checking dependencies": ("Checked", "libraries"),
    "Loading commands": ("Loaded", "commands"),
    "Loading programs": ("Loaded", "programs"),
    "Preparing the file system": ("Mounted", "the file system"),
    "Checking the file system": ("Checked", "the file system"),
    "Checking the last shutdown": ("Checked", "the previous session"),
}
FAILED_TO = {"Loaded": "load", "Checked": "check", "Detected": "detect", "Started": "start", "Mounted": "mount"}


def seconds_since_start():
    """Seconds since this PythonOS process started: the time stamp of a boot log line."""
    try:
        return max(0.0, time.time() - psutil.Process(os.getpid()).create_time())
    except Exception:
        return time.perf_counter()


def _stamp():
    return "[dim]" + "\\[" + f"{seconds_since_start():9.3f}" + "][/dim]"


def _detailed_header():
    """The first lines of a real boot: what is starting and on what. All of it is read from the running system."""
    from pyos import resources
    try:
        host = __import__("pyos").fs.hostname()
    except Exception:
        host = platform.node()
    live = os.environ.get("PYOS_LIVE") == "1"
    lines = [f"PythonOS {get_system_version()} ({platform.system()} {platform.machine()}) Python {platform.python_version()}",
             f"Machine: {host}, {psutil.cpu_count() or 1} CPU(s); memory: {resources.describe()}",
             f"Command line: boot_speed={settings.get('boot_speed')} mode={'live' if live else 'installed' if os.environ.get('PYOS_INSTALLED') == '1' else 'normal'}"]
    for line in lines:
        console.print(f"{_stamp()} {escape(line)}")


def boot_sequence(debug):
    """Run the real boot steps, one line each. The detailed style (default) is a boot log like a real system's, with time stamps; the
    classic style has a progress bar. Either way the timings are saved (see the bootlog and bootspeed commands)."""
    from core import bootlog
    pause = settings.boot_pause()  # the boot_speed setting: normal / fast / instant
    detailed = settings.get("boot_style") != "classic"
    steps = boot_steps(debug)
    sink = _Sink()
    record = []
    started = time.perf_counter()
    if detailed:
        try:
            _detailed_header()
        except Exception:
            pass
    for number, (label, action) in enumerate(steps, 1):
        t0 = time.perf_counter()
        try:
            status, detail = action(debug, sink)
        except Exception as e:  # a step that breaks must still be shown, and must not stop the rest
            status, detail = "fail", f"{e.__class__.__name__}: {e}"
        ms = (time.perf_counter() - t0) * 1000
        record.append({"name": label, "ms": round(ms, 1), "status": status, "detail": detail})
        extra = f" [dim]{escape(detail)}[/dim]" if detail else ""
        if detailed:
            verb, unit = UNITS.get(label, ("Finished", label.lower()))
            what = f"{verb} {unit}." if status != "fail" else f"Failed to {FAILED_TO.get(verb, 'run')} {unit}."
            console.print(f"{_stamp()} {MARKS[status]} {escape(tr(what))}{extra}")
        else:
            console.print(f"{MARKS[status]} {_progress_bar(number, len(steps))} {number * 100 // len(steps):>3}%  {tr(label)}{extra} [dim]{ms:.0f} ms[/dim]")
        if status == "fail" and label == "Checking dependencies":
            console.print("[bold red]Cannot continue without internet to install missing packages.[/bold red]")
            sys.exit(1)
        time.sleep(pause)
    total_ms = (time.perf_counter() - started) * 1000
    bootlog.save_boot(record, total_ms, pause * len(steps) * 1000)

    if detailed:
        console.print(f"{_stamp()} {MARKS['ok']} Reached target PythonOS Multi-User System.")
        console.print(f"{_stamp()} Startup finished in {total_ms / 1000:.3f}s (steps) + {seconds_since_start() - total_ms / 1000:.3f}s (loading).")
    console.print("[bold green]" + tr("System ready!") + "[/bold green]")
    time.sleep(min(0.8, pause * 2.3))
    os.system("cls" if os.name == "nt" else "clear")
    display_home_screen()
    return True
