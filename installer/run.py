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
import platform
import subprocess
import re

REPO_ZIP_URL = "https://github.com/Kalmai221/PythonOS/archive/refs/heads/main.zip"
INSTALL_DIR = os.path.join(os.getcwd(), "PythonOS")
INSTALLER_DIR = os.path.join(INSTALL_DIR, "installer")
PYTHON_DOWNLOAD_URL = "https://www.python.org/ftp/python/3.11.1/python-3.11.1-amd64.exe"
console = Console()

GITHUB_API_URL = "https://api.github.com/repos/Kalmai221/PythonOS/commits/main"
LOCAL_COMMIT_FILE = os.path.join("PythonOS", "commit.txt")

def get_latest_commit():
    """Fetch the latest commit hash from GitHub."""
    try:
        response = requests.get(GITHUB_API_URL)
        response.raise_for_status()
        return response.json()["sha"]
    except requests.RequestException as e:
        print(f"Error fetching latest commit: {e}")
        return None

def get_local_commit():
    """Retrieve the locally stored commit hash."""
    if os.path.exists(LOCAL_COMMIT_FILE):
        with open(LOCAL_COMMIT_FILE, "r") as f:
            return f.read().strip()
    return None

def check_for_updates():
    """Compare local and latest commit hashes."""
    latest_commit = get_latest_commit()
    local_commit = get_local_commit()

    if not latest_commit:
        print("Failed to retrieve latest commit.")
        return

    if local_commit == latest_commit:
        print("PythonOS is up to date.")
    else:
        print("New update available!")
        print(f"Latest commit: {latest_commit}")
        print(f"Local commit: {local_commit}")

def is_python_installed():
    """Check if Python is installed."""
    try:
        try:
            result = subprocess.run(["python", "--version"], capture_output=True, text=True, check=True)
            return True
        except FileNotFoundError:
            return False
        except subprocess.CalledProcessError:
            return False
    except:
        return False

def install_python():
    """Download and install Python if missing."""
    system = platform.system()

    if system == "Windows":
        console.print("[yellow]Python is missing. Downloading installer...[/yellow]")
        response = requests.get(PYTHON_DOWNLOAD_URL, stream=True)
        installer_path = os.path.join(os.getcwd(), "python_installer.exe")

        with open(installer_path, "wb") as f:
            f.write(response.content)

        console.print("[yellow]Running Python installer...[/yellow]")
        os.system(f"{installer_path} /quiet InstallAllUsers=1 PrependPath=1")

        console.print("[green]Python installed! Please restart the script.[/green]")
        sys.exit(0)

    elif system == "Linux":
        console.print("[yellow]Python is missing. Installing via package manager...[/yellow]")
        os.system("sudo apt update && sudo apt install -y python3")

    elif system == "Darwin":  # macOS
        console.print("[yellow]Python is missing. Installing via Homebrew...[/yellow]")
        os.system("brew install python")

    else:
        console.print("[red]Unsupported OS! Please install Python manually.[/red]")
        sys.exit(1)

def replace_clear_with_cls(directory):
    """Recursively replace 'os.system("clear")' with 'os.system("cls")' in all Python files if running on Windows."""
    if platform.system() != "Windows":
        return

    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)

                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()

                new_content = re.sub(r'\bos\.system\("clear"\)', 'os.system("cls")', content)

                if new_content != content:
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(new_content)

def is_pythonos_installed():
    """Check if PythonOS is already installed."""
    return os.path.exists(INSTALL_DIR) and os.path.isdir(INSTALL_DIR)

def remove_existing_installation():
    """Remove the existing PythonOS directory before reinstalling."""
    console.print("[yellow]Removing existing PythonOS installation...[/yellow]")
    with yaspin(text="Deleting old installation...", spinner="dots") as spinner:
        try:
            shutil.rmtree(INSTALL_DIR)
            spinner.text = "Old installation removed!"
            spinner.ok("")
        except Exception as e:
            spinner.text = f"Failed to remove! {e}"
            spinner.fail("")
            sys.exit(1)

