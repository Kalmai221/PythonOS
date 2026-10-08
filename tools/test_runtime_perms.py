#!/usr/bin/env python3
"""Runtime app permissions: an app that asked for something it was not given is asked about on first use (allow this time, always, not now,
never); "always" and "never" are remembered by the shell after the app ends; an app can only change what it was allowed to be asked about; and
nothing is ever asked where nobody can answer (output captured, locked down). The guard runs in this process with a fake keyboard."""
import json
import os
import shutil
import socket
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO_ROOT)


class Keyboard:
    """Answers the guard's questions in order, and remembers what was asked."""

    def __init__(self, *answers):
        self.answers, self.asked = list(answers), []

    def __call__(self, prompt=""):
        self.asked.append(prompt)
        if not self.answers:
            raise EOFError
        return self.answers.pop(0)


def raises(call):
    try:
        call()
    except PermissionError as e:
        return str(e)
    return None


def main():
    tmp = tempfile.mkdtemp()
    here = os.getcwd()
    os.chdir(tmp)
    os.makedirs(os.path.join("files", "tmp"))
    os.makedirs(os.path.join("files", "home", "sam"))
    os.makedirs(".OSData")
    with open("current_user.json", "w", encoding="utf-8") as f:
        json.dump({"username": "sam"}, f)
    try:
        from pyos import sandbox, sandbox_run
        decisions = os.path.join(tmp, "files", "tmp", ".perm.json")

        def guard(perms=(), ask=(), interactive=True, keys=()):
            g = sandbox_run.Guard(list(perms), os.path.join(tmp, "app"), "utilities/notes", list(ask), decisions, interactive)
            g._input = Keyboard(*keys)
            return g

        def recorded():
            try:
                return [json.loads(line) for line in open(decisions, encoding="utf-8").read().splitlines()]
            except OSError:
                return []

        # allow this time: it works now, is not asked again in this run, and nothing is remembered
        g = guard(ask=["network"], keys=["a"])
        assert g.need("network", "connect to the internet") is True and "network" in g.perms
        assert g.need("network", "connect to the internet") is True and len(g._input.asked) == 1
        assert recorded() == []

        # always allow: remembered
        g = guard(ask=["network"], keys=["A"])
        assert g.need("network", "x") is True
        assert recorded() == [{"perm": "network", "decision": "always"}]

        # not now: refused, and not asked a second time in the same run; never: refused and remembered
        os.remove(decisions)
        g = guard(ask=["network", "exec"], keys=["n", "N"])
        assert "not allowed" in (raises(lambda: g.need("network", "use the network")) or "")
        assert raises(lambda: g.need("network", "use the network")) and len(g._input.asked) == 1, "asked once per run"
        assert recorded() == []
        assert raises(lambda: g.need("exec", "start other programs")) and recorded() == [{"perm": "exec", "decision": "never"}]

        # the words people type
        for typed, expect in (("allow", True), ("yes", True), ("y", True), ("always", True), ("", False), ("whatever", False), ("never", False)):
            g = guard(ask=["network"], keys=[typed])
            assert (raises(lambda: g.need("network", "x")) is None) == expect, typed
        os.remove(decisions)

        # a permission the app never asked for is refused without a question; so is everything when nobody can answer
        g = guard(ask=["network"], keys=["A"])
        assert raises(lambda: g.need("exec", "start other programs")) and g._input.asked == []
        g = guard(ask=["network"], interactive=False, keys=["A"])
        assert raises(lambda: g.need("network", "x")) and g._input.asked == [], "output is captured or nobody is there: refused, not asked"
        g = guard(ask=["network"], keys=[])
        assert raises(lambda: g.need("network", "x")), "the keyboard closed: refused"
        assert guard(perms=["network"], keys=[]).need("network", "x") is True, "already allowed: no question"
        assert not os.path.exists(decisions)

        # the guard asks at the moment of use: files inside PythonOS's filesystem, and the network gate (the real function runs once allowed)
        target = os.path.join("files", "home", "sam", "note.txt")
        g = guard(ask=["files"], keys=["n"])
        message = raises(lambda: g.check_path(target, True))
        assert message and "files" in message and len(g._input.asked) == 1
        g = guard(ask=["files"], keys=["a"])
        g.check_path(target, True)
        g.check_path(target, False)
        assert len(g._input.asked) == 1 and "files" in g.perms
        g = guard(ask=[], keys=["a"])
        assert raises(lambda: g.check_path(target, False)) and g._input.asked == [], "files not asked for: refused as before"
        g = guard(ask=["system"], keys=["a"])
        if os.path.exists("/proc"):
            g.check_path("/proc/cpuinfo", False)
            assert "system" in g.perms
        g = guard(ask=["notifications"], keys=["a"])
        g.check_path(os.path.join(".OSData", "notifications.json"), True)
        assert "notifications" in g.perms

        g = guard(ask=["network"], keys=["n"])
        g.install()
        try:
            assert raises(lambda: socket.create_connection(("127.0.0.1", 9), timeout=1)), "refused before anything is connected"
        finally:
            g.uninstall()
        g = guard(ask=["network"], keys=["a"])
        g.install()
        try:
            try:
                socket.create_connection(("127.0.0.1", 9), timeout=1)
                raise AssertionError("nothing listens on port 9")
            except PermissionError:
                raise AssertionError("allowed: the real connection must be tried")
            except OSError:
                pass                                                                    # connection refused: the real function ran
        finally:
            g.uninstall()
        g = guard(ask=["exec"], keys=["n"])
        g.install()
        try:
            import subprocess
            assert raises(lambda: subprocess.Popen([sys.executable, "-c", "pass"])), "starting a program is refused"
        finally:
            g.uninstall()

        # what the shell remembers afterwards: only what the app was allowed to be asked about; never the other way round
        meta = {"permissions": ["network", "exec", "files"]}
        folder = os.path.join("files", "installed_utilities", "notes")
        os.makedirs(folder)
        sandbox.set_granted("utilities/notes", ["files"])
        assert sandbox.askable(folder, meta) == ["network", "exec"]
        env = {"PYOS_PERM_DECISIONS": decisions, "PYOS_PERM_PACKAGE": "utilities/notes", "PYOS_PERM_ASK": "network,exec"}
        with open(decisions, "w", encoding="utf-8") as f:
            f.write(json.dumps({"perm": "network", "decision": "always"}) + "\n" + json.dumps({"perm": "exec", "decision": "never"}) + "\n"
                    + json.dumps({"perm": "files", "decision": "never"}) + "\n" + json.dumps({"perm": "teleport", "decision": "always"}) + "\nnot json\n"
                    + json.dumps({"perm": "system", "decision": "always"}) + "\n")
        applied = sandbox.apply_decisions(env)
        assert applied == [("network", "always"), ("exec", "never")], applied
        assert sorted(sandbox.granted("utilities/notes")) == ["files", "network"], "'files' was not asked about: the forged answer is ignored"
        assert sandbox.denied("utilities/notes") == ["exec"] and not os.path.exists(decisions), "the answers file is deleted"
        assert sandbox.askable(folder, meta) == [], "nothing left to ask: network is allowed, exec is refused for good"
        assert sandbox.state("utilities/notes", "network", meta["permissions"], ["files", "network"]) == "allowed"
        assert sandbox.state("utilities/notes", "exec", meta["permissions"], []) == "never"
        assert sandbox.state("utilities/notes", "files", ["files"], []) == "ask" and sandbox.state("utilities/notes", "system", ["files"], []) == ""
        assert sandbox.apply_decisions({}) == [] and sandbox.apply_decisions({"PYOS_PERM_DECISIONS": "/nowhere", "PYOS_PERM_PACKAGE": "x"}) == []
        # a "never" can be undone, and removing the app forgets everything about it
        sandbox.set_denied("utilities/notes", [])
        assert sandbox.denied("utilities/notes") == []
        sandbox.set_denied("utilities/notes", ["exec"])
        sandbox.forget("utilities/notes")
        assert sandbox.denied("utilities/notes") == [] and sandbox.granted("utilities/notes") is None

        # launching: the guard is told what it may ask about and where to write; on a locked-down system it is told nothing, so it never asks
        sandbox.set_granted("utilities/notes", ["files"])
        script = os.path.join(folder, "run.py")
        open(script, "w", encoding="utf-8").write("pass\n")
        cmd, env = sandbox.launch(script, [], folder, meta)
        assert "--ask" in cmd and cmd[cmd.index("--ask") + 1] == "network,exec" and cmd[cmd.index("--decisions") + 1] == env["PYOS_PERM_DECISIONS"]
        assert env["PYOS_PERM_PACKAGE"] == "utilities/notes" and env["PYOS_PERM_ASK"] == "network,exec"
        assert sandbox_run.parse_ask(cmd[2:]) == (["network", "exec"], env["PYOS_PERM_DECISIONS"])
        from pyos import lockdown
        real_enabled = lockdown.enabled
        lockdown.enabled = lambda: True
        try:
            cmd, env = sandbox.launch(script, [], folder, meta)
            assert "--ask" not in cmd and "PYOS_PERM_DECISIONS" not in env, "locked down: nothing is asked"
        finally:
            lockdown.enabled = real_enabled
        cmd, env = sandbox.launch(script, [], folder, {"permissions": ["files"]})
        assert "--ask" not in cmd, "nothing asked for beyond what was given: no questions"

        # pkg permissions: grant, revoke (never), ask (back to asking)
        from programs import marketplace
        marketplace.console.quiet = True
        pkg = {"id": "utilities/notes", "name": "Notes", "permissions": ["network", "exec", "files"]}
        installed = {"utilities/notes": {"version": "1", "name": "Notes", "path": folder, "meta": meta}}
        marketplace.permissions_command(pkg, installed, ["grant", "network"])
        assert "network" in sandbox.granted("utilities/notes") and sandbox.denied("utilities/notes") == []
        marketplace.permissions_command(pkg, installed, ["revoke", "network"])
        assert "network" not in sandbox.granted("utilities/notes") and sandbox.denied("utilities/notes") == ["network"]
        assert sandbox.askable(folder, meta) == ["exec"]
        marketplace.permissions_command(pkg, installed, ["ask", "network"])
        assert sandbox.denied("utilities/notes") == [] and sandbox.askable(folder, meta) == ["network", "exec"]
        assert marketplace.permissions_command(pkg, installed, ["grant", "bogus"]) is False
    finally:
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    print("runtime permissions: all checks passed")


if __name__ == "__main__":
    main()
