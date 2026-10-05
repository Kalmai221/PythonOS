#!/usr/bin/env python3
"""Speed test: measures your internet latency, download speed and upload speed using Cloudflare's public test servers
(speed.cloudflare.com). It transfers some data (about 25 MB down and 8 MB up by default; 'speedtest quick' uses much less). Results are
saved so you can see how your connection changes. Usage: speedtest [quick|full|history]"""
import statistics
import sys
import time

import requests
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
BASE = "https://speed.cloudflare.com"
SIZES = {"quick": (2_000_000, 1_000_000), "normal": (25_000_000, 8_000_000), "full": (100_000_000, 25_000_000)}
HEADERS = {"User-Agent": "PythonOS-speedtest/1.0"}


def mbps(nbytes, seconds):
    """Megabits per second."""
    return nbytes * 8 / 1_000_000 / seconds if seconds > 0 else 0.0


def latency(samples=8):
    """(median ms, jitter ms, loss %) from small requests."""
    times, lost = [], 0
    for _ in range(samples):
        start = time.perf_counter()
        try:
            requests.get(f"{BASE}/__down?bytes=0", headers=HEADERS, timeout=5)
            times.append((time.perf_counter() - start) * 1000)
        except requests.RequestException:
            lost += 1
        time.sleep(0.05)
    if not times:
        raise requests.ConnectionError("no reply from the test server")
    jitter = statistics.mean(abs(a - b) for a, b in zip(times, times[1:])) if len(times) > 1 else 0.0
    return statistics.median(times), jitter, 100 * lost / samples


def download(nbytes, progress=None, task=None):
    start, got = time.perf_counter(), 0
    with requests.get(f"{BASE}/__down?bytes={nbytes}", headers=HEADERS, stream=True, timeout=30) as r:
        r.raise_for_status()
        for chunk in r.iter_content(65536):
            got += len(chunk)
            if progress:
                progress.update(task, completed=got)
    return mbps(got, time.perf_counter() - start)


def upload(nbytes, progress=None, task=None):
    payload = bytes(nbytes)
    start = time.perf_counter()

    def body():
        sent = 0
        view = memoryview(payload)
        while sent < nbytes:
            piece = view[sent:sent + 65536]
            sent += len(piece)
            if progress:
                progress.update(task, completed=sent)
            yield bytes(piece)

    r = requests.post(f"{BASE}/__up", data=body(), headers={**HEADERS, "Content-Type": "application/octet-stream"}, timeout=60)
    r.raise_for_status()
    return mbps(nbytes, time.perf_counter() - start)


def rating(down):
    if down >= 200:
        return "excellent: fine for 4K streaming and big downloads"
    if down >= 50:
        return "very good: HD video calls and streaming for several people"
    if down >= 15:
        return "good: video streaming and calls are fine"
    if down >= 5:
        return "okay: browsing and music are fine; video may buffer"
    return "slow: pages and downloads will feel slow"


def run(mode="normal"):
    down_bytes, up_bytes = SIZES[mode]
    console.print(f"[bold]Speed test[/bold] ({mode}): about {(down_bytes + up_bytes) / 1_000_000:.0f} MB of data will be transferred.")
    try:
        with console.status("Measuring latency..."):
            ping, jitter, loss = latency()
        with Progress(TextColumn("{task.description}"), BarColumn(), TextColumn("{task.percentage:>3.0f}%"), TimeElapsedColumn(),
                      console=console, transient=True) as progress:
            down = download(down_bytes, progress, progress.add_task("Download", total=down_bytes))
            up = upload(up_bytes, progress, progress.add_task("Upload  ", total=up_bytes))
    except requests.RequestException as e:
        console.print(f"[red]The test could not finish: {str(e)[:120]}. Check your internet connection.[/red]")
        return None
    table = Table(show_header=False, box=None)
    table.add_row("Latency", f"{ping:.0f} ms  (jitter {jitter:.0f} ms, loss {loss:.0f}%)")
    table.add_row("Download", f"[bold green]{down:.1f} Mbit/s[/bold green]")
    table.add_row("Upload", f"[bold cyan]{up:.1f} Mbit/s[/bold cyan]")
    console.print(table)
    console.print(f"[dim]Your connection is {rating(down)}.[/dim]")
    result = {"time": time.strftime("%Y-%m-%d %H:%M"), "ping": round(ping), "down": round(down, 1), "up": round(up, 1)}
    if appdata:
        history = appdata.load("speedtest", [])
        history.append(result)
        appdata.save("speedtest", history[-50:])
    return result


def history():
    rows = appdata.load("speedtest", []) if appdata else []
    if not rows:
        console.print("[dim]No tests saved yet. Run: speedtest[/dim]")
        return
    table = Table(header_style="bold blue", title="Earlier tests")
    for col in ("When", "Ping", "Down (Mbit/s)", "Up (Mbit/s)"):
        table.add_column(col, justify="right" if col != "When" else "left")
    for r in rows[-15:]:
        table.add_row(r["time"], f"{r['ping']} ms", f"{r['down']}", f"{r['up']}")
    console.print(table)
    best = max(rows, key=lambda r: r["down"])
    console.print(f"[dim]Average download {statistics.mean(r['down'] for r in rows):.1f} Mbit/s; best {best['down']} on {best['time']}.[/dim]")


def main(args):
    mode = args[0] if args else "normal"
    if mode == "history":
        history()
    elif mode in ("quick", "full", "normal"):
        run(mode)
    else:
        console.print("speedtest [quick | full | history]")


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
