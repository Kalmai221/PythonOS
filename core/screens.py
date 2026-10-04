"""The shutdown, restart, factory-reset and crash screens - one themed implementation, scaled by the boot-speed setting."""
import json
import os
import shutil
import subprocess
import sys
import time

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from yaspin import yaspin

import pyos
from pyos import jobs, log, settings, theme

console = Console()


def _clear():
    os.system("cls" if os.name == "nt" else "clear")


def pause(seconds):
    """Sleep, scaled by the boot_speed setting (normal = as written, fast = about a quarter, instant = none)."""
    scale = settings.boot_pause() / 0.35
    if scale > 0 and seconds > 0:
        time.sleep(seconds * scale)


def _ok(label, detail=""):
    suffix = f" [dim]{detail}[/dim]" if detail else ""
    console.print(f"{theme.tag('success', '[  OK  ]')} {label}{suffix}")


def _step(label, action=None, seconds=0.6):
    """Show a spinner while a step runs, then an [ OK ] line. The action's return value (text) becomes the detail."""
    detail = ""
    if settings.boot_pause() > 0 and sys.stdout.isatty():
        with yaspin(text=label + "...", spinner="dots") as spinner:
            detail = action() if action else ""
            pause(seconds)
    else:
        detail = action() if action else ""
    _ok(label, detail or "")


# --------------------------------------------------------------------- actions
def _stop_jobs():
    running = [j for j in jobs.all_jobs() if j.status == "running"]
    for job in running:
        jobs.cancel(job.id)
    end = time.time() + 2
    while time.time() < end and any(j.status == "running" for j in running):
        time.sleep(0.05)
    return f"{len(running)} stopped" if running else ""


def _close_sessions():
    try:
        os.remove("current_user.json")
    except OSError:
        pass


def _flush():
    if hasattr(os, "sync"):
        try:
            os.sync()
        except OSError:
            pass


def factory_reset():
    """Erase accounts, settings, every user's files and installed packages. Returns a short description."""
    for name in ("current_user.json", "users.json", "current_directory.txt"):
        try:
            os.remove(name)
        except OSError:
            pass
    shutil.rmtree(".OSData", ignore_errors=True)            # settings, schedule, notifications, lockout, package records, caches
    base = pyos.fs.BASE_DIR
    if os.path.isdir(base):
        for entry in os.listdir(base):
            if entry in ("etc", "var"):
                continue                                        # the system layout stays
            target = os.path.join(base, entry)
            shutil.rmtree(target, ignore_errors=True) if os.path.isdir(target) else os.remove(target)
        for sub in ("tmp",):
            shutil.rmtree(os.path.join(base, sub), ignore_errors=True)
        shutil.rmtree(os.path.join(base, "var", "log"), ignore_errors=True)
    return "accounts, settings, files and packages"


# ------------------------------------------------------------------- sequences
def shutdown_sequence(kind="shutdown"):
    """kind: 'shutdown', 'restart' or 'wipe'. Shutdown and wipe end the process; restart returns so the caller can relaunch."""
    restarting, wiping = kind == "restart", kind == "wipe"
    log.log("System restarting" if restarting else "System factory reset" if wiping else "System shutting down", "WARN" if wiping else "INFO")
    _clear()
    title = "Restarting" if restarting else "Resetting to factory settings" if wiping else "Shutting down"
    console.print(Panel(f"[bold]{title}[/bold]", border_style=theme.style("border"), expand=False))

    _step("Stopping background jobs", _stop_jobs, 0.5)
    _step("Closing open applications", None, 0.5)
    _step("Signing out", _close_sessions, 0.4)
    if wiping:
        _step("Erasing accounts, settings, files and packages", factory_reset, 1.0)
    _step("Flushing the filesystem", _flush, 0.5)
    _step("Releasing the network", None, 0.4)

    if restarting:
        console.print(f"\n{theme.tag('warning', 'Restarting now...')}")
        pause(0.8)
        return
    countdown = max(0, round(3 * settings.boot_pause() / 0.35))
    if countdown and sys.stdout.isatty():
        with yaspin(text="Powering off", spinner="dots") as spinner:
            for remaining in range(countdown, 0, -1):
                spinner.text = f"Powering off in {remaining}..."
                time.sleep(1)
    console.print(f"\n{theme.tag('error', 'Shutdown complete.')}")
    if wiping:
        console.print(f"\n{theme.tag('warning', 'Power on the device for first-time setup.')}")
    sys.exit(0)


def crash_screen(error_message):
    """The blue screen: say what happened, record it, wait a moment, then restart PythonOS - unless it keeps crashing."""
    detail = str(error_message).strip()
    log.log("PythonOS crashed: " + detail.splitlines()[0][:200] if detail else "PythonOS crashed", "ERROR")

    # crash-loop guard: remember recent crashes
    record = os.path.join(".OSData", "crashes.json")
    now = time.time()
    try:
        with open(record, encoding="utf-8") as f:
            recent = [t for t in json.load(f) if now - t < 120]
    except (OSError, ValueError):
        recent = []
    recent.append(now)
    try:
        os.makedirs(".OSData", exist_ok=True)
        with open(record, "w", encoding="utf-8") as f:
            json.dump(recent, f)
    except OSError:
        pass
    looping = len(recent) >= 4

    _clear()
    body = Text()
    body.append(":(\n\n", style="bold white on blue")
    body.append("PythonOS ran into a problem.\n\n", style="bold white on blue")
    body.append(detail[-1800:] + "\n", style="white on blue")
    console.print(Panel(body, style="white on blue", border_style="white", title="[bold white on blue] STOP [/bold white on blue]"))

    if looping:
        console.print("\n[bold white on red] PythonOS keeps crashing, so it will not restart by itself. [/bold white on red]")
        console.print("The details above are also in the system log (logs). Start it again when you are ready.")
        sys.exit(1)
    wait = max(1, round(5 * settings.boot_pause() / 0.35)) if settings.boot_pause() > 0 else 1
    for remaining in range(wait, 0, -1):
        console.print(f"Restarting in {remaining}...", style="white on blue")
        time.sleep(1)
    _clear()
    sys.exit(subprocess.call([sys.executable, "main.py"]))
