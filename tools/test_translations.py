#!/usr/bin/env python3
"""Translations: every message passed to tr() or say() in the code has a Spanish, French and German text with the same {placeholders}, the
messages added in 1.0.13 really come out translated in the commands (report, doctor, sudo, bug detection, app permissions), and a missing
translation falls back to English instead of breaking anything."""
import ast
import io
import os
import re
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

from pyos import i18n, locales  # noqa: E402

FOLDERS = ("commands", "core", "pyos", "programs")
FILES = ("shell.py", "users.py", "main.py")
PLACEHOLDER = re.compile(r"\{(\w+)\}")
# texts that are built at run time (a column heading looked up by name), listed so they are checked too
DYNAMIC = ["Permission", "What it allows", "Asked for", "Now", "files", "system data", "yes", "Internet", "Your files", "Notifications", "Schedule",
           "System info", "Other programs"]


def literal_keys():
    found = {}
    paths = [os.path.join(REPO_ROOT, f) for f in FILES]
    for folder in FOLDERS:
        for base, _dirs, names in os.walk(os.path.join(REPO_ROOT, folder)):
            paths += [os.path.join(base, n) for n in names if n.endswith(".py")]
    for path in paths:
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
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


def main():
    keys = literal_keys()
    assert len(keys) > 150, len(keys)
    problems = []
    for key, where in sorted(keys.items()):
        for code, table in locales.CATALOGS.items():
            text = table.get(key)
            if text is None:
                problems.append(f"{code}: no translation for {key[:70]!r} ({where})")
            elif set(PLACEHOLDER.findall(text)) != set(PLACEHOLDER.findall(key)):
                problems.append(f"{code}: placeholders differ in {key[:70]!r}")
    for key in DYNAMIC:
        for code, table in locales.CATALOGS.items():
            if key not in table:
                problems.append(f"{code}: no translation for {key!r}")
    assert not problems, "\n".join(problems[:25])

    # the language is chosen by PYOS_LANG (or the setting); English is the fallback, and unknown text comes back as it is
    real = os.environ.get("PYOS_LANG")
    try:
        os.environ["PYOS_LANG"] = "es"
        assert i18n.tr("Cancelled.") == "Cancelado." and i18n.tr("{n} check(s):", n=3) == "3 comprobación(es):"
        assert i18n.tr("a text nobody translated") == "a text nobody translated" and i18n.tr("a {x}", x=1) == "a 1"
        os.environ["PYOS_LANG"] = "de"
        assert i18n.tr("Cancelled.") == "Abgebrochen."
        os.environ["PYOS_LANG"] = "fr"
        assert i18n.tr("Cancelled.") == "Annulé."
        os.environ["PYOS_LANG"] = "en"
        assert i18n.tr("Cancelled.") == "Cancelled."

        # the commands really speak the language
        from rich.console import Console
        from commands import doctor as doctor_command
        from commands import report as report_command
        from pyos import bugs, sandbox, services

        def shown(module, call):
            buffer = io.StringIO()
            module.console = Console(file=buffer, width=200, force_terminal=False)
            call()
            return buffer.getvalue()

        os.environ["PYOS_LANG"] = "es"
        text = shown(doctor_command, lambda: doctor_command.execute(["--list"]))
        assert "Comprobaciones:" in text and "(la red necesita --online)" in text, text
        text = shown(report_command, lambda: report_command.say("green", "No crash reports are waiting."))
        assert "No hay informes de fallo en espera." in text
        asked = []
        real_instance = services.instance
        services.instance = lambda name: object()
        try:
            bugs.forget()
            bugs.note("ERROR", "command ls crashed: ValueError: x (at a.py:1 f)")
            bugs.offer(lambda q: (asked.append(q), False)[1], lambda t: None, lambda t: None, now=9999.0)
        finally:
            services.instance = real_instance
            bugs.forget()
        assert asked == ["Se ha encontrado un error inesperado, ¿quieres informar de él?"], asked
        os.environ["PYOS_LANG"] = "de"
        texts = sandbox.prompt_texts()
        assert texts["wants"] == "{name} möchte {what}." and texts["whats"]["network"].startswith("sich mit dem Internet")
        assert texts["names"]["files"] == "Deine Dateien" and texts["prompt"] == "Erlauben? [n] "
        assert sandbox.describe(["exec"]) == "andere Programme starten und Code auf diesem Computer ausführen"

        # the guard asks its question in the person's language, with the words the shell handed over
        from pyos import sandbox_run
        tmp = tempfile.mkdtemp()
        here = os.getcwd()
        os.chdir(tmp)
        try:
            os.makedirs("files")
            guard = sandbox_run.Guard([], os.path.join(tmp, "app"), "utilities/notes", ["network"], None, True, texts)
            printed = io.StringIO()
            real_stdout, sys.stdout = sys.stdout, printed
            prompts = []
            guard._input = lambda prompt="": (prompts.append(prompt), "n")[1]
            try:
                try:
                    guard.need("network", "connect to the internet and your network")
                except PermissionError:
                    pass
            finally:
                sys.stdout = real_stdout
            question = printed.getvalue()
            assert "notes möchte sich mit dem Internet und deinem Netzwerk verbinden." in question and "Berechtigung: Internet." in question, question
            assert "(a) diesmal erlauben" in question and prompts == ["Erlauben? [n] "], (question, prompts)
        finally:
            os.chdir(here)
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
    finally:
        if real is None:
            os.environ.pop("PYOS_LANG", None)
        else:
            os.environ["PYOS_LANG"] = real
    print("translations: all checks passed")


if __name__ == "__main__":
    main()
