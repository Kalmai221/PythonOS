"""Runs PythonOS inside the Android app.

The app (Kotlin) shows a terminal and calls main(files_dir) on a background thread.
This module connects the OS to that terminal:

* stdout/stderr go to the on-screen terminal (ANSI colours supported)
* input() and getpass() wait for the user to type a line in the app
* "clear" clears the screen, and restarting the OS re-runs main.py
* "python script.py" subprocess calls run in-process, because Android has no
  python executable to launch (pip is not available; dependencies ship in the app)
"""
import builtins
import getpass
import io
import json
import os
import runpy
import subprocess
import sys
import threading
import traceback

from java import jclass

Bridge = jclass("com.pythonos.app.TerminalBridge")

CLEAR_SCREEN = "\x1b[2J\x1b[H"
PROJECT_MODULES = ("main", "shell", "users", "core", "pyos", "commands", "programs")
INTERRUPT = "\x03"  # sent by the app's Ctrl+C button


class RestartRequested(BaseException):
    """Raised when something asks to start main.py again (the 'restart' command)."""


class Screen(io.TextIOBase):
    encoding = "utf-8"
    errors = "replace"

    def write(self, text):
        if text:
            Bridge.write(str(text))
        return len(text)

    def writelines(self, lines):
        for line in lines:
            self.write(line)

    def flush(self):
        pass

    def isatty(self):
        return True

    def writable(self):
        return True

    def fileno(self):
        raise OSError("the PythonOS terminal has no file descriptor")


class Keyboard(io.TextIOBase):
    encoding = "utf-8"

    def readline(self, size=-1):
        return _read("", False) + "\n"

    def isatty(self):
        return True

    def readable(self):
        return True


def _read(prompt, secret):
    prompt = str(prompt).replace("\x01", "").replace("\x02", "")  # readline's "zero width" markers
    line = str(Bridge.readLine(prompt, secret))
    if line == INTERRUPT:
        raise KeyboardInterrupt
    return line


def _input(prompt=""):
    return _read(prompt, False)


def _getpass(prompt="Password: ", stream=None):
    return _read(prompt, True)


# ---------------------------------------------------------------- shims
_real_system = os.system
_real_call = subprocess.call
_real_run = subprocess.run


def _is_python(command):
    if not isinstance(command, (list, tuple)) or not command:
        return False
    first = str(command[0])
    return first == sys.executable or os.path.basename(first).lower() in ("python", "python3", "python.exe")


def _run_python(command, cwd=None):
    """Run `python <script> args...` inside this process. Returns an exit code."""
    args = [str(a) for a in command[1:]]
    if not args or args[0].startswith("-"):
        Bridge.write("\x1b[31mpip and python -m are not available in the PythonOS app.\x1b[0m\n")
        return 1
    script = args[0]
    if os.path.basename(script) == "main.py":
        raise RestartRequested
    saved_argv, saved_cwd = sys.argv, os.getcwd()
    try:
        sys.argv = args
        if cwd:
            os.chdir(cwd)
        runpy.run_path(script, run_name="__main__")
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    except KeyboardInterrupt:
        return 130
    except Exception:
        traceback.print_exc()
        return 1
    finally:
        sys.argv = saved_argv
        os.chdir(saved_cwd)


def _system(command):
    if str(command).strip() in ("clear", "cls"):
        Bridge.write(CLEAR_SCREEN)
        return 0
    return _real_system(command)


def _call(command, *args, **kwargs):
    if _is_python(command):
        return _run_python(command, kwargs.get("cwd"))
    return _real_call(command, *args, **kwargs)


def _run(command, *args, **kwargs):
    if _is_python(command):
        if kwargs.get("capture_output") or kwargs.get("stdout") or kwargs.get("stderr"):
            return subprocess.CompletedProcess(command, 1, "", "pip is not available in the PythonOS app\n")
        return subprocess.CompletedProcess(command, _run_python(command, kwargs.get("cwd")))
    return _real_run(command, *args, **kwargs)


def _purge_project_modules():
    """Forget the OS's modules so a restart (or relaunch) starts from a clean slate."""
    for name in list(sys.modules):
        if name in PROJECT_MODULES or name.split(".")[0] in PROJECT_MODULES:
            del sys.modules[name]


_main_thread_id = None


# ---- calls from the app's UI thread (Kotlin) -------------------------------------------------
def complete(line):
    """Tab completion for the last word of `line` (the shell's own completer)."""
    try:
        shell = sys.modules.get("shell")
        return list(shell.complete(line)) if shell else []
    except Exception:
        return []


def interrupt():
    """Ctrl+C while a command is running: raise KeyboardInterrupt in the PythonOS thread."""
    import ctypes
    if _main_thread_id:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(ctypes.c_ulong(_main_thread_id), ctypes.py_object(KeyboardInterrupt))


def set_size(cols, rows):
    """The terminal view was resized or zoomed: tell rich how wide the screen is."""
    os.environ["COLUMNS"] = str(int(cols))
    os.environ["LINES"] = str(int(rows))


