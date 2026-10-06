# pyos/sandbox_run.py - the process a marketplace package runs in:  python -m pyos.sandbox_run <script> [args...]
#
# Reads the package's permissions from the environment (set by pyos.sandbox.launch), installs the guard, then runs the script
# as __main__. See pyos/sandbox.py for what the guard is and is not.
import builtins
import io
import json
import os
import runpy
import site
import socket
import subprocess
import sys
import tempfile

def _real(path):
    if isinstance(path, bytes):                      # libraries such as psutil pass paths as bytes (os.listdir(b"/proc"))
        path = os.fsdecode(path)
    return os.path.normcase(os.path.realpath(path))


def _inside(path, root):
    try:
        return os.path.commonpath([path, root]) == root
    except (ValueError, TypeError):
        return False


class Guard:
    def __init__(self, perms, pkg_dir, pkg_id):
        self.perms, self.pkg_id = set(perms), pkg_id
        self.cwd = _real(os.getcwd())
        self.pkg_dir = _real(pkg_dir)
        self.base = _real(os.path.join(self.cwd, "files"))
        self.osdata = _real(os.path.join(self.cwd, ".OSData"))
        try:
            with open("current_user.json", encoding="utf-8") as f:
                self.user = json.load(f).get("username")
        except Exception:
            self.user = None
        self.role = None
        try:
            with open(os.environ.get("PYOS_USERS_FILE") or "users.json", encoding="utf-8") as f:
                self.role = (json.load(f).get(self.user) or {}).get("role")
        except Exception:
            pass
        self.always_rw = [self.pkg_dir, _real(os.path.join(self.base, "tmp"))]
        temp = _real(tempfile.gettempdir())
        if not _inside(self.cwd, temp):                      # never let "temp" cover PythonOS's own folder
            self.always_rw.append(temp)
        if self.user:
            self.always_rw.append(_real(os.path.join(self.base, "home", self.user, ".config")))
        roots = {sys.prefix, sys.base_prefix, sys.exec_prefix, os.path.dirname(os.__file__)}
        try:
            roots.update(site.getsitepackages())
            roots.add(site.getusersitepackages())
        except Exception:
            pass
        roots.update(p for p in sys.path if p and os.path.isabs(p) and "site-packages" in p)
        for folder in ("commands", "core", "pyos", "programs"):
            roots.add(os.path.join(self.cwd, folder))
        for extra in ("/dev/null", "/dev/tty", "/dev/urandom", "/etc/ssl", "/usr/lib/ssl", "/etc/resolv.conf", "/etc/hosts",
                      "/etc/localtime", "/usr/share/zoneinfo", "/etc/nsswitch.conf", "/etc/mime.types"):
            roots.add(extra)
        if "system" in self.perms:
            roots.update(("/proc", "/sys"))
        self.ro = [_real(r) for r in roots if r]
        # single files the OS itself reads on an app's behalf
        self.ro_files = {_real(os.path.join(self.cwd, n)) for n in ("current_user.json", "current_directory.txt", "config.json", "VERSION")}
        self.ro_files.add(_real(os.path.join(self.osdata, "settings.json")))
        self.ro_files.add(_real(os.path.join(self.osdata, "user_settings.json")))
        self.ro_files.add(_real(os.path.join(self.osdata, "jobs.json")))
        self.ro_files.add(_real(os.path.join(self.osdata, "tasks.json")))       # PythonOS's own task list (System Monitor, Process Inspector)
        self.rw_files = set()
        for perm, name in (("notifications", "notifications.json"), ("schedule", "schedule.json")):
            if perm in self.perms:
                for suffix in ("", ".tmp"):
                    self.rw_files.add(_real(os.path.join(self.osdata, name + suffix)))

    def deny(self, what, need):
        raise PermissionError(13, f"{self.pkg_id or 'this app'} is not allowed to {what} (it needs the '{need}' permission; "
                                  f"change it with: pkg permissions {self.pkg_id})")

    # ---------------------------------------------------------------- files
    def check_path(self, path, write):
        if isinstance(path, int):
            return
        try:
            full = _real(os.fspath(path))
        except (TypeError, ValueError):
            return
        if any(_inside(full, r) for r in self.always_rw):
            return
        if full in self.rw_files:
            return
        if not write and (full in self.ro_files or any(_inside(full, r) for r in self.ro)):
            return
        if "files" in self.perms and _inside(full, self.base):
            if self._user_may(full, write):
                return
            raise PermissionError(13, "Permission denied")
        self.deny(("write " if write else "read ") + self._shown(full), "files")

    def _shown(self, full):
        """A path as the user knows it (/home/bob/...) when it is inside PythonOS's filesystem, else just the file name."""
        if _inside(full, self.base):
            return "/" + os.path.relpath(full, self.base).replace(os.sep, "/")
        return os.path.basename(full) or "that location"

    def _user_may(self, full, write):
        """The same rule the shell uses: you cannot enter other homes, and only admins write outside home and tmp."""
        if self.role == "admin":
            return True
        homes = os.path.join(self.base, "home")
        if _inside(full, homes) and full != homes:
            own = os.path.join(homes, self.user or "")
            if not (self.user and _inside(full, _real(own))):
                return False
        if write:
            return _inside(full, _real(os.path.join(self.base, "tmp"))) or bool(self.user and _inside(full, _real(os.path.join(homes, self.user))))
        return True

    # -------------------------------------------------------------- install
    def install(self):
        guard = self
        real_open = builtins.open
        self._saved = []
        self._env = os.environ.get("PYOS_SANDBOX_USER")
        os.environ["PYOS_SANDBOX_USER"] = f"{self.user or ''}:{self.role or ''}"

        def patch(owner, name, value):
            """Replace owner.name, remembering the original so uninstall() can put it back."""
            self._saved.append((owner, name, getattr(owner, name)))
            setattr(owner, name, value)

        def open_(file, mode="r", *a, **k):
            writing = any(c in mode for c in "wax+")
            guard.check_path(file, writing)
            return real_open(file, mode, *a, **k)

        patch(builtins, "open", open_)
        patch(io, "open", open_)

        def wrap_os(name, write, arg_index=0, both=False):
            original = getattr(os, name, None)
            if original is None:
                return

            def wrapper(*args, **kwargs):
                if args:
                    guard.check_path(args[arg_index], write)
                    if both and len(args) > 1:
                        guard.check_path(args[1], True)
                return original(*args, **kwargs)
            wrapper.__name__ = name
            patch(os, name, wrapper)

        real_os_open = os.open

        def os_open(path, flags, *a, **k):
            writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC))
            guard.check_path(path, writing)
            return real_os_open(path, flags, *a, **k)
        patch(os, "open", os_open)
        for name in ("listdir", "scandir"):
            wrap_os(name, False)
        for name in ("remove", "unlink", "mkdir", "rmdir", "makedirs", "removedirs", "chmod", "utime", "truncate"):
            wrap_os(name, True)
        for name in ("rename", "replace"):
            wrap_os(name, True, both=True)

        if "network" not in self.perms:
            def blocked(*a, **k):
                guard.deny("use the network", "network")
            for owner, names in ((socket.socket, ("connect", "connect_ex", "sendto")),):
                for n in names:
                    patch(owner, n, blocked)
            for n in ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr", "getfqdn"):
                patch(socket, n, blocked)

        if "exec" not in self.perms:
            def blocked_exec(*a, **k):
                guard.deny("start other programs", "exec")
            patch(subprocess.Popen, "__init__", blocked_exec)
            for n in ("system", "popen", "execv", "execve", "execl", "execle", "execlp", "execlpe", "execvp", "execvpe", "spawnl",
                      "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe", "startfile", "fork", "forkpty",
                      "posix_spawn", "posix_spawnp"):
                if hasattr(os, n):
                    patch(os, n, blocked_exec)


    def uninstall(self):
        """Put every patched function back (matters when the guard runs inside a long-lived process, as on Android)."""
        for owner, name, original in reversed(self._saved):
            setattr(owner, name, original)
        self._saved = []
        if self._env is None:
            os.environ.pop("PYOS_SANDBOX_USER", None)
        else:
            os.environ["PYOS_SANDBOX_USER"] = self._env


