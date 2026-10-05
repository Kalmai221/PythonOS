#!/usr/bin/env python3
"""System monitor: a live dashboard of CPU (overall and per core), memory, disk, network, temperature and battery, with history graphs and
alerts when a limit is crossed. Usage: sysmon  (live)  |  sysmon once  |  sysmon graph [cpu|mem|net] [seconds]  |  sysmon alerts  |
sysmon alerts set <cpu|mem|disk|battery|temp> <limit>  |  sysmon alerts reset"""
import os
import sys
import time

import psutil
from rich.console import Console, Group
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

try:
    from pyos import appdata, lockdown, notify
    import pyos
    LOCKED = lockdown.enabled
except ImportError:
    appdata = notify = pyos = None
    LOCKED = lambda: False  # noqa: E731

console = Console()
HISTORY = 60
SPARK = " .:-=+*#"
DEFAULT_LIMITS = {"cpu": 90, "mem": 90, "disk": 90, "battery": 15, "temp": 85}
LABELS = {"cpu": "CPU use above (%)", "mem": "Memory use above (%)", "disk": "Disk use above (%)", "battery": "Battery below (%)",
          "temp": "Temperature above (C)"}
CONSECUTIVE = 3                      # a limit must be crossed this many samples in a row before an alert
COOLDOWN = 300                       # seconds between repeats of the same alert


def bar(percent, width=24, invert=False):
    filled = int(round(width * percent / 100))
    bad = percent < 30 if invert else percent >= 85
    warn = percent < 50 if invert else percent >= 60
    colour = "red" if bad else "yellow" if warn else "green"
    return Text("#" * filled, style=colour) + Text("-" * (width - filled), style="dim")


def spark(values, top=None):
    if not values:
        return ""
    top = top or max(max(values), 1)
    return "".join(SPARK[min(len(SPARK) - 1, int(v / top * (len(SPARK) - 1)))] for v in values)


