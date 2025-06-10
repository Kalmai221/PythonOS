#!/usr/bin/env python3
import psutil
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, IntPrompt
from rich.text import Text

console = Console()

config = {
    "name": "taskman",
    "description": "Runs Task Manager."
}

def get_processes():
    procs = []
    for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
        try:
            info = proc.info
            procs.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return procs

def show_processes(procs, sort_by="cpu_percent", reverse=True, limit=20):
    table = Table(title="Task Manager", show_lines=True)
    table.add_column("PID", justify="right", style="cyan")
    table.add_column("Name", style="magenta")
    table.add_column("CPU %", justify="right", style="green")
    table.add_column("Memory %", justify="right", style="yellow")

    procs = sorted(procs, key=lambda p: p.get(sort_by, 0) or 0, reverse=reverse)
    for proc in procs[:limit]:
        table.add_row(
            str(proc['pid']),
            proc['name'] or "",
            f"{proc['cpu_percent']:.1f}",
            f"{proc['memory_percent']:.1f}"
        )
    console.print(table)

def kill_process(pid):
    try:
        proc = psutil.Process(pid)
        proc.terminate()
        proc.wait(3)
        console.print(f"[green]Process {pid} terminated successfully.[/green]")
    except psutil.NoSuchProcess:
        console.print(f"[red]Process {pid} does not exist.[/red]")
    except psutil.AccessDenied:
        console.print(f"[red]Permission denied to kill process {pid}.[/red]")
    except psutil.TimeoutExpired:
        console.print(f"[yellow]Process {pid} did not terminate in time.[/yellow]")

def main():
    sort_by = "cpu_percent"
    reverse = True
    limit = 20

    while True:
        console.clear()
        procs = get_processes()
        show_processes(procs, sort_by, reverse, limit)

        console.print("\nCommands:")
        console.print("[b]kill <pid>[/b] — Kill process")
        console.print("[b]sort <field>[/b] — Sort by cpu, mem, pid, name")
        console.print("[b]limit <number>[/b] — Show top N processes")
        console.print("[b]refresh[/b] — Refresh list")
        console.print("[b]quit[/b] — Exit\n")

        cmd = Prompt.ask("Enter command").strip().lower()

        if cmd == "quit":
            break
        elif cmd.startswith("kill"):
            parts = cmd.split()
            if len(parts) != 2 or not parts[1].isdigit():
                console.print("[red]Usage: kill <pid>[/red]")
            else:
                kill_process(int(parts[1]))
        elif cmd.startswith("sort"):
            parts = cmd.split()
            if len(parts) != 2:
                console.print("[red]Usage: sort <field>[/red]")
            else:
                field = parts[1]
                if field in ["cpu", "cpu_percent"]:
                    sort_by = "cpu_percent"
                    reverse = True
                elif field in ["mem", "memory", "memory_percent"]:
                    sort_by = "memory_percent"
                    reverse = True
                elif field == "pid":
                    sort_by = "pid"
                    reverse = False
                elif field == "name":
                    sort_by = "name"
                    reverse = False
                else:
                    console.print("[red]Invalid sort field. Use cpu, mem, pid, or name.[/red]")
        elif cmd.startswith("limit"):
            parts = cmd.split()
            if len(parts) != 2 or not parts[1].isdigit():
                console.print("[red]Usage: limit <number>[/red]")
            else:
                limit = max(1, int(parts[1]))
        elif cmd == "refresh":
            continue
        else:
            console.print("[red]Unknown command.[/red]")

        console.print("\nPress Enter to continue...")
        input()

if __name__ == "__main__":
    main()

def execute():
    main()