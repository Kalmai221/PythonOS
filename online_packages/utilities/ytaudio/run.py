#!/usr/bin/env python3
"""YouTube Audio: search YouTube and play just the sound, from the terminal.

    ytaudio                      the player: search, queue, play
    ytaudio lo-fi beats          search and choose
    ytaudio <youtube link>       play a video or a whole playlist

Inside:  search <words>   play <number|link>   add <number|link>   queue   clear   volume <0-130>   player <auto|mpv|vlc|ffplay>   help   quit
While a track plays the player's own keys work (mpv: space pauses, the arrow keys seek, 9 and 0 change the volume, < and > go to the
previous and next track, q stops).

It needs two things: the yt-dlp library (offered for install the first time) and an audio player on this computer (mpv is best; VLC or
ffplay also work). Use it for things you are allowed to listen to; YouTube's terms apply to what you play.
"""
import importlib
import os
import shutil
import subprocess
import sys

try:
    from pyos import appsettings
except ImportError:                                                        # run on its own, outside PythonOS
    appsettings = None

PKG = "utilities/ytaudio"
DEFAULTS = {"player": "auto", "volume": 80, "results": 10}
WINDOWS_PLAYERS = {
    "mpv": [r"C:\Program Files\mpv\mpv.exe", r"C:\Program Files (x86)\mpv\mpv.exe", os.path.expandvars(r"%LOCALAPPDATA%\Programs\mpv\mpv.exe"),
            os.path.expandvars(r"%USERPROFILE%\scoop\apps\mpv\current\mpv.exe")],
    "vlc": [r"C:\Program Files\VideoLAN\VLC\vlc.exe", r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"],
    "ffplay": [os.path.expandvars(r"%USERPROFILE%\scoop\apps\ffmpeg\current\bin\ffplay.exe")],
}
MAC_PLAYERS = {"mpv": ["/opt/homebrew/bin/mpv", "/usr/local/bin/mpv"], "vlc": ["/Applications/VLC.app/Contents/MacOS/VLC"], "ffplay": ["/opt/homebrew/bin/ffplay"]}
EXE_NAMES = {"mpv": ("mpv", "mpv.exe"), "vlc": ("cvlc", "vlc", "vlc.exe"), "ffplay": ("ffplay", "ffplay.exe")}


def option(key):
    """An option of this app (settings app ytaudio), else its default."""
    value = appsettings.get(PKG, key, DEFAULTS[key]) if appsettings else DEFAULTS[key]
    return value if isinstance(value, type(DEFAULTS[key])) else DEFAULTS[key]


def find_players():
    """{'mpv': path, 'vlc': path, 'ffplay': path} for the players that are installed."""
    found = {}
    for name, executables in EXE_NAMES.items():
        path = next((shutil.which(e) for e in executables if shutil.which(e)), None)
        if not path:
            candidates = (WINDOWS_PLAYERS if os.name == "nt" else MAC_PLAYERS if sys.platform == "darwin" else {}).get(name, [])
            path = next((c for c in candidates if os.path.exists(c)), None)
        if path:
            found[name] = path
    return found


def choose_player(found, wanted="auto"):
    """(name, path) of the player to use: the wanted one if it is there, else mpv, vlc, ffplay in that order. None when there is none."""
    order = [wanted] if wanted in found else []
    order += [n for n in ("mpv", "vlc", "ffplay") if n in found and n not in order]
    return (order[0], found[order[0]]) if order else None


def install_hint():
    if os.name == "nt":
        return "Install mpv: winget install mpv   (or: scoop install mpv)"
    if sys.platform == "darwin":
        return "Install mpv: brew install mpv"
    return "Install mpv: sudo apt install mpv   (or your distribution's package tool; VLC and ffplay also work)"


def build_command(name, path, urls, volume):
    """The command that plays `urls` with the chosen player. A list of commands for ffplay (it plays one file per run)."""
    volume = max(0, min(130, int(volume)))
    if name == "mpv":
        return [[path, "--no-video", f"--volume={volume}", "--force-window=no", *urls]]
    if name == "vlc":
        return [[path, "--intf", "dummy", "--no-video", "--play-and-exit", f"--gain={volume / 100:.2f}", *urls]]
    return [[path, "-nodisp", "-autoexit", "-loglevel", "error", "-volume", str(min(100, volume)), url] for url in urls]


def minutes(seconds):
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "live"
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}" if seconds >= 3600 else f"{seconds // 60}:{seconds % 60:02d}"


# ------------------------------------------------------------------------------------------ yt-dlp
def load_ytdlp():
    """The yt_dlp module, offering to install it the first time. None if it cannot be had."""
    try:
        return importlib.import_module("yt_dlp")
    except ImportError:
        pass
    print("This needs the yt-dlp library, which is not installed yet.")
    if input("Install it now for your user (pip)? (yes/no) [yes]: ").strip().lower() in ("n", "no"):
        return None
    try:
        code = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "--quiet", "yt-dlp"]).returncode
    except OSError as e:
        print(f"Could not run pip: {e}")
        return None
    if code != 0:
        print("pip could not install yt-dlp. Install it yourself with: python -m pip install --user yt-dlp")
        return None
    import site
    for path in (site.getusersitepackages(),):
        if path not in sys.path:
            sys.path.append(path)
    importlib.invalidate_caches()
    try:
        return importlib.import_module("yt_dlp")
    except ImportError:
        print("yt-dlp was installed but could not be loaded; start ytaudio again.")
        return None