def set_language(code):
    """The app's language menu changed: PythonOS speaks it too (the setting is what pyos/i18n.py reads)."""
    try:
        from pyos import settings
        settings.set("language", str(code))
    except Exception:
        pass


def app_update():
    """JSON about a newer APK (it cannot update itself), or "" if this app is current / offline."""
    try:
        from core import sysupdate
        st = sysupdate.check_export_update(timeout=6)
        if st and st["state"] in ("update", "incompatible"):
            remote = st["remote"]
            url = remote["url"]
            from pyos import archinfo
            wanted = {"aarch64": "arm64-v8a", "x86_64": "x86_64"}.get(archinfo.arch())          # the device's primary ABI, not the process's
            for candidate in remote.get("urls") or []:
                if wanted and candidate.endswith(f"-android-{wanted}.apk"):
                    url = candidate                     # the smaller APK made for this phone's processor
            try:
                sha256 = sysupdate.checksum_of(url) or ""
            except Exception:
                sha256 = ""
            return json.dumps({"state": st["state"], "title": st["title"], "local": st["local"]["version"],
                               "remote": remote["version"], "notes": remote.get("notes", ""),
                               "url": url, "sha256": sha256, "reason": st.get("reason", "")})
    except Exception:
        pass
    return ""


def refresh_core_after_app_update(files_dir, log=print):
    """Installing a new APK over an old one replaces the app but not the OS: the core lives in files_dir, which Android keeps. Left alone, the
    person would still be on the old PythonOS (and its old version number) after "updating" - and the in-app updater would keep refusing the
    new core ("it needs new libraries, install the new app"), because it judges the libraries by the old core's requirements, so the app
    update would seem to do nothing, for ever.

    The rule is simple and needs no memory of earlier starts: an app built for PythonOS X must not run a core older than X. When the core in
    files_dir is older than the app, the newest release is installed first. Offline, it starts anyway and tries again at the next start.
    Returns True when the core is not older than the app (or there is nothing to compare)."""
    try:
        import pyos_export
        app_version = str(pyos_export.INFO["version"])
    except Exception:                                      # noqa: BLE001 - an app without an identity: nothing to compare
        return True
    try:
        with open(os.path.join(files_dir, "VERSION"), encoding="utf-8") as f:
            core_version = f.read().strip()
    except OSError:
        return True                                        # no core yet: the first start downloads it
    import bootstrap
    if bootstrap.version_key(core_version) >= bootstrap.version_key(app_version):
        return True
    log(f"This app is {app_version} but PythonOS is still {core_version}. Bringing PythonOS up to date...")
    if bootstrap.install(files_dir, log=log):
        return True
    log("Could not update PythonOS now (no connection?). It will try again the next time the app starts.")
    return False


def main(files_dir):
    global _main_thread_id
    _main_thread_id = threading.get_ident()
    _purge_project_modules()
    os.makedirs(files_dir, exist_ok=True)
    os.chdir(files_dir)
    if files_dir not in sys.path:
        sys.path.insert(0, files_dir)
    # Which app this is (generated at build time), so PythonOS can say when a newer APK must be installed
    try:
        import json
        import pyos_export
        os.environ["PYOS_EXPORT"] = json.dumps(pyos_export.INFO)
    except Exception:
        pass
    os.environ.update({
        "PYOS_BUNDLED": "1",
        "TERM": "xterm-256color",
        "COLORTERM": "truecolor",
        "FORCE_COLOR": "1",
        "COLUMNS": str(Bridge.termColumns()),
        "LINES": str(Bridge.termRows()),
        "PYTHONIOENCODING": "utf-8",
        "PYOS_LINE_EDITOR": "1",   # no raw key events on Android: use the line editor
        "HOME": files_dir,
    })

    sys.stdout = sys.stderr = Screen()
    sys.stdin = Keyboard()
    builtins.input = _input
    getpass.getpass = _getpass
    os.system = _system
    subprocess.call = _call
    subprocess.run = _run

    # The app does not contain the OS itself: the first launch downloads the latest core from
    # GitHub releases (bootstrap.py, shipped with the app). After that PythonOS updates itself.
    import bootstrap
    if bootstrap.missing(files_dir):                  # first launch, or something was deleted: download what is missing
        if not bootstrap.install(files_dir, log=print):
            print("\nConnect to the internet, then close and reopen the app to try again.")
            Bridge.finished()
            return
    refresh_core_after_app_update(files_dir)
    while True:
        try:
            runpy.run_path(os.path.join(files_dir, "main.py"), run_name="__main__")
        except RestartRequested:
            _purge_project_modules()
            Bridge.write(CLEAR_SCREEN)
            continue
        except SystemExit:
            pass
        except BaseException:
            traceback.print_exc()
        break

    Bridge.write("\n\x1b[2m[PythonOS has shut down]\x1b[0m\n")
    Bridge.finished()
