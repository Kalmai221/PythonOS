import psutil
from rich.table import Table
from rich.console import Console
import shutil
import subprocess
import sys

config = {
    "name": "taskman",
    "description": "Runs Task Manager."
}

def install_btop():
    print("Installing btop... (requires sudo)")
    try:
        subprocess.run(["sudo", "apt", "update"], check=True)
        subprocess.run(["sudo", "apt", "install", "-y", "btop"], check=True)
        print("btop installed successfully.")
    except subprocess.CalledProcessError:
        print("Failed to install btop. Please install manually.")
        sys.exit(1)

def execute():
    if shutil.which("btop") is None:
        print("btop not found. Installing now...")
        install_btop()

    # Run btop interactively
    subprocess.run(["btop"])

if __name__ == "__main__":
    execute()
