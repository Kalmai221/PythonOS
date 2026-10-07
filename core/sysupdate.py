from pathlib import Path
from urllib.parse import urljoin
import hashlib
import io
import json
import os
import re
import shutil
import sys
import zipfile
import requests
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Confirm
from rich.progress import Progress, BarColumn, TextColumn
import time
from requests.exceptions import HTTPError
import socket

console = Console()
GITHUB_API_BASE = "https://api.github.com/repos/Kalmai221/PythonOS/contents"
IGNORE_FOLDERS = {".git", ".OSData"}

# --- Release updates (packaged builds) -------------------------------------------------
# Every GitHub release carries pythonos-core-<version>.zip and core-manifest.json (built by
# OS_Export/make_core.py). Packaged builds - Linux, Windows, Android, ISO - update their core
# files from the latest release. PYOS_UPDATE_URL points at another manifest (self-hosting, tests).
RELEASES_URL = "https://github.com/Kalmai221/PythonOS/releases"
MANIFEST_URL = os.environ.get("PYOS_UPDATE_URL") or f"{RELEASES_URL}/latest/download/core-manifest.json"
UPDATE_DIR = Path(".OSData") / "update"
CODE_DIRS = ("commands", "core", "programs", "pyos")
TIMEOUT = 20

def check_internet_connection(host="8.8.8.8", port=53, timeout=3):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
        return True
    except socket.error:
        return False

def get_github_files(path=""):
    url = f"{GITHUB_API_BASE}/{path}" if path else GITHUB_API_BASE
    response = requests.get(url)
    response.raise_for_status()
    items = response.json()

    files = []
    for item in items:
        if item["type"] == "dir":
            if item["name"] in IGNORE_FOLDERS:
                continue
            files.extend(get_github_files(item["path"]))
        elif item["type"] == "file":
            files.append(item)
    return files

def is_file_different(local_path: Path, download_url: str) -> bool:
    if not local_path.exists():
        return True
    try:
        remote_content = requests.get(download_url).content
        local_content = local_path.read_bytes()
        return local_content != remote_content
    except Exception:
        return True

def list_updates(files, base_path=Path.cwd()):
    updates = []
    for file_info in files:
        local_file = base_path / file_info["path"]
        if is_file_different(local_file, file_info["download_url"]):
            updates.append(file_info["path"])
    return updates

def download_file(local_path: Path, download_url: str):
    content = requests.get(download_url).content
    local_path.parent.mkdir(parents=True, exist_ok=True)
    with open(local_path, "wb") as f:
        f.write(content)

def apply_updates(files_to_update, all_files, base_path=Path.cwd()):
    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Updating files...", total=len(files_to_update))
        for path_str in files_to_update:
            file_info = next(f for f in all_files if f["path"] == path_str)
            local_file = base_path / file_info["path"]
            download_file(local_file, file_info["download_url"])
            progress.advance(task)
            time.sleep(0.1)

def show_update_table(files_to_update):
    table = Table(title="Files to Update", header_style="bold magenta")
    table.add_column("Index", justify="right")
    table.add_column("File Path", style="cyan")

    for i, filepath in enumerate(files_to_update, start=1):
        table.add_row(str(i), filepath)

    console.print(table)

def packaged_version():
    """Version string if this is a packaged build (APK, ISO, installer, .deb ...), else None.

    Packaged builds are made by OS_Export/stage.py, which writes a VERSION file; bundled
    builds (Android, ISO) also set PYOS_BUNDLED. They update from the latest GitHub
    release (see update_packaged), not from the repository's main branch.
    """
    if os.path.isfile("VERSION"):
        try:
            return Path("VERSION").read_text(encoding="utf-8").strip() or "unknown"
        except OSError:
            return "unknown"
    return "bundled" if os.environ.get("PYOS_BUNDLED") == "1" else None


def version_key(text):
    """Sortable version: numbers first; a '-dev' build counts as older than the same release."""
    numbers = [int(n) for n in re.findall(r"\d+", str(text).split("-")[0])]
    numbers += [0] * (4 - len(numbers))
    return tuple(numbers), 0 if "dev" in str(text).lower() else 1


def requirements_hash():
    """Hash of the dependency lists (must match OS_Export/make_core.py)."""
    parts = []
    for name in ("requirements.txt", "boot-requirements.txt"):
        try:
            parts.append(Path(name).read_bytes().replace(b"\r\n", b"\n"))
        except OSError:
            parts.append(b"")
    return hashlib.sha256(b"\0".join(parts)).hexdigest()


def safe_member(path):
    p = Path(path)
    return bool(path) and not p.is_absolute() and ".." not in p.parts and not path.startswith("/")


