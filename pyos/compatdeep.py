# pyos/compatdeep.py - the part of the compatibility test that actually RUNS things, and looks at the system itself
#
# pyos/compat.py reads the code. This goes further, in separate processes so that nothing it does can hurt the running PythonOS:
#
#   load         every command and program is imported the way the shell imports it at start-up (a missing library or a crash at import shows
#                here, a typo in the code does not), and its config and execute function are checked
#   probe        the commands an app may use (pyos.corecmd) are run on harmless input and their answer is compared with what it should be: sort sorts,
#                sha256sum gives the right hash, calc calculates, df and free report numbers
#   apps         every installed app is started with --help, with no keyboard, for a few seconds, under the permission guard: does it start, or does it
#                stop with a traceback? An app that waits for input is fine; one that cannot start is not
#   environment  this system itself: Python and its modules, the terminal, text encoding, memory, disk, the clock, whether the folders are writable
#                and whether the internet is reachable
#
# Nothing is changed: probes use text and read-only commands, and apps are started with no input. Refused while lockdown is on.
import importlib.util
import inspect
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import time

from . import export, lockdown
from .compat import Result

MARK = "@@COMPAT@@"
APP_SECONDS = 12

# (command, arguments, text to read, what the output must contain, (more that must be there too)). Only commands pyos.corecmd allows, only harmless ones.
PROBES = [
    ("echo", ["hello"], None, "hello"), ("seq", ["3"], None, "3"), ("rev", [], "abc\n", "cba"), ("tac", [], "a\nb\n", "b"), ("nl", [], "x\n", "x"),
    ("wc", [], "a b\n", "1"), ("tr", ["a-z", "A-Z"], "abc\n", "ABC"), ("sort", [], "b\na\n", "a"), ("uniq", [], "a\na\nb\n", "b"),
    ("cut", ["-d", ",", "-f", "2"], "x,y,z\n", "y"), ("grep", ["b"], "abc\nxyz\n", "abc"), ("head", ["-n", "1"], "1\n2\n", "1"), ("tail", ["-n", "1"], "1\n2\n", "2"),
    ("sed", ["s/a/b/"], "aaa\n", "baa"), ("base64", [], "hi\n", "aGkK"), ("sha256sum", [], "abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"),
    ("md5sum", [], "abc", "900150983cd24fb0d6963f7d28e17f72"), ("sha1sum", [], "abc", "a9993e364706816aba3e25717850c26c9cd0d89d"),
    ("calc", ["2", "+", "2"], None, "4"), ("column", ["-t"], "a b\nccc d\n", "ccc"), ("fold", ["-w", "3"], "abcdef\n", "abc"), ("shuf", ["-i", "1-3"], None, "1"),
    ("uuidgen", [], None, "-"), ("basename", ["/a/b.txt"], None, "b.txt"), ("dirname", ["/a/b.txt"], None, "/a"), ("date", [], None, str(time.localtime().tm_year)),
    ("cal", [], None, str(time.localtime().tm_year)), ("uname", [], None, ""), ("hostname", [], None, ""), ("pwd", [], None, ""), ("nproc", [], None, ""),
    ("ls", [], None, ""), ("df", [], None, ""), ("free", [], None, ""), ("uptime", [], None, ""), ("lscpu", [], None, ""), ("sysinfo", [], None, ""),
    ("ps", [], None, ""),
]
NETWORK_PROBES = [("ping", ["127.0.0.1"], None, ""), ("nslookup", ["localhost"], None, "")]


# ---------------------------------------------------------------- the child processes
def _child_load(paths):
    out = {}
    for path in paths:
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            spec = importlib.util.spec_from_file_location("compat_load_" + name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            problems = []
            config = getattr(module, "config", None)
            aliases = []
            if not isinstance(config, dict):
                problems.append("config is not a dictionary")
            else:
                if not str(config.get("description", "")).strip():
                    problems.append("config has no description")
                listed = config.get("alias", [])
                if not isinstance(listed, list):
                    problems.append("config alias is not a list")
                else:
                    aliases = [str(a) for a in listed]
            execute = getattr(module, "execute", None)
            if not callable(execute):
                problems.append("execute is not a function")
            else:
                try:
                    parameters = [p for p in inspect.signature(execute).parameters.values()
                                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD) and p.default is p.empty]
                    if len(parameters) > 1:
                        problems.append("execute needs more than the argument list")
                except (TypeError, ValueError):
                    pass
            out[path] = {"problems": problems, "name": (config or {}).get("name", name) if isinstance(config, dict) else name, "aliases": aliases}
        except BaseException as e:                                       # noqa: BLE001 - SystemExit and KeyboardInterrupt at import time are failures too
            out[path] = {"problems": [f"fails to load: {type(e).__name__}: {str(e)[:160]}"], "name": name, "aliases": []}
    print(MARK + json.dumps(out))


