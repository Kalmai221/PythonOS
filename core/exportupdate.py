"""Export update strategies: how each export installs a newer version of the package around PythonOS, by itself, when it can.

PythonOS always updates its own core files by itself (core/sysupdate.py). The package around it is a different matter: the Windows
app and its launcher, the Android APK, the Linux launcher, the ISO's kernel and boot setup, the Docker image. Each export has a
strategy that fits what it can really do:

  windows   download the web installer, check it, let it replace the app while PythonOS is closed
  linux     installed from a package (.deb, .rpm, Arch): download the package, check it, install it with the distribution's own tool
            (asks for your password through sudo or pkexec). From the tarball: replace the launcher files in place
  android   download the APK, check it, hand it to Android's installer (Android asks you to confirm: an app cannot replace itself silently)
  iso       write the new ISO over the medium the system started from (a USB stick or virtual disk), check what was written, restart
  docker    cannot replace its image, but new Python libraries are installed on the data volume, so a core update that needs them goes ahead

Every download is checked against the release's SHA256SUMS before anything runs or is written. Every strategy asks first.
Nothing here runs a shell: commands are fixed argument lists.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time

import requests
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn, TimeRemainingColumn, TransferSpeedColumn
from rich.prompt import Confirm, Prompt

console = Console()
CHUNK = 1 << 20


# ------------------------------------------------------------------------------------------ shared helpers
def remote_urls(status):
    remote = (status or {}).get("remote") or {}
    urls = list(remote.get("urls") or []) + list(remote.get("extra_urls") or [])
    if remote.get("url"):
        urls.insert(0, remote["url"])
    seen, ordered = set(), []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            ordered.append(url)
    return ordered


def pick(urls, pattern):
    """The first URL whose file name matches the regular expression."""
    for url in urls:
        if re.search(pattern, url.rsplit("/", 1)[-1]):
            return url
    return None


def machine():
    """The computer's processor in the names the release files use: 'x86_64' or 'aarch64' (the real one, also for an emulated program)."""
    from pyos import archinfo
    return archinfo.arch()


def fetch(url, destination, label="Downloading"):
    """Download a release file with a progress bar and check it against the release's SHA256SUMS. A file with no published checksum
    is refused. The partial file is deleted when anything is wrong. Returns the checksum."""
    from core import sysupdate
    want = sysupdate.checksum_of(url)
    if not want:
        raise ValueError("this release has no checksum for the file, so it cannot be checked")
    digest = hashlib.sha256()
    try:
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length") or 0)
            with Progress(TextColumn("[cyan]{task.description}"), BarColumn(), DownloadColumn(), TransferSpeedColumn(),
                          TimeRemainingColumn(), console=console, transient=True) as bar, open(destination, "wb") as f:
                task = bar.add_task(label, total=total or None)
                for chunk in response.iter_content(CHUNK):
                    f.write(chunk)
                    digest.update(chunk)
                    bar.advance(task, len(chunk))
    except BaseException:
        _remove(destination)
        raise
    if digest.hexdigest() != want:
        _remove(destination)
        raise ValueError("the download does not match its checksum (damaged or changed), so it was deleted")
    return want


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


def _run(command, **kwargs):
    return subprocess.run(command, stdin=kwargs.pop("stdin", subprocess.DEVNULL), **kwargs)


def locked_down():
    try:
        from pyos import lockdown
        return lockdown.enabled()
    except Exception:
        return False


# ------------------------------------------------------------------------------------------ the strategies
class Strategy:
    name = ""
    needs_restart = True

    def __init__(self, status):
        self.status = status

    def applies(self):
        """True when this strategy can install the update on this machine. Sets self.why when it cannot (shown to the user)."""
        return False

    why = ""

    def describe(self):
        return ""

    def run(self):
        return False


class WindowsInstaller(Strategy):
    name = "windows"

    def applies(self):
        from core import sysupdate
        return os.name == "nt" and bool(sysupdate.installer_url(self.status))

    def describe(self):
        return ("PythonOS downloads the small Windows installer, checks it against the release's checksum, then closes, updates itself "
                "and starts again. Your accounts and files are kept.")

    def run(self):
        from core import sysupdate
        return sysupdate.update_in_place(self.status)


