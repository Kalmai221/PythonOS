import pyos
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
import core
import sys

console = Console()

config = {
    "name": "Developer Console",
    "description": "Developer tools for advanced system operations"
}

AUTHORIZED_USER = "Kalmai221"

def bsod():
    core.simulate_bsod("Developer triggered BSOD\n\nThis is normal, no problems are current in the system")
def shutdown():
    pyos.shutdown()
    sys.exit(0)

def restart():
    pyos.system("restart")

def dev_commands():
    if pyos.userinfo()[0] != AUTHORIZED_USER:
        console.print("[bold red]You do not have permission to use developer commands[/bold red]")
        return

    console.print(Panel("[bold cyan]Available devel
    oper commands:[/bold cyan]\n"
                        "1. bsod - Trigger Blue Screen of Death\n"
                        "2. shutdown - Shutdown the system\n"
                        "3. restart - Restart the system\n"
                        "4. exit - Exit developer console"))

    while True:
        cmd = Prompt.ask("[bold green]Enter command[/bold green]").strip().lower()

        if cmd == "bsod":
            core.simulate_bsod("Developer triggered BSOD")
        elif cmd == "shutdown":
            pyos.system("shutdown")
        elif cmd == "restart":
            pyos.system("restart")
        elif cmd == "exit":
            console.print("[bold blue]Exiting developer console.[/bold blue]")
            break
        else:
            console.print("[bold red]Unknown command[/bold red]")

def execute():
    console.print(f"[bold green]{config['name']} - {config['description']}[/bold green]")
    dev_commands()