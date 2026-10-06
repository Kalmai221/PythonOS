#!/usr/bin/env python3
"""System monitor: a live dashboard of PythonOS itself - its CPU use, its memory (against the memory PythonOS owns), its tasks, its storage,
and the machine's temperature and battery - with history graphs and alerts when a limit is crossed. It only looks at PythonOS: other
programs on the computer (on Windows: OneDrive, the browser...) are not shown and are not counted.
Usage: sysmon  (live)  |  sysmon once  |  sysmon graph [cpu|mem] [seconds]  |  sysmon alerts  |
sysmon alerts set <cpu|mem|disk|battery|temp> <limit>  |  sysmon alerts reset"""
import json
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
except Exception:                                  # run on its own, outside PythonOS
    appdata = notify = pyos = lockdown = None

console = Console()
HISTORY = 60
SPARK = " .:-=+*#"
DEFAULT_LIMITS = {"cpu": 90, "mem": 90, "disk": 90, "battery": 15, "temp": 85}
LABELS = {"cpu": "PythonOS CPU use above (%)", "mem": "PythonOS memory use above (%)", "disk": "Disk use above (%)",
          "battery": "Battery below (%)", "temp": "Temperature above (C)"}
CONSECUTIVE = 3                      # a limit must be crossed this many samples in a row before an alert
COOLDOWN = 300                       # seconds between repeats of the same alert
FRESH = 5                            # seconds a task list from PythonOS counts as current


def bar(percent, width=24, invert=False):
    percent = max(0.0, min(100.0, percent or 0.0))
    filled = int(round(width * percent / 100))
    bad = percent < 30 if invert else percent >= 85
    warn = percent < 50 if invert else percent >= 60
    colour = "red" if bad else "yellow" if warn else "green"
    return Text("#" * filled, style=colour) + Text("-" * (width - filled), style="dim")


def spark(values, top=None):
    if not values:
        return ""
    top = top or max(max(values), 1)
    return "".join(SPARK[max(0, min(len(SPARK) - 1, int(v / top * (len(SPARK) - 1))))] for v in values)


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
    n = n or 0
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def safe(fn, default=None):
    """Any one reading may be unavailable (a locked-down system, a virtual machine without sensors): the monitor goes on without it."""
    try:
        return fn()
    except Exception:
        return default


# ------------------------------------------------------------------------------------------ what PythonOS is
def task_list():
    """PythonOS's own task list, as published by the running system (None if it is not there or is stale)."""
    try:
        with open(os.path.join(".OSData", "tasks.json"), encoding="utf-8") as f:
            data = json.load(f)
        if time.time() - float(data.get("at", 0)) <= FRESH:
            return data
    except Exception:
        pass
    return None


def find_root(data=None):
    """The PythonOS process: the one the task list came from, else the nearest ancestor running main.py, else this program itself."""
    me = psutil.Process(os.getpid())
    pid = (data or {}).get("pid")
    if pid:
        try:
            return psutil.Process(int(pid))
        except (psutil.Error, ValueError):
            pass
    try:
        for parent in me.parents():
            if any(part.endswith("main.py") for part in (safe(parent.cmdline, []) or [])):
                return parent
    except Exception:
        pass
    return me


def memory_budget():
    """The memory PythonOS owns: its limit (see free), or all the memory the machine has."""
    if pyos is not None:
        value = safe(lambda: pyos.resources.budget(), 0)
        if value:
            return int(value)
    return int(psutil.virtual_memory().total)


def processes(root, limit=6):
    """(cpu %, memory %, pid, name) for PythonOS's own processes when its task list is not available."""
    budget = memory_budget()
    rows = []
    for p in [root] + safe(lambda: root.children(recursive=True), []):
        try:
            rows.append((p.cpu_percent(None), p.memory_info().rss * 100.0 / budget, p.pid, p.name()))
        except (psutil.Error, OSError):
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
    except Exception:
        pass
    percent = plugged = None
    try:
        b = psutil.sensors_battery()
        if b:
            percent, plugged = b.percent, bool(b.power_plugged)
    except Exception:
        pass
    return temp, percent, plugged


def load_limits():
    stored = safe(lambda: appdata.load("sysmon", {}), {}) if appdata else {}
    stored = stored if isinstance(stored, dict) else {}
    limits = {}
    for key, default in DEFAULT_LIMITS.items():
        value = stored.get(key, default)
        limits[key] = value if isinstance(value, int) and not isinstance(value, bool) else default
    return limits


