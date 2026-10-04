import os
import json
import time
import subprocess
import sys
from rich.console import Console
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

# Initialize the console for rich output
console = Console()

CONFIG_FILE = "config.json"
USER_DB = "users.json"
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

    if os.name == "posix":  # Linux/macOS
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])  # Read uptime in seconds
    else:  # Windows
        uptime_seconds = time.time() - psutil.boot_time()

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
        uptime = time.strftime("%H:%M:%S", time.gmtime(time.time() - psutil.boot_time()))
    except Exception:
        uptime = "unknown"

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
        Align.center(Text("Type 'help' once logged in to see what you can do.", style="dim italic")),
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


def _log(spinner, label, status="ok", detail=""):
    """Print a boot log line above the spinner."""
    marks = {"ok": "[bold green][  OK  ][/bold green]",
             "warn": "[bold yellow][ WARN ][/bold yellow]",
             "fail": "[bold red][FAILED][/bold red]"}
    suffix = f" [dim]{detail}[/dim]" if detail else ""
    with console.capture() as cap:
        console.print(f"{marks[status]} {label}{suffix}")
    spinner.write(cap.get().rstrip("\n"))


def boot_sequence(debug):
    pause = 0.35  # short pauses keep the boot feeling like a boot without making you wait
    with yaspin(text="Booting system...", color="cyan") as spinner:
        time.sleep(pause)

        spinner.text = "Initializing hardware components..."
        time.sleep(pause)
        _log(spinner, "Initialized hardware components")

        spinner.text = "Loading kernel..."
        time.sleep(pause)
        _log(spinner, "Loaded kernel")

        spinner.text = "Verifying file system integrity..."
        check_system_integrity(debug, spinner)
        time.sleep(pause)
        _log(spinner, "Verified file system")

        check_pyos_files(debug, spinner)
        _log(spinner, "Loaded system services")

        packages = get_packages_from_requirements("requirements.txt")
        if os.environ.get("PYOS_BUNDLED") == "1":
            _log(spinner, "Bundled packages", "ok", "dependencies ship with this build")
            internet = None
        else:
            spinner.text = "Checking internet connection..."
            internet = check_internet_connection()
        if internet is None:
            pass
        elif internet:
            _log(spinner, "Network online")
            spinner.text = "Installing required packages..."
            try:
                install_requirements(debug, spinner)
                _log(spinner, "Required packages up to date")
            except Exception as e:
                _log(spinner, "Could not update packages", "warn", str(e).splitlines()[0] if str(e) else "")
        else:
            _log(spinner, "No internet connection", "warn", "running offline")
            missing = check_packages_installed(packages) if packages else []
            if missing:
                _log(spinner, "Missing packages", "fail", ", ".join(missing))
                spinner.fail("✗")
                console.print("[bold red]Cannot continue without internet to install missing packages.[/bold red]")
                sys.exit(1)
            _log(spinner, "All required packages are installed")

        spinner.text = "Loading programs and commands..."
        load_programs(debug, spinner)
        load_commands(debug, spinner)
        _log(spinner, "Loaded programs and commands")

        set_current_directory_to_files(debug, spinner)
        time.sleep(pause)
        spinner.ok("✔")

    console.print("[bold green]System ready![/bold green]")
    time.sleep(0.8)
    os.system("cls" if os.name == "nt" else "clear")
    display_home_screen()
    return True
