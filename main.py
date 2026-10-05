import os
import platform
import subprocess
import sys
import site

# Bundled builds (Android app, ISO, packaged installers) ship their dependencies
# and cannot run pip; they set PYOS_BUNDLED=1 and may include a local site-packages.
BUNDLED = os.environ.get("PYOS_BUNDLED") == "1"
_local_packages = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site-packages")
if os.path.isdir(_local_packages):
    site.addsitedir(_local_packages)

def install_requirements():
    """Install dependencies from boot-requirements.txt with platform-specific options."""
    if BUNDLED:
        return
    if not os.path.isfile("boot-requirements.txt"):
        return                                    # nothing to install (a packaged copy ships its libraries and may not carry the file)
    cmd = [sys.executable, "-m", "pip", "install", "-r", "boot-requirements.txt", "-U", "--quiet"]

    # Add --break-system-packages if running on Linux
    if platform.system() == "Linux":
        cmd.append("--break-system-packages")

    try:
        subprocess.run(cmd, check=True)
        os.system("cls" if os.name == "nt" else "clear")
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies. Make sure Python and pip are installed.")
        sys.exit(0)

install_requirements()

import json
from rich.console import Console
import users
import pyos
from pyos import settings
import shell
import core
import traceback
import time
from pathlib import Path

console = Console()

CONFIG_FILE = "config.json"
OSDATA_DIR = Path(".OSData")
FIRST_TIME_DONE_FILE = OSDATA_DIR / "OSFirstTimeDone.txt"

def first_time_done() -> bool:
    return FIRST_TIME_DONE_FILE.exists()

def mark_first_time_done():
    OSDATA_DIR.mkdir(exist_ok=True)
    FIRST_TIME_DONE_FILE.write_text("First time setup completed.")

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
    time.sleep(settings.boot_pause() * 3)
    if config['debug'] == "True":
        debug = "Yes"
        console.print("[bold yellow]Debug Mode is enabled on this OS.[/bold yellow]")
    elif config['debug'] == "False":
        debug = "No"
    else:
        debug = "No"
        console.print("[bold yellow]Debug Mode Setting is not defined. Defaulting to Disabled.[/bold yellow]")
    diagnostics = False
    if os.environ.get("PYOS_LIVE") == "1" or os.environ.get("PYOS_INSTALLED") == "1":
        from core import liveboot
        console.print("[dim]Press D now for a diagnostic start (verbose boot and a hardware report)...[/dim]")
        diagnostics = liveboot.key_pressed("d", 1.5)
        if diagnostics:
            debug = "Yes"
            console.print("[bold cyan]Diagnostic start.[/bold cyan]")
        core.apply_saved_hardware()        # keyboard layout, time zone, audio and Wi-Fi from last time
        liveboot.sync_clock_in_background(lambda text: pyos.log.log(text),
                                          lambda text: __import__("pyos.notify", fromlist=["notify"]).notify(text, title="Clock"))
        try:
            from core import persist
            persist.record_boot()          # when the data disk was last used (persist status)
        except Exception:
            pass
    core.boot_sequence(debug)
    if diagnostics:
        try:
            path = liveboot.save_diagnostics()
            console.print(f"[bold cyan]Diagnostics saved:[/bold cyan] {pyos.fs.display(path, tilde=True)} "
                          "[dim](after you log in: cat it, or send it with 'share')[/dim]")
        except Exception as e:
            console.print(f"[yellow]Could not save diagnostics: {e}[/yellow]")
    try:
        from core import whathappened
        whathappened.show(full=False)              # only says something after a power cut or a crash
    except Exception:
        pass

    just_set_up = False
    if not first_time_done():
        core.firsttimeuse()     # one guided flow: hardware (live ISO), account, preferences, updates, starter apps
        mark_first_time_done()
        just_set_up = True

    attempts = 0
    username = None

    if just_set_up and pyos.userinfo()[0]:
        # the setup just created the account and signed it in: no need to ask for the password again
        shell.start_shell(pyos.userinfo()[0])
    else:
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

