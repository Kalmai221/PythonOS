# pyos/archive.py - zip and tar helpers for the zip, unzip and tar commands.
#
# Everything is checked against the PythonOS filesystem rules (pyos.fs.resolve): you can only read what you may read and
# only write where you may write. Extraction refuses paths that would escape the destination ("zip slip"), links and
# device files, and archives that unpack to an unreasonable size.
import os
import tarfile
import zipfile

from . import fs, optional

MAX_TOTAL = 1024 ** 3          # refuse to unpack more than 1 GB
MAX_FILES = 50_000


class ArchiveError(Exception):
    """A problem to tell the user about (not a crash)."""


def gather(paths):
    """[(real path, name inside the archive)] for files and folders (recursively). Names are relative to each argument."""
    entries = []
    for text in paths:
        full = fs.resolve(text)
        if not os.path.exists(full):
            raise ArchiveError(f"{text}: No such file or directory")
        base = os.path.basename(full.rstrip("/\\")) or "root"
        if os.path.isdir(full):
            entries.append((full, base + "/"))
            for root, dirs, files in os.walk(full):
                dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(root, d)))
                for d in dirs:
                    entries.append((os.path.join(root, d), base + "/" + os.path.relpath(os.path.join(root, d), full).replace(os.sep, "/") + "/"))
                for name in sorted(files):
                    p = os.path.join(root, name)
                    if not os.path.islink(p):
                        entries.append((p, base + "/" + os.path.relpath(p, full).replace(os.sep, "/")))
        else:
            entries.append((full, base))
    if len(entries) > MAX_FILES:
        raise ArchiveError("too many files")
    return entries


def _target(dest, name):
    """Where an archive member goes, refusing anything outside dest."""
    name = name.replace("\\", "/")
    if name.startswith("/") or ".." in name.split("/") or ":" in name.split("/")[0]:
        raise ArchiveError(f"unsafe name in the archive: {name}")
    target = os.path.abspath(os.path.join(dest, *name.split("/")))
    if not fs._inside(target, dest):
        raise ArchiveError(f"unsafe name in the archive: {name}")
    return target


def make_zip(archive, paths):
    out = fs.resolve(archive, write=True)
    entries = [(p, n) for p, n in gather(paths) if os.path.abspath(p) != os.path.abspath(out)]
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for path, name in entries:
            if name.endswith("/"):
                z.writestr(name, "")
            else:
                z.write(path, name)
    return len(entries), os.path.getsize(out)


def list_zip(archive):
    with zipfile.ZipFile(fs.resolve(archive)) as z:
        return [(i.filename, i.file_size) for i in z.infolist()]


def extract_zip(archive, dest_text, overwrite=False):
    src = fs.resolve(archive)
    dest = fs.resolve(dest_text, write=True)
    os.makedirs(dest, exist_ok=True)
    count = total = 0
    with zipfile.ZipFile(src) as z:
        infos = z.infolist()
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_TOTAL:
            raise ArchiveError("the archive is too large to unpack here")
        plan = []
        for info in infos:
            if (info.external_attr >> 28) == 0xA:           # a symbolic link
                continue
            target = _target(dest, info.filename)
            if os.path.exists(target) and not info.is_dir() and not overwrite:
                raise ArchiveError(f"{info.filename} already exists (use -o to overwrite)")
            plan.append((info, target))
        for info, target in plan:
            if info.is_dir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with z.open(info) as s, open(target, "wb") as o:
                while True:
                    chunk = s.read(1 << 20)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_TOTAL:
                        raise ArchiveError("the archive is too large to unpack here")
                    o.write(chunk)
            count += 1
    return count, total


def _py7zr():
    """The py7zr library, or an ArchiveError that says what to do (7z needs it; zip and tar do not)."""
    module = optional.get("py7zr")
    if module is None:
        raise ArchiveError("7z archives need the py7zr library (pip install py7zr)")
    return module


def _guarded(function):
    """py7zr raises its own errors (a damaged file, a password): turn them into the message every archive command shows."""
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (ArchiveError, OSError):
            raise
        except Exception as e:                                # noqa: BLE001 - whatever the library raises is "this 7z cannot be used"
            raise ArchiveError(f"cannot use this 7z archive ({type(e).__name__}: {e})") from e
    wrapper.__name__ = function.__name__
    wrapper.__doc__ = function.__doc__
    return wrapper