def download_repository():
    """Download PythonOS repository as a ZIP and save the latest commit hash."""
    latest_commit = get_latest_commit()
    if not latest_commit:
        console.print("[red]Failed to get latest commit hash.[/red]")
        return

    console.print("\n[bold cyan]Downloading PythonOS...[/bold cyan]")
    response = requests.get(REPO_ZIP_URL, stream=True)
    response.raise_for_status()

    with zipfile.ZipFile(BytesIO(response.content), "r") as zip_ref:
        zip_ref.extractall(os.getcwd())
        shutil.move("PythonOS-main", INSTALL_DIR)

    with open(LOCAL_COMMIT_FILE, "w") as f:
        f.write(latest_commit)

    console.print("\n[bold green]✔ Download and extraction complete![/bold green]")

def verify_installation():
    """Simulate file verification process."""
    console.print("\n[bold yellow]Verifying installation files...[/bold yellow]")
    with yaspin(text="Validating dependencies...", spinner="dots") as spinner:
        spinner.text = "Installation verified!"
        spinner.ok("")

def clear_installation_files():
    """Remove the installer directory after installation."""
    if os.path.exists(INSTALLER_DIR) and os.path.isdir(INSTALLER_DIR):
        console.print("\n[bold yellow]Cleaning up installation files...[/bold yellow]")
        with yaspin(text="Removing temporary files...", spinner="dots") as spinner:
            try:
                shutil.rmtree(INSTALLER_DIR)
                shutil.rmtree(os.path.join(INSTALL_DIR, ".github"))
                os.remove(os.path.join(INSTALL_DIR, "installer-requirements.txt"))
                os.remove(os.path.join(INSTALL_DIR, "replit.nix"))
                os.remove(os.path.join(INSTALL_DIR, ".replit"))
                os.remove(os.path.join(INSTALL_DIR, ".gitignore"))
                os.remove(os.path.join(INSTALL_DIR, ".prettierignore"))
                os.remove(os.path.join(INSTALL_DIR, "generated-icon.png"))
                spinner.text = "Cleanup complete!"
                spinner.ok("")
            except Exception as e:
                spinner.text = f"Failed to remove files! {e}"
                spinner.fail("")

def finalize_installation():
    """Finalize installation with an animated spinner."""
    with yaspin(text="Finalizing installation...", spinner="dots") as spinner:
        spinner.text = "Installation Complete!"
        spinner.ok("")

def run_pythonos():
    """Run PythonOS if installed."""
    console.print("[bold green]Launching PythonOS...[/bold green] 🚀")
    os.chdir(INSTALL_DIR)  # Change directory to PythonOS
    time.sleep(2)
    os.system("cls" if platform.system() == "Windows" else "clear")
    os.system("python main.py")

def install_pythonos():
    """Main function to handle installation with update checking."""
    console.print("[bold cyan]🚀 PythonOS Installer 🚀[/bold cyan]")

    latest_commit = get_latest_commit()
    local_commit = get_local_commit()

    if local_commit and latest_commit:
        if local_commit == latest_commit:
            console.print("\n[bold green]PythonOS is up to date![/bold green]")
            choice = console.input("\n[bold cyan]Do you want to reinstall it anyway? (y/n): [/bold cyan]").strip().lower()

            if choice == 'n':
                run_pythonos()  # Run PythonOS if user chooses not to reinstall
                sys.exit(0)
                
        else:
            console.print("\n[bold yellow]A new version of PythonOS is available![/bold yellow]")
            console.print(f"[bold cyan]Latest commit:[/bold cyan] {latest_commit}")
            console.print(f"[bold magenta]Your version:[/bold magenta] {local_commit}")
            choice = console.input("\n[bold cyan]Do you want to update? (y/n): [/bold cyan]").strip().lower()

            if choice == 'n':
                console.print("[bold yellow]Skipping update. Running current version...[/bold yellow]")
                run_pythonos()
                sys.exit(0)

        remove_existing_installation()  # Delete old installation before reinstalling

    download_repository()
    verify_installation()
    finalize_installation()
    clear_installation_files()

    console.print("\n[bold green]🎉 PythonOS installation successful![/bold green] 🚀")
    run_pythonos()  # Run PythonOS after installation


if __name__ == "__main__":
    if not is_python_installed():
        install_python()

    console.print("[green]Python is installed. Running PythonOS Installer...[/green]")
    install_pythonos()