class LinuxPackage(Strategy):
    """Installed from a .deb, .rpm or Arch package: the distribution's own tool installs the new one."""
    name = "linux-package"
    KINDS = (("deb", ["dpkg", "-S"], r"\.deb$"), ("rpm", ["rpm", "-qf"], r"\.rpm$"), ("pacman", ["pacman", "-Qo"], r"\.pkg\.tar\.zst$"))

    def __init__(self, status):
        super().__init__(status)
        self.home = launcher_dir()
        self.kind = None
        self.url = None

    def owner(self):
        launcher = os.path.join(self.home, "pythonos") if self.home else None
        if not launcher or not os.path.exists(launcher):
            return None
        for kind, command, pattern in self.KINDS:
            if shutil.which(command[0]):
                try:
                    if _run(command + [launcher], capture_output=True).returncode == 0:
                        return kind, pattern
                except OSError:
                    continue
        return None

    def applies(self):
        if os.name != "posix" or os.environ.get("PYOS_LIVE") == "1" or locked_down():
            return False
        found = self.owner()
        if not found:
            return False
        self.kind, pattern = found
        self.url = pick(remote_urls(self.status), pattern)
        if not self.url:
            self.why = "this release has no package of that kind"
            return False
        if not elevation():
            self.why = "installing needs sudo or pkexec, and neither is available"
            return False
        return True

    def command(self, package):
        return install_command(self.kind, package)

    def describe(self):
        return (f"PythonOS downloads the {self.kind} package, checks it against the release's checksum, then installs it with your "
                f"system's package tool ({' '.join(elevation())} will ask for your password). Your files and accounts are kept.")

    def run(self):
        package = os.path.join(tempfile.gettempdir(), self.url.rsplit("/", 1)[-1])
        try:
            fetch(self.url, package, "Downloading the package")
        except (ValueError, requests.RequestException, OSError) as e:
            console.print(f"[bold red]Not updated: {escape(str(e))}[/bold red]")
            return False
        command = elevation() + self.command(package)
        console.print(f"[dim]Running: {escape(' '.join(command))}[/dim]")
        try:
            code = _run(command, stdin=None).returncode
        except OSError as e:
            console.print(f"[bold red]Not updated: {escape(str(e))}[/bold red]")
            code = 1
        _remove(package)
        if code != 0:
            console.print("[bold red]The package tool did not finish the update. Nothing was changed by PythonOS.[/bold red]")
            return False
        console.print("[bold green]The new package is installed.[/bold green] Restart PythonOS to use it.")
        return True


class LinuxTarball(Strategy):
    """Unpacked from the .tar.gz: replace the launcher files in the folder it runs from."""
    name = "linux-tarball"
    FILES = ("pythonos", "bootstrap.py", "export.json")

    def __init__(self, status):
        super().__init__(status)
        self.home = launcher_dir()
        self.url = None

    def applies(self):
        if os.name != "posix" or os.environ.get("PYOS_LIVE") == "1" or locked_down() or not self.home:
            return False
        if not os.access(self.home, os.W_OK) or not os.path.exists(os.path.join(self.home, "pythonos")):
            return False
        self.url = pick(remote_urls(self.status), r"-linux\.tar\.gz$")
        return bool(self.url)

    def describe(self):
        return (f"PythonOS downloads the new tarball, checks it against the release's checksum and replaces the launcher files in "
                f"{self.home}. Your files and accounts are kept.")

    def run(self):
        archive = os.path.join(tempfile.gettempdir(), self.url.rsplit("/", 1)[-1])
        try:
            fetch(self.url, archive, "Downloading the new launcher")
            replaced = replace_from_tarball(archive, self.home, self.FILES)
        except (ValueError, requests.RequestException, OSError, tarfile.TarError) as e:
            console.print(f"[bold red]Not updated: {escape(str(e))}[/bold red]")
            return False
        finally:
            _remove(archive)
        console.print(f"[bold green]Replaced {', '.join(replaced)}.[/bold green] Restart PythonOS to use it.")
        return True


class AndroidInstaller(Strategy):
    """The app hands the checked APK to Android's installer; Android asks you to confirm."""
    name = "android"
    needs_restart = False

    def applies(self):
        if self.status.get("platform") != "android":
            return False
        try:
            from java import jclass  # noqa: F401 - only there inside the Android app
        except Exception:
            return False
        self.url = apk_for(remote_urls(self.status), machine())
        return bool(self.url)

    def describe(self):
        return ("PythonOS downloads the new app, checks it against the release's checksum and hands it to Android's installer. "
                "Android asks you to confirm (an app cannot replace itself silently). Your files are kept.")

    def run(self):
        from core import sysupdate
        try:
            sha = sysupdate.checksum_of(self.url)
        except Exception:
            sha = None
        if not sha:
            console.print("[bold red]Not updated: this release has no checksum for the file, so it cannot be checked.[/bold red]")
            return False
        from java import jclass
        problem = str(jclass("com.pythonos.app.TerminalBridge").installUpdate(self.url, sha))
        if problem:
            console.print(f"[bold red]Not updated: {escape(problem)}[/bold red]")
            return False
        return True


