#!/usr/bin/env python3
"""The bug-detection service: it finds unexpected bugs in the system log (a crashed command or program, an app that ended with a traceback, a
service or scheduled task that failed), ignores what is not a bug (network, updates, a wrong password), tells each bug once, never too
often, and the shell asks "An unexpected bug has been found, would you like to report it?" before the next prompt."""
import os
import shutil
import sys
import tempfile
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

from pyos import apprun, bugs, log, services  # noqa: E402

QUESTION = "An unexpected bug has been found, would you like to report it?"


def main():
    tmp = tempfile.mkdtemp()
    real_log, real_instance = log.LOG_FILE, services.instance
    log.LOG_FILE = os.path.join(tmp, "system.log")
    try:
        bugs.forget()

        # what is and is not a bug
        assert bugs.classify("ERROR", "command ls crashed: ValueError: bad (at a.py:3 f)")
        assert bugs.classify("ERROR", "service scheduler could not start: RuntimeError: x")
        assert bugs.classify("WARN", "command failed (exit 1, 0.1s): ls /nowhere") is None, "a failing command is not a bug"
        assert bugs.classify("INFO", "login ok") is None and bugs.classify("DEBUG", "command not found: lss") is None
        for text in ("update: could not reach the update server: ConnectionError", "installos stopped: no disk", "report: GitHub failed: x",
                     "app notes could not be installed: timed out", "update: failed (1.0.11 -> 1.0.12), nothing was changed: OSError"):
            assert bugs.classify("ERROR", text) is None, text

        # the same bug is queued once, however many times it happens or what the numbers in it are
        assert bugs.note("ERROR", "command ls crashed: ValueError: bad value 12 (at ls.py:41 run)")
        assert not bugs.note("ERROR", "command ls crashed: ValueError: bad value 99 (at ls.py:77 run)")
        assert bugs.note("ERROR", "command cp crashed: KeyError: 'x' (at cp.py:5 run)")
        assert bugs.waiting() == 2

        # it asks about one at a time, not twice within two minutes, and not more than five times in a session
        t = 1000.0
        first = bugs.take(t)
        assert first["summary"].startswith("command ls crashed") and bugs.waiting() == 1
        assert bugs.take(t + 10) is None, "too soon after the last question"
        second = bugs.take(t + 130)
        assert second["summary"].startswith("command cp crashed") and bugs.take(t + 400) is None
        bugs.forget()
        for i in range(8):
            bugs.note("ERROR", f"program p{chr(97 + i)} crashed: Error")
        asked = [bugs.take(10000.0 + i * 500) for i in range(8)]
        assert sum(1 for a in asked if a) == bugs.MAX_OFFERS == 5

        # the shell's question: exact words, a yes starts the report with the bug described, a no does not
        bugs.forget()
        bugs.note("ERROR", "command ls crashed: ValueError: bad (at ls.py:3 run)")
        printed, questions, reports = [], [], []
        services.instance = lambda name: None
        assert bugs.offer(lambda q: True, reports.append, printed.append) is False and not reports, "the service is switched off: no question"
        services.instance = lambda name: object() if name == "bug-detection" else real_instance(name)
        assert bugs.offer(lambda q: (questions.append(q), True)[1], reports.append, printed.append, now=2000.0) is True
        assert questions == [QUESTION] and printed and "ls crashed" in printed[0]
        assert len(reports) == 1 and reports[0].startswith("Unexpected bug found by bug-detection: command ls crashed")
        bugs.note("ERROR", "command mv crashed: OSError: x (at mv.py:1 run)")
        reports.clear()
        printed.clear()
        assert bugs.offer(lambda q: False, reports.append, printed.append, now=3000.0) is True and not reports
        assert any("report at any time" in p for p in printed), "a no is answered politely and says how to report later"
        assert bugs.offer(lambda q: True, reports.append, printed.append, now=3001.0) is False, "nothing new: no question"

        # the detector reads only what is NEW in the log, and copes with the log being trimmed
        bugs.forget()
        log.log("command old crashed: ValueError: before the service started", "ERROR")
        detector = bugs.Detector("sam")
        assert detector.scan() == 0, "what was already in the log is history"
        log.log("login ok", "INFO", user="sam")
        log.log("command failed (exit 1, 0.2s): cat missing", "WARN", user="sam")
        assert detector.scan() == 0
        log.log("command cat crashed: UnicodeDecodeError: x (at cat.py:9 run)", "ERROR", user="sam")
        log.log("update: could not reach the update server: ConnectionError", "ERROR")
        assert detector.scan() == 1 and bugs.waiting() == 1
        assert detector.scan() == 0, "the same lines are not read twice"
        with open(log.LOG_FILE, "w", encoding="utf-8") as f:                       # trimmed: the file is shorter than before
            f.write("")
        log.log("program tetris crashed: IndexError: y (at t.py:1 run)", "ERROR")
        assert detector.scan() == 1, "after a trim it reads from the start of the new file"

        # the service runs in the background and finds a bug on its own
        bugs.forget()
        bugs.POLL_SECONDS = 0.05
        live = bugs.Detector("sam")
        live.start()
        try:
            log.log("scheduler: a task failed: ZeroDivisionError: division by zero (at s.py:2 run)", "ERROR")
            deadline = time.time() + 3
            while bugs.waiting() == 0 and time.time() < deadline:
                time.sleep(0.05)
            assert bugs.waiting() == 1, "the background thread found it"
        finally:
            live.stop()
            live.join(timeout=2)
        assert not live.is_alive()

        # an app that ends with a traceback is logged as a bug (ERROR); one that merely exits non-zero is not
        bugs.forget()
        log.LOG_FILE = os.path.join(tmp, "apps.log")
        detector = bugs.Detector("sam")
        apprun.outcome("notes", 1, 0.2, "usage: notes add TEXT\n", "sam")
        apprun.outcome("tool", 1, 0.2, "Traceback (most recent call last):\n  File x, line 1\nKeyError: 'a'\n", "sam")
        assert detector.scan() == 1 and "app tool crashed" in bugs.take(5000.0)["summary"]

        # the shell defines the service, and the question is asked before the prompt
        import shell
        shell.define_services()
        assert "bug-detection" in services.names()
        assert "bug-detection" in services.get("bug-detection").name or services.get("bug-detection").description.startswith("Bug Detection")
        source = open(os.path.join(REPO_ROOT, "shell.py"), encoding="utf-8").read()
        assert source.index("offer_bug_report()") < source.index("idle.waiting(True)"), "asked before the prompt is shown"
    finally:
        services.instance = real_instance
        log.LOG_FILE = real_log
        bugs.forget()
        shutil.rmtree(tmp, ignore_errors=True)
    print("bug detection: all checks passed")


if __name__ == "__main__":
    main()
