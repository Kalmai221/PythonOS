import time
import sys
import os
import pyos
from rich.console import Console
from rich.progress import Progress, BarColumn, TextColumn
from yaspin import yaspin
import random
import json

# Initialize the console for rich output
console = Console()

def simulate_shutdown(FromLoaded):
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
        if FromLoaded == "True":
            os.remove('current_user.json')
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


def restart_system(FromLoaded):
    """Simulate restarting the OS by shutting down and then running main.py."""
    console.print("\n[bold yellow]Restarting system to apply updates...[/bold yellow]")
    time.sleep(3)
    simulate_shutdown(FromLoaded)
    time.sleep(3)
    os.system("clear")
    time.sleep(1)
    os.system("python main.py")
    sys.exit(0)

def get_current_version():
    """Reads the current OS version from config.json"""
    try:
        with open(CONFIG_FILE, "r") as file:
            config = json.load(file)
        return config.get("version", "1.0")  # Ensure version is a float
    except (FileNotFoundError, json.JSONDecodeError):
        return 1.0  # Default version if file is missing/corrupt

def increment_version(version: str) -> str:
    """Increments the version with a 50% chance of patch update and 50% chance of minor update."""
    parts = list(map(int, version.split(".")))

    if len(parts) == 2:  # Ensure patch level exists (e.g., "1.1" → "1.1.0")
        parts.append(0)

    if random.randint(1, 2) == 1:  # 50% chance to increase patch
        if parts[2] >= 9:  # If patch is at max, remove it and increase minor
            parts = [parts[0], parts[1] + 1]
        else:
            parts[2] += 1
    else:  # 50% chance to increase minor
        parts = [parts[0], parts[1] + 1]  # Drop the patch

    return ".".join(map(str, parts))  # Convert back to string

def check_for_updates():
    """Simulates checking for updates with realistic output"""
    current_version = get_current_version()

    console.print("\n[bold cyan]Initializing update check...[/bold cyan]")

    with yaspin(text="Connecting to update server...", spinner="dots") as sp:
        time.sleep(random.uniform(1.5, 2.5))

        sp.text = "Authenticating request..."
        time.sleep(random.uniform(1.0, 2.0))

        sp.text = "Fetching system specifications..."
        time.sleep(random.uniform(1.5, 2.5))

        sp.text = "Checking for compatible updates..."
        time.sleep(random.uniform(1.5, 2.5))

        sp.text = "Finalizing update check..."
        time.sleep(random.uniform(1.0, 2.0))

    update_available = random.randint(1, 10) == 1  
    
    if update_available:
        new_version = increment_version(str(current_version))
        console.print(f"\n[bold green]✔ Update available! PyOS v{new_version} is ready to download and install.[/bold green] 🎉")
        return [update_available, new_version]
    else:
        console.print("\n[bold yellow]✔ No updates available. Your system is up to date![/bold yellow]")
        return [update_available, None]

def download_update():
    """Simulates downloading an update"""
    console.print("\n[bold cyan]Downloading update...[/bold cyan]")

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Downloading update package...", total=100)

        while not progress.finished:
            time.sleep(0.1)
            progress.update(task, advance=5)

CONFIG_FILE = "config.json"

def install_update(version):
    """Simulates installing the update and updates config.json"""
    console.print("\n[bold cyan]Installing update...[/bold cyan]")

    with yaspin(text="Extracting update files...", spinner="dots") as sp:
        time.sleep(2)
        sp.text = "Verifying installation integrity..."
        time.sleep(2)
        sp.text = "Applying system patches..."
        time.sleep(1.5)

    # Update config.json version
    update_config_version(version)

    console.print("\n[bold green]Update installed successfully![/bold green] ✅")

def update_config_version(version):
    """Reads config.json, increments the version, and saves it"""
    try:
        with open(CONFIG_FILE, "r") as file:
            config = json.load(file)

        # Update config and save
        config["version"] = str(version)  # Store as string for safety
        with open(CONFIG_FILE, "w") as file:
            json.dump(config, file, indent=4)

        console.print(f"\n[bold cyan]Updated system version to v{version}[/bold cyan] 🚀")

    except Exception as e:
        console.print(f"\n[bold red]Error updating config.json: {e}[/bold red]")

def update_system(FromLoaded):
    """Main function to check, download, install, and restart for updates"""
    update_info = check_for_updates()
    if update_info[0]:
        download_update()
        install_update(update_info[1])
        restart_system(FromLoaded)
    time.sleep(1)