class Monitor:
    def __init__(self, limits=None):
        self.limits = limits or dict(DEFAULT_LIMITS)
        self.cpu_hist, self.mem_hist = [], []
        self.strikes = {k: 0 for k in self.limits}
        self.last_alert = {}
        self.alerts = []                                     # alert messages currently active
        self.cores = psutil.cpu_count() or 1
        self.last_cpu = {}                                   # pid -> cpu seconds at the last sample
        self.last_time = time.time()
        self.files_size, self.files_at = 0, 0.0
        self.root = find_root(task_list())
        self.started = safe(self.root.create_time, time.time())
        self.sample_cpu()                                    # the first reading is the starting point

    def tree(self):
        procs = [self.root] + safe(lambda: self.root.children(recursive=True), [])
        return procs

    def sample_cpu(self):
        """PythonOS's CPU use as a percent of the whole machine: the CPU time its processes used since the last look."""
        used, now = 0.0, time.time()
        seen = {}
        for p in self.tree():
            try:
                t = p.cpu_times()
                total = t.user + t.system
            except (psutil.Error, OSError):
                continue
            seen[p.pid] = total
            used += max(0.0, total - self.last_cpu.get(p.pid, total))
        self.last_cpu = seen
        span = max(0.1, now - self.last_time)
        self.last_time = now
        return min(100.0, used / span / self.cores * 100.0)

    def storage(self):
        """(PythonOS's own files in bytes, disk used, disk total, disk percent). The folder is measured every 15 seconds."""
        folder = os.path.abspath("files")
        if time.time() - self.files_at > 15:
            total, count = 0, 0
            for base, _dirs, names in os.walk(folder):
                for name in names:
                    count += 1
                    if count > 30000:
                        break
                    total += safe(lambda: os.path.getsize(os.path.join(base, name)), 0)
                if count > 30000:
                    break
            self.files_size, self.files_at = total, time.time()
        disk = safe(lambda: psutil.disk_usage(folder)) or safe(lambda: psutil.disk_usage(os.path.abspath(".")))
        if disk is None:
            return self.files_size, 0, 0, 0.0
        return self.files_size, disk.used, disk.total, disk.percent

    def sample(self):
        """Take one reading and update the histories and alerts. Returns a dict of the values."""
        cpu = self.sample_cpu()
        procs = self.tree()
        used = 0
        threads = 0
        for p in procs:
            used += safe(lambda: p.memory_info().rss, 0)
            threads += safe(p.num_threads, 0)
        budget = memory_budget()
        mem_percent = min(100.0, used * 100.0 / budget) if budget else 0.0
        files, disk_used, disk_total, disk_percent = self.storage()
        connections = 0
        for p in procs:
            getter = getattr(p, "net_connections", None) or getattr(p, "connections", None)
            connections += len(safe(getter, []) or []) if getter else 0
        temp, battery, plugged = sensors()
        self.cpu_hist = (self.cpu_hist + [cpu])[-HISTORY:]
        self.mem_hist = (self.mem_hist + [mem_percent])[-HISTORY:]
        values = {"cpu": cpu, "mem": mem_percent, "disk": disk_percent, "battery": battery, "temp": temp}
        self.check_limits(values, plugged)
        return {"cpu": cpu, "mem_used": min(used, budget) if budget else used, "mem_total": budget, "mem": mem_percent,
                "files": files, "disk_used": disk_used, "disk_total": disk_total, "disk": disk_percent,
                "processes": len(procs), "threads": threads, "connections": connections,
                "temp": temp, "battery": battery, "plugged": plugged}

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
        width = console.width
        grid = Table.grid(padding=(0, 1))
        grid.add_column(min_width=8, no_wrap=True, style="bold")
        grid.add_column(no_wrap=True)
        grid.add_column(overflow="fold")
        bar_width = 24 if width >= 100 else 14
        trend = width >= 100
        grid.add_row("CPU", bar(s["cpu"], bar_width), f"{s['cpu']:5.1f}%" + (f"  [cyan]{spark(self.cpu_hist, 100)}[/cyan]" if trend else ""))
        grid.add_row("Memory", bar(s["mem"], bar_width), f"{s['mem']:5.1f}%  {human(s['mem_used'])} of {human(s['mem_total'])}")
        grid.add_row("Storage", bar(s["disk"], bar_width), f"{s['disk']:5.1f}%  files {human(s['files'])}; disk {human(s['disk_used'])}/{human(s['disk_total'])}")
        grid.add_row("Tasks", Text(""), f"{s['processes']} proc, {s['threads']} threads, {s['connections']} connections")
        if s["battery"] is not None:
            grid.add_row("Battery", bar(s["battery"], bar_width, invert=True),
                         f"{s['battery']:.0f}% " + ("(plugged in)" if s["plugged"] else "(on battery)"))
        if s["temp"] is not None:
            grid.add_row("Temp", bar(min(100, s["temp"]), bar_width), f"{s['temp']:.0f} C")
        parts = []
        if self.alerts:
            parts.append(Panel("\n".join(self.alerts), title="[bold red]Alert[/bold red]", border_style="red"))
        up = max(0, time.time() - self.started)
        parts.append(Panel(grid, title="PythonOS monitor", subtitle=f"up {int(up // 3600)}h {int(up % 3600 // 60)}m {int(up % 60)}s - Ctrl+C to leave",
                           border_style="blue"))

        # the tasks inside PythonOS; fits what is left of the screen so the display never scrolls
        grid_rows = 4 + (s["battery"] is not None) + (s["temp"] is not None)
        spare = max(3, console.height - (grid_rows + 2 + (3 if self.alerts else 0) + 6))
        data = task_list()
        table = Table(header_style="bold blue", expand=True, title="PythonOS tasks")
        table.add_column("PID", justify="right")
        table.add_column("Task", no_wrap=True, overflow="ellipsis")
        table.add_column("State")
        table.add_column("CPU %", justify="right")
        table.add_column("Memory", justify="right")
        if data and data.get("tasks"):
            rows = sorted(data["tasks"], key=lambda t: (t.get("cpu_percent") or 0, t.get("rss") or 0), reverse=True)[:spare]
            for t in rows:
                table.add_row(str(t["pid"]), t.get("name", "?") + (f" ({t['cmd']})" if t.get("cmd") not in (None, t.get("name")) and width >= 90 else ""),
                              t.get("state", ""), f"{t.get('cpu_percent', 0):.1f}", human(t.get("rss", 0)))
        else:
            table.title = "PythonOS processes"
            for cpu_p, mem_p, pid, name in processes(self.root, spare):
                table.add_row(str(pid), name, "", f"{cpu_p:.1f}", f"{mem_p:.1f}%")
        parts.append(table)
        return Group(*parts)