def is_7z(name):
    return name.lower().endswith(".7z")


@_guarded
def make_7z(archive, paths):
    py7zr = _py7zr()
    out = fs.resolve(archive, write=True)
    entries = [(p, n) for p, n in gather(paths) if os.path.abspath(p) != os.path.abspath(out)]
    with py7zr.SevenZipFile(out, "w") as z:
        for path, name in entries:
            z.write(path, name.rstrip("/"))
    return len(entries), os.path.getsize(out)


@_guarded
def list_7z(archive):
    py7zr = _py7zr()
    with py7zr.SevenZipFile(fs.resolve(archive), "r") as z:
        return [(i.filename + ("/" if i.is_directory else ""), 0 if i.is_directory else i.uncompressed) for i in z.list()]


@_guarded
def extract_7z(archive, dest_text, overwrite=False):
    """Unpack a .7z with the same rules as zip and tar: no names outside the destination, no links, a size limit, and nothing replaced without -o."""
    py7zr = _py7zr()
    src = fs.resolve(archive)
    dest = fs.resolve(dest_text, write=True)
    os.makedirs(dest, exist_ok=True)
    with py7zr.SevenZipFile(src, "r") as z:
        infos = list(z.list())
        if len(infos) > MAX_FILES or sum(i.uncompressed or 0 for i in infos) > MAX_TOTAL:
            raise ArchiveError("the archive is too large to unpack here")
        count = total = 0
        for info in infos:
            if getattr(info, "is_symlink", False) or getattr(info, "is_junction", False):
                raise ArchiveError(f"{info.filename} is a link (7z archives with links are not unpacked)")
            target = _target(dest, info.filename)
            if os.path.exists(target) and not info.is_directory and not overwrite:
                raise ArchiveError(f"{info.filename} already exists (use -o to overwrite)")
            if not info.is_directory:
                count += 1
                total += info.uncompressed or 0
        if hasattr(z, "reset"):
            z.reset()                                          # the listing above read the archive's index
        z.extractall(path=dest)  # nosec B202 - every name was checked against the destination above, links refused
    return count, total


def _tar_mode(letter, gz):
    return f"{letter}:gz" if gz else f"{letter}"


def make_tar(archive, paths, gz=False):
    out = fs.resolve(archive, write=True)
    entries = [(p, n) for p, n in gather(paths) if os.path.abspath(p) != os.path.abspath(out)]
    with tarfile.open(out, _tar_mode("w", gz)) as t:
        for path, name in entries:
            t.add(path, arcname=name.rstrip("/"), recursive=False)
    return len(entries), os.path.getsize(out)


def list_tar(archive):
    with tarfile.open(fs.resolve(archive), "r:*") as t:
        return [(m.name, m.size) for m in t.getmembers()]


def extract_tar(archive, dest_text, overwrite=False):
    src = fs.resolve(archive)
    dest = fs.resolve(dest_text, write=True)
    os.makedirs(dest, exist_ok=True)
    count = total = 0
    with tarfile.open(src, "r:*") as t:
        members = t.getmembers()
        if len(members) > MAX_FILES or sum(m.size for m in members) > MAX_TOTAL:
            raise ArchiveError("the archive is too large to unpack here")
        plan = []
        for m in members:
            if not (m.isfile() or m.isdir()):
                continue                                      # links, devices, fifos are never created
            target = _target(dest, m.name)
            if os.path.exists(target) and m.isfile() and not overwrite:
                raise ArchiveError(f"{m.name} already exists (use -o to overwrite)")
            plan.append((m, target))
        for m, target in plan:
            if m.isdir():
                os.makedirs(target, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(target), exist_ok=True)
            src_file = t.extractfile(m)
            with open(target, "wb") as o:
                while True:
                    chunk = src_file.read(1 << 20)
                    if not chunk:
                        break
                    total += len(chunk)
                    o.write(chunk)
            count += 1
    return count, total


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
