import os
import subprocess
import sys
import shutil
import time
import random
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from yaspin import yaspin

REPO_URL = "https://github.com/Kalmai221/PythonOS.git"
INSTALL_DIR = os.path.join(os.getcwd(), "PythonOS")
INSTALLER_DIR = os.path.join(INSTALL_DIR, "installer")
console = Console()

def check_git():
    """Check if Git is installed."""
    with yaspin(text="\033[96mChecking for Git...\033[0m", spinner="dots") as spinner:
        time.sleep(random.uniform(1, 2))
        try:
            subprocess.run(["git", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            spinner.text = "\033[92m✔ Git found!\033[0m"
            spinner.ok("")
        except FileNotFoundError:
            spinner.text = "\033[91m✖ Git not installed! Please install Git and retry.\033[0m"
            spinner.fail("")
            sys.exit(1)

def is_pythonos_installed():
    """Check if PythonOS is already installed."""
    return os.path.exists(INSTALL_DIR) and os.path.isdir(INSTALL_DIR)

def remove_existing_installation():
    """Remove the existing PythonOS directory before reinstalling."""
    console.print("[yellow]Removing existing PythonOS installation...[/yellow]")

    with yaspin(text="\033[93mDeleting old installation...\033[0m", spinner="dots") as spinner:
        try:
            shutil.rmtree(INSTALL_DIR)
            time.sleep(random.uniform(1, 2))
            spinner.text = "\033[92m✔ Old installation removed!\033[0m"
            spinner.ok("")
        except Exception as e:
            spinner.text = f"\033[91m✖ Failed to remove! {e}\033[0m"
            spinner.fail("")
            sys.exit(1)

def clone_repository():
    """Clone the PythonOS repository with a simulated authentication process."""
    console.print("\n[bold cyan]Connecting to server...[/bold cyan]")

    with yaspin(text="\033[96mAuthenticating request...\033[0m", spinner="dots") as spinner:
        time.sleep(random.uniform(1, 2))
        spinner.text = "\033[92m✔ Authentication successful!\033[0m"
        spinner.ok("")

    with yaspin(text="\033[96mChecking repository integrity...\033[0m", spinner="dots") as spinner:
        time.sleep(random.uniform(1, 1.5))
        spinner.text = "\033[92m✔ Repository verified!\033[0m"
        spinner.ok("")

    with yaspin(text="\033[96mCloning PythonOS...\033[0m", spinner="dots") as spinner:
        try:
            subprocess.run(["git", "clone", REPO_URL, INSTALL_DIR], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            spinner.text = "\033[92m✔ Repository cloned successfully!\033[0m"
            spinner.ok("")
        except subprocess.CalledProcessError:
            spinner.text = "\033[91m✖ Failed to clone the repository!\033[0m"
            spinner.fail("")
            sys.exit(1)

def download_progress():
    """Simulates a realistic progress bar for downloading process."""
    console.print("\n[bold cyan]Downloading required files...[/bold cyan]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Establishing connection...", total=100)

        for i in range(20):
            time.sleep(random.uniform(0.1, 0.3))  # Simulate network variability
            progress.update(task, advance=random.randint(3, 6))

        progress.update(task, advance=100 - progress.tasks[0].completed)

def verify_installation():
    """Simulate file verification process."""
    console.print("\n[bold yellow]Verifying installation files...[/bold yellow]")

    with yaspin(text="\033[96mScanning installed components...\033[0m", spinner="dots") as spinner:
        time.sleep(random.uniform(1, 2))
        spinner.text = "\033[96mValidating dependencies...\033[0m"
        time.sleep(random.uniform(1, 2))
        spinner.text = "\033[92m✔ Installation verified!\033[0m"
        spinner.ok("")

def clear_installation_files():
    """Remove the installer directory after installation."""
    if os.path.exists(INSTALLER_DIR) and os.path.isdir(INSTALLER_DIR):
        console.print("\n[bold yellow]Cleaning up installation files...[/bold yellow]")

        with yaspin(text="\033[93mRemoving temporary files...\033[0m", spinner="dots") as spinner:
            try:
                shutil.rmtree(INSTALLER_DIR)
                time.sleep(random.uniform(1, 2))
                spinner.text = "\033[92m✔ Installation cleanup complete!\033[0m"
                spinner.ok("")
            except Exception as e:
                spinner.text = f"\033[91m✖ Failed to remove installer files! {e}\033[0m"
                spinner.fail("")

def finalize_installation():
    """Finalize installation with an animated spinner."""
    with yaspin(text="\033[96mFinalizing installation...\033[0m", spinner="dots") as spinner:
        time.sleep(random.uniform(2, 3))
        spinner.text = "\033[92m✔ Installation Complete!\033[0m"
        spinner.ok("")

def run_pythonos():
    """Run PythonOS if installed."""
    console.print("[bold green]Launching PythonOS...[/bold green] 🚀")
    os.chdir(INSTALL_DIR)  # Change directory to PythonOS
    time.sleep(2)
    os.system("clear")
    subprocess.run(["python", "main.py"], check=True)

def install_pythonos():
    """Main function to handle installation."""
    console.print("[bold cyan]🚀 PythonOS Installer 🚀[/bold cyan]")
    check_git()

    if is_pythonos_installed():
        console.print("\n[bold green]PythonOS is already installed![/bold green]")
        choice = console.input("\n[bold cyan]Do you want to reinstall it? (y/n): [/bold cyan]").strip().lower()

        if choice == 'n':
            run_pythonos()  # Run PythonOS if user chooses not to reinstall
            sys.exit(0)

        remove_existing_installation()  # Delete old installation before reinstalling

    clone_repository()
    download_progress()
    verify_installation()
    finalize_installation()
    clear_installation_files()

    console.print("\n[bold green]🎉 PythonOS installation successful![/bold green] 🚀")
    run_pythonos()  # Run PythonOS after installation

if __name__ == "__main__":
    install_pythonos()
