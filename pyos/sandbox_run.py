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


PERMISSION_NAMES = {"network": "Internet", "files": "Your files", "notifications": "Notifications", "schedule": "Schedule", "system": "System info",
                    "exec": "Other programs"}


class Guard:
    def __init__(self, perms, pkg_dir, pkg_id, ask=(), decisions=None, interactive=None, texts=None):
        self.perms, self.pkg_id = set(perms), pkg_id
        self.texts = texts or {}                     # the question's words in the person's language (from the shell); English where missing
        self.ask = set(ask)                          # asked for, not given, not refused for good: the person may be asked about these while the app runs
        self.decisions = decisions                   # the file the shell reads after the app ends ("always" and "never" answers)
        self._interactive = interactive              # None: look at the terminal each time
        self._answers = {}                           # permission -> True/False for this run (so one question is asked once)
        self._input = builtins.input
        self._real_open = builtins.open
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
        self.ask_files = {}                          # the files a permission opens, so the first use can ask for it
        for perm, name in (("notifications", "notifications.json"), ("schedule", "schedule.json")):
            for suffix in ("", ".tmp"):
                path = _real(os.path.join(self.osdata, name + suffix))
                self.ask_files[path] = perm
                if perm in self.perms:
                    self.rw_files.add(path)
        self.system_roots = [_real("/proc"), _real("/sys")]

    # ------------------------------------------------------------ asking
    def can_ask(self):
        if self._interactive is not None:
            return self._interactive
        try:
            return sys.stdin.isatty() and sys.stdout.isatty()
        except Exception:                            # noqa: BLE001
            return False

    def need(self, perm, what):
        """The app is using something that needs `perm`. True if it may (it has it, or the person has just said yes). Otherwise raises
        PermissionError. A permission the app never asked for, was refused for good, or when nobody can be asked: refused."""
        if perm in self.perms:
            return True
        if perm in self._answers:
            if self._answers[perm]:
                return True
            self.deny(what, perm)
        if perm in self.ask and self.can_ask():
            answer = self._question(perm, what)
            if answer in ("a", "A"):
                self._grant(perm)
                if answer == "A":
                    self._record(perm, "always")
                return True
            self._answers[perm] = False
            if answer == "N":
                self._record(perm, "never")
        self.deny(what, perm)

    def _question(self, perm, what):
        name = (self.pkg_id or "This app").split("/")[-1]
        t = self.texts
        what = (t.get("whats") or {}).get(perm) or what
        shown = (t.get("names") or {}).get(perm) or PERMISSION_NAMES.get(perm, perm)
        try:
            first = t.get("wants", "{name} wants to {what}.").format(name=name, what=what)
            second = t.get("permission", "Permission: {perm}.").format(perm=shown)
            sys.stdout.write(f"\n{first}\n  {second} {t.get('choices', '(a) allow this time   (A) always allow   (n) not now   (N) never allow')}\n")
            sys.stdout.flush()
            answer = self._input(t.get("prompt", "Allow? [n] ")).strip()
        except (EOFError, KeyboardInterrupt, OSError):
            return "n"
        words = {"a": "a", "A": "A", "N": "N", "n": "n", "allow": "a", "yes": "a", "y": "a", "always": "A", "never": "N"}
        return words.get(answer) or words.get(answer.lower(), "n")

    def _grant(self, perm):
        self.perms.add(perm)
        self._answers[perm] = True
        if perm == "system":
            self.ro.extend(self.system_roots)
        for path, owner in self.ask_files.items():
            if owner == perm:
                self.rw_files.add(path)

    def _record(self, perm, decision):
        if not self.decisions:
            return
        try:
            with self._real_open(self.decisions, "a", encoding="utf-8") as f:
                f.write(json.dumps({"perm": perm, "decision": decision}) + "\n")
        except OSError:
            pass

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
        what = ("write " if write else "read ") + self._shown(full)
        if _inside(full, self.base):
            self.need("files", "read and change your files (" + what + ")")        # asks the first time; raises if it is not allowed
            if self._user_may(full, write):
                return
            raise PermissionError(13, "Permission denied")
        owner = self.ask_files.get(full)
        if owner and write:
            self.need(owner, "use " + PERMISSION_NAMES.get(owner, owner).lower())
            return
        if not write and any(_inside(full, root) for root in self.system_roots):
            self.need("system", "read information about this computer")
            return
        self.deny(what, "files")

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

        def gate(perm, what, original):
            """Refuse (or ask) before the real function runs; once the permission is there the real one is called as usual."""
            def gated(*a, **k):
                guard.need(perm, what)
                return original(*a, **k)
            return gated

        if "network" not in self.perms:
            for owner, names in ((socket.socket, ("connect", "connect_ex", "sendto")),):
                for n in names:
                    patch(owner, n, gate("network", "connect to the internet and your network", getattr(owner, n)))
            for n in ("create_connection", "getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr", "getfqdn"):
                patch(socket, n, gate("network", "connect to the internet and your network", getattr(socket, n)))

        if "exec" not in self.perms:
            patch(subprocess.Popen, "__init__", gate("exec", "start other programs and run code on this computer", subprocess.Popen.__init__))
            for n in ("system", "popen", "execv", "execve", "execl", "execle", "execlp", "execlpe", "execvp", "execvpe", "spawnl",
                      "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe", "startfile", "fork", "forkpty",
                      "posix_spawn", "posix_spawnp"):
                if hasattr(os, n):
                    patch(os, n, gate("exec", "start other programs and run code on this computer", getattr(os, n)))


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


