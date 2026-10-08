#!/usr/bin/env python3
"""Choosing the optional libraries: pyos/extras.py (the list, the choice, installing with pip or Alpine's apk), the `extras` command and the question of
the first-time setup, the update step, the lists the Windows installers are built from, and what start.py reads. Nothing is installed: the program
runner is replaced by a recorder and the libraries' presence by a table."""
import importlib.util
import io
import json
import os
import sys
import tempfile
import types

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO)

LIST = """# comment line
python-dateutil     # date -d "next friday"
humanize            # "3 minutes ago"
py7zr; python_version < "3.14"       # zip, unzip: .7z archives
watchfiles; python_version >= "3.99" # never applies
distro              # the distribution's name
py-cpuinfo          # the processor's model
"""


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(REPO, path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Recorder:
    """Stands in for core.hardware.run: remembers every command, answers 0 (or a failure for names in `fail`)."""
    def __init__(self):
        self.commands, self.fail, self.available = [], set(), None

    def __call__(self, command, timeout=15, text_input=None, env=None, merge=False):
        self.commands.append(list(command))
        if command[:2] == ["apk", "search"]:
            found = self.available is None or command[3] in self.available
            return (0, command[3] + "-1.0\n") if found else (0, "")
        return (1, "failed") if any(name in " ".join(command) for name in self.fail) else (0, "ok")


def main():
    os.chdir(tempfile.mkdtemp(prefix="pyos-extras-"))
    os.environ["PYOS_BUNDLED"] = "1"
    os.environ.pop("PYOS_LIVE", None)
    os.environ.pop("PYOS_INSTALLED", None)
    with open("requirements-extra.txt", "w", encoding="utf-8") as f:
        f.write(LIST)
    from pyos import extras, export, lockdown
    from core import hardware
    original_applies = extras.Extra.applies
    extras.Extra.applies = lambda self, version=None: original_applies(self, version or (3, 12))      # the same answers on every Python

    # ---- the list
    items = extras.catalog()
    assert [e.name for e in items] == ["python-dateutil", "humanize", "py7zr", "distro", "py-cpuinfo"], "a marker for another Python leaves a library out"
    assert items[0].description == 'date -d "next friday"' and items[2].marker == 'python_version < "3.14"'
    assert items[4].module == "cpuinfo" and items[0].module == "dateutil"
    assert extras.Extra("x", "x", 'python_version < "3.14"', "").applies((3, 12)) and not extras.Extra("x", "x", 'python_version < "3.14"', "").applies((3, 14))
    assert extras.Extra("x", "x", 'python_version >= "3.9"', "").applies((3, 9)) and extras.Extra("x", "x", "sys_platform == 'win32'", "").applies((3, 12))

    # ---- the choice file
    assert extras.load_choice() is None
    assert extras.backend() == "pip" and extras.wanted() == [e.name for e in items], "no choice: the exports that install libraries have all of them"
    extras.save_choice("custom", ["humanize", "distro"])
    assert extras.load_choice() == {"mode": "custom", "selected": ["distro", "humanize"]} and extras.wanted() == ["humanize", "distro"]
    extras.save_choice("none")
    assert extras.wanted() == [] and json.load(open(os.path.join(".OSData", "extras.json")))["mode"] == "none"
    extras.save_choice("all", ["ignored"])
    assert extras.wanted() == [e.name for e in items] and extras.load_choice()["selected"] == []
    try:
        extras.save_choice("some")
        raise AssertionError("an unknown mode is refused")
    except ValueError:
        pass
    with open(os.path.join(".OSData", "extras.json"), "w") as f:
        f.write("{broken")
    assert extras.load_choice() is None, "a damaged file is no choice"

    # ---- which are installed decides whether to ask, and what an update offers
    present = {"dateutil": True}
    real_find = importlib.util.find_spec
    importlib.util.find_spec = lambda name: object() if present.get(name) else None
    try:
        os.remove(os.path.join(".OSData", "extras.json"))
        assert extras.undecided() is True
        present.update({"humanize": True, "py7zr": True, "distro": True, "cpuinfo": True})
        assert extras.undecided() is False, "everything is there: nothing to ask"
        present.update({"humanize": False, "distro": False})
        extras.save_choice("custom", ["dateutil"] if False else ["python-dateutil"])
        assert extras.undecided() is False and [e.name for e in extras.new_since_choice()] == ["humanize", "distro"]
        extras.save_choice("custom", ["python-dateutil"], declined=["distro"])
        assert [e.name for e in extras.new_since_choice()] == ["humanize"], "a library the person turned down is not offered again"
        extras.save_choice("all")
        assert extras.new_since_choice() == [], "choosing all takes the new ones without asking"

        # ---- installing with pip
        recorder = Recorder()
        real_run = hardware.run
        hardware.run = recorder
        try:
            done, why = extras.install(["humanize", "distro", "nosuch"], lambda text: None)
            assert why == "" and done == {"humanize": True, "distro": True}
            pip = [c for c in recorder.commands if "pip" in c]
            assert len(pip) == 2 and pip[0][-1] == "humanize" and "--no-input" in pip[0] and sys.executable == pip[0][0]
            recorder.fail.add("distro")
            assert extras.install(["distro"], lambda text: None)[0] == {"distro": False}, "one failing library is reported, not raised"
            recorder.fail.clear()
            assert extras.install(["python-dateutil"], lambda text: None)[0] == {"python-dateutil": True}
            assert not any("dateutil" in " ".join(c) for c in recorder.commands[-1:]), "an installed library is not installed again"
            recorder.commands.clear()
            done, _ = extras.sync(lambda text: None)
            assert sorted(done) == ["distro", "humanize"], "sync installs what the choice wants and is missing"
            extras.save_choice("none")
            recorder.commands.clear()
            assert extras.sync(lambda text: None) == ({}, "") and recorder.commands == []
            done, _ = extras.remove(["humanize"], lambda text: None)
            assert done == {"humanize": True} and recorder.commands[-1][-3:] == ["uninstall", "-y", "humanize"]

            # lockdown: nothing is started
            lockdown_before = lockdown.enabled
            lockdown.enabled = lambda: True
            try:
                recorder.commands.clear()
                assert extras.install(["distro"])[1] and extras.remove(["distro"])[1] and recorder.commands == []
            finally:
                lockdown.enabled = lockdown_before

            # ---- the live ISO and virtual machines: apk, only what Alpine has, and only when the network answers
            os.environ["PYOS_LIVE"] = "1"
            try:
                assert extras.backend() == "apk" and extras.wanted() == [], "no choice on the ISO: only what is on the disc"
                os.remove(os.path.join(".OSData", "extras.json"))
                assert extras.wanted() == [] and extras.undecided() is True
                recorder.commands.clear()
                recorder.available = {"py3-distro"}
                extras.save_choice("all")
                done, why = extras.install(["distro", "humanize"], lambda text: None)
                assert done == {"distro": True, "humanize": False}, done
                assert ["apk", "add", "--quiet", "py3-distro"] in recorder.commands and not any("py3-humanize" in c for c in recorder.commands if c[:2] == ["apk", "add"])
                recorder.fail.add("update")
                assert extras.install(["distro"], lambda text: None)[1].startswith("the package repositories"), "no network: a sentence, not a crash"
                recorder.fail.clear()
            finally:
                os.environ.pop("PYOS_LIVE", None)
            # the Android app carries its libraries inside
            real_current = export.current
            export.current = lambda: "android"
            try:
                assert extras.backend() is None and extras.install(["distro"])[1] and extras.undecided() is False
            finally:
                export.current = real_current
        finally:
            hardware.run = real_run
    finally:
        importlib.util.find_spec = real_find

    # ---- the command and the first-time question
    command = load(os.path.join("commands", "extras.py"), "cmd_extras")
    from rich.console import Console
    out = io.StringIO()
    command.console = Console(file=out, force_terminal=False, width=150)
    present.clear()
    present.update({"dateutil": True})
    importlib.util.find_spec = lambda name: object() if present.get(name) else None
    hardware.run = Recorder()
    try:
        os.remove(os.path.join(".OSData", "extras.json"))
        assert command.execute([]) and "python-dateutil" in out.getvalue() and "not chosen yet" in out.getvalue()
        assert command.execute(["install", "distro"])
        assert "distro" in extras.load_choice()["selected"] or extras.load_choice()["mode"] == "all"
        assert command.execute(["install", "nosuch"]) is False and "Unknown" in out.getvalue()
        assert command.execute(["remove", "distro"]) and "distro" not in extras.load_choice()["selected"]
        assert command.execute(["none"]) and extras.load_choice()["mode"] == "none"
        assert command.execute(["install", "all"]) and extras.load_choice()["mode"] == "all"
        assert command.execute(["bogus"]) is False
        # the interactive chooser
        answers = []
        command.Prompt = types.SimpleNamespace(ask=lambda *a, **k: answers.pop(0))
        command.Confirm = types.SimpleNamespace(ask=lambda *a, **k: False)
        answers[:] = ["1 3"]
        assert command.choose(extras.catalog())
        assert extras.load_choice() == {"mode": "custom", "selected": ["py7zr", "python-dateutil"]}, extras.load_choice()
        answers[:] = ["9"]
        assert command.choose(extras.catalog()) is False, "numbers that are not in the list are refused"
        answers[:] = [""]
        before = extras.load_choice()
        assert command.choose(extras.catalog()) and extras.load_choice() == before, "Enter keeps the choice"
        answers[:] = ["n"]
        command.choose(extras.catalog())
        assert extras.load_choice()["mode"] == "none"
        # first-time setup: asked once; an answer is remembered; nothing to ask when an installer chose or everything is there
        os.remove(os.path.join(".OSData", "extras.json"))
        answers[:] = ["n"]
        command.first_time()
        assert extras.load_choice()["mode"] == "none" and answers == []
        command.first_time()                                        # (no prompt left to answer: it must not ask again)
        os.remove(os.path.join(".OSData", "extras.json"))
        answers[:] = ["a"]
        command.first_time()
        assert extras.load_choice()["mode"] == "all"
        os.remove(os.path.join(".OSData", "extras.json"))
        answers[:] = ["c", "2"]
        command.first_time()
        assert extras.load_choice()["mode"] == "custom"
        # lockdown blocks changes but not the listing
        lockdown_before = lockdown.enabled
        lockdown.enabled = lambda: True
        try:
            assert command.execute(["install", "distro"]) is False and command.execute([])
        finally:
            lockdown.enabled = lockdown_before
    finally:
        importlib.util.find_spec = real_find
        hardware.run = real_run

    # ---- the update step
    sysupdate = load(os.path.join("core", "sysupdate.py"), "core_sysupdate_extras")
    seen = io.StringIO()
    sysupdate.console = Console(file=seen, force_terminal=False, width=150)
    extras.save_choice("custom", ["python-dateutil"])
    importlib.util.find_spec = lambda name: object() if name == "dateutil" else None
    hardware.run = Recorder()
    try:
        sysupdate.sync_extras()
        assert "New optional libraries since you chose" in seen.getvalue() and "humanize" in seen.getvalue()
        assert not any("humanize" in " ".join(c) for c in hardware.run.commands), "a hand-picked list never installs a new library on its own"
        extras.save_choice("all")
        sysupdate.sync_extras()
        assert any("humanize" in " ".join(c) for c in hardware.run.commands), "all: the update installs what is new"
    finally:
        importlib.util.find_spec = real_find
        hardware.run = real_run

    # ---- the Windows installers' lists and what start.py reads
    generator = load(os.path.join("OS_Export", "Windows", "make_extras_list.py"), "make_extras_list")
    entries = generator.items(LIST)
    assert [n for n, _d in entries] == ["python-dateutil", "humanize", "py7zr", "distro", "py-cpuinfo"], entries
    assert generator.items(LIST, (3, 14))[2][0] == "distro", "the marker is checked against the Python in the package"
    assert generator.as_text(entries).splitlines()[0] == 'python-dateutil|date -d "next friday"'
    cs = generator.as_csharp([("a", 'say "hi"'), ("b", "back\\slash")])
    assert 'new string[] { "a", "say \\"hi\\"" }' in cs and '"back\\\\slash"' in cs and "class ExtrasList" in cs
    with open(os.path.join(REPO, "requirements-extra.txt"), encoding="utf-8") as f:
        real = generator.items(f.read())
    assert len(real) >= 8 and all(d for _n, d in real), "every real library says what it adds"
    start = load(os.path.join("OS_Export", "Windows", "start.py"), "win_start_extras")
    start.HERE = os.getcwd()
    for mode, selected, expected in (("all", [], None), ("none", [], set()), ("custom", ["Distro", "humanize"], {"distro", "humanize"})):
        with open(os.path.join(".OSData", "extras.json"), "w") as f:
            json.dump({"mode": mode, "selected": selected}, f)
        assert start.chosen_extras() == expected, (mode, start.chosen_extras())
    os.remove(os.path.join(".OSData", "extras.json"))
    assert start.chosen_extras() is None
    iss = open(os.path.join(REPO, "OS_Export", "Windows", "PythonOS.iss"), encoding="utf-8").read()
    assert "ChosenExtras" in iss and "extras.json" in iss and "{param:extras|}" in iss and "MakeExtrasPage" in iss
    ui = open(os.path.join(REPO, "OS_Export", "Windows", "native", "setup", "Ui.cs"), encoding="utf-8").read()
    assert "ShowExtras" in ui and "ExtrasList.Items" in ui
    print("optional libraries (choosing them): all checks passed")


if __name__ == "__main__":
    main()
