# pyos/system.py
import os
import importlib.util
from rich.console import Console

console = Console()

def system(command):
    """
    This function executes commands or programs.
    It checks if the command is in the 'commands' or 'programs' directory
    and executes it accordingly.
    """
    # Check if the command exists in the 'commands' directory
    command_file = os.path.join("commands", f"{command}.py")
    program_file = os.path.join("programs", f"{command}.py")

    if os.path.exists(command_file):  # Command found in 'commands'
        try:
            # Dynamically load the command module
            spec = importlib.util.spec_from_file_location(command, command_file)
            command_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(command_module)

            # If the command has an 'execute' function, call it
            if hasattr(command_module, "execute"):
                command_module.execute()
            else:
                console.print(f"[bold red]Error:[/bold red] Command '{command}' does not have an execute function.")
        except Exception as e:
            console.print(f"[bold red]Error executing command '{command}': {e}[/bold red]")

    elif os.path.exists(program_file):  # Program found in 'programs'
        try:
            # Dynamically load the program module
            spec = importlib.util.spec_from_file_location(command, program_file)
            program_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(program_module)

            # If the program has an 'execute' function, call it
            if hasattr(program_module, "execute"):
                program_module.execute()
            else:
                console.print(f"[bold red]Error:[/bold red] Program '{command}' does not have an execute function.")
        except Exception as e:
            console.print(f"[bold red]Error executing program '{command}': {e}[/bold red]")

    else:
        # Command or program not found
        console.print(f"[bold red]Error:[/bold red] '{command}' not found in either 'commands' or 'programs' directory.")
