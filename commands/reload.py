import importlib
import os
from rich.console import Console
import pyos

# Initialize the console for rich output
console = Console()

# Command metadata
config = {
    "name": "reload",
    "description": "Reloads all commands and programs."
}

def reload_modules(module_type):
    """
    Reloads all modules of a specific type ('commands' or 'programs').
    """
    directory = "commands" if module_type == "commands" else "programs"

    # Debug: Print the directory being scanned
    console.print(f"[bold yellow]Scanning directory[/bold yellow]: {directory}")

    # Initialize lists to track the success and failure of modules
    reloaded_modules = []
    failed_modules = []

    # Iterate over all Python files in the specified directory
    for file_name in os.listdir(directory):
        if file_name.endswith(".py"):
            module_name = file_name[:-3]  # Strip the '.py' extension
            try:
                # Dynamically import the module
                if module_type == "commands":
                    module = importlib.import_module(f"commands.{module_name}")
                else:
                    module = importlib.import_module(f"programs.{module_name}")

                # Reload the module
                importlib.reload(module)
                reloaded_modules.append(module_name)
            except ModuleNotFoundError:
                failed_modules.append(f"Module '{module_name}' not found.")
            except Exception as e:
                failed_modules.append(f"Failed to reload '{module_name}': {e}")

    # Print the results
    if reloaded_modules:
        console.print(f"[bold green]Successfully reloaded the following {module_type} modules:[/bold green]")
        console.print(f"[green]• {', '.join(reloaded_modules)}[/green]")
    if failed_modules:
        console.print("[bold red]Failed to reload the following modules:[/bold red]")
        console.print(f"[red]• {', '.join(failed_modules)}[/red]")

    if not reloaded_modules and not failed_modules:
        console.print(f"[bold red]No {module_type} modules were reloaded.[/bold red]")

def execute():
    pyos.system("clear")
    # Inform the user that we're reloading the modules
    console.print("[bold yellow]Reloading commands and programs...[/bold yellow]")
    try:
        # Reload both commands and programs
        reload_modules("commands")
        reload_modules("programs")
        console.print("[bold green]Reload complete![/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error during reload:[/bold red] {e}")
