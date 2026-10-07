# pyos/compat.py - does every command and app work on this export?
#
# Used by the developer tools ("compat"). It looks at each installed command and marketplace app WITHOUT running it (running everything
# would shut the computer down, wipe it, or wait for a keypress): it reads the code and checks what it needs against what this system has.
#
#   - the file parses, and a command has a config and an execute function
#   - it is meant for this export ("exports" in the command's config or the app's data.json)
#   - the Python modules it imports exist here (a Windows-only module on Android, a library that did not install). An import inside a
#     try/except ImportError is optional, so a missing one is only a note
#   - the os functions it uses exist here (os.fork on Windows, os.geteuid on Android)
#   - the system tools it starts (ip, rc-service, ping) are installed
#   - an app: its marketplace API level fits, its scripts exist, its permissions and libraries are valid, what it requires is installed
#
# Each result is ok, warn (something is missing but it may still work), fail (it will not work here) or skip (it is not for this export).
import ast
import importlib.machinery
import importlib.util
import json
import os
import platform
import shutil
import sys
import time

LEVELS = ("fail", "warn", "skip", "ok")
LOCAL = {"pyos", "core", "shell", "users", "commands", "programs", "main", "core_video", "core_overlay", "installer", "bootstrap", "pyos_export",
         "pyos_android"}
EXEC_FUNCTIONS = {"run", "call", "Popen", "check_output", "check_call"}


class Result:
    def __init__(self, kind, name, level, notes):
        self.kind, self.name, self.level, self.notes = kind, name, level, notes

    def line(self):
        return f"{self.kind} {self.name}: " + "; ".join(self.notes) if self.notes else f"{self.kind} {self.name}"


def _top(name):
    return name.split(".")[0]


def _exists(module, extra_paths=None):
    """True if `module` can be imported here (looked for, not imported)."""
    if module in LOCAL or module in sys.builtin_module_names:
        return True
    try:
        if importlib.util.find_spec(module) is not None:
            return True
    except (ImportError, ValueError, AttributeError):
        pass
    if extra_paths:
        return importlib.machinery.PathFinder.find_spec(module, extra_paths) is not None
    return False


def _guarded(node):
    """Imports in the body of a `try` that catches ImportError, ModuleNotFoundError or everything are optional."""
    for handler in node.handlers:
        names = []
        if handler.type is None:
            return True
        types = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
        for t in types:
            names.append(getattr(t, "id", getattr(t, "attr", "")))
        if {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"} & set(names):
            return True
    return False


def analyse(source):
    """(required modules, optional modules, os attributes used, system tools started, problem) for a piece of Python source."""
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        return set(), set(), set(), set(), f"does not parse (line {e.lineno}: {e.msg})"
    required, optional, os_names, tools, checked = set(), set(), set(), set(), set()
    optional_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try) and _guarded(node):
            for child in node.body:
                for inner in ast.walk(child):
                    optional_nodes.add(id(inner))
    for node in ast.walk(tree):
        modules = []
        if isinstance(node, ast.Import):
            modules = [_top(alias.name) for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules = [_top(node.module)]
        for module in modules:
            (optional if id(node) in optional_nodes else required).add(module)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "os":
            os_names.add(node.attr)
        if isinstance(node, ast.Call):
            func = node.func
            called = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", "")
            owner = func.value.id if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) else ""
            if called in EXEC_FUNCTIONS and owner in ("subprocess", "hardware") and node.args:
                first = node.args[0]
                if isinstance(first, (ast.List, ast.Tuple)) and first.elts and isinstance(first.elts[0], ast.Constant) and isinstance(first.elts[0].value, str):
                    tools.add(first.elts[0].value)
            if called == "which" and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                checked.add(node.args[0].value)              # the code checks for it itself
    return required, optional, os_names, tools - checked, None