def live(limits):
    monitor = Monitor(limits)
    time.sleep(0.8)                           # the first CPU reading needs a short interval
    try:
        with Live(monitor.frame(monitor.sample()), console=console, refresh_per_second=2, screen=False, transient=True,
                  vertical_overflow="crop") as view:
            while True:
                time.sleep(1)
                view.update(monitor.frame(monitor.sample()))
    except KeyboardInterrupt:
        pass
    console.print(monitor.frame(monitor.sample()))


def snapshot(limits):
    monitor = Monitor(limits)
    time.sleep(0.8)
    console.print(monitor.frame(monitor.sample()))


def show_graph(kind="cpu", seconds=60):
    """Sample for `seconds` and draw a chart of how PythonOS's CPU or memory changed."""
    monitor = Monitor()
    seconds = max(10, min(300, seconds))
    values = []
    end = time.time() + seconds
    console.print(f"[dim]Sampling PythonOS {kind} for {seconds} s (Ctrl+C to stop early)...[/dim]")
    try:
        while time.time() < end:
            time.sleep(1)
            s = monitor.sample()
            values.append(s["cpu"] if kind == "cpu" else s["mem"])
    except KeyboardInterrupt:
        pass
    if not values:
        return
    console.print(graph(values[-100:], 10, 100, f"{kind}, last {len(values)} s   min {min(values):.0f}%  avg {sum(values) / len(values):.0f}%  "
                                              f"max {max(values):.0f}%"), markup=False)


def alerts(args):
    limits = load_limits()
    if args and args[0] == "reset":
        if appdata:
            safe(lambda: appdata.save("sysmon", {}))
        limits = dict(DEFAULT_LIMITS)
        console.print("[green]Limits are back to the defaults.[/green]")
    elif len(args) >= 3 and args[0] == "set" and args[1] in DEFAULT_LIMITS and args[2].lstrip("-").isdigit():
        limits[args[1]] = int(args[2])
        if appdata:
            safe(lambda: appdata.save("sysmon", limits))
        console.print(f"[green]{LABELS[args[1]]}: {limits[args[1]]}[/green]")
    elif args:
        console.print("[yellow]Usage: sysmon alerts [set <cpu|mem|disk|battery|temp> <limit> | reset][/yellow]")
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
            kind = args[1] if len(args) > 1 and args[1] in ("cpu", "mem") else "cpu"
            if len(args) > 1 and args[1] == "net":
                console.print("[yellow]Network use is not shown: it cannot be told apart from the rest of the computer's.[/yellow]")
            seconds = int(args[-1]) if len(args) > 1 and args[-1].isdigit() else 60
            show_graph(kind, seconds)
        elif args and args[0] == "alerts":
            alerts(args[1:])
        else:
            live(load_limits())
    except (KeyboardInterrupt, EOFError):
        console.print()
    except Exception as e:                                      # say what went wrong instead of a traceback
        console.print(f"[red]sysmon could not read this system: {type(e).__name__}: {e}[/red]")
        return False


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