def _child_probe(items):
    from pyos import corecmd
    out = []
    for command, args, stdin, expect in items:
        started = time.time()
        try:
            result = corecmd.run(command, args, stdin=stdin)
        except BaseException as e:                                       # noqa: BLE001
            out.append({"command": command, "problem": f"crashed: {type(e).__name__}: {str(e)[:120]}"})
            continue
        seconds = time.time() - started
        if not result.ok:
            out.append({"command": command, "problem": f"reported a failure: {result.output.strip()[:120] or result.code}"})
        elif expect and expect.lower() not in result.output.lower():
            out.append({"command": command, "problem": f"did not print what it should (wanted '{expect[:30]}', got '{result.output.strip()[:60]}')"})
        elif not result.output.strip() and command not in ("ls", "ps"):
            out.append({"command": command, "problem": "printed nothing"})
        elif seconds > 10:
            out.append({"command": command, "problem": f"took {seconds:.0f} seconds"})
        else:
            out.append({"command": command, "problem": None})
    print(MARK + json.dumps(out))


def _child_fuzz(cases):
    from pyos import corecmd
    crashed = []
    for index, (command, args, text) in enumerate(cases):
        print(f"{MARK}CASE {index}", flush=True)
        try:
            result = corecmd.run(command, args, stdin=text)
        except BaseException as e:                                       # noqa: BLE001
            crashed.append({"command": command, "args": [str(a)[:40] for a in args], "text": (text or "")[:20], "error": f"{type(e).__name__}: {str(e)[:100]}"})
            continue
        if result.crashed:
            crashed.append({"command": command, "args": [str(a)[:40] for a in args], "text": (text or "")[:20],
                            "error": (result.output.strip().splitlines() or ["?"])[-1][:140]})
    print(MARK + json.dumps(crashed))