class IsoMedium(Strategy):
    """Writes the new ISO over the medium the live system started from, then restarts."""
    name = "iso"

    def __init__(self, status):
        super().__init__(status)
        self.medium = None
        self.url = None

    def applies(self):
        if self.status.get("platform") != "iso" or os.environ.get("PYOS_LIVE") != "1" or not hasattr(os, "geteuid") or os.geteuid() != 0:
            return False
        self.medium = boot_medium()
        if not self.medium:
            self.why = "could not tell which disk this system started from"
            return False
        if self.medium["optical"]:
            self.why = "this system started from a disc, which cannot be rewritten"
            return False
        self.url = iso_for(remote_urls(self.status), machine(), minimal_variant())
        if not self.url:
            self.why = "this release has no ISO of the kind in use"
            return False
        return True

    def describe(self):
        size = self.medium["size"] // (1024 ** 2) if self.medium and self.medium.get("size") else 0
        return (f"PythonOS downloads the new ISO, checks it against the release's checksum, writes it over {self.medium['disk']} "
                f"({size} MB, the disk this system started from), checks what was written, and restarts. "
                "If power is lost during the write, that disk will not start until the ISO is written to it again with the flash tool. "
                "Your data disk (persistent storage) is a different disk and is not touched.")

    def run(self):
        from core import sysupdate, persist
        disk = self.medium["disk"]
        try:
            if persist.active() and persist.mounted_device() and disk_name(persist.mounted_device()) == disk_name(disk):
                console.print("[bold red]Not updated: the data disk is on the same disk as the system.[/bold red]")
                return False
        except Exception:
            pass
        iso_size = remote_size(self.url)
        if iso_size and self.medium["size"] and iso_size > self.medium["size"]:
            console.print(f"[bold red]Not updated: the new ISO ({iso_size // 1024 ** 2} MB) does not fit on {disk} "
                          f"({self.medium['size'] // 1024 ** 2} MB).[/bold red]")
            return False
        folder = scratch_folder(iso_size or 0)
        if folder is None:
            console.print("[bold red]Not updated: there is no room to keep the download (it goes on the data disk, or in memory).[/bold red]")
            return False
        image = os.path.join(folder, self.url.rsplit("/", 1)[-1])
        try:
            fetch(self.url, image, "Downloading the new ISO")
        except (ValueError, requests.RequestException, OSError) as e:
            console.print(f"[bold red]Not updated: {escape(str(e))}[/bold red]")
            return False
        answer = Prompt.ask(f"[bold red]About to overwrite {disk}.[/bold red] Type the disk name ({disk}) to continue, or anything else to cancel",
                            default="").strip()
        if answer != disk:
            console.print("[yellow]Cancelled. Nothing was changed.[/yellow]")
            _remove(image)
            return False
        try:
            written = write_image(image, disk, progress=_write_progress)
        except (OSError, ValueError) as e:
            console.print(f"[bold red]The write failed: {escape(str(e))}[/bold red]\n"
                          "The disk may not start now: write the ISO to it again with the flash tool.")
            return False
        _remove(image)
        console.print(f"[bold green]Wrote and checked {written // 1024 ** 2} MB.[/bold green] Restarting into the new version...")
        time.sleep(2)
        try:
            from core import screens
            screens.power("restart")
        except Exception:
            pass
        return True


STRATEGIES = (WindowsInstaller, LinuxPackage, LinuxTarball, AndroidInstaller, IsoMedium)


def strategy_for(status):
    """The strategy that can install this export's update on this machine, or None."""
    if not status or not status.get("remote"):
        return None
    for cls in STRATEGIES:
        strategy = cls(status)
        try:
            if strategy.applies():
                return strategy
        except Exception:
            continue
    return None


def why_not(status):
    """Why nothing can install the update itself (for the notice), or ''."""
    for cls in STRATEGIES:
        strategy = cls(status)
        try:
            strategy.applies()
        except Exception:
            continue
        if strategy.why:
            return strategy.why
    return ""


