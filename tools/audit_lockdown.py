#!/usr/bin/env python3
"""Fail if PythonOS code can run commands or code in a way that lets a user out of PythonOS.

On the live ISO PythonOS runs as root, so any path that executes a command or Python the user can
influence is a way out to the Linux side. This scans the OS code (not the marketplace packages, which
are covered by the catalog's lockdown_safe flag and hash checks) and reports every call that can spawn
a process or evaluate code. Marketplace packages that claim lockdown_safe are held to the same standard with
no exceptions: they may not spawn processes, evaluate code or import anything but the editor module. Each such use must be listed in ALLOWED below with the reason it is safe;
a new, unreviewed use fails the build.

    python tools/audit_lockdown.py
"""
import ast
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
SCAN = ["commands", "core", "programs", "pyos", "shell.py", "users.py", "main.py"]

# call names that start processes or run code
RISKY_ATTRS = {
    "subprocess": {"run", "call", "check_call", "check_output", "Popen", "getoutput", "getstatusoutput"},
    "os": {"system", "popen", "execv", "execve", "execl", "execle", "execlp", "execvp", "execvpe", "execlpe",
           "spawnl", "spawnle", "spawnlp", "spawnv", "spawnve", "spawnvp", "posix_spawn", "startfile", "fork", "forkpty"},
    "pty": {"spawn", "fork"},
    "code": {"interact", "InteractiveConsole", "InteractiveInterpreter"},
    "runpy": {"run_path", "run_module"},
}
RISKY_NAMES = {"eval", "exec", "compile", "__import__", "breakpoint", "input_exec"}

# file -> why its process/code use is acceptable
ALLOWED = {
    "core/hardware.py": "runs a fixed list of system tools (ip, iw, amixer, ...) with argument lists, never a shell",
    "core/boot.py": "pip install of requirements.txt (skipped when PYOS_BUNDLED/lockdown) and clearing the screen",
    "core/BSOD.py": "clears the screen and restarts PythonOS itself with sys.executable",
    "core/screens.py": "clears the screen and restarts PythonOS itself with sys.executable",
    "pyos/stdio.py": "clears the screen (constant command only)",
    "commands/restart.py": "restarts PythonOS itself with sys.executable",
    "commands/clear.py": "clears the screen",
    "programs/marketplace.py": "package installer scripts - never run in lockdown, packages are hash-checked",
    "programs/programs.py": "imports package scripts - only trusted packages when locked down",
    "programs/calc.py": "eval over a whitelist of arithmetic AST nodes with empty builtins",
    "shell.py": "runs marketplace package scripts - only trusted packages when locked down",
    "users.py": "clears the screen",
    "main.py": "pip install of boot requirements (skipped when bundled)",
    "pyos/system.py": "loads OS commands/programs from the OS's own folders",
    "core/sysupdate.py": "loads the restart command from the OS's own folder",
    "commands/pkg.py": "loads the OS's own marketplace program",
    "commands/updatecheck.py": "",
}
# modules whose import must be a deliberate decision
FORBIDDEN_IMPORTS = {"pty", "ctypes", "code", "pdb", "cmd", "telnetlib"}


def check(path, rel):
    findings = []
    try:
        tree = ast.parse(open(path, encoding="utf-8").read(), filename=rel)
    except SyntaxError as e:
        return [(rel, e.lineno or 0, f"cannot parse: {e.msg}")]
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name.split(".")[0] for a in node.names] if isinstance(node, ast.Import) else [(node.module or "").split(".")[0]]
            for name in names:
                if name in FORBIDDEN_IMPORTS:
                    findings.append((rel, node.lineno, f"imports '{name}'"))
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            if func.attr in RISKY_ATTRS.get(func.value.id, ()):
                findings.append((rel, node.lineno, f"{func.value.id}.{func.attr}()"))
        elif isinstance(func, ast.Name) and func.id in RISKY_NAMES:
            findings.append((rel, node.lineno, f"{func.id}()"))
        for kw in node.keywords:
            if kw.arg == "shell" and isinstance(kw.value, ast.Constant) and kw.value.value is True:
                findings.append((rel, node.lineno, "shell=True"))
    return findings


def files():
    for item in SCAN:
        full = os.path.join(ROOT, item)
        if os.path.isfile(full):
            yield full, item
        else:
            for name in sorted(os.listdir(full)):
                if name.endswith(".py"):
                    yield os.path.join(full, name), f"{item}/{name}"


SAFE_IMPORT_MODULES = {"commands.edit"}          # the built-in editor: it cannot run commands


def safe_packages():
    """(path, relative name) of every .py file in a catalog package that is marked lockdown_safe."""
    import json
    base = os.path.join(ROOT, "online_packages")
    for category in sorted(os.listdir(base)):
        cat_dir = os.path.join(base, category)
        if not os.path.isdir(cat_dir):
            continue
        for name in sorted(os.listdir(cat_dir)):
            folder = os.path.join(cat_dir, name)
            try:
                with open(os.path.join(folder, "data.json"), encoding="utf-8") as f:
                    if not json.load(f).get("lockdown_safe"):
                        continue
            except (OSError, ValueError):
                continue
            for dirpath, _dirs, filenames in os.walk(folder):
                for filename in sorted(filenames):
                    if filename.endswith(".py"):
                        full = os.path.join(dirpath, filename)
                        yield full, os.path.relpath(full, ROOT).replace(os.sep, "/")


def check_package(path, rel):
    findings = check(path, rel)
    tree = ast.parse(open(path, encoding="utf-8").read(), filename=rel)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in ("import_module", "__import__"):
            arg = node.args[0] if node.args else None
            if not (isinstance(arg, ast.Constant) and arg.value in SAFE_IMPORT_MODULES):
                findings.append((rel, node.lineno, f"{node.func.attr}() of something other than {sorted(SAFE_IMPORT_MODULES)}"))
    return findings


def main():
    problems, reviewed = [], 0
    for path, rel in safe_packages():
        problems += check_package(path, rel)
    for path, rel in files():
        found = check(path, rel)
        if not found:
            continue
        if rel in ALLOWED:
            reviewed += len(found)
            # shell=True is never acceptable, even in reviewed files
            problems += [f for f in found if "shell=True" in f[2]]
            continue
        problems += found
    if problems:
        print("Lockdown audit FAILED - these can run commands or code and are not reviewed:")
        for rel, line, what in problems:
            print(f"  {rel}:{line}  {what}")
        print("\nIf a use is genuinely safe, add the file to ALLOWED in tools/audit_lockdown.py with the reason,")
        print("and make sure it is refused when pyos.lockdown.enabled() if it could run user-controlled code.")
        return 1
    print(f"Lockdown audit passed ({reviewed} reviewed uses in {len(ALLOWED)} allowed files, no unreviewed ones).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
