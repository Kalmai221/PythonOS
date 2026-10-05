import ast
import os
import time

from rich.console import Console
from rich.table import Table

from core import bootlog
from pyos import settings

console = Console()
config = {"name": "bootspeed", "description": "How fast does PythonOS start, and what is slowing it down? Runs a quick benchmark."}


def _timed(fn):
    t0 = time.perf_counter()
    fn()
    return (time.perf_counter() - t0) * 1000


def _parse_folder(folder):
    for name in os.listdir(folder):
        if name.endswith(".py"):
            with open(os.path.join(folder, name), encoding="utf-8") as f:
                ast.parse(f.read())


def execute(args=None):
    console.print("[bold]Boot speed[/bold]")
    boots = bootlog.load()
    if boots:
        recent = [b["total_ms"] for b in boots]
        avg = sum(recent) / len(recent)
        anim = sum(b.get("animation_ms", 0) for b in boots) / len(boots)
        console.print(f"Last {len(boots)} boot(s): average [bold]{avg / 1000:.2f} s[/bold] "
                      f"(fastest {min(recent) / 1000:.2f} s, slowest {max(recent) / 1000:.2f} s)")
        table = Table(title="Average time per step", header_style="bold blue")
        table.add_column("Step")
        table.add_column("ms", justify="right")
        table.add_column("")
        steps = bootlog.averages(boots)
        top = max(steps.values()) or 1
        for name, ms in steps.items():
            table.add_row(name, f"{ms:.0f}", "[cyan]" + "#" * max(1, int(20 * ms / top)) + "[/cyan]")
        console.print(table)
        if anim > 50:
            console.print(f"The boot animation pauses add about [bold]{anim / 1000:.2f} s[/bold] "
                          f"(boot_speed is '{settings.get('boot_speed')}'). [dim]settings set boot_speed instant[/dim] removes them.")
    else:
        console.print("[dim]No saved boots yet; showing the benchmark only.[/dim]")

    console.print("\n[bold]Benchmark now[/bold] (this machine, right now)")
    results = [("Parse every command file", _timed(lambda: _parse_folder("commands"))),
               ("Parse every system file", _timed(lambda: [_parse_folder(f) for f in ("pyos", "core")])),
               ("Read settings and accounts", _timed(lambda: (settings.load(), open("config.json").read()))),
               ("Write and read a small file", _timed(lambda: _disk()))]
    table = Table(header_style="bold blue")
    table.add_column("Test")
    table.add_column("ms", justify="right")
    for name, ms in results:
        table.add_row(name, f"{ms:.1f}")
    console.print(table)
    slow = max(results, key=lambda r: r[1])
    console.print(f"[dim]Slowest: {slow[0]}. A slow disk or storage card makes every step slower.[/dim]")
    return True


def _disk():
    path = os.path.join(".OSData", "bench.tmp")
    os.makedirs(".OSData", exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"x" * 200_000)
    with open(path, "rb") as f:
        f.read()
    os.remove(path)
