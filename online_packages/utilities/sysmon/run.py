#!/usr/bin/env python3
"""System monitor: a live dashboard of CPU, memory, disk, network and (when allowed) the busiest processes."""
import os
import time

import psutil
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

try:
    from pyos import lockdown
    LOCKED = lockdown.enabled
except ImportError:
    LOCKED = lambda: False  # noqa: E731

console = Console()
HISTORY = 40
SPARK = " .:-=+*#"


def bar(percent, width=24):
    filled = int(round(width * percent / 100))
    colour = "green" if percent < 60 else "yellow" if percent < 85 else "red"
    return Text("#" * filled, style=colour) + Text("-" * (width - filled), style="dim")


def spark(values):
    if not values:
        return ""
    top = max(max(values), 1)
    return "".join(SPARK[min(len(SPARK) - 1, int(v / top * (len(SPARK) - 1)))] for v in values)


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def processes(limit=8):
    """The busiest processes. A locked-down system only shows PythonOS's own."""
    if LOCKED():
        try:
            me = psutil.Process(os.getpid())
            pool = [me] + me.children(recursive=True)
        except psutil.Error:
            return []
    else:
        pool = psutil.process_iter()
    rows = []
    for p in pool:
        try:
            rows.append((p.cpu_percent(None), p.memory_percent(), p.pid, p.name()))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    rows.sort(reverse=True)
    return rows[:limit]


class Monitor:
    def __init__(self):
        self.cpu_hist, self.net_hist = [], []
        self.last_net = psutil.net_io_counters()
        self.last_time = time.time()
        psutil.cpu_percent(None)
        for p in psutil.process_iter():
            try:
                p.cpu_percent(None)
            except psutil.Error:
                pass

    def frame(self):
        cpu = psutil.cpu_percent(None)
        self.cpu_hist = (self.cpu_hist + [cpu])[-HISTORY:]
        mem, swap = psutil.virtual_memory(), psutil.swap_memory()
        try:
            disk = psutil.disk_usage(os.path.abspath("files"))
        except OSError:
            disk = psutil.disk_usage(os.path.abspath("."))
        net = psutil.net_io_counters()
        now = time.time()
        span = max(0.1, now - self.last_time)
        down, up = (net.bytes_recv - self.last_net.bytes_recv) / span, (net.bytes_sent - self.last_net.bytes_sent) / span
        self.last_net, self.last_time = net, now
        self.net_hist = (self.net_hist + [down + up])[-HISTORY:]

        grid = Table.grid(padding=(0, 1))
        grid.add_column(width=7, style="bold")
        grid.add_column()
        grid.add_column()
        grid.add_row("CPU", bar(cpu), f"{cpu:5.1f}%  [cyan]{spark(self.cpu_hist)}[/cyan]")
        grid.add_row("Memory", bar(mem.percent), f"{mem.percent:5.1f}%  {human(mem.used)} of {human(mem.total)}")
        if swap.total:
            grid.add_row("Swap", bar(swap.percent), f"{swap.percent:5.1f}%  {human(swap.used)} of {human(swap.total)}")
        grid.add_row("Disk", bar(disk.percent), f"{disk.percent:5.1f}%  {human(disk.used)} of {human(disk.total)}")
        grid.add_row("Network", Text(""), f"down {human(down)}/s  up {human(up)}/s  [cyan]{spark(self.net_hist)}[/cyan]")
        parts = [Panel(grid, title="System monitor", subtitle="Ctrl+C to leave", border_style="blue")]

        table = Table(header_style="bold blue", expand=True, title="Busiest processes" + (" (PythonOS only)" if LOCKED() else ""))
        table.add_column("PID", justify="right")
        table.add_column("Name")
        table.add_column("CPU %", justify="right")
        table.add_column("Mem %", justify="right")
        for cpu_p, mem_p, pid, name in processes():
            table.add_row(str(pid), name, f"{cpu_p:.1f}", f"{mem_p:.1f}")
        parts.append(table)
        try:
            boot = time.time() - psutil.boot_time()
            parts.append(Text(f"Up {int(boot // 3600)}h {int(boot % 3600 // 60)}m   {psutil.cpu_count()} CPU(s)", style="dim"))
        except (OSError, AttributeError):
            pass
        return Group(*parts)


def snapshot():
    console.print(Monitor().frame())


def live(seconds=None):
    monitor = Monitor()
    time.sleep(0.6)                           # first CPU reading needs a short interval
    end = time.time() + seconds if seconds else None
    try:
        with Live(monitor.frame(), console=console, refresh_per_second=2, screen=False, transient=True) as view:
            while end is None or time.time() < end:
                time.sleep(1)
                view.update(monitor.frame())
    except KeyboardInterrupt:
        pass
    console.print(monitor.frame())


def execute(args=None):
    args = list(args or [])
    if args and args[0] in ("once", "snapshot"):
        snapshot()
    elif args and args[0].isdigit():
        live(int(args[0]))
    else:
        live()


if __name__ == "__main__":
    import sys
    execute(sys.argv[1:])
