import psutil
from rich.table import Table
from rich.console import Console

config = {
    "name": "taskman",
    "description": "Runs the OS's Task Manager."
}

def execute():
    console = Console()

    # System usage summary
    total_cpu = psutil.cpu_percent(interval=1)
    total_memory = psutil.virtual_memory().percent
    total_processes = len(psutil.pids())

    console.print(f"\n[bold]System Usage:[/bold] CPU: {total_cpu}% | RAM: {total_memory}% | Running Processes: {total_processes}\n")

    # Table of processes
    table = Table(title="Task Manager")

    table.add_column("PID", style="cyan", justify="right")
    table.add_column("Name", style="magenta")
    table.add_column("CPU (%)", style="yellow", justify="right")
    table.add_column("Memory (MB)", style="green", justify="right")

    for proc in psutil.process_iter(attrs=['pid', 'name', 'cpu_percent', 'memory_info']):
        pid = proc.info['pid']
        name = proc.info['name']
        cpu = proc.info['cpu_percent']
        mem = f"{proc.info['memory_info'].rss / (1024 * 1024):.2f}"
        table.add_row(str(pid), name, f"{cpu:.1f}", mem)

    console.print(table)
