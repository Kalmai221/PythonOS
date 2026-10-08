#!/usr/bin/env python3
"""pyos/corecmd.py: an app asking for PythonOS's own commands. Only the listed commands run, an app without the permission a command uses is refused,
what a command prints comes back as text, a failing command is a result and not a crash, and the permission guard exports what it has granted."""
import io
import os
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO)
os.chdir(REPO)
os.environ["PYOS_BUNDLED"] = "1"

from pyos import corecmd  # noqa: E402


def main():
    # the list: every name has a command file, nothing dangerous is in it, and every permission is a real one
    from pyos import sandbox
    here = os.path.join(REPO, "commands")
    for name, permission in corecmd.ALLOWED.items():
        assert os.path.isfile(os.path.join(here, name + ".py")), f"{name} is listed but there is no such command"
        assert permission == "" or permission in sandbox.PERMISSIONS, (name, permission)
    for dangerous in ("sudo", "su", "passwd", "manageusers", "shutdown", "restart", "wipe", "installos", "pkg", "gh", "report", "kill", "edit", "fm", "service",
                      "persist", "hwsetup", "updatecheck", "rollback", "export", "source", "alias", "xargs", "watch", "time", "lock", "logout", "env", "settings"):
        assert dangerous not in corecmd.ALLOWED, f"{dangerous} must not be available to apps"
        assert corecmd.run(dangerous, []).code == "refused"

    # not under the guard: nothing is held back
    os.environ.pop("PYOS_APP_PERMS", None)
    assert corecmd.granted() is None and corecmd.check("curl") == (True, "")
    result = corecmd.run("echo", ["hello", "apps"])
    assert result.ok and result.output.strip() == "hello apps" and bool(result) and result.code == "ok"
    assert corecmd.text("echo", ["x"]).strip() == "x"
    # text in, text out (the stdin argument is the pipe)
    assert corecmd.run("sort", [], stdin="b\na\nc\n").output.split() == ["a", "b", "c"]
    assert corecmd.run("sort", ["-r"], stdin="b\na\nc\n").output.split() == ["c", "b", "a"]
    assert corecmd.run("sha256sum", [], stdin="abc").output.startswith("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    assert corecmd.run("calc", ["2", "+", "3", "*", "4"]).output.strip() == "14"
    assert corecmd.run("calc", []).ok is False, "a command that would ask the keyboard reads nothing and says so (it does not wait)"
    # the input does not leak into the next command
    corecmd.run("sort", [], stdin="x\n")
    leaked = corecmd.run("sort", [])
    assert leaked.output.strip() == "", "no input given: nothing from the earlier call is left over"
    # a command that fails is a result
    failed = corecmd.run("calc", ["1/0"])
    assert failed.ok is False and failed.code == "failed" and "dividing by zero" in failed.output
    try:
        corecmd.text("calc", ["1/0"])
        raise AssertionError("text() raises for a failed command")
    except RuntimeError as e:
        assert "dividing by zero" in str(e)
    assert corecmd.run("nosuchcommand", []).code == "refused" and corecmd.run("echo", [7, 8]).output.strip() == "7 8", "arguments become text"

    # files: a command on a file in the scratch folder (the PythonOS file rules are replaced by the plain path)
    import pyos.fs as fs
    scratch = tempfile.mkdtemp(prefix="pyos-corecmd-")
    real_resolve = fs.resolve
    fs.resolve = lambda path, write=False: os.path.abspath(os.path.join(scratch, path)) if not os.path.isabs(path) else path
    try:
        with open(os.path.join(scratch, "list.txt"), "w", encoding="utf-8", newline="\n") as f:
            f.write("one\ntwo\nthree\n")
        assert corecmd.run("wc", ["list.txt"]).output.split()[0] == "3"
        assert corecmd.run("head", ["-n", "1", "list.txt"]).output.strip() == "one"
        assert corecmd.run("gzip", ["-k", "list.txt"]).ok and os.path.exists(os.path.join(scratch, "list.txt.gz"))
        assert "one" in corecmd.run("zcat", ["list.txt.gz"]).output
    finally:
        fs.resolve = real_resolve

    # under the guard: the permissions it granted decide what can be asked for
    os.environ["PYOS_APP_PERMS"] = "files"
    try:
        assert corecmd.granted() == {"files"}
        assert corecmd.check("cat") == (True, "") and corecmd.check("echo") == (True, "")
        ok, why = corecmd.check("curl")
        assert not ok and "network" in why
        refused = corecmd.run("curl", ["example.com"])
        assert refused.ok is False and refused.code == "refused" and "network" in refused.output
        assert corecmd.run("df", []).code == "refused" and corecmd.run("schedule", []).code == "refused"
        os.environ["PYOS_APP_PERMS"] = ""
        assert corecmd.granted() == set() and corecmd.run("cat", ["x"]).code == "refused" and corecmd.run("echo", ["still fine"]).ok
        os.environ["PYOS_APP_PERMS"] = "network,files,system,schedule"
        assert all(corecmd.check(n)[0] for n in corecmd.names())
    finally:
        os.environ.pop("PYOS_APP_PERMS", None)
    assert corecmd.needs("curl") == "network" and corecmd.needs("echo") == "" and corecmd.needs("sudo") is None and "gzip" in corecmd.names()

    # the guard process exports its permissions (and puts back what it found)
    import subprocess
    script = os.path.join(tempfile.mkdtemp(prefix="pyos-corecmd-app-"), "app.py")
    with open(script, "w", encoding="utf-8") as f:
        f.write("import os, sys\nsys.path.insert(0, os.getcwd())\nfrom pyos import corecmd\nprint('PERMS', sorted(corecmd.granted() or []))\n"
                "print('NET', corecmd.run('curl', ['x']).code)\nprint('ECHO', corecmd.run('echo', ['hi']).output.strip())\n")
    env = dict(os.environ, PYTHONPATH=REPO, PYOS_BUNDLED="1")
    done = subprocess.run([sys.executable, os.path.join(REPO, "pyos", "sandbox_run.py"), "--perms", "files", "--dir", os.path.dirname(script), "--id", "t/app", "--", script],
                          capture_output=True, text=True, env=env, cwd=REPO, timeout=60)
    assert done.returncode == 0, done.stderr
    assert "PERMS ['files']" in done.stdout and "NET refused" in done.stdout and "ECHO hi" in done.stdout, done.stdout + done.stderr
    # the audit tool that points at apps which could use a command
    sys.path.insert(0, os.path.join(REPO, "tools"))
    import audit_apps_core
    table = audit_apps_core.by_command(audit_apps_core.audit())
    assert {"curl", "wget", "sha256sum", "find"} <= set(table) and any(name == "hn" for name, _job, _gain in table["curl"]), sorted(table)
    assert all(command in corecmd.ALLOWED for command in table), "every command the audit suggests is one an app may ask for: " + str(sorted(set(table) - set(corecmd.ALLOWED)))
    print("apps using core commands: all checks passed")


if __name__ == "__main__":
    main()
