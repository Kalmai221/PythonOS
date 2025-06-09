from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel
from rich.text import Text
import pyos
import time
import core

# Command metadata
config = {
    "name": "wipe",
    "description": "Clears all data and returns the OS to factory conditions."
}

console = Console()

def execute():
    user_info = pyos.userinfo()
    if user_info[1] == "admin":
        console.print(Panel.fit("[bold red]WARNING: This action will erase all data and reset the OS to factory conditions![/bold red]", style="red"))
    
        confirm = Confirm.ask("[bold yellow]Are you absolutely sure you want to proceed?[/bold yellow]", default=False)
        if not confirm:
            console.print("[bold green]Wipe cancelled.[/bold green]")
            return 
    
        # Simulate wipe operation here
        console.print("[bold red]Wiping data...[/bold red]")
        time.sleep(10)
        console.print("[bold green]System has been reset to factory conditions.[/bold green]")
        time.sleep(2)
        console.print("[bold yellow]System needs to shutdown in order to complete the removal.[/bold yellow]")
        confirm_shutdown = Confirm.ask("[bold yellow]Do you want to shutdown now?[/bold yellow]", default=True)
    
        if confirm_shutdown:
            console.print("[bold cyan]Shutting down system...[/bold cyan]")
            core.simulate_shutdown_wipe()
        else:
            console.print("[bold green]Shutdown canceled. Please remember to shutdown later to complete the wipe.[/bold green]")
    else:
        console.print(
            "[bold red]You do not have permission to use this command[/bold red]")