def options(**more):
    base = {"quiet": True, "no_warnings": True, "cachedir": False, "skip_download": True, "noprogress": True}
    base.update(more)
    return base


def entry_from(info):
    """{'title', 'who', 'seconds', 'url'} from one yt-dlp entry (None when it has no address)."""
    url = info.get("webpage_url") or info.get("url")
    if not url and info.get("id"):
        url = f"https://www.youtube.com/watch?v={info['id']}"
    if not url:
        return None
    return {"title": info.get("title") or "(no title)", "who": info.get("uploader") or info.get("channel") or "", "seconds": info.get("duration"), "url": url}


def search(yt, query, count):
    with yt.YoutubeDL(options(extract_flat="in_playlist")) as ydl:
        info = ydl.extract_info(f"ytsearch{count}:{query}", download=False)
    return [e for e in (entry_from(x) for x in (info or {}).get("entries") or [] if x) if e]


def expand(yt, link):
    """The tracks behind a link: one video, or every video of a playlist."""
    with yt.YoutubeDL(options(extract_flat="in_playlist")) as ydl:
        info = ydl.extract_info(link, download=False)
    if not info:
        return []
    if info.get("entries"):
        return [e for e in (entry_from(x) for x in info["entries"] if x) if e]
    entry = entry_from(info)
    return [entry] if entry else []


def stream_url(yt, page_url):
    """The direct audio address of a video (valid for a few hours), found just before it is played."""
    with yt.YoutubeDL(options(format="bestaudio/best")) as ydl:
        info = ydl.extract_info(page_url, download=False)
    return info["url"]


