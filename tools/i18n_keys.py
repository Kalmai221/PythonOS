"""The messages PythonOS can show in another language: every text passed to tr() (or to a command's say() helper) in the code, found by
reading the source, plus the few texts that are looked up at run time by name. Used by tools/translate_ci.py and by the translation test."""
import ast
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
FOLDERS = ("commands", "core", "pyos", "programs")
FILES = ("shell.py", "users.py", "main.py")
# texts that are built at run time (a column heading looked up by name) and so cannot be found by reading the source
DYNAMIC = ["Permission", "What it allows", "Asked for", "Now", "files", "system data", "yes", "Internet", "Your files", "Notifications", "Schedule",
           "System info", "Other programs", "connect to the internet and your network", "read and change your files and folders",
           "show you notifications", "schedule tasks that run later (alarms, reminders)",
           "read information about this computer (processes, memory, disk)", "start other programs and run code on this computer",
           "Disk space", "System files", "Commands", "Folders", "Accounts", "Permissions", "Packages", "Libraries", "Stale data", "Settings",
           "Aliases", "Storage", "Log", "Python", "Clock", "Terminal", "Package", "Memory", "Swap", "Network", "Updates", "Crash reports"]
# a multi-line text that the doctor command passes by name
DOCTOR_USAGE = ("usage: doctor [--fix] [--yes] [--online] [--problems] [--only name,...] [--json] [--timings] [--list]\n"
                "  --fix       offer the fixes without asking first    --yes   apply every fix without asking\n"
                "  --online    also check the internet and the latest release\n"
                "  --problems  show only what needs attention           --only  run just those checks (see --list)\n"
                "  --json      machine-readable result                  --timings  how long each check took")


def _source_files():
    paths = [os.path.join(REPO_ROOT, f) for f in FILES]
    for folder in FOLDERS:
        for base, _dirs, names in os.walk(os.path.join(REPO_ROOT, folder)):
            paths += [os.path.join(base, n) for n in sorted(names) if n.endswith(".py")]
    return sorted(paths)


def literal_keys():
    """{English text: the first file that uses it} for every literal text given to tr() or say()."""
    found = {}
    for path in _source_files():
        try:
            with open(path, encoding="utf-8") as f:
                tree = ast.parse(f.read())
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            arg = None
            if node.func.id == "tr" and node.args:
                arg = node.args[0]
            elif node.func.id == "say" and len(node.args) >= 2:
                arg = node.args[1]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                found.setdefault(arg.value, os.path.relpath(path, REPO_ROOT))
    return found


def all_keys():
    """Every message that needs a translation, in a stable order."""
    keys = dict(literal_keys())
    for text in DYNAMIC + [DOCTOR_USAGE]:
        keys.setdefault(text, "(looked up by name)")
    return sorted(keys)
