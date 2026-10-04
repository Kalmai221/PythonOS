# pyos/fs.py - the virtual filesystem: layout, home directories and permissions
import os

# 'files/' on the host is "/" inside PyOS.
BASE_DIR = os.path.abspath("files")
CURRENT_DIR_FILE = "current_directory.txt"

# Standard directories created at boot (relative to "/")
LAYOUT = ["home", "etc", "tmp", "var/log"]


def _inside(path, base=BASE_DIR):
    """True if path is base or lives under it (case-insensitive on Windows).

    Symlinks are resolved first, so a link inside the sandbox that points outside it does not count.
    """
    path, base = os.path.normcase(os.path.realpath(path)), os.path.normcase(os.path.realpath(base))
    try:
        return os.path.commonpath([path, base]) == base
    except ValueError:  # different drives on Windows
        return False


def ensure_layout():
    """Create the standard directory tree and a few system files."""
    for d in LAYOUT:
        os.makedirs(os.path.join(BASE_DIR, *d.split("/")), exist_ok=True)
    defaults = {
        os.path.join("etc", "hostname"): "pyOS\n",
        os.path.join("etc", "motd"): "Welcome to PyOS. Type 'help' to get started.\n",
    }
    for rel, text in defaults.items():
        path = os.path.join(BASE_DIR, rel)
        if not os.path.exists(path):
            with open(path, "w") as f:
                f.write(text)


def hostname():
    try:
        with open(os.path.join(BASE_DIR, "etc", "hostname")) as f:
            return f.read().strip() or "pyOS"
    except OSError:
        return "pyOS"


def home_dir(username):
    return os.path.join(BASE_DIR, "home", username)


def ensure_home(username):
    path = home_dir(username)
    os.makedirs(path, exist_ok=True)
    return path


def current_user():
    """(username, role) of the logged-in user, or (None, None)."""
    from .userinfo import userinfo
    name, role = userinfo()
    return name, role


def current_dir():
    """Return the shell's current directory, falling back to the base directory."""
    try:
        with open(CURRENT_DIR_FILE, "r") as f:
            path = os.path.abspath(f.read().strip())
        if os.path.isdir(path) and _inside(path):
            return path
    except OSError:
        pass
    return BASE_DIR


def save_current_dir(path):
    with open(CURRENT_DIR_FILE, "w") as f:
        f.write(path)


def _check_permission(full, write):
    """Raise PermissionError if the logged-in user may not access `full`.

    Admins can access everything. Other users cannot enter other users' home
    directories and can only write inside their own home and /tmp.
    """
    name, role = current_user()
    if role == "admin":
        return
    homes = os.path.join(BASE_DIR, "home")
    if _inside(full, homes) and os.path.normcase(full) != os.path.normcase(homes):
        own = home_dir(name) if name else None
        if not own or not _inside(full, own):
            raise PermissionError("Permission denied")
    if write:
        allowed = [os.path.join(BASE_DIR, "tmp")]
        if name:
            allowed.append(home_dir(name))
        if not any(_inside(full, a) for a in allowed):
            raise PermissionError("Permission denied (read-only for non-admin users)")


def resolve(path, write=False):
    """Resolve a user-supplied path ('~' = your home, leading '/' = root).

    Raises PermissionError if the path escapes the sandbox or the user lacks
    permission (pass write=True when the path is about to be modified).
    """
    path = path.replace("\\", "/")
    name, _ = current_user()
    if path == "~" or path.startswith("~/"):
        start = home_dir(name) if name else BASE_DIR
        path = path[2:] if path.startswith("~/") else "."
    elif path.startswith("/"):
        start = BASE_DIR
    else:
        start = current_dir()
    full = os.path.abspath(os.path.join(start, path.lstrip("/")))
    if not _inside(full):
        raise PermissionError("Access denied: path is outside of the filesystem.")
    _check_permission(full, write)
    return full


def display(path, tilde=False):
    """Format an absolute path the way the shell shows it ('~' for home if tilde)."""
    if tilde:
        name, _ = current_user()
        if name:
            home = home_dir(name)
            if os.path.normcase(os.path.abspath(path)) == os.path.normcase(home):
                return "~"
            if _inside(path, home):
                return "~/" + os.path.relpath(path, home).replace(os.sep, "/")
    rel = os.path.relpath(path, BASE_DIR)
    return "/" if rel == "." else "/" + rel.replace(os.sep, "/")