def _run_child(mode, payload, timeout):
    """The JSON a child process printed, or (None, why)."""
    try:
        done = subprocess.run([sys.executable, "-m", "pyos.compatdeep", "--child", mode], input=json.dumps(payload), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                              cwd=os.getcwd(), env=dict(os.environ, PYOS_BUNDLED=os.environ.get("PYOS_BUNDLED", "1"), PYTHONPATH=os.getcwd(), PYTHONUTF8="1"))
    except subprocess.TimeoutExpired as e:
        partial = e.stdout.decode("utf-8", "replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        cases = [l for l in partial.splitlines() if l.startswith(MARK + "CASE")]
        return None, f"did not finish in {timeout} seconds" + (f" (it was on test case {cases[-1].split()[-1]})" if cases else "")
    except OSError as e:
        return None, f"could not be started ({type(e).__name__})"
    for line in done.stdout.splitlines():
        if line.startswith(MARK) and not line.startswith(MARK + "CASE"):
            try:
                return json.loads(line[len(MARK):]), None
            except ValueError:
                break
    tail = (done.stderr or done.stdout).strip().splitlines()[-1:] or ["no answer"]
    return None, f"stopped (exit {done.returncode}): {tail[0][:140]}"


# ---------------------------------------------------------------- what the parent runs
def refused():
    return "the deep test starts programs, so it is switched off while lockdown is on" if lockdown.enabled() else ""


def load_check(folders=("commands", "programs"), timeout=180):
    """Results for importing every command and program in a fresh Python, plus name clashes between them. [Result]"""
    files = []
    for folder in folders:
        if os.path.isdir(folder):
            files += [(folder, os.path.join(os.path.abspath(folder), n)) for n in sorted(os.listdir(folder)) if n.endswith(".py") and not n.startswith("_")]
    if not files:
        return []
    answer, why = _run_child("load", [p for _f, p in files], timeout)
    if answer is None:
        return [Result("system", "loading commands and programs", "fail", [why])]
    out, owners = [], {}
    for folder, path in files:
        info = answer.get(path) or {"problems": ["was not tested"], "name": os.path.basename(path)[:-3], "aliases": []}
        kind = "command" if folder == "commands" else "program"
        name = os.path.basename(path)[:-3]
        if info["problems"]:
            out.append(Result(kind, name, "fail", ["loading it: " + "; ".join(info["problems"])]))
        for word in [info["name"]] + info["aliases"]:
            owners.setdefault(word, []).append(f"{kind} {name}")
    for word, who in sorted(owners.items()):
        if len(who) > 1:
            out.append(Result("system", f"the word '{word}'", "warn", ["claimed by " + " and ".join(who) + " (only one of them can be reached by that name)"]))
    return out


def probe_check(network=False, timeout=240):
    """Results for running the safe commands on harmless input. [Result]"""
    items = PROBES + (NETWORK_PROBES if network else [])
    answer, why = _run_child("probe", [list(i) for i in items], timeout)
    if answer is None:
        return [Result("system", "running commands", "fail", [why])]
    return [Result("command", row["command"], "fail", ["ran on test input and " + row["problem"]]) for row in answer if row["problem"]]


def fuzz_check(per_command=None, timeout=300):
    """Results for trying the commands apps may use with odd arguments and odd text. A command that raises an error of its own is a bug. [Result]"""
    from . import corecmd, devtools
    cases = devtools.fuzz_cases(corecmd.names(), per_command)
    answer, why = _run_child("fuzz", [[c, list(a), t] for c, a, t in cases], timeout)
    if answer is None:
        return [Result("system", "trying odd input", "fail", [why])]
    out = []
    for row in answer:
        shown = " ".join(row["args"]) or "(no arguments)"
        out.append(Result("command", row["command"], "fail", [f"raised an error on odd input: {row['error']}  [{shown}{' + text ' + repr(row['text']) if row['text'] else ''}]"]))
    if not out:
        out.append(Result("system", "odd input", "ok", [f"{len(cases)} odd cases tried on {len({c for c, _a, _t in cases})} commands, none raised an error"]))
    return out


def app_script(folder, meta):
    scripts = meta.get("scripts") or {}
    here = export.current()
    key = "run_" + str(here) if here and ("run_" + str(here)) in scripts else "run"
    name = scripts.get(key) or next(iter(scripts.values()), None)
    return os.path.join(folder, name) if name else None


def launch_check(root="files", progress=None):
    """Results for starting every installed app with --help and no keyboard. [Result]"""
    from . import apprun, compat, sandbox
    if apprun._in_process_only():
        return [Result("system", "starting apps", "skip", ["apps run inside the program here, so they cannot be started on their own for a test"])]
    out, apps = [], compat.installed_apps(root)
    for index, (folder, meta) in enumerate(apps):
        name = os.path.basename(folder)
        if progress:
            progress(index, len(apps), name)
        if not isinstance(meta, dict):
            continue
        from . import marketapi
        fits, _why = marketapi.compatibility(meta)
        script = app_script(folder, meta)
        if not fits or not script or not os.path.isfile(script):
            continue                                                       # compat.scan_apps already says why
        if (meta.get("requires") or meta.get("pip")) and not os.path.isfile(os.path.join(folder, ".libs", ".specs")) and meta.get("pip"):
            continue
        try:
            command, env = sandbox.launch(script, ["--help"], folder, meta)
        except Exception as e:                                             # noqa: BLE001
            out.append(Result("app", name, "fail", [f"could not be prepared to start ({type(e).__name__})"]))
            continue
        env = dict(env, PYOS_COMPAT_TEST="1", PYTHONUTF8="1")
        started = time.time()
        try:
            done = subprocess.run(command, env=env, input="", capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=APP_SECONDS)
            code, err, text = done.returncode, done.stderr or "", done.stdout or ""
        except subprocess.TimeoutExpired as e:
            raw = e.stderr or b""
            code, err, text = None, raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw, ""
        except OSError as e:
            out.append(Result("app", name, "fail", [f"could not be started ({type(e).__name__}: {e})"]))
            continue
        seconds = time.time() - started
        last = [l for l in err.strip().splitlines() if l.strip()][-1:] or [""]
        if "Traceback (most recent call last)" in err:
            out.append(Result("app", name, "fail", [f"started and crashed: {last[0][:160]}"]))
        elif "Blocked:" in err:
            out.append(Result("app", name, "warn", [f"started and was stopped by its permissions: {last[0][:140]}"]))
        elif code is not None and code not in (0, 1, 2, 130):
            out.append(Result("app", name, "fail", [f"started and ended with exit code {code}" + (f": {last[0][:120]}" if last[0] else "")]))
        elif seconds > APP_SECONDS - 1 and code is None:
            out.append(Result("app", name, "ok", ["started and was waiting for input"]))
        elif not (text.strip() or err.strip()) and code == 0:
            out.append(Result("app", name, "warn", ["started and printed nothing"]))
        else:
            out.append(Result("app", name, "ok", []))
    return out


def environment(network=False):
    """Results about this system itself. [Result]"""
    out = []

    def add(name, level, notes):
        out.append(Result("system", name, level, notes))
    version = sys.version_info
    add("Python", "ok" if version >= (3, 9) else "fail", [f"{platform.python_version()} ({platform.python_implementation()})"] + ([] if version >= (3, 9) else ["PythonOS needs 3.9 or newer"]))
    missing = []
    for module in ("ssl", "sqlite3", "zlib", "bz2", "lzma", "ctypes", "hashlib", "json", "socket", "threading", "uuid", "decimal", "zipfile", "tarfile"):
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(module)
    add("Python modules", "warn" if missing else "ok", [("missing from this Python: " + ", ".join(missing)) if missing else "the standard modules PythonOS uses are all there"])
    import hashlib
    add("scrypt passwords", "ok" if hasattr(hashlib, "scrypt") else "warn", ["available" if hasattr(hashlib, "scrypt") else "this Python has no hashlib.scrypt, so passwords use PBKDF2"])
    encoding = (sys.stdout.encoding or "unknown")
    add("text encoding", "ok" if "utf" in encoding.lower() else "warn",
        [f"the screen uses {encoding}" + ("" if "utf" in encoding.lower() else " (accents, boxes and emoji may show wrongly; PYTHONUTF8=1 fixes it)")])
    columns, lines = shutil.get_terminal_size((0, 0))
    if columns:
        add("terminal", "ok" if columns >= 60 else "warn", [f"{columns} x {lines}" + ("" if columns >= 60 else " (narrow: tables will wrap)"),
                                                            "colour: " + ("yes" if os.environ.get("COLORTERM") or "color" in os.environ.get("TERM", "") or os.environ.get("WT_SESSION") else "not sure")])
    else:
        add("terminal", "skip", ["not a terminal (output is being captured)"])
    for folder in ("files", ".OSData"):
        if os.path.isdir(folder):
            writable = os.access(folder, os.W_OK)
            add(f"{folder}/ folder", "ok" if writable else "fail", ["writable" if writable else "cannot be written to"])
    try:
        free = shutil.disk_usage(".").free
        add("disk space", "ok" if free > 200 * 1024 * 1024 else "warn", [f"{free // (1024 * 1024):,} MB free" + ("" if free > 200 * 1024 * 1024 else " (updates and apps need more)")])
    except OSError:
        pass
    try:
        import psutil
        memory = psutil.virtual_memory()
        add("memory", "ok" if memory.available > 150 * 1024 * 1024 else "warn", [f"{memory.available // (1024 * 1024):,} MB free of {memory.total // (1024 * 1024):,} MB"])
    except Exception:                                                      # noqa: BLE001 - some systems hide it
        add("memory", "skip", ["cannot be read here"])
    year = time.localtime().tm_year
    add("clock", "ok" if year >= 2024 else "warn", [time.strftime("%Y-%m-%d %H:%M") + ("" if year >= 2024 else " (the clock is wrong: certificates and updates will fail)")])
    add("export", "ok", [export.title(export.current()) if export.current() else "a source checkout", platform.platform()])
    try:
        from . import extras
        items = extras.catalog()
        missing_libs = [e.name for e in items if not e.installed()]
        add("optional libraries", "ok" if not missing_libs else "warn",
            [f"{len(items) - len(missing_libs)} of {len(items)} installed" + (f"; missing: {', '.join(missing_libs[:6])}" if missing_libs else "")])
    except Exception:                                                      # noqa: BLE001
        pass
    if network:
        for host in ("github.com", "pypi.org"):
            started = time.time()
            try:
                socket.create_connection((host, 443), timeout=5).close()
                add(f"internet ({host})", "ok", [f"reachable in {time.time() - started:.1f} s"])
            except OSError as e:
                add(f"internet ({host})", "warn", [f"not reachable ({type(e).__name__}); updates, the marketplace and gh need it"])
    return out


def run(root="files", network=False, progress=None):
    """Everything above, in order. [Result]"""
    why = refused()
    if why:
        return [Result("system", "deep test", "skip", [why])]
    results = environment(network)
    results += load_check()
    results += probe_check(network)
    results += launch_check(root, progress)
    return results


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--child":
        sys.path.insert(0, os.getcwd())
        payload = json.loads(sys.stdin.read())
        if sys.argv[2] == "load":
            _child_load(payload)
        elif sys.argv[2] == "probe":
            _child_probe([tuple(i) for i in payload])
        elif sys.argv[2] == "fuzz":
            _child_fuzz([tuple(i) for i in payload])
