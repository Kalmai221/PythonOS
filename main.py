import os
import platform
import subprocess
import sys

def install_requirements():
    """Install dependencies from boot-requirements.txt with platform-specific options."""
    cmd = ["python", "-m", "pip", "install", "-r", "boot-requirements.txt", "-U", "--quiet"]

    # Add --break-system-packages if running on Linux
    if platform.system() == "Linux":
        cmd.append("--break-system-packages")

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies. Make sure Python and pip are installed.")
        sys.exit(0)

install_requirements()

import json
from rich.console import Console
import users
import shell
import core
import traceback
import time

console = Console()

CONFIG_FILE = "config.json"

# Load or create OS config
def load_config():
    if not os.path.exists(CONFIG_FILE):
        config = {"os_name": "pyOS", "version": "1.0", "debug": "False"}
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        console.print(f"[bold green]Config file created: {CONFIG_FILE}[/bold green]")
    else:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    return config

MAX_ATTEMPTS = 3  # Set the maximum number of login attempts
try:
    # result = 10 / 0  # BSOD TESTING
    config = load_config()
    console.print(f"[bold green]{config['os_name']} v{config['version']}[/bold green]")
    time.sleep(1)
    if config['debug'] == "True":
        debug = "Yes"
        console.print("[bold yellow]Debug Mode is enabled on this OS.[/bold yellow]")
    elif config['debug'] == "False":
        debug = "No"
    else:
        debug = "No"
        console.print("[bold yellow]Debug Mode Setting is not defined. Defaulting to Disabled.[/bold yellow]")
    core.boot_sequence(debug)

    attempts = 0
    username = None

    # Retry mechanism for login attempts
    while attempts < MAX_ATTEMPTS:
        username = users.boot_sequence()
        if username:
            shell.start_shell(username)
            break
        else:
            attempts += 1
            remaining_attempts = MAX_ATTEMPTS - attempts
            if remaining_attempts > 0:
                console.print(f"[bold yellow]Login failed. {remaining_attempts} attempts remaining...[/bold yellow]")
            else:
                console.print("[bold red]Login failed. Shutting down...[/bold red]")
                core.simulate_shutdown()
                break
except KeyboardInterrupt:
    core.simulate_shutdown()
except Exception as e:
    # Catch the error and show the BSOD
    error_message = f"Error: {str(e)}\n\nStack Trace:\n"
    error_message += "".join(traceback.format_exception(None, e, e.__traceback__))
    
    core.simulate_bsod(error_message)
    sys.exit(1)  # Exit the program with a non-zero exit code

