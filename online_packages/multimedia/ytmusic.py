#!/usr/bin/env python3
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
from rich.table import Table
from rich import box
import subprocess
import sys
import shutil
import tempfile
import os

console = Console()

def is_installed_pip(pkg):
    try:
        __import__(pkg)
        return True
    except ImportError:
        return False

def install_dependencies():
    console.print(Panel("Checking & installing dependencies...", style="cyan", box=box.ROUNDED))

    # Check yt-dlp
    if not is_installed_pip("yt_dlp"):
        console.print("[yellow]yt-dlp is not installed.[/yellow]")
        if Confirm.ask("Install yt-dlp via pip?", default=True):
            subprocess.run([sys.executable, "-m", "pip", "install", "--user", "yt-dlp", "--break-system-packages"], check=True)
        else:
            console.print("[red]yt-dlp is required. Exiting.[/red]")
            sys.exit(1)

    # Check playsound
    if not is_installed_pip("playsound"):
        console.print("[yellow]playsound is not installed.[/yellow]")
        if Confirm.ask("Install playsound via pip?", default=True):
            subprocess.run([sys.executable, "-m", "pip", "install", "--user", "playsound", "--break-system-packages"], check=True)
        else:
            console.print("[red]playsound is required. Exiting.[/red]")
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
    import yt_dlp
    from playsound import playsound

    ydl_opts = {
        'format': 'bestaudio/best',
        'quiet': True,
        'outtmpl': os.path.join(tempfile.gettempdir(), '%(id)s.%(ext)s'),
        'noplaylist': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + ".mp3"

    console.print(f"[green]Playing downloaded audio:[/green] {filename}")
    try:
        playsound(filename)
    except Exception as e:
        console.print(f"[red]Playback error: {e}[/red]")
    finally:
        try:
            os.remove(filename)
        except Exception:
            pass

def main():
    install_dependencies()
    console.clear()

    header = Text("🎵 YouTube Music CLI Launcher (pip-only)", style="bold black on white", justify="center")
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
