from pathlib import Path
from urllib.parse import urljoin
import hashlib
import json
import os
import re
import shutil
import sys
import zipfile
import requests
from rich.console import Console
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
    """Download the core zip and check it against the manifest's checksum."""
    digest = hashlib.sha256()
    total = int(manifest.get("size") or 0)
    with requests.get(core_url(manifest), stream=True, timeout=TIMEOUT) as response:
        response.raise_for_status()
        with Progress("[progress.description]{task.description}", BarColumn(),
                      "[progress.percentage]{task.percentage:>3.0f}%", console=console, transient=True) as progress:
            task = progress.add_task("Downloading update...", total=total or None)
            with open(destination, "wb") as f:
                for chunk in response.iter_content(65536):
                    f.write(chunk)
                    digest.update(chunk)
                    progress.advance(task, len(chunk))
    if digest.hexdigest() != manifest["sha256"]:
        raise ValueError("the downloaded update is corrupted (checksum mismatch)")


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
    except Exception:
        for name in moved_dirs:
            shutil.rmtree(name, ignore_errors=True)
            if (backup / name).exists():
                shutil.move(str(backup / name), name)
        for name in copied_files:
            if (backup / name).exists():
                shutil.copy2(backup / name, name)
        raise


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
        status["state"], status["reason"] = "incompatible", "it needs features this version of the package does not have"
    elif os.environ.get("PYOS_BUNDLED") == "1" and manifest.get("requirements_sha256") not in (None, requirements_hash()):
        status["state"], status["reason"] = "incompatible", "it needs new libraries, which this package cannot install itself"
    elif version_key(remote["version"]) > version_key(local["version"]):
        status["state"] = "update"
    return status


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
        console.print(Panel(
            f"A newer [bold]{status['title']}[/bold] is available: {local['version']} -> [bold green]{remote['version']}[/bold green]\n"
            f"[dim]{remote.get('notes') or ''}[/dim]\n\n"
            "This is a change to the package itself, so PythonOS [bold]can't update it automatically[/bold]. "
            "The core still updates by itself; to get the new package, download and install it:",
            title="[bold yellow]Manual update available[/bold yellow]", border_style="yellow", expand=False))
    for url in remote.get("urls") or [remote.get("url")]:
        console.print(f"  [bold cyan]{url}[/bold cyan]", soft_wrap=True)   # never break a link across lines


def check_export_update(timeout=8):
    """For the Android app and scripts: the export status dict (with 'state') or None. Never raises."""
    try:
        response = requests.get(MANIFEST_URL, timeout=timeout)
        response.raise_for_status()
        return export_status(response.json())
    except Exception:
        return None


def check_in_background(user):
    """After login: look for updates at most once a day and leave notifications (never blocks the prompt)."""
    import threading
    from pyos import notify, settings
    if not settings.get("update_check") or not packaged_version():
        return

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

    threading.Thread(target=work, name="update-check", daemon=True).start()


def update_packaged(current, auto_update):
    """Update a packaged build from the latest GitHub release. Returns True if the core was updated."""
    console.print(f"[bold cyan]PythonOS {current}[/bold cyan] - checking for a newer release...")
    try:
        manifest = fetch_manifest()
    except requests.RequestException as e:
        console.print(f"[bold red]Could not reach the update server:[/bold red] {e}")
        return False
    except ValueError as e:
        console.print(f"[bold red]The latest release has no usable update information:[/bold red] {e}")
        return False

    latest = str(manifest["version"])
    export_info = export_status(manifest)
    core_newer = version_key(latest) > version_key(current)

    if export_info and export_info["state"] == "incompatible" and core_newer:
        print_export_notice(export_info, blocking=True)
        return False

    updated = False
    if not core_newer:
        console.print(f"[bold green]PythonOS itself is up to date (latest release: {latest}).[/bold green]")
    else:
        table = Table(show_header=False, box=None)
        table.add_row("[bold]Installed[/bold]", str(current))
        table.add_row("[bold]Available[/bold]", f"[green]{latest}[/green]")
        if manifest.get("size"):
            table.add_row("[bold]Download[/bold]", f"{int(manifest['size']) / 1024:.0f} KB")
        console.print(table)
        if manifest.get("notes"):
            console.print(f"[dim]{manifest['notes']}[/dim]")

        if not (auto_update or Confirm.ask("Install this update?", default=True)):
            console.print("[bold yellow]Update cancelled.[/bold yellow]")
        else:
            zip_path = UPDATE_DIR / manifest["asset"]
            stage_dir = UPDATE_DIR / "stage"
            try:
                UPDATE_DIR.mkdir(parents=True, exist_ok=True)
                download_core(manifest, zip_path)
                extract_core(zip_path, manifest, stage_dir)
                apply_core(stage_dir, latest)
                updated = True
            except (requests.RequestException, OSError, ValueError, zipfile.BadZipFile, KeyError) as e:
                console.print(f"[bold red]Update failed - nothing was changed:[/bold red] {e}")
            finally:
                shutil.rmtree(stage_dir, ignore_errors=True)
                try:
                    zip_path.unlink()
                except OSError:
                    pass
            if updated:
                console.print(f"[bold green]Updated to {latest}![/bold green] Your files and accounts were not touched.")
                if not auto_update:
                    offer_restart()
                else:
                    console.print("[bold cyan]Restart PythonOS to start using it.[/bold cyan]")

    # The package around PythonOS is a separate matter: tell the user if it needs replacing by hand
    if export_info and export_info["state"] == "update":
        print_export_notice(export_info)
    elif export_info and export_info["state"] == "current" and not core_newer:
        console.print(f"[dim]This {export_info['title']} ({export_info['local']['version']}) is the latest.[/dim]")
    return updated


def update_system(auto_update=False):
    packaged = packaged_version()
    if packaged:
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