def offer(status):
    """After the update notice: say what PythonOS can do about it, and do it when the user agrees. Returns True if an update was started."""
    strategy = strategy_for(status)
    if strategy is None:
        return False
    console.print(Panel(escape(strategy.describe()), title="[bold cyan]PythonOS can do this itself[/bold cyan]", border_style="cyan", expand=False))
    try:
        if not Confirm.ask("Update the package now?", default=True):
            return False
    except (KeyboardInterrupt, EOFError):
        return False
    return bool(strategy.run())


# ------------------------------------------------------------------------------------------ Linux
def launcher_dir():
    """The folder the Linux launcher runs from (where export.json is), or None."""
    path = os.environ.get("PYOS_EXPORT_INFO")
    if path and os.path.isfile(path):
        return os.path.dirname(os.path.realpath(path))
    return None


def elevation():
    """['sudo'] / ['pkexec'] / [] (already root) / None (cannot become root)."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return []
    for tool in ("sudo", "pkexec"):
        if shutil.which(tool):
            return [tool]
    return None


def install_command(kind, package):
    """The package tool's command (a list, no shell) that installs a downloaded package file."""
    if kind == "deb":
        return ["apt-get", "install", "-y", package] if shutil.which("apt-get") else ["dpkg", "-i", package]
    if kind == "rpm":
        if shutil.which("dnf"):
            return ["dnf", "install", "-y", "--nogpgcheck", package]
        if shutil.which("zypper"):
            return ["zypper", "--non-interactive", "install", "--allow-unsigned-rpm", package]
        return ["rpm", "-U", package]
    if kind == "pacman":
        return ["pacman", "-U", "--noconfirm", package]
    raise ValueError(f"unknown package kind {kind}")


def replace_from_tarball(archive, folder, names):
    """Put the named files from the release tarball into `folder`, each replaced in one step (never half written)."""
    replaced = []
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar.getmembers():
            parts = member.name.split("/")
            if not member.isfile() or len(parts) != 2 or parts[1] not in names or ".." in parts:
                continue
            data = tar.extractfile(member).read()
            target = os.path.join(folder, parts[1])
            temporary = target + ".new"
            with open(temporary, "wb") as f:
                f.write(data)
            os.chmod(temporary, 0o755 if parts[1] == "pythonos" else 0o644)
            os.replace(temporary, target)
            replaced.append(parts[1])
    if not replaced:
        raise ValueError("the tarball does not contain the launcher files")
    return replaced


# ------------------------------------------------------------------------------------------ Android
def apk_for(urls, arch):
    """The APK made for this processor, else the universal one."""
    wanted = {"aarch64": "arm64-v8a", "arm64": "arm64-v8a", "x86_64": "x86_64"}.get(arch)
    if wanted:
        found = pick(urls, rf"-android-{re.escape(wanted)}\.apk$")
        if found:
            return found
    return pick(urls, r"-android\.apk$") or pick(urls, r"\.apk$")


# ------------------------------------------------------------------------------------------ ISO
def minimal_variant():
    try:
        with open("/etc/pythonos-variant", encoding="utf-8") as f:
            return f.read().strip() == "minimal"
    except OSError:
        return False


def iso_for(urls, arch, minimal):
    """The ISO of the same processor and variant (full or minimal) as the one in use."""
    for url in urls:
        name = url.rsplit("/", 1)[-1]
        if name.endswith(f"-{arch}.iso") and (("-minimal-" in name) == bool(minimal)):
            return url
    return None


def parse_mounts(text):
    """[(device, mount point, file system)] from the text of /proc/mounts."""
    rows = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            rows.append((parts[0], parts[1].replace("\\040", " "), parts[2]))
    return rows


def mount_for_path(path, mounts):
    """The mount (device, mount point, file system) that holds `path`: the one with the longest matching mount point."""
    best = None
    for device, point, fs in mounts:
        if path == point or path.startswith(point.rstrip("/") + "/"):
            if best is None or len(point) > len(best[1]):
                best = (device, point, fs)
    return best


def disk_name(device):
    """'sdb' for /dev/sdb1, 'nvme0n1' for /dev/nvme0n1p2, 'mmcblk0' for /dev/mmcblk0p1 (the whole disk a partition is on)."""
    name = os.path.basename(str(device))
    try:
        if os.path.exists(f"/sys/class/block/{name}/partition"):
            return os.path.basename(os.path.dirname(os.path.realpath(f"/sys/class/block/{name}")))
    except OSError:
        pass
    match = re.match(r"^((?:nvme\d+n\d+|mmcblk\d+|loop\d+|sr\d+)|[a-z]+)(?:p?\d+)?$", name)
    return match.group(1) if match else name


