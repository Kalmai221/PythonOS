import os
import importlib.util
import time
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt
import readline

# Initialize the console for rich output
console = Console()

# Metadata dictionary for commands
commands_config = {}

base_directory = os.path.abspath("files")  # Base directory is '/files'
current_directory_file = "current_directory.txt"  # File containing the current directory

def get_relative_path():
    """Returns the shell path from 'current_directory.txt' relative to '/files'."""
    try:
        with open(current_directory_file, "r") as file:
            current_directory = file.read().strip()

        # Ensure that the path is relative to '/files'
        if current_directory.startswith(base_directory):
            relative_path = os.path.relpath(current_directory, base_directory)
            return f"/{relative_path}" if relative_path != "." else ""
        else:
            return "[bold red]Error:[/bold red] Current directory is outside of '/files'."
    except FileNotFoundError:
        return "[bold red]Error:[/bold red] current_directory.txt not found."

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

def start_shell(username):
    """Starts the interactive shell."""
    available_commands = load_all_modules("commands")
    available_programs = load_all_modules("programs")

    # Enable shell-specific command history (Up/Down arrows)
    readline.parse_and_bind("tab: complete")
    readline.parse_and_bind("set editing-mode vi")  # Enables Up/Down for navigation

    while True:
        relative_path = get_relative_path()
        prompt = f"{username}@pyOS{relative_path}> "

        try:
            cmd = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):  # Handle Ctrl+C and Ctrl+D safely
            console.print("\n[bold yellow]Exiting shell...[/bold yellow]")
            break

        if cmd == "exit":
            console.print("[bold green]Logging out...[/bold green]")
            break
        elif cmd == "help":
            show_help(available_commands, available_programs)
        elif cmd.startswith("cd "):
            args = cmd[3:].strip()
            if "cd" in available_commands:
                available_commands["cd"]["module"].execute(args)
            else:
                console.print("[bold red]cd command not found![/bold red]")
        elif cmd.startswith("run "):
            program_name = cmd[4:].strip()
            matched_program = next((name for name, info in available_programs.items()
                                    if program_name == name or program_name in info["aliases"]), None)

            if matched_program:
                # **Disable Up/Down history when inside a program**
                readline.parse_and_bind("set editing-mode emacs")  # Disable arrow-based navigation

                # Run the selected program
                available_programs[matched_program]["module"].execute()

                # **Re-enable Up/Down history after the program exits**
                readline.parse_and_bind("set editing-mode vi")
            else:
                console.print(f"[bold red]Program '{program_name}' not found.[/bold red]")
        else:
            matched_command = next((name for name, info in available_commands.items()
                                    if cmd == name or cmd in info["aliases"]), None)

            if matched_command:
                available_commands[matched_command]["module"].execute()
            else:
                console.print("[bold red]Command not found.[/bold red] Type 'help' for a list of commands.")

def draw_help_menu(selected_index, mode, available_commands, available_programs):
    """Generates and displays the help menu."""
    console.clear()
    table = Table(title=f"[bold cyan]Help Menu ({mode.capitalize()})[/bold cyan]", expand=True)
    table.add_column("Name", style="bold")
    table.add_column("Description", style="yellow")
    table.add_column("Aliases", justify="right", style="blue")

    data = available_commands if mode == "commands" else available_programs
    items = list(data.items())

    for i, (name, info) in enumerate(items):
        highlight = "[bold green]→[/bold green] " if i == selected_index else "   "
        aliases = ", ".join(info['aliases']) if info['aliases'] else "None"
        table.add_row(f"{highlight}{name}", info['description'], aliases)

    table.add_row("\n[bold cyan]Use [W/S] to navigate, [Enter] to select, [T] for Programs, [Q] to quit[/bold cyan]", "", "")
    console.print(table)
    
def show_help(available_commands, available_programs):
    """Interactive help menu following the correct structure."""
    mode = None  # No mode selected initially
    selected_index = 0
    options = ["Programs", "Commands"]

    while True:
        console.clear()

        if mode is None:
            # TITLE: Choose between Programs or Commands
            console.print("[bold cyan]HELP MENU[/bold cyan]\n")
            for i, option in enumerate(options):
                prefix = "[bold green]→[/bold green] " if i == selected_index else "   "
                console.print(f"{prefix}{option}")
            key = console.input("\n[bold cyan]Use [W/S] to move, [Enter] to select, [Q] to quit: [/bold cyan]").strip().lower()

            if key in ["w", "up"]:
                selected_index = (selected_index - 1) % len(options)
            elif key in ["s", "down"]:
                selected_index = (selected_index + 1) % len(options)
            elif key == "":
                mode = options[selected_index].lower()  # Set mode to 'programs' or 'commands'
                selected_index = 0  # Reset selection
            elif key == "q":
                console.print("[bold yellow]Exiting Help Menu...[/bold yellow]")
                return

        else:
            # SELECT COMMAND OR PROGRAM NAME
            console.clear()
            data = available_programs if mode == "programs" else available_commands
            items = list(data.keys())

            if not items:
                console.print(f"[bold red]No {mode} available.[/bold red]")
                console.input("\n[bold cyan]Press Enter to go back...[/bold cyan]")
                mode = None
                continue

            console.print(f"[bold cyan]Select a {mode[:-1].capitalize()}[/bold cyan]\n")
            for i, name in enumerate(items):
                prefix = "[bold green]→[/bold green] " if i == selected_index else "   "
                console.print(f"{prefix}{name}")
            key = console.input("\n[bold cyan]Use [W/S] to move, [Enter] to select, [B] to go back: [/bold cyan]").strip().lower()

            if key in ["w", "up"]:
                selected_index = (selected_index - 1) % len(items)
            elif key in ["s", "down"]:
                selected_index = (selected_index + 1) % len(items)
            elif key == "":
                selected_item = items[selected_index]
                if show_command_info(selected_item, mode, available_commands, available_programs):
                    return  # If the user runs a command, exit help completely
                selected_index = 0  # Reset selection after returning
            elif key == "b":
                mode = None
                selected_index = 0  # Reset selection

def show_command_info(item_name, mode, available_commands, available_programs):
    """Displays command or program details with options to run or go back."""
    console.clear()
    data = available_programs if mode == "programs" else available_commands
    info = data.get(item_name, {})

    description = info.get("description", "No description available.")
    aliases = ", ".join(info.get("aliases", [])) if info.get("aliases") else "None"

    console.print(f"[bold cyan]{item_name} Information[/bold cyan]\n")
    console.print(f"[bold]Description:[/bold] {description}")
    console.print(f"[bold]Aliases:[/bold] {aliases}")

    while True:
        key = console.input("\n[bold cyan][R] Run, [B] Back: [/bold cyan]").strip().lower()
        if key == "r":
            console.print(f"[bold green]Running {item_name}...[/bold green]\n")
            info["module"].execute()  # Run the command or program
            return True  # Exit help completely after running
        elif key == "b":
            return False  # Go back to the previous menu
