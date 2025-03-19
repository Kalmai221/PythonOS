import os
import sys
import shutil
import time
import random
import zipfile
import requests
from io import BytesIO
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from yaspin import yaspin

REPO_ZIP_URL = "https://github.com/Kalmai221/PythonOS/archive/refs/heads/main.zip"
INSTALL_DIR = os.path.join(os.getcwd(), "PythonOS")
INSTALLER_DIR = os.path.join(INSTALL_DIR, "installer")
console = Console()

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

def download_repository():
    """Download PythonOS repository as a ZIP using requests."""
    console.print("\n[bold cyan]Downloading PythonOS...[/bold cyan]")

    with yaspin(text="\033[96mFetching repository...\033[0m", spinner="dots") as spinner:
        try:
            response = requests.get(REPO_ZIP_URL, stream=True)
            response.raise_for_status()
            zip_data = BytesIO(response.content)
            spinner.text = "\033[92m✔ Download complete!\033[0m"
            spinner.ok("")
        except requests.RequestException as e:
            spinner.text = f"\033[91m✖ Failed to download! {e}\033[0m"
            spinner.fail("")
            sys.exit(1)

    console.print("\n[bold cyan]Extracting files...[/bold cyan]")
    with yaspin(text="\033[96mUnzipping files...\033[0m", spinner="dots") as spinner:
        try:
            with zipfile.ZipFile(zip_data, "r") as zip_ref:
                zip_ref.extractall(os.getcwd())
                shutil.move("PythonOS-main", INSTALL_DIR)  # Rename extracted folder
            time.sleep(random.uniform(1, 2))
            spinner.text = "\033[92m✔ Extraction complete!\033[0m"
            spinner.ok("")
        except Exception as e:
            spinner.text = f"\033[91m✖ Failed to extract! {e}\033[0m"
            spinner.fail("")
            sys.exit(1)

def verify_installation():
    """Simulate file verification process."""
    console.print("\n[bold yellow]Verifying installation files...[/bold yellow]")
    with yaspin(text="\033[96mValidating dependencies...\033[0m", spinner="dots") as spinner:
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
                spinner.text = "\033[92m✔ Cleanup complete!\033[0m"
                spinner.ok("")
            except Exception as e:
                spinner.text = f"\033[91m✖ Failed to remove files! {e}\033[0m"
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
    os.system("python main.py")

def install_pythonos():
    """Main function to handle installation."""
    console.print("[bold cyan]🚀 PythonOS Installer 🚀[/bold cyan]")

    if is_pythonos_installed():
        console.print("\n[bold green]PythonOS is already installed![/bold green]")
        choice = console.input("\n[bold cyan]Do you want to reinstall it? (y/n): [/bold cyan]").strip().lower()

        if choice == 'n':
            run_pythonos()  # Run PythonOS if user chooses not to reinstall
            sys.exit(0)

        remove_existing_installation()  # Delete old installation before reinstalling

    download_repository()
    verify_installation()
    finalize_installation()
    clear_installation_files()

    console.print("\n[bold green]🎉 PythonOS installation successful![/bold green] 🚀")
    run_pythonos()  # Run PythonOS after installation

if __name__ == "__main__":
    install_pythonos()