def graph(values, height=8, top=None, label=""):
    """A small column chart: one column per sample, `height` rows tall, scaled to `top` (or the largest value)."""
    top = top or max(max(values, default=1), 1)
    rows = []
    for level in range(height, 0, -1):
        threshold = top * (level - 0.5) / height
        axis = f"{top * level / height:6.0f} |" if level in (height, height // 2 + 1) else "       |"
        rows.append(axis + "".join("#" if v >= threshold else " " for v in values))
    rows.append("       +" + "-" * len(values))
    return "\n".join(rows + ([f"        {label}"] if label else []))


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def processes(limit=6):
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
            if p.pid == 0:
                continue                                      # Windows' "System Idle Process" is not a program
            rows.append((p.cpu_percent(None), p.memory_percent(), p.pid, p.name()))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    rows.sort(reverse=True)
    return rows[:limit]


def sensors():
    """(highest temperature in C or None, battery percent or None, plugged in or None)."""
    temp = None
    try:
        data = psutil.sensors_temperatures()
        values = [t.current for entries in (data or {}).values() for t in entries if t.current]
        temp = max(values) if values else None
    except (AttributeError, NotImplementedError, OSError):
        pass
    percent = plugged = None
    try:
        b = psutil.sensors_battery()
        if b:
            percent, plugged = b.percent, bool(b.power_plugged)
    except (AttributeError, NotImplementedError, OSError):
        pass
    return temp, percent, plugged


def load_limits():
    stored = appdata.load("sysmon", {}) if appdata else {}
    return {k: stored.get(k, v) for k, v in DEFAULT_LIMITS.items()}


class Monitor:
    def __init__(self, limits=None):
        self.limits = limits or dict(DEFAULT_LIMITS)
        self.cpu_hist, self.mem_hist, self.net_hist = [], [], []
        self.last_net = psutil.net_io_counters()
        self.last_time = time.time()
        self.strikes = {k: 0 for k in self.limits}
        self.last_alert = {}
        self.alerts = []                                     # alert messages currently active
        psutil.cpu_percent(None, percpu=True)
        for p in psutil.process_iter():
            try:
                p.cpu_percent(None)
            except psutil.Error:
                pass

    def sample(self):
        """Take one reading and update the histories and alerts. Returns a dict of the values."""
        cores = psutil.cpu_percent(None, percpu=True)
        cpu = sum(cores) / max(1, len(cores))
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
        temp, battery, plugged = sensors()
        self.cpu_hist = (self.cpu_hist + [cpu])[-HISTORY:]
        self.mem_hist = (self.mem_hist + [mem.percent])[-HISTORY:]
        self.net_hist = (self.net_hist + [down + up])[-HISTORY:]
        values = {"cpu": cpu, "mem": mem.percent, "disk": disk.percent, "battery": battery, "temp": temp}
        self.check_limits(values, plugged)
        return {"cores": cores, "cpu": cpu, "mem": mem, "swap": swap, "disk": disk, "down": down, "up": up, "temp": temp,
                "battery": battery, "plugged": plugged}

    def check_limits(self, values, plugged):
        self.alerts = []
        for key, limit in self.limits.items():
            value = values.get(key)
            if value is None or (key == "battery" and plugged):
                self.strikes[key] = 0
                continue
            crossed = value < limit if key == "battery" else value > limit
            self.strikes[key] = self.strikes[key] + 1 if crossed else 0
            if self.strikes[key] >= CONSECUTIVE:
                message = f"{LABELS[key].split(' (')[0]}: {value:.0f}{'C' if key == 'temp' else '%'} (limit {limit})"
                self.alerts.append(message)
                if notify and pyos and time.time() - self.last_alert.get(key, 0) > COOLDOWN:
                    self.last_alert[key] = time.time()
                    try:
                        notify.notify(message, title="System monitor", level="warn", user=pyos.userinfo()[0])
                    except Exception:
                        pass

    def frame(self, s):
        grid = Table.grid(padding=(0, 1))
        grid.add_column(width=8, style="bold")
        grid.add_column()
        grid.add_column()
        mem, swap, disk = s["mem"], s["swap"], s["disk"]
        grid.add_row("CPU", bar(s["cpu"]), f"{s['cpu']:5.1f}%  [cyan]{spark(self.cpu_hist, 100)}[/cyan]")
        grid.add_row("Memory", bar(mem.percent), f"{mem.percent:5.1f}%  {human(mem.used)} of {human(mem.total)}  [cyan]{spark(self.mem_hist, 100)}[/cyan]")
        if swap.total:
            grid.add_row("Swap", bar(swap.percent), f"{swap.percent:5.1f}%  {human(swap.used)} of {human(swap.total)}")
        grid.add_row("Disk", bar(disk.percent), f"{disk.percent:5.1f}%  {human(disk.used)} of {human(disk.total)}")
        grid.add_row("Network", Text(""), f"down {human(s['down'])}/s  up {human(s['up'])}/s  [cyan]{spark(self.net_hist)}[/cyan]")
        if s["battery"] is not None:
            grid.add_row("Battery", bar(s["battery"], invert=True), f"{s['battery']:.0f}% " + ("(plugged in)" if s["plugged"] else "(on battery)"))
        if s["temp"] is not None:
            grid.add_row("Temp", bar(min(100, s["temp"]), width=24), f"{s['temp']:.0f} C")
        parts = []
        if self.alerts:
            parts.append(Panel("\n".join(self.alerts), title="[bold red]Alert[/bold red]", border_style="red"))
        parts.append(Panel(grid, title="System monitor", subtitle="Ctrl+C to leave", border_style="blue"))

        cores = Table.grid(padding=(0, 2))
        per_row = 4 if console.width >= 100 else 2
        cells = [Text(f"{i:>2} ") + bar(c, 8) + Text(f" {c:3.0f}%") for i, c in enumerate(s["cores"])]
        for i in range(0, len(cells), per_row):
            cores.add_row(*cells[i:i + per_row])
        parts.append(Panel(cores, title=f"{len(s['cores'])} CPU core(s)", border_style="dim"))

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


def live(limits):
    monitor = Monitor(limits)
    time.sleep(0.6)                           # the first CPU reading needs a short interval
    try:
        with Live(monitor.frame(monitor.sample()), console=console, refresh_per_second=2, screen=False, transient=True) as view:
            while True:
                time.sleep(1)
                view.update(monitor.frame(monitor.sample()))
    except KeyboardInterrupt:
        pass
    console.print(monitor.frame(monitor.sample()))


def snapshot(limits):
    monitor = Monitor(limits)
    time.sleep(0.5)
    console.print(monitor.frame(monitor.sample()))


def show_graph(kind="cpu", seconds=60):
    """Sample for `seconds` and draw a chart of how the chosen value changed."""
    monitor = Monitor()
    seconds = max(10, min(300, seconds))
    values = []
    end = time.time() + seconds
    console.print(f"[dim]Sampling {kind} for {seconds} s (Ctrl+C to stop early)...[/dim]")
    try:
        while time.time() < end:
            time.sleep(1)
            s = monitor.sample()
            values.append({"cpu": s["cpu"], "mem": s["mem"].percent, "net": s["down"] + s["up"]}[kind])
    except KeyboardInterrupt:
        pass
    if not values:
        return
    top = 100 if kind != "net" else None
    unit = "%" if kind != "net" else " B/s"
    console.print(graph(values[-100:], 10, top, f"{kind}, last {len(values)} s   min {min(values):.0f}{unit}  avg {sum(values) / len(values):.0f}{unit}  max {max(values):.0f}{unit}"), markup=False)


def alerts(args):
    limits = load_limits()
    if args and args[0] == "reset":
        if appdata:
            appdata.save("sysmon", {})
        limits = dict(DEFAULT_LIMITS)
        console.print("[green]Limits are back to the defaults.[/green]")
    elif len(args) >= 3 and args[0] == "set" and args[1] in DEFAULT_LIMITS and args[2].lstrip("-").isdigit():
        limits[args[1]] = int(args[2])
        if appdata:
            appdata.save("sysmon", limits)
        console.print(f"[green]{LABELS[args[1]]}: {limits[args[1]]}[/green]")
    table = Table(header_style="bold blue", title="Alert limits")
    table.add_column("Alert when")
    table.add_column("Limit", justify="right")
    for key, label in LABELS.items():
        table.add_row(label, str(limits[key]))
    console.print(table)
    console.print("[dim]An alert fires after the limit is crossed for 3 readings in a row and arrives as a notification (at most every 5 minutes). "
                  "Change one: sysmon alerts set cpu 80[/dim]")


def execute(args=None):
    args = list(args or [])
    try:
        if args and args[0] in ("once", "snapshot"):
            snapshot(load_limits())
        elif args and args[0] == "graph":
            kind = args[1] if len(args) > 1 and args[1] in ("cpu", "mem", "net") else "cpu"
            seconds = int(args[-1]) if args[-1].isdigit() and len(args) > 1 else 60
            show_graph(kind, seconds)
        elif args and args[0] == "alerts":
            alerts(args[1:])
        else:
            live(load_limits())
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
