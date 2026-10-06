"""The file manager's engine: browsing, selecting, copying, moving, deleting (to the trash), renaming, previewing.

It works on real paths inside PythonOS's filesystem and asks the same permission rules as the shell (pyos.fs): you cannot leave the
filesystem, enter other users' homes, or write outside your home and /tmp unless you are an administrator. The full-screen
program (commands/files.py) is only a way of looking at this and pressing keys; everything that decides something is here.
"""
import os
import shutil
import stat
import time

from . import fs, trash

TEXT_PREVIEW_BYTES = 16 * 1024
PREVIEW_LINES = 200


class FileManagerError(Exception):
    """Something the user should be told, in words (permission, name taken, missing...)."""


class Entry:
    def __init__(self, name, path):
        self.name, self.path = name, path
        try:
            info = os.lstat(path)
        except OSError:
            info = None
        self.is_link = bool(info and stat.S_ISLNK(info.st_mode))
        self.is_dir = os.path.isdir(path)
        self.size = 0 if self.is_dir or info is None else info.st_size
        self.mtime = info.st_mtime if info else 0
        self.hidden = name.startswith(".")


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def when(timestamp):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(timestamp)) if timestamp else ""


def unique_name(folder, name):
    """`name`, or `name (2)`, `name (3)`... when something with that name is already in `folder`."""
    if not os.path.lexists(os.path.join(folder, name)):
        return name
    stem, ext = os.path.splitext(name)
    n = 2
    while os.path.lexists(os.path.join(folder, f"{stem} ({n}){ext}")):
        n += 1
    return f"{stem} ({n}){ext}"


