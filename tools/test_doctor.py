#!/usr/bin/env python3
"""Checks the doctor: every check runs, the score and report work, a broken command file and a bad alias are found, fixes are re-verified,
and the network check degrades to a warning when there is no network (the network is faked, never used)."""
import os
import sys
import tempfile
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO)
os.chdir(REPO)

from core import doctor  # noqa: E402


def main():
    # every check runs and returns Findings with a known level; the check name is filled in
    timings = {}
    findings = doctor.run_all(timings=timings)
    assert findings and all(f.level in ("ok", "warn", "error") for f in findings)
    assert all(f.check for f in findings), "run_all must say which check each finding came from"
    assert set(timings) == {c.__name__[6:] for c in doctor.CHECKS}
    assert "network" not in timings, "the network check must only run with online=True"

    only = doctor.run_all(only={"commands"})
    assert only and {f.check for f in only} == {"commands"}

    # score: 100 when clean, 20 per problem, 5 per warning, never below 0
    F = doctor.Finding
    assert doctor.score([F("ok", "a", "b")]) == 100
    assert doctor.score([F("error", "a", "b"), F("warn", "a", "b")]) == 75
    assert doctor.score([F("error", "a", "b")] * 9) == 0

    # a command file with no execute() is reported, and so is a duplicated name, in a scratch copy of the folder
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "commands"))
        with open(os.path.join(tmp, "commands", "good.py"), "w", encoding="utf-8") as f:
            f.write('config = {"name": "good", "description": "x"}\ndef execute(args=None):\n    return True\n')
        with open(os.path.join(tmp, "commands", "dupe.py"), "w", encoding="utf-8") as f:
            f.write('config = {"name": "good", "description": "x"}\ndef execute(args=None):\n    return True\n')
        with open(os.path.join(tmp, "commands", "broken.py"), "w", encoding="utf-8") as f:
            f.write('config = {"name": "broken"}\n')
        here = os.getcwd()
        os.chdir(tmp)
        try:
            found = doctor.check_commands()
            levels = {f.level for f in found}
            assert "error" in levels and any("broken.py" in f.message for f in found), found
            assert any("twice" in f.message for f in found), found
        finally:
            os.chdir(here)

        # old crash reports are found and the fix removes them
        logs = os.path.join(tmp, "logs")
        os.makedirs(logs)
        old = os.path.join(logs, "crash-old.txt")
        with open(old, "w", encoding="utf-8") as f:
            f.write("x")
        past = time.time() - 40 * 86400
        os.utime(old, (past, past))
        real = doctor.pyos.log.LOG_FILE
        doctor.pyos.log.LOG_FILE = os.path.join(logs, "pyos.log")
        try:
            fixable = [f for f in doctor.check_storage() if f.fix]
            assert fixable and os.path.exists(old)
            fixable[0].fix()
            assert not os.path.exists(old)
        finally:
            doctor.pyos.log.LOG_FILE = real

    # the network check: no DNS -> a warning with something to do, not a crash; with a fake newer release -> an update warning
    real_lookup, real_release = doctor.socket.getaddrinfo, doctor._latest_release
    try:
        def no_dns(*_a, **_k):
            raise OSError("no network")
        doctor.socket.getaddrinfo = no_dns
        out = doctor.check_network()
        assert out[0].level == "warn" and out[0].hint, out

        doctor.socket.getaddrinfo = lambda *a, **k: [()]
        doctor._latest_release = lambda: {"tag_name": "v99.0.0"}
        out = doctor.check_network()
        assert any(f.area == "Updates" and f.level == "warn" and "99.0.0" in f.message for f in out), out
    finally:
        doctor.socket.getaddrinfo, doctor._latest_release = real_lookup, real_release

    # the report remembers what was wrong, and only what was wrong
    saved = doctor.REPORT
    with tempfile.TemporaryDirectory() as tmp:
        doctor.REPORT = os.path.join(tmp, "doctor.json")
        try:
            doctor.save_report([F("ok", "a", "fine"), F("warn", "b", "careful")])
            report = doctor.last_report()
            assert report["findings"] == [["warn", "b", "careful"]] and report["score"] == 95
        finally:
            doctor.REPORT = saved

    # a check that raises is reported as a warning and does not stop the others
    def boom():
        raise RuntimeError("bad")
    boom.__name__ = "check_boom"
    doctor.CHECKS.append(boom)
    try:
        results = doctor.run_all()
        assert any(f.area == "Boom" and f.level == "warn" for f in results)
        assert any(f.check == "commands" for f in results)
    finally:
        doctor.CHECKS.remove(boom)
    # missing optional libraries: a plain note for each export, and never a pip command (PythonOS is a closed system; most exports cannot run pip)
    from pyos import export
    real_current = export.current
    with tempfile.TemporaryDirectory() as tmp:
        here = os.getcwd()
        os.chdir(tmp)
        try:
            with open("requirements-extra.txt", "w", encoding="utf-8") as f:
                f.write("no-such-library-zzz  # not installed\n")
            for platform_name in (None, "windows", "linux", "android", "iso"):
                export.current = lambda name=platform_name: name
                found = doctor.check_libraries()
                assert found and found[0].level == "warn" and "no-such-library-zzz" in found[0].message, found
                hint = found[0].hint
                assert hint and "pip" not in hint.lower() and "requirements-extra" not in hint, (platform_name, hint)
        finally:
            export.current = real_current
            os.chdir(here)
    print("doctor: all checks passed")


if __name__ == "__main__":
    main()
