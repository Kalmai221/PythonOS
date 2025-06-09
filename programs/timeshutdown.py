import pyos
from rich.console import Console
from datetime import datetime, timedelta
import re
import threading
import time

console = Console()

config = {
    "name": "timeshutdown",
    "description": "Schedule system shutdown with flexible time units"
}

def parse_delay(input_str: str) -> timedelta:
    pattern = r"^(\d+)([smhdSMHD]?)$"
    match = re.match(pattern, input_str.strip())
    if not match:
        raise ValueError("Invalid time format. Use number followed by s, m, h, or d (e.g. 10m, 2h)")
    value, unit = match.groups()
    value = int(value)
    unit = unit.lower()

    if unit == "s" or unit == "":
        return timedelta(seconds=value)
    elif unit == "m":
        return timedelta(minutes=value)
    elif unit == "h":
        return timedelta(hours=value)
    elif unit == "d":
        return timedelta(days=value)
    else:
        raise ValueError("Unknown time unit")

def countdown_shutdown(delay: timedelta):
    shutdown_time = datetime.now() + delay
    console.print(f"System will shutdown at [bold cyan]{shutdown_time.strftime('%Y-%m-%d %H:%M:%S')}[/bold cyan]")

    while datetime.now() < shutdown_time:
        remaining = shutdown_time - datetime.now()
        console.print(f"Time remaining: {str(remaining).split('.')[0]}", end="\r")
        time.sleep(1)
    console.print("\nShutting down now...")
    pyos.shutdown()

def execute():
    try:
        user_input = input("Shutdown after (e.g. 10s, 5m, 2h, 1d): ")
        delay = parse_delay(user_input)
    except ValueError as e:
        console.print(f"[bold red]{e}[/bold red]")
        return

    # Start the countdown in a separate thread so it doesn't block main thread
    t = threading.Thread(target=countdown_shutdown, args=(delay,), daemon=True)
    t.start()

    # Main thread can do other things or wait for thread to finish
    t.join()  # Wait for shutdown countdown to complete before exiting execute()
