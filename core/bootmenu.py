"""The boot menu: choose how PythonOS starts. Shown by pressing M at the start (ISO and VM images), or with `main.py --menu` on any export."""
from rich.console import Console
from rich.panel import Panel

console = Console()
CHOICES = [
    ("1", "Start normally", "normal"),
    ("2", "Safe mode (only the system: no marketplace apps, startup commands or background checks)", "safe"),
    ("3", "Diagnostic start (verbose, and saves a hardware report)", "diagnostics"),
    ("4", "Emergency console (read the logs and crash reports; no login needed)", "emergency"),
    ("5", "Restart", "restart"),
    ("6", "Power off", "off"),
]


def show(ask=input):
    """Show the menu until a start mode is chosen. Returns 'normal', 'safe' or 'diagnostics'."""
    while True:
        lines = "\n".join(f"  [bold]{key}[/bold]  {text}" for key, text, _mode in CHOICES)
        console.print(Panel(f"[bold]PythonOS boot menu[/bold]\n\n{lines}", border_style="cyan", expand=False))
        try:
            pick = ask("Choose 1-6 (Enter = start normally): ").strip() or "1"
        except (EOFError, KeyboardInterrupt):
            return "normal"
        mode = next((m for key, _t, m in CHOICES if key == pick), None)
        if mode in ("normal", "safe", "diagnostics"):
            return mode
        if mode == "emergency":
            from core import emergency
            emergency.run()
        elif mode == "restart":
            from core import screens
            screens.relaunch()
        elif mode == "off":
            import core
            core.simulate_shutdown()
            return "normal"
        else:
            console.print("[yellow]Type a number from 1 to 6.[/yellow]")
