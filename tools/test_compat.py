#!/usr/bin/env python3
"""The developer tool "compat": every command, program and app is checked against the export WITHOUT being run. A tree of small fake commands
and apps stands in for the real ones; the Discord way is faked."""
import json
import os
import shutil
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

from pyos import compat  # noqa: E402

GOOD = 'config = {"name": "good", "description": "x"}\n\ndef execute(args=None):\n    import json\n    return True\n'


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def by_name(results):
    return {(r.kind, r.name): r for r in results}


def main():
    tmp = tempfile.mkdtemp()
    real_runs_here = compat._runs_here
    try:
        commands, programs = os.path.join(tmp, "commands"), os.path.join(tmp, "programs")
        write(os.path.join(commands, "good.py"), GOOD)
        write(os.path.join(commands, "broken.py"), "def execute(:\n")
        write(os.path.join(commands, "noexec.py"), 'config = {"name": "noexec"}\n')
        write(os.path.join(commands, "needs.py"), GOOD + "import no_such_module_zzz\nfrom no_such_other_zzz.sub import thing\n")
        write(os.path.join(commands, "soft.py"), GOOD + "try:\n    import no_such_module_zzz\nexcept ImportError:\n    no_such_module_zzz = None\n")
        write(os.path.join(commands, "osattr.py"), GOOD + "x = os.no_such_os_function_zzz()\nimport os\n")
        write(os.path.join(commands, "tool.py"), GOOD + 'import subprocess\nsubprocess.run(["no-such-tool-zzz", "-x"])\n')
        write(os.path.join(commands, "checked.py"), GOOD + 'import shutil, subprocess\nif shutil.which("no-such-tool-zzz"):\n    subprocess.run(["no-such-tool-zzz"])\n')
        write(os.path.join(commands, "droid.py"), 'config = {"name": "droid", "exports": ["android"]}\n\ndef execute(args=None):\n    import termios\n')
        write(os.path.join(programs, "prog.py"), GOOD)
        write(os.path.join(commands, "_private.py"), "this is not python (and is skipped)")

        results = compat.scan_commands(commands, programs)
        found = by_name(results)
        assert found[("command", "good")].level == "ok" and found[("program", "prog")].level == "ok"
        assert ("command", "_private") not in found
        assert found[("command", "broken")].level == "fail" and "does not parse" in found[("command", "broken")].notes[0]
        assert found[("command", "noexec")].level == "fail" and "no config" in found[("command", "noexec")].notes[0]
        needs = found[("command", "needs")]
        assert needs.level == "fail" and "no_such_module_zzz" in needs.notes[0] and "no_such_other_zzz" in needs.notes[0], needs.notes
        soft = found[("command", "soft")]
        assert soft.level == "warn" and "optional" in soft.notes[0], "an import inside try/except ImportError is only a note"
        assert found[("command", "osattr")].level == "warn" and "os.no_such_os_function_zzz" in found[("command", "osattr")].notes[0]
        assert found[("command", "tool")].level == "warn" and "no-such-tool-zzz" in found[("command", "tool")].notes[0]
        assert found[("command", "checked")].level == "ok", "code that checks for a tool itself is not blamed"
        # a command for another export is skipped, not failed (this checkout runs everything, so ask as the Windows app)
        assert found[("command", "droid")].level in ("ok", "fail", "skip")
        compat._runs_here = lambda exports: "windows" in exports
        again = by_name(compat.scan_commands(commands, programs))
        assert again[("command", "droid")].level == "skip" and "is for" in again[("command", "droid")].notes[0], again[("command", "droid")].notes
        compat._runs_here = real_runs_here

        # apps
        root = os.path.join(tmp, "files")

        def app(name, meta, scripts=None, libs=None):
            folder = os.path.join(root, "installed_utilities", name)
            write(os.path.join(folder, "data.json"), json.dumps(meta))
            for script, text in (scripts or {}).items():
                write(os.path.join(folder, script), text)
            if libs is not None:
                write(os.path.join(folder, ".libs", ".specs"), json.dumps(libs))
            return folder

        base = {"name": "x", "version": "1.0", "scripts": {"run": "run.py"}, "permissions": ["files"]}
        app("fine", dict(base), {"run.py": "import json\n"})
        app("nolib", dict(base, api=2, pip=["pretty-lib"]), {"run.py": "import json\n"})
        app("withlib", dict(base, api=2, pip=["pretty-lib"]), {"run.py": "import pretty_lib_zzz\n"}, libs=["pretty-lib"])
        os.makedirs(os.path.join(root, "installed_utilities", "withlib", ".libs", "pretty_lib_zzz"))
        write(os.path.join(root, "installed_utilities", "withlib", ".libs", "pretty_lib_zzz", "__init__.py"), "")
        app("noscript", dict(base), {})
        app("missingmod", dict(base), {"run.py": "import no_such_module_zzz\n"})
        app("toonew", dict(base, api=99), {"run.py": "pass\n"})
        app("badperm", dict(base, permissions=["files", "teleport"]), {"run.py": "pass\n"})
        app("needsother", dict(base, requires=["notinstalledapp"]), {"run.py": "pass\n"})
        app("othersexport", dict(base, scripts={"run": "run.py", "run_android": "android.py"}), {"run.py": "pass\n", "android.py": "import no_such_module_zzz\n"})
        write(os.path.join(root, "installed_games", "damaged", "data.json"), "{not json")
        results = compat.scan_apps(root)
        apps = {r.name: r for r in results}
        assert apps["fine"].level == "ok"
        assert apps["nolib"].level == "fail" and "libraries are not installed" in apps["nolib"].notes[0]
        assert apps["withlib"].level == "ok", apps["withlib"].notes
        assert apps["noscript"].level == "fail" and apps["noscript"].notes
        assert apps["missingmod"].level == "fail" and "no_such_module_zzz" in apps["missingmod"].notes[0]
        assert apps["toonew"].level == "fail" and "newer PythonOS" in apps["toonew"].notes[0]
        assert apps["badperm"].level == "warn" and "teleport" in apps["badperm"].notes[0]
        assert apps["needsother"].level == "warn" and "notinstalledapp" in apps["needsother"].notes[0]
        assert apps["othersexport"].level == "ok", "the start script of another export is not tested here"
        assert apps["damaged"].level == "fail" and "damaged" in apps["damaged"].notes[0]
        assert compat.scan_apps(os.path.join(tmp, "nowhere")) == []

        # the totals and the text that is sent: system, counts, then every problem with its reason
        everything = results + compat.scan_commands(commands, programs)
        counts = compat.summary(everything)
        assert counts["app"]["fail"] >= 5 and counts["command"]["ok"] >= 2
        text = compat.report(everything, version="9.9.9", package="Android app (APK) 9.9.9")
        for want in ("## Compatibility test", "- PythonOS: 9.9.9", "- Package: Android app (APK) 9.9.9", "## Totals", "## Will not work here",
                     "## Warnings", "command needs: needs no_such_module_zzz", "app toonew: it needs a newer PythonOS"):
            assert want in text, (want, text)

        # the developer tool: shows the result, asks before sending, sends nothing on "no", sends the redacted text on "yes", and says so
        # when sending is not set up
        sys.path.insert(0, REPO_ROOT)
        from programs import developer
        from pyos import reportsend
        developer.console.quiet = True
        sent, asked = [], []
        reportsend.send_discord = lambda title, body: sent.append((title, body))
        compat.run = lambda progress=None: everything
        reportsend.can_discord = lambda: False
        developer.tool_compat()
        assert sent == [], "no Discord set up: nothing to send"
        reportsend.can_discord = lambda: True
        developer.Confirm.ask = lambda q, **k: (asked.append(q), False)[1]
        developer.tool_compat()
        assert sent == [] and asked, "the person is asked first"
        answers = iter([True, False])
        developer.Confirm.ask = lambda q, **k: next(answers)
        developer.tool_compat()
        assert sent == [], "a second 'no' after the preview sends nothing"
        developer.Confirm.ask = lambda q, **k: True
        developer.tool_compat()
        assert len(sent) == 1 and sent[0][0].startswith("Compatibility test:") and "## Totals" in sent[0][1]
        assert "TOOLS" and "compat" in developer.TOOLS and "compat" in developer.MENU
    finally:
        compat._runs_here = real_runs_here
        shutil.rmtree(tmp, ignore_errors=True)
    print("compatibility test: all checks passed")


if __name__ == "__main__":
    main()