def fetch_manifest():
    response = requests.get(MANIFEST_URL, timeout=TIMEOUT)
    response.raise_for_status()
    manifest = response.json()
    for key in ("version", "asset", "sha256", "files"):
        if key not in manifest:
            raise ValueError(f"the release manifest is missing '{key}'")
    return manifest


def core_url(manifest):
    if manifest.get("url"):
        return manifest["url"]
    if os.environ.get("PYOS_UPDATE_URL"):
        return urljoin(MANIFEST_URL, manifest["asset"])
    return f"{RELEASES_URL}/download/{manifest.get('tag', 'v' + manifest['version'])}/{manifest['asset']}"


def download_core(manifest, destination):
    """Download the whole core zip and check it against the manifest's checksum. A download that was cut off is
    continued next time from where it stopped (the partial file is kept as <name>.part)."""
    destination = Path(destination)
    part = destination.with_name(destination.name + ".part")
    total = int(manifest.get("size") or 0)
    digest = hashlib.sha256()
    have = 0
    if part.exists():
        have = part.stat().st_size
        if total and have >= total:
            part.unlink()                      # a leftover that cannot be a prefix of this file
            have = 0
        else:
            with open(part, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    digest.update(chunk)
    headers = {"Range": f"bytes={have}-"} if have else {}
    started = time.time()
    fetched = 0
    with requests.get(core_url(manifest), stream=True, timeout=TIMEOUT, headers=headers) as response:
        response.raise_for_status()
        if have and response.status_code != 206:      # the server ignored the range: start again from the top
            have, digest = 0, hashlib.sha256()
        with Progress("[progress.description]{task.description}", BarColumn(),
                      "[progress.percentage]{task.percentage:>3.0f}%", console=console, transient=True) as progress:
            task = progress.add_task("Resuming download..." if have else "Downloading update...", total=total or None, completed=have)
            with open(part, "ab" if have else "wb") as f:
                for chunk in response.iter_content(65536):
                    f.write(chunk)
                    digest.update(chunk)
                    fetched += len(chunk)
                    progress.advance(task, len(chunk))
    _remember_speed(fetched, time.time() - started)
    if digest.hexdigest() != manifest["sha256"]:
        part.unlink(missing_ok=True)           # corrupt, not merely incomplete: do not resume from it
        raise ValueError("the downloaded update is corrupted (checksum mismatch)")
    os.replace(part, destination)
    return fetched


# ------------------------------------------------------------------ delta updates
# Most updates change a handful of files. The core zip's directory is read with small HTTP range requests, the files that
# differ from the installed ones are fetched one by one (each verified against the manifest), and the rest are copied from
# the installed copy. Files already fetched are kept (UPDATE_DIR/files), so a dropped connection resumes where it stopped.
class RangeUnsupported(Exception):
    pass


class RemoteFile(io.RawIOBase):
    """A read-only, seekable view of a file on a web server, fetched in pieces with Range requests."""
    CHUNK = 65536

    def __init__(self, url, size):
        super().__init__()
        self.url, self.size, self.pos = url, size, 0
        self.fetched = 0
        self._cache = (0, b"")
        self._session = requests.Session()

    def seekable(self):
        return True

    def readable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        self.pos = offset if whence == io.SEEK_SET else self.pos + offset if whence == io.SEEK_CUR else self.size + offset
        self.pos = max(0, min(self.pos, self.size))
        return self.pos

    def readinto(self, buffer):
        want = min(len(buffer), self.size - self.pos)
        if want <= 0:
            return 0
        start, data = self._cache
        if not (start <= self.pos and self.pos + want <= start + len(data)):
            end = min(self.size, max(self.pos + want, self.pos + self.CHUNK)) - 1
            # a read that lands near the end (the zip directory) is fetched as one block
            r = self._session.get(self.url, headers={"Range": f"bytes={self.pos}-{end}"}, timeout=TIMEOUT)
            if r.status_code != 206:
                raise RangeUnsupported("the server does not support partial downloads")
            self._cache = (self.pos, r.content)
            self.fetched += len(r.content)
            start, data = self._cache
        piece = data[self.pos - start:self.pos - start + want]
        buffer[:len(piece)] = piece
        self.pos += len(piece)
        return len(piece)


def _speed_state():
    try:
        return json.loads((UPDATE_DIR / "speed.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _remember_speed(nbytes, seconds):
    """Keep a rough download speed (bytes per second) so the next update can estimate its time."""
    if nbytes < 20_000 or seconds <= 0:
        return
    try:
        UPDATE_DIR.mkdir(parents=True, exist_ok=True)
        old = _speed_state().get("bps")
        bps = nbytes / seconds
        (UPDATE_DIR / "speed.json").write_text(json.dumps({"bps": int(bps if not old else (old + bps) / 2)}), encoding="utf-8")
    except OSError:
        pass


def _human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def _estimate_seconds(nbytes):
    bps = _speed_state().get("bps") or 400_000
    seconds = nbytes / bps + 1
    return "a few seconds" if seconds < 8 else f"about {int(round(seconds / 5) * 5)} seconds" if seconds < 90 else f"about {int(seconds // 60) + 1} minutes"


def local_hash(rel):
    try:
        return hashlib.sha256(Path(rel).read_bytes()).hexdigest()
    except OSError:
        return None


def plan_update(manifest):
    """What would the update download? Returns a dict: mode ('delta' or 'full'), changed (list of manifest entries),
    total (files in the release), bytes (to download), remote (RemoteFile for delta mode)."""
    files = manifest["files"]
    changed = [e for e in files if local_hash(e["path"]) != e["sha256"]]
    full = {"mode": "full", "changed": changed, "total": len(files), "bytes": int(manifest.get("size") or 0), "remote": None}
    size = int(manifest.get("size") or 0)
    if not size or os.environ.get("PYOS_NO_DELTA"):
        return full
    try:
        remote = RemoteFile(core_url(manifest), size)
        with zipfile.ZipFile(remote) as z:
            sizes = {i.filename: i.compress_size for i in z.infolist()}
        need = sum(sizes.get(e["path"], e["size"]) + 100 for e in changed) + remote.fetched
        if need >= size * 0.7:               # not worth the extra requests
            return full
        return {"mode": "delta", "changed": changed, "total": len(files), "bytes": need, "remote": RemoteFile(core_url(manifest), size)}
    except (requests.RequestException, RangeUnsupported, zipfile.BadZipFile, OSError):
        return full


def stage_delta(manifest, plan, stage_dir):
    """Build the new tree: unchanged files copied from the installed copy, changed ones fetched and verified."""
    shutil.rmtree(stage_dir, ignore_errors=True)
    stage_dir.mkdir(parents=True)
    cache = UPDATE_DIR / "files"
    cache.mkdir(parents=True, exist_ok=True)
    changed = {e["path"] for e in plan["changed"]}
    started, fetched_before = time.time(), 0
    with zipfile.ZipFile(plan["remote"]) as z, Progress("[progress.description]{task.description}", BarColumn(),
                                                         "[progress.percentage]{task.percentage:>3.0f}%", console=console,
                                                         transient=True) as progress:
        task = progress.add_task("Downloading changed files...", total=max(1, len(changed)))
        for entry in manifest["files"]:
            rel = entry["path"]
            if not safe_member(rel):
                raise ValueError(f"unsafe path in update: {rel}")
            target = stage_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            if rel in changed:
                cached = cache / entry["sha256"]
                data = cached.read_bytes() if cached.exists() else None
                if data is None or hashlib.sha256(data).hexdigest() != entry["sha256"]:
                    data = z.read(rel)
                    if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                        raise ValueError(f"checksum mismatch for {rel}")
                    cached.write_bytes(data)           # kept until the whole update is applied: a retry does not refetch it
                target.write_bytes(data)
                progress.advance(task)
            else:
                shutil.copy2(rel, target)
    _remember_speed(plan["remote"].fetched, time.time() - started)
    shutil.rmtree(cache, ignore_errors=True)


# -------------------------------------------------------------- what's new / rollback
LAST_UPDATE = Path(".OSData") / "last_update.json"


def record_update(previous, latest, manifest, plan, fetched):
    try:
        LAST_UPDATE.parent.mkdir(exist_ok=True)
        LAST_UPDATE.write_text(json.dumps({
            "from": str(previous), "to": str(latest), "time": time.time(), "notes": manifest.get("notes", ""),
            "changed": [e["path"] for e in plan["changed"]] if plan else [], "mode": plan["mode"] if plan else "full",
            "bytes": fetched, "seen": False, "rollback": False}), encoding="utf-8")
    except OSError:
        pass


def load_last_update():
    try:
        return json.loads(LAST_UPDATE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def show_whats_new(force=False):
    """Print what the last update changed. Without force it appears once, the first time PythonOS starts after the update."""
    info = load_last_update()
    if not info or (info.get("seen") and not force):
        return False
    parts = [f"[bold]{'Rolled back' if info.get('rollback') else 'Updated'}[/bold] {info['from']} -> [green]{info['to']}[/green]"]
    if info.get("notes"):
        parts += ["", Markdown(str(info["notes"]))]                 # the notes are Markdown: lists, `code`, **bold**
    changed = info.get("changed") or []
    if changed:
        shown = ", ".join(changed[:6]) + (f" and {len(changed) - 6} more" if len(changed) > 6 else "")
        parts += ["", f"[dim]{len(changed)} file(s) changed: {shown}[/dim]"]
    console.print(Panel(Group(*parts), title="[bold cyan]What's new in PythonOS[/bold cyan]", border_style="cyan", expand=False))
    info["seen"] = True
    try:
        LAST_UPDATE.write_text(json.dumps(info), encoding="utf-8")
    except OSError:
        pass
    return True


def can_rollback():
    backup = UPDATE_DIR / "backup"
    info = load_last_update()
    return backup.is_dir() and any(backup.iterdir()) and bool(info) and not info.get("rollback")


def rollback():
    """Go back to the version before the last update. The version being left is kept, so it can be rolled forward again
    by updating. Returns True on success."""
    info = load_last_update()
    backup = UPDATE_DIR / "backup"
    if not can_rollback():
        console.print("[yellow]There is no earlier version to go back to (rollback works once, right after an update).[/yellow]")
        return False
    previous = info["from"]
    if not Confirm.ask(f"Go back to PythonOS {previous} (from {info['to']})? Your files and accounts are not touched.", default=False):
        console.print("[yellow]Cancelled.[/yellow]")
        return False
    staged = UPDATE_DIR / "rollback_stage"
    shutil.rmtree(staged, ignore_errors=True)
    shutil.move(str(backup), str(staged))
    try:
        apply_core(staged, previous)
    except Exception as e:
        console.print(f"[bold red]Rollback failed ({e}). The current version is unchanged.[/bold red]")
        return False
    finally:
        shutil.rmtree(staged, ignore_errors=True)
    try:
        LAST_UPDATE.write_text(json.dumps({**info, "from": info["to"], "to": previous, "rollback": True, "seen": True,
                                           "time": time.time()}), encoding="utf-8")
    except OSError:
        pass
    console.print(f"[bold green]Rolled back to {previous}.[/bold green] Restart PythonOS to use it.")
    return True


def extract_core(zip_path, manifest, stage_dir):
    """Unpack only the files listed in the manifest, verifying each one."""
    shutil.rmtree(stage_dir, ignore_errors=True)
    stage_dir.mkdir(parents=True)
    with zipfile.ZipFile(zip_path) as z:
        for entry in manifest["files"]:
            rel = entry["path"]
            if not safe_member(rel):
                raise ValueError(f"unsafe path in update: {rel}")
            data = z.read(rel)
            if hashlib.sha256(data).hexdigest() != entry["sha256"]:
                raise ValueError(f"checksum mismatch for {rel}")
            target = stage_dir / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)


def apply_core(stage_dir, version):
    """Swap the new core files in. If anything fails, the old ones are put back."""
    backup = UPDATE_DIR / "backup"
    shutil.rmtree(backup, ignore_errors=True)
    backup.mkdir(parents=True)
    moved_dirs, copied_files = [], []
    staged_files = [p.relative_to(stage_dir).as_posix() for p in stage_dir.rglob("*") if p.is_file()]
    try:
        for name in CODE_DIRS:
            new = stage_dir / name
            if not new.is_dir():
                continue
            old = Path(name)
            if old.exists():
                shutil.move(str(old), str(backup / name))
            moved_dirs.append(name)
            shutil.move(str(new), str(old))
        for item in sorted(stage_dir.iterdir()):
            if item.is_file():
                if Path(item.name).exists():
                    shutil.copy2(item.name, backup / item.name)
                copied_files.append(item.name)
                shutil.copy2(item, item.name)
        # keep the version shown on the home screen in step (config.json is otherwise untouched)
        try:
            cfg = json.loads(Path("config.json").read_text(encoding="utf-8"))
            cfg["version"] = version
            Path("config.json").write_text(json.dumps(cfg, indent=4), encoding="utf-8")
        except (OSError, ValueError):
            pass
        keep_across_restarts(staged_files, version)
    except Exception:
        for name in moved_dirs:
            shutil.rmtree(name, ignore_errors=True)
            if (backup / name).exists():
                shutil.move(str(backup / name), name)
        for name in copied_files:
            if (backup / name).exists():
                shutil.copy2(backup / name, name)
        raise


def keep_across_restarts(files, version):
    """Where the program files do not survive a restart (the live ISO, a Docker container) but a data disk or volume does, save
    the updated files there too: core_overlay.py puts them back at the next start (see its notes). Elsewhere the update just stays."""
    try:
        import core_overlay
        if core_overlay.enabled():
            core_overlay.save(files, version)
            console.print("[dim]The update is saved on your data disk and will be used again after a restart.[/dim]")
        elif os.environ.get("PYOS_LIVE") == "1" or os.environ.get("PYOS_VOLATILE") == "1":
            console.print("[yellow]This update lasts until the system is switched off. To keep it, set up persistent storage "
                          "(persist create), or get the newer image.[/yellow]")
    except Exception:
        pass


def update_lasts_only_until_restart():
    """A warning when an update here would be gone after a restart (the live ISO or a container with nowhere to keep it), else ''."""
    try:
        import core_overlay
        if core_overlay.enabled():
            return ""
    except Exception:
        pass
    if os.environ.get("PYOS_LIVE") == "1" or os.environ.get("PYOS_VOLATILE") == "1":
        return ("This system runs from memory and has no data disk to keep an update on: the update would be gone after a restart. "
                "Set up persistent storage first (persist create; the VM images come with a data disk), or get the newer image.")
    return ""


def offer_restart():
    if Confirm.ask("Restart PythonOS now to use the new version?", default=True):
        import importlib.util
        spec = importlib.util.spec_from_file_location("restart_cmd", os.path.join("commands", "restart.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        module.restart_system()


# ------------------------------------------------------------------ exports
# PythonOS updates its core by itself. The package around it - the APK and its terminal screen, the Windows
# launcher and bundled Python, the Linux launcher, the ISO's kernel and boot setup - cannot be replaced from
# inside the running OS. Those are "exports"; the release manifest says what the latest ones are, and this
# works out whether the one in use needs to be downloaded and installed by hand.
CHECK_FILE = Path(".OSData") / "update_check.json"
CHECK_INTERVAL = 24 * 3600


def export_status(manifest):
    """Compare this export with the latest release. Returns None for a source checkout, else a dict:

    state: "current" | "update" (newer package exists, core update still works) |
           "incompatible" (the new core needs a newer package first) | "unknown"
    """
    from pyos import export
    local = export.info()
    if not local:
        return None
    remote = (manifest.get("exports") or {}).get(local["platform"])
    status = {"platform": local["platform"], "title": export.title(local["platform"]), "local": local,
              "remote": remote, "state": "unknown", "reason": ""}
    if not remote:
        return status
    status["state"] = "current"
    if int(remote.get("api", 1)) > int(local.get("api", 1)):
        status["state"], status["reason"], status["why"] = "incompatible", "it needs features this version of the package does not have", "api"
    elif os.environ.get("PYOS_BUNDLED") == "1" and manifest.get("requirements_sha256") not in (None, requirements_hash()):
        status["state"], status["reason"], status["why"] = "incompatible", "it needs new libraries, which this package cannot install itself", "libraries"
    elif version_key(remote["version"]) > version_key(local["version"]):
        status["state"] = "update"
    return status


# ------------------------------------------------------------------ checking and installing a new package
def release_checksums(file_url, timeout=15):
    """{file name: sha256} from the SHA256SUMS file that sits next to a release file (empty if there is none)."""
    base = file_url.rsplit("/", 1)[0]
    try:
        response = requests.get(base + "/SHA256SUMS", timeout=timeout)
        response.raise_for_status()
    except requests.RequestException:
        return {}
    sums = {}
    for line in response.text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            sums[parts[1].lstrip("*").strip()] = parts[0].lower()
    return sums


def checksum_of(file_url):
    """The published SHA-256 of a release file, or None when the release has no checksum list."""
    return release_checksums(file_url).get(file_url.rsplit("/", 1)[-1])


def download_verified(file_url, destination, timeout=60):
    """Download a release file and check it against the release's SHA256SUMS before anyone runs it. Raises ValueError if the
    release has no checksum for it or the download does not match; the file is deleted in that case."""
    want = checksum_of(file_url)
    if not want:
        raise ValueError("this release has no checksum for the file, so it cannot be checked")
    digest = hashlib.sha256()
    with requests.get(file_url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with open(destination, "wb") as f:
            for chunk in response.iter_content(1 << 16):
                f.write(chunk)
                digest.update(chunk)
    if digest.hexdigest() != want:
        try:
            os.remove(destination)
        except OSError:
            pass
        raise ValueError("the download does not match its checksum (damaged or changed), so it was deleted")
    return want


def installer_url(status):
    """The small web installer of this release, if the Windows app has one."""
    for url in (status.get("remote") or {}).get("urls", []):
        if url.endswith("web-setup.exe"):
            return url
    return None


def update_in_place(status):
    """Windows app: download the web installer, check it, and let it replace the app while PythonOS is closed. Returns True if started."""
    import subprocess
    import tempfile
    url = installer_url(status)
    if os.name != "nt" or not url:
        return False
    target = os.path.join(tempfile.gettempdir(), url.rsplit("/", 1)[-1])
    try:
        console.print("[cyan]Downloading the installer and checking it...[/cyan]")
        download_verified(url, target)
    except (ValueError, requests.RequestException, OSError) as e:
        console.print(f"[bold red]Not updated: {e}[/bold red]")
        return False
    console.print("[green]The installer is genuine.[/green] PythonOS will close, update itself and start again.")
    subprocess.Popen([target, "/update", "/silent"], close_fds=True,
                     creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    time.sleep(2)
    return True


def offer_in_place(status):
    """After the update notice: offer to install the new package right now, the way this export can (see core/exportupdate.py)."""
    try:
        from core import exportupdate
        if exportupdate.offer(status):
            return True
        why = exportupdate.why_not(status)
        if why:
            console.print(f"[dim]PythonOS cannot do this update itself here: {why}.[/dim]")
    except Exception:
        pass
    return False


def print_export_notice(status, blocking=False):
    """Explain, in plain words, that this package must be replaced by hand."""
    remote, local = status["remote"], status["local"]
    if blocking:
        console.print(Panel(
            f"The latest PythonOS can't be installed on this {status['title']} yet: {status['reason']}.\n"
            f"You have package version [bold]{local['version']}[/bold]; version [bold green]{remote['version']}[/bold green] "
            f"is needed.\n\n[bold]This can't be done from inside PythonOS[/bold] - download and install the new "
            f"{status['title']}:", title="[bold yellow]Install the new package first[/bold yellow]", border_style="yellow", expand=False))
    else:
        console.print(Panel(Group(
            f"A newer [bold]{status['title']}[/bold] is available: {local['version']} -> [bold green]{remote['version']}[/bold green]",
            *([Markdown(str(remote["notes"]))] if remote.get("notes") else []),
            "",
            "This is a change to the package itself, so PythonOS [bold]can't update it automatically[/bold]. "
            "The core still updates by itself; to get the new package, download and install it:"),
            title="[bold yellow]Manual update available[/bold yellow]", border_style="yellow", expand=False))
    for url in remote.get("urls") or [remote.get("url")]:
        console.print(f"  [bold cyan]{url}[/bold cyan]", soft_wrap=True)   # never break an address across lines
    console.print("[dim]PythonOS is a command line system and cannot open links: type the address into a browser on any device.[/dim]")


def check_export_update(timeout=8):
    """For the Android app and scripts: the export status dict (with 'state') or None. Never raises."""
    try:
        response = requests.get(MANIFEST_URL, timeout=timeout)
        response.raise_for_status()
        return export_status(response.json())
    except Exception:
        return None


def check_thread(user):
    """The thread (not started) that looks for updates at most once a day and leaves notifications; None when there is nothing to check
    (updates switched off, or a source checkout). It is the update-check service."""
    import threading
    from pyos import notify, settings
    if not settings.get("update_check") or not packaged_version():
        return None

    def work():
        try:
            state = {}
            try:
                state = json.loads(CHECK_FILE.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
            if time.time() - state.get("last", 0) < CHECK_INTERVAL:
                return
            response = requests.get(MANIFEST_URL, timeout=8)
            response.raise_for_status()
            manifest = response.json()
            state["last"] = time.time()
            current = packaged_version()
            latest = str(manifest["version"])
            if version_key(latest) > version_key(current) and state.get("core") != latest:
                notify.notify(f"PythonOS {latest} is available - it updates itself: run updatecheck.",
                              title="Update available", user=user)
                state["core"] = latest
            es = export_status(manifest)
            if es and es["state"] in ("update", "incompatible"):
                key = f"{es['remote']['version']}:{es['state']}"
                if state.get("export") != key:
                    what = "needs" if es["state"] == "incompatible" else "has"
                    notify.notify(f"A new {es['title']} ({es['remote']['version']}) {what} a manual download - it can't "
                                  "update itself. Run updatecheck for the link.", title="Manual update", level="warn", user=user)
                    state["export"] = key
            CHECK_FILE.parent.mkdir(exist_ok=True)
            CHECK_FILE.write_text(json.dumps(state), encoding="utf-8")
        except Exception:
            pass   # offline or GitHub unavailable - try again next time

    return threading.Thread(target=work, name="update-check", daemon=True)


def check_in_background(user):
    """After login: look for updates at most once a day and leave notifications (never blocks the prompt)."""
    thread = check_thread(user)
    if thread is not None:
        thread.start()


def _log(message, level="INFO"):
    """A line in the system log about updating (never raises): what was checked, what was installed, why something failed."""
    try:
        from pyos import log
        log.log(f"update: {message}", level)
    except Exception:                                      # noqa: BLE001
        pass


def update_packaged(current, auto_update):
    """Update a packaged build from the latest GitHub release. Returns True if the core was updated."""
    console.print(f"[bold cyan]PythonOS {current}[/bold cyan] - checking for a newer release...")
    try:
        manifest = fetch_manifest()
    except requests.RequestException as e:
        _log(f"could not reach the update server: {type(e).__name__}: {str(e)[:150]}", "WARN")
        console.print(f"[bold red]Could not reach the update server:[/bold red] {e}")
        if "certificate" in str(e).lower() or "ssl" in str(e).lower():
            console.print("[yellow]A secure connection failed. The most common cause is a wrong clock: run timesync, then try again.[/yellow]")
        return False
    except ValueError as e:
        _log(f"the latest release has no usable update information: {str(e)[:150]}", "WARN")
        console.print(f"[bold red]The latest release has no usable update information:[/bold red] {e}")
        return False

    latest = str(manifest["version"])
    export_info = export_status(manifest)
    core_newer = version_key(latest) > version_key(current)

    bridge_libraries = False
    if export_info and export_info["state"] == "incompatible" and core_newer:
        from core import exportupdate
        if export_info.get("why") == "libraries" and exportupdate.can_install_libraries():
            bridge_libraries = True              # a container with a data volume: the new libraries are installed onto the volume first
        else:
            print_export_notice(export_info, blocking=True)
            offer_in_place(export_info)
            return False

    updated = False
    _log(f"checked: installed {current}, latest {latest}" + (f", package {export_info['state']}" if export_info else ""))
    if not core_newer:
        console.print(f"[bold green]PythonOS itself is up to date (latest release: {latest}).[/bold green]")
    else:
        table = Table(show_header=False, box=None)
        table.add_row("[bold]Installed[/bold]", str(current))
        table.add_row("[bold]Available[/bold]", f"[green]{latest}[/green]")
        with console.status("Working out what has changed..."):
            plan = plan_update(manifest)
        if plan["mode"] == "delta":
            table.add_row("[bold]Download[/bold]", f"{_human(plan['bytes'])}  [dim]({len(plan['changed'])} of {plan['total']} files changed)[/dim]")
        else:
            table.add_row("[bold]Download[/bold]", _human(plan["bytes"]) if plan["bytes"] else "unknown size")
        table.add_row("[bold]Time[/bold]", f"{_estimate_seconds(plan['bytes'])} at your usual speed")
        console.print(table)
        if manifest.get("notes"):
            console.print(Panel(Markdown(str(manifest["notes"])), title="What's new in PythonOS", border_style="dim", expand=False))

        lasts = update_lasts_only_until_restart()
        if lasts and not auto_update:
            console.print(f"[yellow]{lasts}[/yellow]")
        if not (auto_update or Confirm.ask("Install this update?", default=not lasts)):
            console.print("[bold yellow]Update cancelled.[/bold yellow]")
        else:
            zip_path = UPDATE_DIR / manifest["asset"]
            stage_dir = UPDATE_DIR / "stage"
            fetched = 0
            try:
                UPDATE_DIR.mkdir(parents=True, exist_ok=True)
                if plan["mode"] == "delta":
                    try:
                        stage_delta(manifest, plan, stage_dir)
                        fetched = plan["remote"].fetched
                    except RangeUnsupported:
                        plan = {**plan, "mode": "full"}
                if plan["mode"] != "delta":
                    fetched = download_core(manifest, zip_path)
                    extract_core(zip_path, manifest, stage_dir)
                if bridge_libraries:
                    from core import exportupdate
                    exportupdate.install_libraries(stage_dir / "requirements.txt")
                apply_core(stage_dir, latest)
                record_update(current, latest, manifest, plan, fetched)
                updated = True
            except (requests.RequestException, OSError, ValueError, zipfile.BadZipFile, KeyError) as e:
                _log(f"failed ({current} -> {latest}), nothing was changed: {type(e).__name__}: {str(e)[:200]}", "ERROR")
                console.print(f"[bold red]Update failed - nothing was changed:[/bold red] {e}")
            finally:
                shutil.rmtree(stage_dir, ignore_errors=True)
                if updated:
                    try:
                        zip_path.unlink()
                    except OSError:
                        pass
            if updated:
                _log(f"core updated {current} -> {latest} ({plan['mode']}, {fetched} bytes downloaded)")
                console.print(f"[bold green]Updated to {latest}![/bold green] Your files and accounts were not touched.")
                if not auto_update:
                    offer_restart()
                else:
                    console.print("[bold cyan]Restart PythonOS to start using it.[/bold cyan]")

    # The package around PythonOS is a separate matter: tell the user if it needs replacing by hand
    if export_info and export_info["state"] == "update":
        print_export_notice(export_info)
        offer_in_place(export_info)
    elif export_info and export_info["state"] == "current" and not core_newer:
        console.print(f"[dim]This {export_info['title']} ({export_info['local']['version']}) is the latest.[/dim]")
    return updated


def system_packages_available():
    """Why the system packages (Alpine's apk) cannot be updated here, or None. They exist on the ISO / VM images and installed systems."""
    if not sys.platform.startswith("linux") or not shutil.which("apk") or not (os.environ.get("PYOS_LIVE") == "1" or os.environ.get("PYOS_INSTALLED") == "1"):
        return "no system packages of its own here"
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return "needs root"
    return None


def upgradable(output):
    """Package names from `apk list -u` output (lines like 'busybox-1.36.1-r5 x86_64 {busybox} (GPL-2.0-only) [upgradable from: busybox-1.36.1-r4]')."""
    names = []
    for line in (output or "").splitlines():
        line = line.strip()
        if "upgradable" in line and line.split(" ")[0]:
            names.append(re.sub(r"-\d.*$", "", line.split(" ")[0]))
    return names


def update_system_packages():
    """Part of `updatecheck` on the ISO / VM images: refresh the system package lists (apk update) and offer the waiting upgrades
    (apk upgrade). On the live system the root is memory, so upgrades last until the restart, and the person is told; on an installed
    system they are kept."""
    if system_packages_available():
        return
    from core import hardware
    live = os.environ.get("PYOS_LIVE") == "1" and not os.environ.get("PYOS_INSTALLED")
    console.print("[bold cyan]Checking the system packages (the Linux underneath)...[/bold cyan]")
    code, out = hardware.run(["apk", "update"], timeout=180, merge=True)
    if code != 0:
        console.print(f"[yellow]Could not refresh the system package lists (no internet?): {escape_text(out)}[/yellow]")
        return
    code, out = hardware.run(["apk", "list", "-u"], timeout=60, merge=True)
    names = upgradable(out) if code == 0 else []
    if not names:
        console.print("[green]The system packages are up to date.[/green]")
        return
    shown = ", ".join(names[:8]) + (f" and {len(names) - 8} more" if len(names) > 8 else "")
    console.print(f"[bold]{len(names)} system package(s) can be upgraded:[/bold] {shown}")
    if live:
        console.print("[yellow]This system runs from memory: the upgrades last until it is switched off, and they use memory (about the size "
                      "of the download). Install the newer image to keep them.[/yellow]")
    if not Confirm.ask("Upgrade the system packages now?", default=not live):
        return
    code, out = hardware.run(["apk", "upgrade", "--no-progress"], timeout=1800, merge=True)
    if code == 0:
        console.print("[bold green]System packages upgraded.[/bold green]" + (" They are used again after a restart." if not live else ""))
    else:
        console.print(f"[bold red]The upgrade did not finish:[/bold red] {escape_text(out)}")


def escape_text(text):
    from rich.markup import escape
    lines = [l.strip() for l in (text or "").splitlines() if l.strip()]
    return escape(" | ".join(lines[-3:])[:300])


def update_system(auto_update=False):
    packaged = packaged_version()
    if packaged:
        if not auto_update:
            try:
                update_system_packages()
            except Exception as e:                       # noqa: BLE001 - the core update below must still run
                console.print(f"[dim]System packages skipped: {e}[/dim]")
        return update_packaged(packaged, auto_update)
    base_path = Path.cwd()  # Detect current working directory dynamically
    console.print(f"[bold blue]Working directory detected as:[/bold blue] {base_path}\n")
    # Check internet connection before proceeding
    console.print("[bold cyan]Checking internet connection...[/bold cyan]")
    if not check_internet_connection():
        console.print("[bold red]No internet connection detected. Please connect to the internet and try again.[/bold red]")
        return False
    console.print("[bold cyan]Checking for updates...[/bold cyan]")
    try:
        files = get_github_files()
    except HTTPError as e:
        if e.response.status_code == 403:
            console.print("[bold red]GitHub API rate limit exceeded. Please try again later.[/bold red]")
        else:
            console.print(f"[bold red]Failed to fetch update info: {e}[/bold red]")
        return False
    except requests.RequestException as e:
        console.print(f"[bold red]Failed to fetch update info: {e}[/bold red]")
        return False

    files_to_update = list_updates(files, base_path)

    if not files_to_update:
        console.print("[bold green]Your system is up to date! 🎉[/bold green]")
        return False

    show_update_table(files_to_update)

    if auto_update or Confirm.ask("\nDo you want to update these files?"):
        apply_updates(files_to_update, files, base_path)
        console.print("[bold green]Update complete![/bold green]")
        return True
    else:
        console.print("[bold yellow]Update cancelled.[/bold yellow]")
        return False

if __name__ == "__main__":
    update_system()
