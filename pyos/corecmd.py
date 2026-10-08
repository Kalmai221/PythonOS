# pyos/corecmd.py - an app uses PythonOS's own commands
#
# A marketplace app is a program of its own, but PythonOS already has commands that do real work: curl and wget download, zip and tar pack, sha256sum
# checks, du measures, schedule sets things for later. Instead of every app writing that again (and getting the size limits, the progress and the file
# rules slightly different), an app can ask for the command:
#
#     from pyos import corecmd
#     result = corecmd.run("sha256sum", ["report.pdf"])
#     if result.ok:
#         print(result.output)
#
# run() runs the command inside the app's own process, captures what it prints, and never raises for a command that fails (result.ok is False and
# result.output has the message). Only the commands below can be asked for: nothing that changes accounts, installs software or shuts the computer down.
# The app's permissions still hold, because the guard watches what the command does: curl asks the internet, so an app without the "network" permission
# is refused (and, like any other use, the first time it may be asked). `needs` says which permission a command uses, so an app can check first.
import contextlib
import importlib.util
import os

from . import stdio

# command -> the permission it uses ("" = none). Commands that ask questions or take over the screen (edit, fm, less) are not here.
ALLOWED = {
    # work on text (from the `stdin` argument, or on files)
    "echo": "", "seq": "", "sort": "", "uniq": "", "cut": "", "tr": "", "rev": "", "tac": "", "nl": "", "sed": "", "paste": "", "fold": "", "column": "",
    "shuf": "", "comm": "", "calc": "", "uuidgen": "", "basename": "", "dirname": "", "base64": "", "wc": "", "date": "", "cal": "",
    "md5sum": "", "sha1sum": "", "sha256sum": "", "sha512sum": "",
    # read and change files (the file rules of PythonOS apply as well)
    "ls": "files", "cat": "files", "head": "files", "tail": "files", "grep": "files", "find": "files", "tree": "files", "stat": "files", "file": "files",
    "du": "files", "diff": "files", "cmp": "files", "strings": "files", "touch": "files", "mkdir": "files", "cp": "files", "mv": "files", "rm": "files",
    "zip": "files", "unzip": "files", "tar": "files", "gzip": "files", "gunzip": "files", "zcat": "files", "tee": "files", "pwd": "files",
    # the internet
    "curl": "network", "wget": "network", "ping": "network", "nslookup": "network", "whois": "network", "tracert": "network", "ipinfo": "network",
    # this computer
    "df": "system", "free": "system", "uptime": "system", "uname": "", "lscpu": "system", "nproc": "system", "sysinfo": "system", "hostname": "",
    "ps": "system", "pgrep": "system", "arch": "",
    # later
    "schedule": "schedule",
}
MAX_OUTPUT = 4 * 1024 * 1024
_modules = {}


class Result:
    """What a command did: ok (it reported success), output (everything it printed, as text), code ('ok', 'refused', 'missing' or 'failed')."""

    def __init__(self, ok, output="", code="ok", crashed=False):
        self.ok, self.output, self.code, self.crashed = ok, output, code, crashed       # crashed: the command raised an error of its own (a bug)

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return f"Result(ok={self.ok}, code={self.code!r}, {len(self.output)} characters)"


def names():
    """The commands an app can ask for, sorted."""
    return sorted(ALLOWED)


def needs(name):
    """The permission a command uses ('' for none), or None if the command cannot be asked for."""
    return ALLOWED.get(name)


def granted():
    """The permissions of the app this runs in, or None when it is not running under the permission guard (then nothing is held back here)."""
    value = os.environ.get("PYOS_APP_PERMS")
    return None if value is None else {p for p in value.split(",") if p}


def check(name):
    """(True, '') when this app can run the command, else (False, why)."""
    if name not in ALLOWED:
        return False, f"'{name}' cannot be run by an app (see corecmd.names() for the commands that can)"
    held = granted()
    if ALLOWED[name] and held is not None and ALLOWED[name] not in held:
        return False, f"'{name}' uses the '{ALLOWED[name]}' permission, which this app does not have"
    return True, ""


def _load(name):
    if name not in _modules:
        path = os.path.join(os.getcwd(), "commands", name + ".py")
        if not os.path.isfile(path):
            _modules[name] = None
        else:
            spec = importlib.util.spec_from_file_location("corecmd_" + name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            _modules[name] = module
    return _modules[name]


def _call(module, args):
    """module.execute with the argument list, only if it takes one (the way the shell calls commands)."""
    import inspect
    try:
        takes_args = len(inspect.signature(module.execute).parameters) > 0
    except (TypeError, ValueError):
        takes_args = False
    return module.execute(args) if takes_args else module.execute()


def run(name, args=(), stdin=None):
    """Run a PythonOS command and return a Result. `stdin` is text for it to read as if piped in."""
    allowed, why = check(name)
    if not allowed:
        return Result(False, why, "refused")
    try:
        module = _load(name)
    except Exception as e:                                            # noqa: BLE001 - a command that cannot even load
        return Result(False, f"'{name}' could not be loaded ({type(e).__name__})", "missing")
    if module is None or not hasattr(module, "execute"):
        return Result(False, f"this PythonOS has no '{name}' command", "missing")
    stdio.install()
    previous = getattr(stdio._local, "stdin", None)
    stdio.set_stdin("" if stdin is None else stdin)               # an app is never at a keyboard: a command that would wait for typing reads nothing
    try:
        with stdio.capture() as buffer:
            try:
                ok = _call(module, [str(a) for a in args])
            except PermissionError as e:                              # the app's guard said no
                return Result(False, (buffer.getvalue() + f"Blocked: {e.strerror or e}").strip(), "refused")
            except SystemExit:
                ok = False
            except Exception as e:                                    # noqa: BLE001 - a command's own error is the app's result, not a crash
                return Result(False, (buffer.getvalue() + f"{name}: {type(e).__name__}: {e}").strip(), "failed", crashed=True)
        output = buffer.getvalue()
    finally:
        stdio.set_stdin(previous)
    if len(output) > MAX_OUTPUT:
        output = output[:MAX_OUTPUT] + "\n[output cut]"
    ok = ok is not False                                              # most commands return True; a few return None for "fine"
    return Result(ok, output, "ok" if ok else "failed")


def text(name, args=(), stdin=None):
    """The output of a command as text; raises RuntimeError with its message when it failed."""
    result = run(name, args, stdin)
    if not result.ok:
        raise RuntimeError(result.output or f"{name} failed")
    return result.output