class Manager:
    SORTS = ("name", "size", "time", "type")

    def __init__(self, start=None, user=None):
        self.user = user
        self.cwd = os.path.abspath(start or fs.current_dir())
        self.sort = "name"
        self.reverse = False
        self.show_hidden = False
        self.filter = ""
        self.cursor = 0
        self.selected = set()
        self.clipboard = ("", [])               # ("copy" | "cut", [paths])
        self.message = ""

    # ------------------------------------------------------------------------------------------ permissions
    def allowed(self, path, write=False):
        """Raise FileManagerError unless the signed-in user may touch `path` (the shell's rules)."""
        full = os.path.abspath(path)
        if not fs._inside(full):
            raise FileManagerError("that is outside the filesystem")
        try:
            fs._check_permission(full, write)
        except PermissionError as e:
            raise FileManagerError(str(e))
        return full

    # ------------------------------------------------------------------------------------------ listing
    def entries(self):
        """The visible entries of the current folder, folders first, in the chosen order."""
        try:
            names = os.listdir(self.cwd)
        except OSError as e:
            raise FileManagerError(fs.errtext(e))
        items = [Entry(n, os.path.join(self.cwd, n)) for n in names]
        if not self.show_hidden:
            items = [e for e in items if not e.hidden]
        if self.filter:
            needle = self.filter.lower()
            items = [e for e in items if needle in e.name.lower()]
        keys = {"name": lambda e: e.name.lower(), "size": lambda e: e.size, "time": lambda e: e.mtime,
                "type": lambda e: (os.path.splitext(e.name)[1].lower(), e.name.lower())}
        items.sort(key=keys[self.sort], reverse=self.reverse)
        items.sort(key=lambda e: not e.is_dir)                         # folders stay on top (a stable sort keeps the order inside)
        return items

    def current(self, items=None):
        items = items if items is not None else self.entries()
        if not items:
            return None
        self.cursor = max(0, min(self.cursor, len(items) - 1))
        return items[self.cursor]

    def move(self, delta, items=None):
        count = len(items if items is not None else self.entries())
        self.cursor = max(0, min(self.cursor + delta, max(0, count - 1)))

    # ------------------------------------------------------------------------------------------ going places
    def go(self, path):
        full = self.allowed(path)
        if not os.path.isdir(full):
            raise FileManagerError("that is not a folder")
        self.cwd, self.cursor, self.selected, self.filter = full, 0, set(), ""

    def up(self):
        parent = os.path.dirname(self.cwd)
        if parent == self.cwd or not fs._inside(parent):
            raise FileManagerError("this is the top of the filesystem")
        came_from = os.path.basename(self.cwd)
        self.go(parent)
        names = [e.name for e in self.entries()]
        if came_from in names:
            self.cursor = names.index(came_from)

    def home(self):
        name, _role = fs.current_user()
        self.go(fs.home_dir(name) if name else fs.BASE_DIR)

    def open_current(self):
        """Enter the folder under the cursor. Returns the entry when it is a file (the caller decides what to do with it)."""
        entry = self.current()
        if entry is None:
            return None
        if entry.is_dir:
            self.go(entry.path)
            return None
        return entry

    def goto_text(self, text):
        """Go to a path the user typed ('~', '/etc', 'docs')."""
        try:
            self.go(fs.resolve(text.strip() or "~"))
        except PermissionError as e:
            raise FileManagerError(str(e))

    # ------------------------------------------------------------------------------------------ selecting
    def toggle(self, entry=None):
        entry = entry or self.current()
        if entry is None:
            return
        (self.selected.discard if entry.path in self.selected else self.selected.add)(entry.path)

    def select_all(self):
        every = {e.path for e in self.entries()}
        self.selected = set() if every and every <= self.selected else every

    def targets(self):
        """What a command works on: the selection, or the entry under the cursor."""
        if self.selected:
            return sorted(self.selected)
        entry = self.current()
        return [entry.path] if entry else []

    # ------------------------------------------------------------------------------------------ doing things
    def copy(self):
        paths = self.targets()
        for p in paths:
            self.allowed(p)
        self.clipboard = ("copy", paths)
        return len(paths)

    def cut(self):
        paths = self.targets()
        for p in paths:
            self.allowed(p, write=True)
        self.clipboard = ("cut", paths)
        return len(paths)

    def paste(self):
        """Put the clipboard into the current folder. Returns (done, [problems]). A name already taken gets ' (2)' added: nothing is overwritten."""
        op, paths = self.clipboard
        if not paths:
            raise FileManagerError("the clipboard is empty (copy or cut something first)")
        self.allowed(self.cwd, write=True)
        done, problems = 0, []
        for source in paths:
            try:
                if not os.path.lexists(source):
                    raise FileManagerError("it is gone")
                if os.path.isdir(source) and not os.path.islink(source) and (self.cwd + os.sep).startswith(os.path.abspath(source) + os.sep):
                    raise FileManagerError("a folder cannot be put inside itself")
                target = os.path.join(self.cwd, unique_name(self.cwd, os.path.basename(source)))
                if op == "cut":
                    self.allowed(source, write=True)
                    shutil.move(source, target)
                elif os.path.isdir(source) and not os.path.islink(source):
                    shutil.copytree(source, target, symlinks=True)
                else:
                    shutil.copy2(source, target)
                done += 1
            except (OSError, FileManagerError, shutil.Error) as e:
                problems.append(f"{os.path.basename(source)}: {fs.errtext(e) if isinstance(e, OSError) else e}")
        if op == "cut":
            self.clipboard = ("", [])
        self.selected = set()
        return done, problems

    def delete(self, permanent=False):
        """Move the targets to the trash (or delete for good). Returns (done, [problems])."""
        done, problems = 0, []
        for path in self.targets():
            try:
                self.allowed(path, write=True)
                if path == fs.BASE_DIR:
                    raise FileManagerError("the top of the filesystem cannot be removed")
                if not permanent and trash.enabled():
                    if trash.discard(path, self.user) is None:
                        raise FileManagerError("it is too big for the trash (delete it for good instead)")
                elif os.path.isdir(path) and not os.path.islink(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)
                done += 1
            except (OSError, FileManagerError) as e:
                problems.append(f"{os.path.basename(path)}: {fs.errtext(e) if isinstance(e, OSError) else e}")
        self.selected = set()
        return done, problems

    def rename(self, new_name):
        entry = self.current()
        if entry is None:
            raise FileManagerError("nothing is chosen")
        new_name = new_name.strip()
        if not new_name or "/" in new_name or "\\" in new_name or new_name in (".", ".."):
            raise FileManagerError("a name cannot be empty or contain / or \\")
        self.allowed(entry.path, write=True)
        target = os.path.join(self.cwd, new_name)
        if os.path.lexists(target):
            raise FileManagerError(f"'{new_name}' already exists")
        try:
            os.rename(entry.path, target)
        except OSError as e:
            raise FileManagerError(fs.errtext(e))
        self.selected.discard(entry.path)

    def make_folder(self, name):
        name = name.strip()
        if not name or "/" in name or "\\" in name:
            raise FileManagerError("a name cannot be empty or contain / or \\")
        self.allowed(self.cwd, write=True)
        target = os.path.join(self.cwd, name)
        if os.path.lexists(target):
            raise FileManagerError(f"'{name}' already exists")
        try:
            os.makedirs(target)
        except OSError as e:
            raise FileManagerError(fs.errtext(e))
        self.focus(name)

    def make_file(self, name):
        name = name.strip()
        if not name or "/" in name or "\\" in name:
            raise FileManagerError("a name cannot be empty or contain / or \\")
        self.allowed(self.cwd, write=True)
        target = os.path.join(self.cwd, name)
        if os.path.lexists(target):
            raise FileManagerError(f"'{name}' already exists")
        try:
            open(target, "x").close()
        except OSError as e:
            raise FileManagerError(fs.errtext(e))
        self.focus(name)

    def focus(self, name):
        """Put the cursor on `name` if it is listed."""
        names = [e.name for e in self.entries()]
        if name in names:
            self.cursor = names.index(name)

    def undo(self):
        """Bring back the last thing this user moved to the trash. Returns the name restored."""
        _name, role = fs.current_user()
        items = sorted(trash.mine(self.user, role == "admin"), key=lambda i: i["time"], reverse=True)
        if not items:
            raise FileManagerError("the trash is empty")
        item = items[0]
        try:
            trash.restore(item)
        except (OSError, PermissionError) as e:
            raise FileManagerError(fs.errtext(e) if isinstance(e, OSError) else str(e))
        self.focus(item["name"])
        return item["name"]

    def cycle_sort(self):
        self.sort = self.SORTS[(self.SORTS.index(self.sort) + 1) % len(self.SORTS)]
        return self.sort

    # ------------------------------------------------------------------------------------------ looking at things
    def preview(self, entry, lines=PREVIEW_LINES):
        """Lines of text for the preview pane: the start of a text file, the contents of a folder, or a note about a binary file."""
        if entry is None:
            return ["(nothing here)"]
        try:
            self.allowed(entry.path)
        except FileManagerError as e:
            return [f"({e})"]
        if entry.is_dir:
            try:
                names = sorted(os.listdir(entry.path), key=str.lower)
            except OSError as e:
                return [f"({fs.errtext(e)})"]
            shown = [n + ("/" if os.path.isdir(os.path.join(entry.path, n)) else "") for n in names if self.show_hidden or not n.startswith(".")]
            return shown[:lines] + ([f"... and {len(shown) - lines} more"] if len(shown) > lines else []) or ["(empty folder)"]
        try:
            with open(entry.path, "rb") as f:
                data = f.read(TEXT_PREVIEW_BYTES)
        except OSError as e:
            return [f"({fs.errtext(e)})"]
        if b"\0" in data:
            return [f"(binary file, {human(entry.size)})"]
        text = data.decode("utf-8", errors="replace").replace("\t", "    ")
        out = text.splitlines()[:lines]
        if entry.size > len(data):
            out.append(f"... ({human(entry.size)} in all)")
        return out or ["(empty file)"]

    def info(self, entry):
        """A few lines about one entry."""
        if entry is None:
            return []
        kind = "folder" if entry.is_dir else "link" if entry.is_link else "file"
        count = ""
        if entry.is_dir:
            try:
                count = f"{len(os.listdir(entry.path))} item(s)"
            except OSError:
                count = ""
        return [f"Name:      {entry.name}", f"Where:     {fs.display(os.path.dirname(entry.path))}", f"Kind:      {kind}",
                f"Size:      {count or human(entry.size)}", f"Modified:  {when(entry.mtime)}"]
