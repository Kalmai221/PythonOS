#!/usr/bin/env python3
from pydub import AudioSegment
import simpleaudio
import subprocess
import os
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel

console = Console()

def download_audio(query):
    mp3 = "yt_audio.mp3"
    wav = "yt_audio.wav"

    subprocess.run([
        "yt-dlp", "-f", "bestaudio",
        "--extract-audio", "--audio-format", "mp3",
        "-o", mp3,
        f"ytsearch1:{query}"
    ], check=True)

    audio = AudioSegment.from_file(mp3, format="mp3")
    audio.export(wav, format="wav")
    return wav

def play_audio(wav_path):
    wave_obj = simpleaudio.WaveObject.from_wave_file(wav_path)
    play_obj = wave_obj.play()
    play_obj.wait_done()

def main():
    console.print(Panel("🎵 YouTube Music Search & Play", style="bold black on white"))
    query = Prompt.ask("Enter a song or artist")
    try:
        wav = download_audio(query)
        play_audio(wav)
        os.remove("yt_audio.mp3")
        os.remove(wav)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")

if __name__ == "__main__":
    main()
