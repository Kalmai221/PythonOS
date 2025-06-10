import os
import subprocess
import pygame
import tempfile
import time
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()

def download_audio(search_query):
    tmpdir = tempfile.gettempdir()
    output_template = os.path.join(tmpdir, "yt_audio.%(ext)s")
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "mp3",
        "-o", output_template,
        f"ytsearch1:{search_query}"
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return os.path.join(tmpdir, "yt_audio.mp3")

def play_audio(file_path):
    pygame.init()
    pygame.mixer.init()
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        time.sleep(0.5)

def main():
    console.print(Panel("[bold cyan]YouTube Music Player[/bold cyan]", expand=False))

    search_query = Prompt.ask("Enter the song or artist to search on YouTube").strip()
    if not search_query:
        console.print("[bold red]No input given, exiting.[/bold red]")
        return

    try:
        with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}")) as progress:
            progress.add_task(description=f"Downloading top result for: [bold green]{search_query}[/bold green]", total=None)
            audio_file = download_audio(search_query)
        console.print("[bold green]Download complete![/bold green]\n")
        console.print(Panel("[bold yellow]Playing audio...[/bold yellow]", expand=False))
        play_audio(audio_file)
    except subprocess.CalledProcessError:
        console.print(Panel("[bold red]Failed to download audio. Make sure yt-dlp is installed and working.[/bold red]", expand=False))
    finally:
        if 'audio_file' in locals() and os.path.exists(audio_file):
            os.remove(audio_file)

if __name__ == "__main__":
    main()