def _judge(kind, name, source, extra_paths=None):
    """Result for one file's code: what it needs against what this system has."""
    required, optional, os_names, tools, problem = analyse(source)
    if problem:
        return Result(kind, name, "fail", [problem])
    notes, level = [], "ok"
    missing = sorted(m for m in required if not _exists(m, extra_paths))
    if missing:
        level = "fail"
        notes.append("needs " + ", ".join(missing) + ", which this system does not have")
    soft = sorted(m for m in optional if not _exists(m, extra_paths))
    if soft:
        notes.append("optional: " + ", ".join(soft) + " missing")
        level = "warn" if level == "ok" else level
    gone = sorted(n for n in os_names if not hasattr(os, n))
    if gone:
        notes.append("uses os." + ", os.".join(gone) + ", which this system does not have")
        level = "warn" if level == "ok" else level
    absent = sorted(t for t in tools if shutil.which(t) is None)
    if absent:
        notes.append("starts " + ", ".join(absent) + ", which is not installed here")
        level = "warn" if level == "ok" else level
    return Result(kind, name, level, notes)


def _runs_here(exports):
    from pyos import export
    return export.runs_here(exports)


def scan_commands(folder="commands", programs_folder="programs"):
    """One Result for each command and built-in program."""
    out = []
    for directory, kind in ((folder, "command"), (programs_folder, "program")):
        if not os.path.isdir(directory):
            continue
        for file_name in sorted(os.listdir(directory)):
            if not file_name.endswith(".py") or file_name.startswith("_"):
                continue
            path = os.path.join(directory, file_name)
            name = file_name[:-3]
            try:
                with open(path, encoding="utf-8") as f:
                    source = f.read()
            except OSError as e:
                out.append(Result(kind, name, "fail", [f"cannot be read ({e.__class__.__name__})"]))
                continue
            try:
                tree = ast.parse(source)
            except SyntaxError as e:
                out.append(Result(kind, name, "fail", [f"does not parse (line {e.lineno}: {e.msg})"]))
                continue
            exports, has_config, has_execute = None, False, False
            for node in tree.body:
                if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "config" for t in node.targets):
                    has_config = True
                    if isinstance(node.value, ast.Dict):
                        for key, value in zip(node.value.keys, node.value.values):
                            if isinstance(key, ast.Constant) and key.value == "exports":
                                try:
                                    exports = ast.literal_eval(value)
                                except ValueError:
                                    exports = None
                elif isinstance(node, ast.FunctionDef) and node.name == "execute":
                    has_execute = True
            if exports and not _runs_here(exports):
                from pyos import export
                out.append(Result(kind, name, "skip", [f"is for {export.where(exports)}"]))
                continue
            if not (has_config and has_execute):
                out.append(Result(kind, name, "fail", ["has no config or no execute function"]))
                continue
            out.append(_judge(kind, name, source))
    return out


def installed_apps(root="files"):
    """[(folder, data.json contents or None)] of the installed marketplace apps."""
    found = []
    try:
        categories = sorted(d for d in os.listdir(root) if d.startswith("installed_"))
    except OSError:
        return found
    for category in categories:
        base = os.path.join(root, category)
        for name in sorted(os.listdir(base)):
            folder = os.path.join(base, name)
            if not os.path.isdir(folder) or name.startswith((".tmp_", ".old_")):
                continue
            try:
                with open(os.path.join(folder, "data.json"), encoding="utf-8") as f:
                    found.append((folder, json.load(f)))
            except (OSError, ValueError):
                found.append((folder, None))
    return found