def boot_medium():
    """{'disk': '/dev/sdb', 'size': bytes, 'optical': bool} for the disk the live system started from, or None. Found through the
    file the system image (modloop) is read from, and the mount that file sits on."""
    try:
        with open("/proc/mounts", encoding="utf-8") as f:
            mounts = parse_mounts(f.read())
    except OSError:
        return None
    backing = []
    try:
        for entry in os.listdir("/sys/block"):
            if entry.startswith("loop"):
                try:
                    with open(f"/sys/block/{entry}/loop/backing_file", encoding="utf-8") as f:
                        backing.append(f.read().strip())
                except OSError:
                    continue
    except OSError:
        pass
    for path in backing:
        mount = mount_for_path(path, mounts)
        if mount and mount[0].startswith("/dev/") and mount[1] != "/":
            return describe_disk(disk_name(mount[0]))
    for device, point, fs in mounts:
        if point.startswith("/media/") and device.startswith("/dev/") and fs in ("iso9660", "vfat", "ext4", "ext2", "ext3", "squashfs"):
            if os.path.exists(os.path.join(point, ".alpine-release")) or os.path.isdir(os.path.join(point, "boot")):
                return describe_disk(disk_name(device))
    return None


def describe_disk(name):
    size = 0
    try:
        with open(f"/sys/class/block/{name}/size", encoding="utf-8") as f:
            size = int(f.read().strip()) * 512
    except (OSError, ValueError):
        pass
    return {"disk": f"/dev/{name}", "size": size, "optical": name.startswith("sr")}


def remote_size(url):
    try:
        response = requests.head(url, allow_redirects=True, timeout=15)
        return int(response.headers.get("Content-Length") or 0)
    except (requests.RequestException, ValueError):
        return 0


def scratch_folder(size):
    """Where the downloaded ISO is kept before it is written: the data disk when there is one, else memory. None if neither has room."""
    margin = 64 * 1024 ** 2
    for folder in ("/mnt/pyos-data", tempfile.gettempdir()):
        try:
            if os.path.isdir(folder) and os.access(folder, os.W_OK) and shutil.disk_usage(folder).free >= size + margin:
                return folder
        except OSError:
            continue
    return None


def _write_progress(done, total):
    pass


def write_image(source, destination, progress=None):
    """Copy the file `source` over the disk (or file) `destination` and read it back to check every byte. Returns the bytes written."""
    total = os.path.getsize(source)
    digest = hashlib.sha256()
    written = 0
    with Progress(TextColumn("[cyan]Writing"), BarColumn(), DownloadColumn(), TimeRemainingColumn(), console=console, transient=True) as bar:
        task = bar.add_task("write", total=total)
        with open(source, "rb") as src, open(destination, "r+b") as dst:
            while True:
                chunk = src.read(CHUNK)
                if not chunk:
                    break
                dst.write(chunk)
                digest.update(chunk)
                written += len(chunk)
                bar.advance(task, len(chunk))
            dst.flush()
            os.fsync(dst.fileno())
    check = hashlib.sha256()
    left = written
    with Progress(TextColumn("[cyan]Checking"), BarColumn(), console=console, transient=True) as bar:
        task = bar.add_task("check", total=written)
        with open(destination, "rb") as dst:
            while left > 0:
                chunk = dst.read(min(CHUNK, left))
                if not chunk:
                    break
                check.update(chunk)
                left -= len(chunk)
                bar.advance(task, len(chunk))
    if left or check.hexdigest() != digest.hexdigest():
        raise ValueError("what was written does not match the download")
    return written


# ------------------------------------------------------------------------------------------ Docker: libraries on the volume
def libraries_dir():
    """Where new Python libraries go in a container with a data volume (the entrypoint adds it to the search path), else None."""
    folder = os.environ.get("PYOS_LIBS_DIR")
    return folder if folder and os.environ.get("PYOS_PERSISTENT") == "1" else None


def can_install_libraries():
    return bool(libraries_dir()) and not locked_down()


def install_libraries(requirements):
    """pip-install the libraries a core update needs onto the data volume. Raises ValueError (and changes nothing the old core needs) on failure."""
    folder = libraries_dir()
    if not folder:
        raise ValueError("there is no data volume to keep new libraries on")
    console.print("[cyan]Installing the new libraries this update needs onto your data volume...[/cyan]")
    os.makedirs(folder, exist_ok=True)
    code = _run([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "--target", folder, "-r", str(requirements)]).returncode
    if code != 0:
        raise ValueError("pip could not install the new libraries")
