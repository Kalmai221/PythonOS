# pyos/ghfetch.py - the GitHub CLI for the exports that do not already have it
#
# The ISO and the virtual machines install `gh` with their package manager (github-cli): that is their own system. Every other export
# (Windows, the Linux package, Docker, a source checkout, macOS) has the `gh` command download GitHub's own release the first time it is
# wanted, after asking, into PythonOS's private data (.OSData/tools/gh). Nothing is installed on the computer itself and nothing outside PythonOS's
# folder changes. The download is a pinned version, checked against the SHA-256 checksums GitHub publishes with it, and only the
# gh program is taken out of the archive.
import hashlib
import io
import os
import platform
import stat
import tarfile
import urllib.error
import urllib.request
import zipfile

VERSION = "2.102.0"
BASE = f"https://github.com/cli/cli/releases/download/v{VERSION}"
MAX_BYTES = 80 * 1024 * 1024
_open = urllib.request.urlopen               # replaced by tests

ARCH = {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64", "armv7l": "armv6", "armv6l": "armv6", "i686": "386", "i386": "386", "x86": "386"}


class FetchError(Exception):
    """Something the person can be told in one sentence."""


def on_android():
    return bool(os.environ.get("ANDROID_DATA") or os.environ.get("ANDROID_ROOT"))


def asset(system=None, machine=None):
    """The file name of GitHub's release for this computer, or None if there is none (Android, an unusual processor)."""
    if on_android():
        return None
    system = system or platform.system()
    arch = ARCH.get((machine or platform.machine()).lower())
    if not arch:
        return None
    if system == "Linux" and arch in ("amd64", "arm64", "armv6", "386"):
        return f"gh_{VERSION}_linux_{arch}.tar.gz"
    if system == "Windows" and arch in ("amd64", "arm64", "386"):
        return f"gh_{VERSION}_windows_{arch}.zip"
    if system == "Darwin" and arch in ("amd64", "arm64"):
        return f"gh_{VERSION}_macOS_{arch}.zip"
    return None


def possible():
    return asset() is not None


def folder():
    return os.path.join(".OSData", "tools", "gh", VERSION)


def program():
    return os.path.join(folder(), "gh.exe" if os.name == "nt" else "gh")


def fetched():
    """The downloaded gh, or None."""
    path = os.path.abspath(program())
    return path if os.path.isfile(path) else None


def _download(url):
    if not url.startswith("https://"):
        raise FetchError("only https:// addresses are used")
    try:
        with _open(urllib.request.Request(url, headers={"User-Agent": "PythonOS-gh"}), timeout=60) as response:    # nosec - pinned https address
            data = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as e:
        raise FetchError(f"GitHub answered HTTP {e.code} for {url.rsplit('/', 1)[-1]}") from e
    except (urllib.error.URLError, OSError) as e:
        raise FetchError(f"could not download the GitHub CLI: {getattr(e, 'reason', e)}") from e
    if len(data) > MAX_BYTES:
        raise FetchError("the download is larger than expected; it was refused")
    return data


def _wanted_hash(sums, name):
    for line in sums.decode("utf-8", "replace").splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1].lstrip("*") == name:
            return parts[0].lower()
    return None


def _extract(name, data):
    """The bytes of the gh program inside the archive. Nothing else is read out of it."""
    wanted = "gh.exe" if name.endswith(".zip") and "windows" in name else "gh"
    if name.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for info in archive.infolist():
                parts = info.filename.replace("\\", "/").split("/")
                if parts[-1] == wanted and parts[-2:-1] == ["bin"] and not info.is_dir():
                    return archive.read(info)
    else:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive.getmembers():
                parts = member.name.split("/")
                if member.isfile() and parts[-1] == wanted and parts[-2:-1] == ["bin"]:
                    return archive.extractfile(member).read()
    raise FetchError("the GitHub CLI program was not in the download")


def fetch(log=print):
    """Download gh into PythonOS's private data. Returns its path. Raises FetchError."""
    name = asset()
    if not name:
        raise FetchError("GitHub's CLI has no download for this system")
    log(f"Downloading the GitHub CLI {VERSION} ({name})...")
    data = _download(f"{BASE}/{name}")
    wanted = _wanted_hash(_download(f"{BASE}/gh_{VERSION}_checksums.txt"), name)
    if not wanted or hashlib.sha256(data).hexdigest() != wanted:
        raise FetchError("the download did not match GitHub's published checksum, so it was thrown away")
    program_bytes = _extract(name, data)
    os.makedirs(folder(), exist_ok=True)
    target = os.path.abspath(program())
    temporary = target + ".part"
    with open(temporary, "wb") as f:
        f.write(program_bytes)
    os.chmod(temporary, os.stat(temporary).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.replace(temporary, target)
    return target