def scan_apps(root="files"):
    """One Result for each installed marketplace app."""
    from pyos import marketapi, sandbox
    apps = installed_apps(root)
    names = {str((meta or {}).get("name", "")).lower() for _f, meta in apps} | {os.path.basename(f).lower() for f, _m in apps}
    out = []
    for folder, meta in apps:
        name = os.path.basename(folder)
        if not isinstance(meta, dict):
            out.append(Result("app", name, "fail", ["data.json is missing or damaged"]))
            continue
        fits, why = marketapi.compatibility(meta)
        if not fits:
            exports = meta.get("exports")
            level = "skip" if isinstance(exports, list) and exports and not _runs_here(exports) else "fail"
            out.append(Result("app", name, level, [why]))
            continue
        notes, level = [], "ok"
        scripts = meta.get("scripts") or {}
        if not scripts:
            notes.append("data.json has no scripts")
            level = "fail"
        libs = os.path.join(folder, ".libs")
        paths = [libs] if os.path.isdir(libs) else None
        try:
            specs = marketapi.pip_specs(meta)
        except ValueError as e:
            specs = []
            notes.append(f"its libraries list is not valid ({e})")
            level = "fail"
        if specs and not os.path.isfile(os.path.join(libs, ".specs")):
            notes.append("its Python libraries are not installed (reinstall it with pkg install)")
            level = "fail"
        from pyos import export
        here = export.current()
        for key, script in scripts.items():
            if key.startswith("run_") and key != "run_" + str(here):
                continue                                   # the start script of another export
            path = os.path.join(folder, script)
            if not os.path.isfile(path):
                notes.append(f"script {script} ({key}) is missing")
                level = "fail"
                continue
            try:
                with open(path, encoding="utf-8") as f:
                    judged = _judge("app", name, f.read(), paths)
            except OSError:
                notes.append(f"script {script} cannot be read")
                level = "fail"
                continue
            for note in judged.notes:
                notes.append(f"{script}: {note}")
            if LEVELS.index(judged.level) < LEVELS.index(level):
                level = judged.level
        asked = meta.get("permissions")
        unknown = [p for p in asked if p not in sandbox.PERMISSIONS] if isinstance(asked, list) else []
        if unknown:
            notes.append("asks for permissions this PythonOS does not know: " + ", ".join(unknown))
            level = "warn" if level == "ok" else level
        for requirement in meta.get("requires") or []:
            base = str(requirement).split(">")[0].split("<")[0].split("=")[0].strip().lower()
            if base and base not in names and not any(base in n for n in names):
                notes.append(f"requires {base}, which is not installed")
                level = "warn" if level == "ok" else level
        out.append(Result("app", name, level, notes))
    return out


def summary(results):
    counts = {"command": {l: 0 for l in LEVELS}, "program": {l: 0 for l in LEVELS}, "app": {l: 0 for l in LEVELS}}
    for r in results:
        counts[r.kind][r.level] += 1
    return counts


def report(results, version="?", package="unknown"):
    """The text sent as feedback: the system, the totals, and every failure, warning and skip with its reason."""
    counts = summary(results)
    lines = ["## Compatibility test", "",
             f"- PythonOS: {version}", f"- Package: {package}", f"- Python: {platform.python_version()}",
             f"- System: {platform.system()} {platform.release()} {platform.machine()}", f"- Time: {time.strftime('%Y-%m-%d %H:%M:%S')}", "",
             "## Totals", ""]
    for kind, label in (("command", "Commands"), ("program", "Built-in programs"), ("app", "Apps")):
        c = counts[kind]
        total = sum(c.values())
        if total:
            lines.append(f"- {label}: {total} tested - {c['ok']} ok, {c['warn']} with warnings, {c['fail']} failing, {c['skip']} for another export")
    for level, title in (("fail", "Will not work here"), ("warn", "Warnings (may still work)"), ("skip", "Not for this export")):
        picked = [r for r in results if r.level == level]
        if picked:
            lines += ["", f"## {title} ({len(picked)})", ""] + [f"- {r.line()}" for r in picked]
    return "\n".join(lines) + "\n"


def run(progress=None):
    """Test everything. `progress(done, total)` is called as it goes. Returns the results (commands, programs, then apps)."""
    results = scan_commands()
    results += scan_apps()
    if progress:
        progress(len(results), len(results))
    return results
