#!/usr/bin/env python3
"""Wi-Fi signal meter: a live reading of how strong your Wi-Fi signal is, so you can walk around and find the best spot. Shows signal
strength (dBm), quality, a bar and a short history graph. Works on Linux (including the PythonOS live ISO), reading the system's own
wireless statistics. Usage: wifimeter [seconds]  (default: until you press Ctrl+C)"""
import os
import sys
import time

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.text import Text

console = Console()
SPARK = " .:-=+*#"
PROC = "/proc/net/wireless"


def parse_proc(text):
    """/proc/net/wireless -> [{name, quality (0-100), dbm}]. The columns are: status, link quality, signal level, noise."""
    out = []
    for line in text.splitlines()[2:]:
        if ":" not in line:
            continue
        name, _, rest = line.partition(":")
        parts = rest.split()
        if len(parts) < 3:
            continue
        try:
            link = float(parts[1].rstrip("."))
            level = float(parts[2].rstrip("."))
        except ValueError:
            continue
        if level > 0:                                  # some drivers report 0-255 instead of dBm
            level -= 256 if level > 127 else 0
        out.append({"name": name.strip(), "quality": min(100, round(link / 70 * 100)), "dbm": level})
    return out


def read_interfaces():
    try:
        with open(PROC, encoding="utf-8") as f:
            return parse_proc(f.read())
    except OSError:
        return None


def quality_from_dbm(dbm):
    """A rough 0-100 quality from a dBm signal level: -50 and above is excellent, -90 and below is unusable."""
    return max(0, min(100, round(2 * (dbm + 100))))


def describe(dbm):
    if dbm >= -50:
        return "excellent", "bright_green"
    if dbm >= -60:
        return "very good", "green"
    if dbm >= -70:
        return "good", "yellow"
    if dbm >= -80:
        return "weak", "dark_orange"
    return "very weak", "red"


def spark(values, lo=-100, hi=-30):
    return "".join(SPARK[max(0, min(len(SPARK) - 1, int((v - lo) / (hi - lo) * (len(SPARK) - 1))))] for v in values)


def panel(reading, history):
    label, colour = describe(reading["dbm"])
    pct = quality_from_dbm(reading["dbm"])
    filled = pct // 5
    body = Text()
    body.append(f"{reading['name']}\n", style="bold")
    body.append(f"{reading['dbm']:.0f} dBm  ", style=f"bold {colour}")
    body.append(f"{label}\n", style=colour)
    body.append("#" * filled, style=colour)
    body.append("-" * (20 - filled) + f" {pct}%\n", style="dim")
    body.append(f"\n{spark(history[-40:])}\n", style="cyan")
    body.append(f"min {min(history):.0f}  avg {sum(history) / len(history):.0f}  max {max(history):.0f} dBm", style="dim")
    advice = {"excellent": "Great spot.", "very good": "A very good spot.", "good": "Fine for most things.",
              "weak": "Try moving closer to the router or away from walls.", "very weak": "Too weak: move much closer to the router."}[label]
    body.append(f"\n{advice}", style="italic")
    return Panel(body, title="Wi-Fi signal", subtitle="Ctrl+C to stop", border_style=colour, expand=False)


def main(args):
    if not sys.platform.startswith("linux"):
        console.print("[yellow]The signal meter reads Linux's wireless statistics, so it works on Linux and the PythonOS live ISO only.[/yellow]")
        return
    seconds = int(args[0]) if args and args[0].isdigit() else None
    readings = read_interfaces()
    if readings is None:
        console.print("[yellow]This system does not report wireless statistics.[/yellow]")
        return
    if not readings:
        console.print("[yellow]No Wi-Fi connection found. Connect first (hwsetup network), then run this again.[/yellow]")
        return
    history = []
    end = time.time() + seconds if seconds else None
    try:
        with Live(console=console, refresh_per_second=2, transient=False) as live:
            while end is None or time.time() < end:
                current = (read_interfaces() or [readings[0]])[0]
                history.append(current["dbm"])
                live.update(panel(current, history))
                time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    console.print(f"[dim]{len(history)} readings, average {sum(history) / max(1, len(history)):.0f} dBm.[/dim]")


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
