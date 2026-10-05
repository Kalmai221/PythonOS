# pyos/trash.py - the recycle bin: rm moves things here instead of deleting them, so they can be brought back
#
# Items live in .OSData/trash/<id>/ (the data itself) with one index file, .OSData/trash/index.json, that remembers
# where each came from, who removed it and when. Each user sees their own items (admins can see everyone's).
# The bin cleans itself: items older than the trash_days setting and anything over the size cap are removed for good.
import json
import os
import shutil
import threading
import time

import pyos.fs as fs
from pyos import settings

TRASH_DIR = os.path.join(".OSData", "trash")
INDEX = os.path.join(TRASH_DIR, "index.json")
MAX_BYTES = 256 * 1024 * 1024
_lock = threading.Lock()


def _load():
    try:
        with open(INDEX, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(items):
    os.makedirs(TRASH_DIR, exist_ok=True)
    tmp = INDEX + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f)
    os.replace(tmp, INDEX)


def size_of(path):
    if os.path.isfile(path):
        return os.path.getsize(path)
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def _virtual(path):
    """The path as the user sees it, starting with /."""
    rel = os.path.relpath(path, fs.BASE_DIR).replace(os.sep, "/")
    return "/" + rel


def _real(virtual):
    return os.path.join(fs.BASE_DIR, *virtual.strip("/").split("/"))


def enabled():
    return bool(settings.get("use_trash"))


def discard(path, user):
    """Move `path` (an absolute path inside the filesystem) into the bin. Returns the item, or None if it was too big for the bin."""
    size = size_of(path)
    if size > MAX_BYTES:
        return None
    with _lock:
        items = _load()
        stamp = int(time.time() * 1000)
        item_id = str(stamp)
        while any(i["id"] == item_id for i in items):
            stamp += 1
            item_id = str(stamp)
        os.makedirs(TRASH_DIR, exist_ok=True)
        target = os.path.join(TRASH_DIR, item_id)
        shutil.move(path, target)
        item = {"id": item_id, "name": os.path.basename(path), "from": _virtual(path), "user": user or "?",
                "time": time.time(), "dir": os.path.isdir(target), "size": size}
        items.append(item)
        _save(items)
    clean()
    return item


def mine(user, is_admin=False, everyone=False):
    items = _load()
    if everyone and is_admin:
        return items
    return [i for i in items if i["user"] == user]


def find(spec, user, is_admin=False):
    """An item by number from the list ('1' = newest), by id, or by exact name (the newest one with that name)."""
    items = sorted(mine(user, is_admin, everyone=is_admin), key=lambda i: i["time"], reverse=True)
    if spec.isdigit() and 1 <= int(spec) <= len(items) and len(spec) < 6:
        return items[int(spec) - 1]
    for i in items:
        if i["id"] == spec or i["name"] == spec:
            return i
    return None


def restore(item, to=None):
    """Put an item back (to its old place, or `to`, a path the user may write). Returns the path used. Never overwrites."""
    destination = fs.resolve(to, write=True) if to else fs.resolve(item["from"], write=True)
    if os.path.isdir(destination) and to:
        destination = os.path.join(destination, item["name"])
    if os.path.exists(destination):
        raise FileExistsError(f"{fs.display(destination, tilde=True)} already exists (restore it somewhere else: trash restore <item> <path>)")
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    with _lock:
        items = _load()
        shutil.move(os.path.join(TRASH_DIR, item["id"]), destination)
        _save([i for i in items if i["id"] != item["id"]])
    return destination


def purge(item):
    with _lock:
        items = _load()
        target = os.path.join(TRASH_DIR, item["id"])
        if os.path.isdir(target):
            shutil.rmtree(target, ignore_errors=True)
        elif os.path.exists(target):
            os.remove(target)
        _save([i for i in items if i["id"] != item["id"]])


def empty(user, is_admin=False, everyone=False):
    removed = 0
    for item in mine(user, is_admin, everyone):
        purge(item)
        removed += 1
    return removed


def clean():
    """Remove items older than the trash_days setting, then the oldest ones while the bin is over its size cap. Never raises."""
    try:
        days = settings.get("trash_days")
        items = _load()
        if days:
            for item in items:
                if time.time() - item["time"] > days * 86400:
                    purge(item)
        items = sorted(_load(), key=lambda i: i["time"])
        total = sum(i.get("size", 0) for i in items)
        while items and total > MAX_BYTES:
            total -= items[0].get("size", 0)
            purge(items.pop(0))
    except Exception:
        pass