# ------------------------------------------------------------------------------------------ the player
class Player:
    def __init__(self, yt):
        self.yt = yt
        self.results = []
        self.queue = []

    def show_results(self):
        for number, e in enumerate(self.results, 1):
            print(f"  {number:>2}) {e['title']}" + (f"  -  {e['who']}" if e["who"] else "") + f"  [{minutes(e['seconds'])}]")

    def find(self, text):
        """What a number or a link in a command means: a list of tracks."""
        text = text.strip()
        if text.isdigit():
            number = int(text)
            if 1 <= number <= len(self.results):
                return [self.results[number - 1]]
            print("There is no result with that number: search first.")
            return []
        if text.startswith(("http://", "https://")):
            try:
                return expand(self.yt, text)
            except Exception as e:                                       # noqa: BLE001 - yt-dlp raises many kinds of errors
                print(f"Could not read that link: {str(e)[:200]}")
                return []
        return []

    def do_search(self, words):
        if not words:
            print("Search for what? For example: search lo-fi beats")
            return
        try:
            self.results = search(self.yt, words, int(option("results")))
        except Exception as e:                                           # noqa: BLE001
            print(f"The search failed: {str(e)[:200]}")
            return
        print("Nothing found." if not self.results else "")
        self.show_results()
        if self.results:
            print("play <number> plays one, add <number> queues it.")

    def play_tracks(self, tracks):
        found = find_players()
        chosen = choose_player(found, option("player"))
        if not chosen:
            print("No audio player was found.\n" + install_hint())
            return
        name, path = chosen
        urls = []
        for track in tracks:
            print(f"Getting {track['title']}...")
            try:
                urls.append(stream_url(self.yt, track["url"]))
            except Exception as e:                                       # noqa: BLE001
                print(f"  could not get it: {str(e)[:160]}")
        if not urls:
            return
        print(f"Playing {len(urls)} track(s) with {name}. " + ("Press q to stop." if name == "mpv" else "Press Ctrl+C to stop."))
        try:
            for command in build_command(name, path, urls, option("volume")):
                subprocess.run(command)
        except KeyboardInterrupt:
            print("\nStopped.")
        except OSError as e:
            print(f"Could not start the player: {e}")

    def handle(self, line):
        """One command. Returns False to leave."""
        word, _space, rest = line.strip().partition(" ")
        word, rest = word.lower(), rest.strip()
        if word in ("quit", "exit", "q"):
            return False
        if word in ("help", "?"):
            print(__doc__.split("Inside:")[1].split("While a track")[0].strip())
        elif word == "search" or (word and word not in ("play", "add", "queue", "clear", "volume", "player") and not line.startswith("http")):
            self.do_search(rest if word == "search" else line.strip())
        elif word == "play":
            tracks = self.find(rest) if rest else list(self.queue)
            if tracks:
                self.play_tracks(tracks)
            else:
                print("Nothing to play: search first, then play <number>." if rest else "The queue is empty: search, then add <number>.")
        elif word.startswith("http"):
            self.play_tracks(self.find(line.strip()))
        elif word == "add":
            tracks = self.find(rest)
            self.queue += tracks
            print(f"Queued {len(tracks)} track(s); the queue has {len(self.queue)}.")
        elif word == "queue":
            for number, e in enumerate(self.queue, 1):
                print(f"  {number:>2}) {e['title']}  [{minutes(e['seconds'])}]")
            print("The queue is empty." if not self.queue else "play (with no number) plays the queue.")
        elif word == "clear":
            self.queue = []
            print("Queue cleared.")
        elif word == "volume" and rest.isdigit():
            DEFAULTS["volume"] = int(rest)
            if appsettings:
                try:
                    appsettings.set_value(PKG, {"key": "volume", "type": "int", "min": 0, "max": 130}, rest, None)
                except Exception:                                        # noqa: BLE001 - the option may not be saved; it still applies now
                    pass
            print(f"Volume {rest}.")
        elif word == "player" and rest:
            DEFAULTS["player"] = rest
            print(f"Using {rest} when it is installed.")
        elif word:
            print("I did not understand that. help lists the commands.")
        return True


def execute(args=None):
    args = list(args or [])
    if "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ:
        print("YouTube Audio needs an audio player program, which Android does not offer to apps like this one. Use it on a computer.")
        return False
    yt = load_ytdlp()
    if yt is None:
        return False
    player = Player(yt)
    first = " ".join(args).strip()
    if first.startswith(("http://", "https://")):
        player.play_tracks(player.find(first))
        return True
    if first:
        player.do_search(first)
    print("\nType a search, play <number>, or help. quit leaves.")
    try:
        while True:
            line = input("ytaudio> ")
            if not line.strip():
                continue
            if player.handle(line) is False:
                break
    except (EOFError, KeyboardInterrupt):
        print()
    return True


if __name__ == "__main__":
    sys.exit(0 if execute(sys.argv[1:]) is not False else 1)
