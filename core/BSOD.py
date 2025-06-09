import sys
import time
import os
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
import pyos

# Initialize the console
console = Console()

def simulate_bsod(error_message):
    os.system("clear") 
    # Start creating the BSOD text with the basic error message
    bsod_text = Text(f"*** STOP: 0x000000D1 ***\n\n{error_message}\n", style="bold white on blue")

    # Display the BSOD in a blue-colored screen with the initial error message
    console.print(Panel(bsod_text, style="bold white on blue"))

    # Simulate a short delay before restarting
    time.sleep(5)

    # Clear the terminal and print the rebooting message
    os.system("clear")  # Clear the terminal
    bsod_text = Text(f"*** STOP: 0x000000D1 ***\n\n{error_message}\n", style="bold white on blue")  # Reassign text
    bsod_text.append("\nSystem Rebooting...")

    # Clear the terminal again and show the final reboot message
    os.system("clear")
    console.print(Panel(bsod_text, style="bold white on blue"))

    # Simulate a short delay before rebooting
    time.sleep(2)

    # Simulate rebooting (just restart the script)
    pyos.system("clear")
    os.system("python main.py")  # Replace with the appropriate path to restart your script
    sys.exit(0)
