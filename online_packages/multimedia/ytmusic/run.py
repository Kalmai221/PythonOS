#!/usr/bin/env python3
import subprocess
import sys
import os
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from playsound import playsound

console = Console()

def download_audio(query):
    output_path = "yt_audio.mp3"
    search_query = f"ytsearch1:{query}"
    try:
        subprocess.run(
            ["yt-dlp", "-f", "bestaudio", "--extract-audio", "--audio-format", "mp3",
             "-o", output_path, search_query],
            check=True
        )
        return output_path
    except subprocess.CalledProcessError as e:
        console.print(Panel(f"[red]Download failed:[/red] {e}", style="red"))
        return None

def main():
    console.clear()
    console.print(Panel("🎧 YouTube Music Search & Play", style="bold black on white", padding=(1, 4)))

    query = Prompt.ask("Enter a song/artist to search and play")
    console.print(f"[yellow]Searching and downloading...[/yellow]")
    path = download_audio(query)

    if path and os.path.exists(path):
        console.print("[green]Playing...[/green]")
        try:
            playsound(path)
        except Exception as e:
            console.print(f"[red]Playback failed:[/red] {e}")
        finally:
            os.remove(path)
    else:
        console.print("[red]Nothing was downloaded.[/red]")

if __name__ == "__main__":
    main()

def execute():
    main()