#!/usr/bin/env python3
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.spinner import Spinner
from rich import box
import subprocess
import sys
import shutil

console = Console()

def is_installed(cmd):
    return shutil.which(cmd) is not None

def install_dependencies():
    console.print(Panel("Checking & installing dependencies...", style="cyan", box=box.ROUNDED))

    # Check mpv
    if not is_installed("mpv"):
        console.print("[yellow]mpv is not installed.[/yellow]")
        if Confirm.ask("Install mpv via apt? (Requires sudo)", default=True):
            if shutil.which("sudo") is None:
                console.print("[red]sudo not found. Please install mpv manually.[/red]")
                sys.exit(1)
            try:
                subprocess.run(["sudo", "apt", "install", "-y", "mpv"], check=True)
            except subprocess.CalledProcessError:
                console.print("[red]Failed to install mpv. Please install it manually.[/red]")
                sys.exit(1)
        else:
            console.print("[red]mpv is required. Exiting.[/red]")
            sys.exit(1)

    # Check yt-dlp
    try:
        import yt_dlp  # noqa: F401
    except ImportError:
        console.print("[yellow]yt-dlp is not installed.[/yellow]")
        if Confirm.ask("Install yt-dlp via pip?", default=True):
            try:
                subprocess.run([sys.executable, "-m", "pip", "install", "--user", "yt-dlp"], check=True)
            except subprocess.CalledProcessError:
                console.print("[red]Failed to install yt-dlp. Please install it manually.[/red]")
                sys.exit(1)
        else:
            console.print("[red]yt-dlp is required. Exiting.[/red]")
            sys.exit(1)

def search_youtube(query, max_results=5):
    import yt_dlp

    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'format': 'bestaudio/best',
        'extract_flat': 'in_playlist',
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            result = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            return result.get('entries', [])
        except Exception as e:
            console.print(f"[red]Search failed:[/red] {e}")
            return []

def play_url(url):
    try:
        subprocess.run(["mpv", url], check=True)
    except subprocess.CalledProcessError:
        console.print("[red]Failed to play the track with mpv.[/red]")
    except FileNotFoundError:
        console.print("[red]mpv not found. Please install it.[/red]")

def main():
    install_dependencies()
    console.clear()

    header = Text("🎵 YouTube Music CLI Launcher", style="bold black on white", justify="center")
    console.print(Panel(header, box=box.ROUNDED, padding=(1, 4)))

    try:
        query = Prompt.ask("[bold cyan]Search YouTube for music[/bold cyan]")
        if not query.strip():
            console.print("[red]Empty search query. Exiting.[/red]")
            sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[red]Aborted by user.[/red]")
        sys.exit(0)

    with console.status("[green]Searching YouTube...[/green]", spinner="dots"):
        results = search_youtube(query)

    if not results:
        console.print("[red]No results found.[/red]")
        sys.exit(1)

    table = Table(title="Search Results", box=box.SIMPLE, show_lines=True)
    table.add_column("Index", justify="center", style="cyan")
    table.add_column("Title", style="magenta")
    for i, entry in enumerate(results, 1):
        table.add_row(str(i), entry.get('title', 'Unknown'))

    console.print()
    console.print(table)

    while True:
        try:
            choice_str = Prompt.ask("Pick a number to play (or 'q' to quit)").strip()
            if choice_str.lower() == 'q':
                console.print("[yellow]Exiting.[/yellow]")
                sys.exit(0)

            choice = int(choice_str) - 1
            if 0 <= choice < len(results):
                selected = results[choice]
                console.print(f"[green]Now playing:[/green] {selected['title']}\n")
                play_url(selected['url'])
                break
            else:
                console.print(f"[red]Number out of range. Enter a number between 1 and {len(results)}.[/red]")
        except ValueError:
            console.print("[red]Invalid input. Please enter a number or 'q' to quit.[/red]")
        except KeyboardInterrupt:
            console.print("\n[red]Aborted by user.[/red]")
            sys.exit(0)

if __name__ == "__main__":
    main()

def execute():
    main()