def parse_args(argv):
    """['--perms', 'a,b', '--dir', D, '--id', I, '--', script, args...] -> (perms, dir, id, [script, args...])"""
    perms, pkg_dir, pkg_id = [], "", ""
    i = 0
    while i < len(argv) and argv[i].startswith("--"):
        if argv[i] == "--":
            i += 1
            break
        if argv[i] == "--perms" and i + 1 < len(argv):
            perms = [p for p in argv[i + 1].split(",") if p]
        elif argv[i] == "--dir" and i + 1 < len(argv):
            pkg_dir = argv[i + 1]
        elif argv[i] == "--id" and i + 1 < len(argv):
            pkg_id = argv[i + 1]
        i += 2
    return perms, pkg_dir, pkg_id, argv[i:]


def main():
    perms, pkg_dir, pkg_id, rest = parse_args(sys.argv[1:])
    if not rest:
        print("usage: sandbox_run.py --perms a,b --dir D --id I -- <script> [args...]", file=sys.stderr)
        return 2
    script = rest[0]
    guard = Guard(perms, pkg_dir or os.path.dirname(os.path.abspath(script)), pkg_id)
    guard.install()
    saved_argv, saved_path = sys.argv, list(sys.path)
    sys.argv = [script, *rest[1:]]
    sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
    try:
        runpy.run_path(script, run_name="__main__")
    except PermissionError as e:
        print(f"Blocked: {e.strerror or e}", file=sys.stderr)
        return 1
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        guard.uninstall()
        sys.argv, sys.path[:] = saved_argv, saved_path
    return 0


if __name__ == "__main__":
    sys.exit(main())
