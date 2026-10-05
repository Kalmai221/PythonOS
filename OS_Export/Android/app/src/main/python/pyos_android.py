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


def app_update():
    """JSON about a newer APK (it cannot update itself), or "" if this app is current / offline."""
    try:
        from core import sysupdate
        st = sysupdate.check_export_update(timeout=6)
        if st and st["state"] in ("update", "incompatible"):
            remote = st["remote"]
            url = remote["url"]
            import platform
            wanted = {"aarch64": "arm64-v8a", "arm64": "arm64-v8a", "x86_64": "x86_64"}.get(platform.machine().lower())
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
    if not os.path.isfile(os.path.join(files_dir, "main.py")):
        import bootstrap
        print("Downloading PythonOS (first launch only)...")
        if not bootstrap.install(files_dir, log=print):
            print("\nConnect to the internet, then close and reopen the app to try again.")
            Bridge.finished()
            return
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
