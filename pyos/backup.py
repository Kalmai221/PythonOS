# pyos/backup.py - back up and restore your files (and, for admins, the whole system)
#
# A backup is an ordinary zip with a manifest.json. "user" backups hold one person's home folder; "system" backups
# (admins only) hold every home folder, the accounts, settings and schedule. Restoring never trusts the archive:
# paths are checked so nothing can be written outside the folder being restored into.
import datetime
import json
import os
import zipfile

from . import fs, paths

FORMAT = 1
MAX_TOTAL = 2 * 1024 ** 3          # refuse archives that unpack to more than 2 GB
MAX_FILES = 200_000
BACKUP_DIR = "backups"             # ~/backups holds a user's backups; it is never included in a backup

# files kept outside files/ that a system backup includes (relative to the OS folder)
SYSTEM_EXTRAS = ["users.json", "config.json", os.path.join(".OSData", "settings.json"), os.path.join(".OSData", "schedule.json")]


def _system_path(name):
    """Where a system file really lives (the account database may be on the ISO's data partition)."""
    return paths.USER_DB if name == "users.json" else name


def _pythonos_version():
    try:
        with open("VERSION", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        return "unknown"


def _walk(root, skip_dirs=()):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if os.path.join(dirpath, d) not in skip_dirs and not os.path.islink(os.path.join(dirpath, d))]
        for name in filenames:
            full = os.path.join(dirpath, name)
            if not os.path.islink(full):
                yield full


def default_name(kind, user):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"pythonos-{user}-{stamp}" + ("-system" if kind == "system" else "") + ".zip"


def create(kind, user, dest):
    """Write a backup zip to `dest` (an absolute host path). Returns (file count, bytes)."""
    if kind not in ("user", "system"):
        raise ValueError("kind must be 'user' or 'system'")
    home = fs.home_dir(user)
    entries = []                                    # (host path, name inside the zip)
    skip = {os.path.join(home, BACKUP_DIR)}
    if kind == "user":
        for full in _walk(home, skip):
            entries.append((full, "home/" + os.path.relpath(full, home).replace(os.sep, "/")))
    else:
        homes = os.path.join(fs.BASE_DIR, "home")
        skip = {os.path.join(homes, u, BACKUP_DIR) for u in (os.listdir(homes) if os.path.isdir(homes) else [])}
        for full in _walk(homes, skip):
            entries.append((full, "files/home/" + os.path.relpath(full, homes).replace(os.sep, "/")))
        for extra in ("etc",):
            folder = os.path.join(fs.BASE_DIR, extra)
            if os.path.isdir(folder):
                for full in _walk(folder):
                    entries.append((full, f"files/{extra}/" + os.path.relpath(full, folder).replace(os.sep, "/")))
        for name in SYSTEM_EXTRAS:
            if os.path.isfile(_system_path(name)):
                entries.append((_system_path(name), "system/" + name.replace(os.sep, "/")))

    entries = [(full, name) for full, name in entries if os.path.abspath(full) != os.path.abspath(dest)]   # never include itself

    manifest = {"format": FORMAT, "kind": kind, "user": user, "created": datetime.datetime.now().isoformat(timespec="seconds"),
                "pythonos": _pythonos_version(), "files": len(entries)}
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    tmp = dest + ".tmp"
    total = 0
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(manifest, indent=2))
        for full, name in entries:
            z.write(full, name)
            total += os.path.getsize(full)
    os.replace(tmp, dest)
    return len(entries), total


def read_manifest(path):
    """The manifest of a backup, or raises ValueError saying why it is not one."""
    try:
        with zipfile.ZipFile(path) as z:
            manifest = json.loads(z.read("manifest.json"))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as e:
        raise ValueError("that is not a PythonOS backup") from e
    if manifest.get("format") != FORMAT or manifest.get("kind") not in ("user", "system"):
        raise ValueError("that backup is from a version this PythonOS cannot read")
    return manifest


def _safe_member(name):
    norm = name.replace("\\", "/")
    parts = norm.split("/")
    return bool(name) and not norm.startswith("/") and ".." not in parts and ":" not in parts[0]


def plan_restore(path, kind, user):
    """List (zip member, host target) pairs a restore would write, after checking the archive is sane."""
    manifest = read_manifest(path)
    if manifest["kind"] != kind:
        raise ValueError(f"this is a {manifest['kind']} backup, not a {kind} one")
    plan = []
    total = 0
    with zipfile.ZipFile(path) as z:
        infos = [i for i in z.infolist() if not i.is_dir() and i.filename != "manifest.json"]
        if len(infos) > MAX_FILES:
            raise ValueError("the backup holds too many files")
        for info in infos:
            name = info.filename
            if not _safe_member(name):
                raise ValueError(f"the backup contains an unsafe path ({name}) and was not restored")
            if (info.external_attr >> 28) == 0xA:                      # a symlink entry
                raise ValueError(f"the backup contains a link ({name}) and was not restored")
            total += info.file_size
            if total > MAX_TOTAL:
                raise ValueError("the backup is too large to restore")
            if kind == "user":
                if not name.startswith("home/"):
                    continue
                target = os.path.join(fs.home_dir(user), *name[len("home/"):].split("/"))
                if not fs._inside(target, fs.home_dir(user)):
                    raise ValueError(f"the backup contains an unsafe path ({name}) and was not restored")
            else:
                if name.startswith("files/"):
                    target = os.path.join(fs.BASE_DIR, *name[len("files/"):].split("/"))
                    if not fs._inside(target):
                        raise ValueError(f"the backup contains an unsafe path ({name}) and was not restored")
                elif name.startswith("system/") and name[len("system/"):].replace("/", os.sep) in SYSTEM_EXTRAS:
                    target = _system_path(name[len("system/"):].replace("/", os.sep))
                else:
                    continue
            plan.append((name, target))
    return manifest, plan


def restore(path, kind, user):
    """Write the planned files. Returns how many were restored."""
    _manifest, plan = plan_restore(path, kind, user)
    with zipfile.ZipFile(path) as z:
        for name, target in plan:
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            with z.open(name) as src, open(target + ".tmp", "wb") as out:
                while True:
                    chunk = src.read(1 << 20)
                    if not chunk:
                        break
                    out.write(chunk)
            os.replace(target + ".tmp", target)
    return len(plan)


def list_backups(user):
    folder = os.path.join(fs.home_dir(user), BACKUP_DIR)
    found = []
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if name.endswith(".zip"):
                try:
                    m = read_manifest(path)
                except ValueError:
                    continue
                found.append({"name": name, "path": path, "kind": m["kind"], "created": m.get("created", ""),
                              "files": m.get("files", 0), "size": os.path.getsize(path)})
    return found
