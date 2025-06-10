import os
import sys
import subprocess
import json
from pathlib import Path
import importlib.util
from rich.console import Console
from rich.table import Table
from rich.prompt import IntPrompt, Prompt, Confirm
import shutil
import glob

console = Console()

config = {
    "name": "programs",
    "description": "Browse and launch installed programs from any category (games, multimedia, etc)."
}

ROOT_DIR = Path("files")

def list_installed_programs():
    """List all installed programs with their metadata."""
    programs = []
    # Use glob to find all directories matching the pattern "installed_*"
    category_dirs = glob.glob(str(ROOT_DIR / "installed_*"))
    for category_dir in category_dirs:
        category_path = Path(category_dir)
        if category_path.is_dir():
            for folder in category_path.iterdir():
                if folder.is_dir():
                    metadata = load_program_metadata(folder)
                    if metadata:  # Only include folders with valid data.json
                        programs.append((folder, metadata))
    return programs

def load_program_metadata(program_folder: Path):
   """Load metadata from data.json file."""
   data_file = program_folder / "data.json"
   if data_file.exists():
       try:
           with open(data_file, 'r') as f:
               data = json.load(f)
               print(f"Successfully loaded metadata from {data_file}")  # Add this line
               return data
       except json.JSONDecodeError as e:
           console.print(f"[bold yellow]Warning: Could not read metadata for {program_folder.name}: Invalid JSON in {data_file}: {e}[/bold yellow]")
       except Exception as e:
           console.print(f"[bold yellow]Warning: Could not read metadata for {program_folder.name}: Error reading {data_file}: {e}[/bold yellow]")
   else:
       console.print(f"[bold yellow]Warning: data.json not found in {program_folder.name}[/bold yellow]") # Add this line

   return None

def import_program_module(filepath: Path):
    """Dynamically import a .py file as a module."""
    try:
        spec = importlib.util.spec_from_file_location(filepath.stem, str(filepath))
        if spec is None:
            return None
        mod = importlib.util.module_from_spec(spec)
        sys.modules[f"{filepath.parent.name}_{filepath.stem}"] = mod
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        console.print(f"[bold red]Failed to import module {filepath.name}: {e}[/bold red]")
        return None

def execute_program_script(program_folder: Path, script_name: str, metadata: dict):
    """Execute a specific script from the program folder using metadata."""
    scripts = metadata.get("scripts", {})

    if script_name not in scripts:
        console.print(f"[bold red]Script '{script_name}' not defined in {program_folder.name}/data.json[/bold red]")
        return False

    script_filename = scripts[script_name]
    script_path = program_folder / script_filename

    if not script_path.exists():
        console.print(f"[bold red]Script file {script_filename} not found in {program_folder.name}[/bold red]")
        return False

    mod = import_program_module(script_path)
    if mod is None:
        console.print(f"[bold red]Import error. Cannot execute {script_filename}.[/bold red]")
        return False

    if hasattr(mod, "execute") and callable(mod.execute):
        try:
            mod.execute()
            return True
        except Exception as e:
            console.print(f"[bold red]Script execution error:[/bold red] {e}")
            return False
    else:
        console.print(f"[bold red]Script {script_filename} does not have an executable 'execute()' function.[/bold red]")
        return False

def get_available_actions(metadata: dict):
    """Get available actions based on scripts defined in metadata."""
    scripts = metadata.get("scripts", {})
    available_actions = []

    # Map script names to user-friendly action names
    action_map = {
        "run": "run",
        "launcher": "run",
        "start": "run",
        "install": "install",
        "installer": "install",
        "uninstall": "uninstall",
        "uninstaller": "uninstall",
        "remove": "uninstall"
    }

    for script_key in scripts.keys():
        action = action_map.get(script_key, script_key)
        if action not in available_actions:
            available_actions.append(action)

    available_actions.append("cancel")
    return available_actions

