import platform
import sys
import os
import psutil
from rich.console import Console
from rich.table import Table

# Command metadata
config = {
    "name": "sysinfo",
    "description": "Displays basic system information"
}

console = Console()

def get_system_info():
    # Create a table with headers for system information
    table = Table(show_header=True, header_style="bold cyan", title="System Information")

    # Add columns for the information we want to display
    table.add_column("Component", style="bold magenta", width=20)
    table.add_column("Details", style="green")

    # Get system information
    system_info = {
        "OS": platform.system(),
        "OS Version": platform.version(),
        "Machine": platform.machine(),
        "Processor": platform.processor(),
        "Python Version": sys.version,
        "Disk Usage": get_disk_usage(),
        "Memory Usage": get_memory_usage()
    }

    # Add rows to the table
    for key, value in system_info.items():
        table.add_row(key, value)

    # Display the table
    console.print(table)

def get_disk_usage():
    # Get disk usage statistics using psutil
    disk_usage = psutil.disk_usage('/')
    return f"{disk_usage.percent}% used of {disk_usage.total // (1024 ** 3)} GB"

def get_memory_usage():
    # Get memory usage statistics using psutil
    memory = psutil.virtual_memory()
    return f"{memory.percent}% used of {memory.total // (1024 ** 3)} GB"

# The execute function will be called when the user selects this program
def execute():
    get_system_info()