def parse_ask(argv):
    """(permissions the guard may ask about, the file that records the answers) from --ask a,b and --decisions FILE."""
    ask, decisions = [], None
    i = 0
    while i < len(argv) and argv[i].startswith("--"):
        if argv[i] == "--":
            break
        if argv[i] == "--ask" and i + 1 < len(argv):
            ask = [p for p in argv[i + 1].split(",") if p]
        elif argv[i] == "--decisions" and i + 1 < len(argv):
            decisions = argv[i + 1]
        i += 2
    return ask, decisions


def parse_texts(argv):
    """The question's words (JSON) from --texts, or {}."""
    i = 0
    while i < len(argv) and argv[i].startswith("--"):
        if argv[i] == "--":
            break
        if argv[i] == "--texts" and i + 1 < len(argv):
            try:
                value = json.loads(argv[i + 1])
                return value if isinstance(value, dict) else {}
            except ValueError:
                return {}
        i += 2
    return {}


def parse_limits(argv):
    """(memory MB, CPU seconds) from --mem-mb and --cpu-seconds in the guard's own options (0 = no limit)."""
    found = {"--mem-mb": 0, "--cpu-seconds": 0}
    i = 0
    while i < len(argv) and argv[i].startswith("--"):
        if argv[i] == "--":
            break
        if argv[i] in found and i + 1 < len(argv) and argv[i + 1].isdigit():
            found[argv[i]] = int(argv[i + 1])
        i += 2
    return found["--mem-mb"], found["--cpu-seconds"]


def _load_resources():
    """pyos/resources.py loaded from its file (the standard library only) so the app is not made to import the whole OS first."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("pyos_resources", os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _stop_for_limit(name, what, detail):
    try:
        sys.stderr.write(f"\n{name} was stopped: {what} ({detail}). "
                         f"Change it with: limits set {name} {'memory' if 'memory' in what else 'cpu'} <number>\n")
        sys.stderr.flush()
    except Exception:
        pass
    os._exit(137)


def start_limits(name, memory_mb, cpu_seconds):
    """Hold this process to its limits. The system caps the memory where it can; a watchdog thread covers what it cannot and the
    CPU time. Returns the thread (or None when there is nothing to watch)."""
    import threading
    import time
    if not memory_mb and not cpu_seconds:
        return None
    if memory_mb:
        try:
            _load_resources().cap_this_process(memory_mb * 1024 * 1024)
        except Exception:
            pass
    try:
        import resource
    except ImportError:
        resource = None

    def peak_mb():
        if resource is None:
            return 0
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024

    def watch():
        while True:
            time.sleep(0.25)
            if cpu_seconds and time.process_time() > cpu_seconds:
                _stop_for_limit(name, "it used more processor time than its limit", f"{cpu_seconds} s")
            if memory_mb and peak_mb() > memory_mb * 1.05 + 4:
                _stop_for_limit(name, "it used more memory than its limit", f"{memory_mb} MB")

    thread = threading.Thread(target=watch, name="app-limits", daemon=True)
    thread.start()
    return thread


def main(enforce_limits=False):
    perms, pkg_dir, pkg_id, rest = parse_args(sys.argv[1:])
    memory_mb, cpu_seconds = parse_limits(sys.argv[1:])
    if not rest:
        print("usage: sandbox_run.py --perms a,b --dir D --id I -- <script> [args...]", file=sys.stderr)
        return 2
    script = rest[0]
    app_name = (pkg_id or os.path.basename(os.path.dirname(os.path.abspath(script))) or "the app").split("/")[-1]
    if enforce_limits:                      # only when run as its own process: never inside the host process (the Android app)
        start_limits(app_name, memory_mb, cpu_seconds)
    ask, decisions = parse_ask(sys.argv[1:])
    guard = Guard(perms, pkg_dir or os.path.dirname(os.path.abspath(script)), pkg_id, ask, decisions, texts=parse_texts(sys.argv[1:]))
    guard.install()
    saved_argv, saved_path = sys.argv, list(sys.path)
    saved_perms = os.environ.get("PYOS_APP_PERMS")
    os.environ["PYOS_APP_PERMS"] = ",".join(sorted(perms))          # so the app can ask pyos.corecmd what it may run
    sys.argv = [script, *rest[1:]]
    sys.path.insert(0, os.path.dirname(os.path.abspath(script)))
    try:
        runpy.run_path(script, run_name="__main__")
    except PermissionError as e:
        print(f"Blocked: {e.strerror or e}", file=sys.stderr)
        return 1
    except MemoryError:
        guard.uninstall()
        print(f"\n{app_name} was stopped: it used more memory than its limit ({memory_mb or 'the system'} MB). "
              f"Change it with: limits set {app_name} memory <MB>", file=sys.stderr)
        return 137
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    finally:
        guard.uninstall()
        sys.argv, sys.path[:] = saved_argv, saved_path
        if saved_perms is None:
            os.environ.pop("PYOS_APP_PERMS", None)
        else:
            os.environ["PYOS_APP_PERMS"] = saved_perms
    return 0


if __name__ == "__main__":
    sys.exit(main(enforce_limits=True))
