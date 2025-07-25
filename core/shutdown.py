import time
import sys
from rich.console import Console
from yaspin import yaspin
import pyos
import os
import subprocess

# Initialize the console for rich output
console = Console()

def simulate_shutdown():
    pyos.system("clear")
    console.print("\n[bold red]Initiating system shutdown...[/bold red]", style="bold")
    time.sleep(1)

    # Simulate closing applications and services
    with yaspin(text="Closing open applications...", spinner="dots") as sp:
        time.sleep(1)
        sp.text = "Waiting for applications to close gracefully..."
        time.sleep(1)
        sp.text = "Force closing some applications..."
        time.sleep(1)

    with yaspin(text="Terminating background services...", spinner="dots") as sp:
        time.sleep(1)
        sp.text = "Waiting for services to stop..."
        time.sleep(1)

    with yaspin(text="Cleaning up temporary files...", spinner="dots") as sp:
        time.sleep(1)
        try:
            os.remove('current_user.json')
        except:
            sp.text = "Failed to delete temporary files."
        time.sleep(1.5)
        sp.text = "Clearing system caches..."
        time.sleep(1)

    # Saving user data and disconnecting from the network
    with yaspin(text="Saving user data...", spinner="dots") as sp:
        time.sleep(2)
        sp.text = "Disconnecting from network..."
        time.sleep(1)

    # Stopping critical services with dynamic text
    with yaspin(text="Stopping critical services...", spinner="dots") as sp:
        for i in range(10):
            sp.text = f"Stopping services... {i+1}/10"
            time.sleep(0.2)

    with yaspin(text="Preparing hardware for power-off...", spinner="dots") as sp:
        time.sleep(1)
        sp.text = "Finalizing shutdown procedures..."
        time.sleep(1.5)

    # Using yaspin for shutdown countdown with spinner
    with yaspin(text="Powering off hardware...", spinner="dots") as sp:
        time.sleep(1)
        for i in range(10, 0, -1):
            sp.text = f"Shutting down in {i} seconds..."
            time.sleep(1)

    # Final message
    console.print("\n[bold red]Shutdown complete.[/bold red]")
    sys.exit(0)
