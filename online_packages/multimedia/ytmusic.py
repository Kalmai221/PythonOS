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

    # Install mpv
    if not is_installed("mpv"):
        if Confirm.ask("[yellow]mpv is not installed. Install with apt?[/yellow]", default=True):
            subprocess.run(["sudo", "apt", "install", "-y", "mpv"])
        else:
            console.print("[red]mpv is required. Exiting.[/red]")
            sys.exit(1)

    # Install yt-dlp
    try:
        import yt_dlp
    except ImportError:
        if Confirm.ask("[yellow]yt-dlp not found. Install with pip?[/yellow]", default=True):
            subprocess.run([sys.executable, "-m", "pip", "install", "yt-dlp"])
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
            return result['entries']
        except Exception as e:
            console.print(f"[red]Search failed:[/red] {e}")
            return []

def play_url(url):
    try:
        subprocess.run(["mpv", url], check=True)
    except subprocess.CalledProcessError:
        console.print("[red]Failed to play the track with mpv.[/red]")

def main():
    console.clear()
    header = Text("🎵 YouTube Music CLI Launcher", style="bold black on white", justify="center")
    console.print(Panel(header, box=box.ROUNDED, padding=(1, 4)))

    install_dependencies()

    query = Prompt.ask("[bold cyan]Search YouTube for music[/bold cyan]")
    console.print(f"[dim]Searching for:[/dim] [bold]{query}[/bold]...\n")

    results = search_youtube(query)

    if not results:
        console.print("[red]No results found.[/red]")
        sys.exit(1)

    table = Table(title="Search Results", box=box.SIMPLE, show_lines=True)
    table.add_column("Index", justify="center")
    table.add_column("Title")
    for i, entry in enumerate(results, 1):
        table.add_row(str(i), entry.get('title', 'Unknown'))

    console.print()
    console.print(table)

    try:
        choice = int(Prompt.ask("Pick a number to play")) - 1
        selected = results[choice]
        console.print(f"[green]Now playing:[/green] {selected['title']}")
        play_url(selected['url'])
    except (ValueError, IndexError):
        console.print("[red]Invalid selection.[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()
