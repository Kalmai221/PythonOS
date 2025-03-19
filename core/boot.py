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
from rich.table import Table
import datetime
import core
import platform

# Initialize the console for rich output
console = Console()

CONFIG_FILE = "config.json"
USER_DB = "users.json"
PROGRAMS_DIR = "programs"
COMMANDS_DIR = "commands"
SYSTEM_FILES = [CONFIG_FILE, USER_DB]
REQUIREMENTS_FILE = "requirements.txt"
        
PACKAGE_JSON_FILE = "package.json"

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
        spinner.text = "Missing files have been recreated.[/bold green]"
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
    system_info = get_system_info()
    system_version = get_system_version()

    # Content inside the panel
    panel_content = Align.center(
        f"[bold cyan]Welcome to pyOS v{system_version}![/bold cyan]\n\n{system_info}"
    )

    # Home screen panel
    home_panel = Panel(
        panel_content,
        title="[bold green]Home Page[/bold green]",
        border_style="blue"
    )

    # Print the panel
    console.print(home_panel)
    
def boot_sequence(debug):
    with yaspin(text="Booting system...") as spinner:
        time.sleep(1)  # Simulate booting delay
        spinner.text = "Initializing hardware components..."
        time.sleep(2)  # Simulate hardware initialization

        spinner.text = "Loading kernel..."
        time.sleep(2)  # Simulate kernel loading

        spinner.text = "Checking system memory..."
        time.sleep(1)

        spinner.text = "Verifying file system integrity..."
        check_system_integrity(debug, spinner)
        time.sleep(1)

        spinner.text = "Loading system services..."
        time.sleep(2)

        # Check Python files in the pyos folder
        check_pyos_files(debug, spinner)

        spinner.text = "Starting network services..."
        time.sleep(1)

        install_requirements(debug, spinner)  # Install required packages from requirements.txt
        time.sleep(1)

        load_programs(debug, spinner)  # No longer showing programs
        time.sleep(1)
        load_commands(debug, spinner)  # No longer showing commands

        # Set the current directory to the "files" folder
        set_current_directory_to_files(debug, spinner)
        spinner.text = "Initialising Update Checher..."
        time.sleep(1.5)
        
    core.update_system("False")
    console.print("[bold green]System ready![/bold green]\n")
    os.system("clear")
    display_home_screen()
    return True