def get_script_key_for_action(action: str, metadata: dict):
    """Get the script key that corresponds to the user's action choice."""
    scripts = metadata.get("scripts", {})

    # Map actions back to script keys
    action_to_script = {
        "run": ["run", "launcher", "start"],
        "install": ["install", "installer"],
        "uninstall": ["uninstall", "uninstaller", "remove"]
    }

    if action in action_to_script:
        for script_key in action_to_script[action]:
            if script_key in scripts:
                return script_key

    # If it's a direct script name, return it
    if action in scripts:
        return action

    return None

def execute():
    programs = list_installed_programs()
    if not programs:
        console.print(
            "[bold yellow]No installed programs found.[/bold yellow] "
            "[cyan]Visit the [bold]Marketplace[/bold] to download packages.[/cyan]"
        )
        return

    table = Table(title="Installed Programs", show_lines=True, header_style="bold cyan")
    table.add_column("Index", justify="right", style="bold")
    table.add_column("Program Name", style="green")
    table.add_column("Description", style="white")
    table.add_column("Version", style="yellow")
    table.add_column("Available Actions", style="cyan")

    for idx, (folder, metadata) in enumerate(programs, start=1):
        available_actions = get_available_actions(metadata)
        actions_str = ", ".join([a for a in available_actions if a != "cancel"])

        table.add_row(
            str(idx), 
            metadata.get("name", folder.name),
            metadata.get("description", "No description available")[:40] + ("..." if len(metadata.get("description", "")) > 40 else ""),
            metadata.get("version", "Unknown"),
            actions_str
        )

    console.print(table)

    try:
        choice = IntPrompt.ask("Enter the index of the program to manage (0 to cancel)", default=0)
        if choice == 0:
            console.print("Cancelled.")
            return
        if choice < 1 or choice > len(programs):
            console.print("[bold red]Invalid selection.[/bold red]")
            return
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Cancelled by user.[/bold yellow]")
        return

    program_folder, metadata = programs[choice - 1]
    program_name = metadata.get("name", program_folder.name)
    available_actions = get_available_actions(metadata)

    # Ask what action to perform
    action = Prompt.ask(
        f"What do you want to do with [green]{program_name}[/green]?",
        choices=available_actions,
        default="run" if "run" in available_actions else available_actions[0]
    )

    if action == "cancel":
        console.print("Operation cancelled.")
        return

    # Get the script key for the chosen action
    script_key = get_script_key_for_action(action, metadata)
    if not script_key:
        console.print(f"[bold red]No script found for action '{action}'[/bold red]")
        return

    # Execute the script
    action_messages = {
        "run": f"[bold green]Launching:[/bold green] {program_name}",
        "install": f"[bold blue]Running installer for:[/bold blue] {program_name}",
        "uninstall": f"[bold red]Running uninstaller for:[/bold red] {program_name}"
    }

    console.print(action_messages.get(action, f"[bold cyan]Running {action} for:[/bold cyan] {program_name}"))

    success = execute_program_script(program_folder, script_key, metadata)
    if success:
        success_messages = {
            "run": "[bold green]Program exited successfully.[/bold green]",
            "install": "[bold green]Installation completed successfully.[/bold green]",
            "uninstall": "[bold green]Uninstallation completed successfully.[/bold green]"
        }
        console.print(success_messages.get(action, f"[bold green]{action.capitalize()} completed successfully.[/bold green]"))
        # Add folder deletion here
        if action == "uninstall":
            if Confirm.ask(f"[bold yellow]Do you want to delete the program folder '{program_folder.name}'?[/bold yellow]", default=False):
                try:
                    shutil.rmtree(program_folder)
                    console.print(f"[bold green]Program folder '{program_folder.name}' deleted successfully.[/bold green]")
                except Exception as e:
                    console.print(f"[bold red]Failed to delete program folder: {e}[/bold red]")
    else:
        console.print("[bold red]Uninstallation failed.[/bold red]")

if __name__ == "__main__":
    execute()