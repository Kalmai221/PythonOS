#!/usr/bin/env python3
"""YouTube Audio: search YouTube and play just the sound, from the terminal.

    ytaudio                      the player: search, queue, play
    ytaudio lo-fi beats          search and choose
    ytaudio <youtube link>       play a video or a whole playlist

Inside:  search <words>   play <number|link>   add <number|link>   queue   clear   volume <0-130>   help   quit
While a track plays, Ctrl+C stops it.

It plays the sound itself, inside PythonOS: the marketplace installs the libraries it needs (yt-dlp, av and miniaudio) with the app, so
nothing has to be installed on the computer and no other program is started. Use it for things you are allowed to listen to; YouTube's terms apply to what you play.
"""
import array
import importlib
import os
import queue
import sys
import threading

try:
    from pyos import appsettings
except ImportError:                                                        # run on its own, outside PythonOS
    appsettings = None

PKG = "utilities/ytaudio"
DEFAULTS = {"volume": 80, "results": 10}


def option(key):
    """An option of this app (settings app ytaudio), else its default."""
    value = appsettings.get(PKG, key, DEFAULTS[key]) if appsettings else DEFAULTS[key]
    return value if isinstance(value, type(DEFAULTS[key])) else DEFAULTS[key]


# ------------------------------------------------------------------------------------------ the built-in player
RATE = 44100


def load_builtin():
    """(av, miniaudio) when both libraries can be loaded here, else None."""
    try:
        return importlib.import_module("av"), importlib.import_module("miniaudio")
    except Exception:                                                      # noqa: BLE001 - a missing library or a missing audio backend
        return None


def scale(pcm, volume):
    """16-bit little-endian PCM at `volume` percent (100 leaves it as it is; louder is clipped)."""
    if volume == 100:
        return pcm
    samples = array.array("h")
    samples.frombytes(pcm[: len(pcm) - len(pcm) % 2])
    factor = volume / 100.0
    return array.array("h", [max(-32768, min(32767, int(x * factor))) for x in samples]).tobytes()


def decode_chunks(av, url):
    """Stereo 16-bit PCM at RATE for the audio behind `url`, as chunks of bytes."""
    container = av.open(url, options={"reconnect": "1", "reconnect_streamed": "1", "reconnect_delay_max": "4"}, timeout=20)
    try:
        stream = container.streams.audio[0]
        resampler = av.AudioResampler(format="s16", layout="stereo", rate=RATE)
        for frame in container.decode(stream):
            for out in resampler.resample(frame):
                yield bytes(out.planes[0])[: out.samples * 4]
        for out in resampler.resample(None) or []:
            yield bytes(out.planes[0])[: out.samples * 4]
    finally:
        container.close()


def play_builtin(libs, urls, volume):
    """Play each address in turn through the sound output, in this process. Ctrl+C stops."""
    av, miniaudio = libs
    volume = max(0, min(130, int(volume)))
    for number, url in enumerate(urls, 1):
        chunks = queue.Queue(maxsize=64)                                  # decoded sound waiting for the output
        stop = threading.Event()
        done = threading.Event()

        def decoder():
            try:
                for chunk in decode_chunks(av, url):
                    data = scale(chunk, volume)
                    while not stop.is_set():
                        try:
                            chunks.put(data, timeout=0.2)
                            break
                        except queue.Full:
                            continue
                    if stop.is_set():
                        return
                tail = None
            except Exception as e:                                         # noqa: BLE001
                tail = e
            while not stop.is_set():
                try:
                    chunks.put(tail, timeout=0.2)
                    return
                except queue.Full:
                    continue

        def source():
            buffered = bytearray()
            finished = False
            wanted = yield b""
            while True:
                need = wanted * 4
                while len(buffered) < need and not finished:
                    try:
                        item = chunks.get_nowait()
                    except queue.Empty:
                        break
                    if item is None or isinstance(item, Exception):
                        finished = True
                        if isinstance(item, Exception):
                            print(f"\n  playback problem: {str(item)[:160]}")
                    else:
                        buffered += item
                if finished and not buffered:
                    done.set()
                data = bytes(buffered[:need])
                del buffered[:need]
                wanted = yield data + b"\0" * (need - len(data))            # silence when the network is slower than the sound

        threading.Thread(target=decoder, daemon=True).start()
        device = miniaudio.PlaybackDevice(output_format=miniaudio.SampleFormat.SIGNED16, nchannels=2, sample_rate=RATE)
        stream = source()
        next(stream)
        device.start(stream)
        print(f"  playing {number}/{len(urls)}  (Ctrl+C stops)")
        try:
            while not done.wait(0.25):
                pass
            threading.Event().wait(0.6)                                    # let the last of the sound out
        finally:
            stop.set()
            device.close()


def minutes(seconds):
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "live"
    return f"{seconds // 3600}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}" if seconds >= 3600 else f"{seconds // 60}:{seconds % 60:02d}"


# ------------------------------------------------------------------------------------------ yt-dlp
def load_ytdlp():
    """The yt_dlp module (installed by the marketplace with the app). None if it is missing."""
    try:
        return importlib.import_module("yt_dlp")
    except ImportError:
        print("The yt-dlp library is missing. Fetch it again with: pkg install ytaudio")
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
        libs = load_builtin()
        if libs is None:
            print("The sound libraries (av, miniaudio) could not be loaded, or there is no sound output on this system.\n"
                  "Fetch the libraries again with: pkg install ytaudio")
            return
        urls = []
        for track in tracks:
            print(f"Getting {track['title']}...")
            try:
                urls.append(stream_url(self.yt, track["url"]))
            except Exception as e:                                       # noqa: BLE001
                print(f"  could not get it: {str(e)[:160]}")
        if not urls:
            return
        print(f"Playing {len(urls)} track(s). Press Ctrl+C to stop.")
        try:
            play_builtin(libs, urls, option("volume"))
        except KeyboardInterrupt:
            print("\nStopped.")
        except Exception as e:                                           # noqa: BLE001 - no sound device, or the stream failed
            print(f"Could not play it: {str(e)[:200]}")

    def handle(self, line):
        """One command. Returns False to leave."""
        word, _space, rest = line.strip().partition(" ")
        word, rest = word.lower(), rest.strip()
        if word in ("quit", "exit", "q"):
            return False
        if word in ("help", "?"):
            print(__doc__.split("Inside:")[1].split("While a track")[0].strip())
        elif word == "search" or (word and word not in ("play", "add", "queue", "clear", "volume") and not line.startswith("http")):
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
        elif word:
            print("I did not understand that. help lists the commands.")
        return True


def execute(args=None):
    args = list(args or [])
    if "ANDROID_ROOT" in os.environ or "ANDROID_DATA" in os.environ:
        print("YouTube Audio cannot reach the sound output from inside the Android app. Use it on a computer.")
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
