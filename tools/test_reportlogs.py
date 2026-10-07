#!/usr/bin/env python3
"""What a problem report can learn: secrets never reach the log, a crash says what and where, every command leaves a trail entry and a failure a
log line, an app that fails logs why, the screen log is kept only in memory and only used when the person says yes, and `report` asks."""
import io
import os
import shutil
import sys
import tempfile
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

import pyos  # noqa: E402
from pyos import apprun, log, report, screenlog, settings, trail  # noqa: E402


def main():
    tmp = tempfile.mkdtemp()
    real_log = log.LOG_FILE
    log.LOG_FILE = os.path.join(tmp, "system.log")
    real_get = settings.get
    try:
        # secrets: scrubbed from every log line, and from a report
        cleaned = log.scrub("x ghp_abcdefghijklmnopqrstuvwxyz0123456789 password=hunter2 Bearer abcdefghijklmnop12 "
                            "https://discord.com/api/webhooks/1/abc " + "a" * 40)
        assert "ghp_" not in cleaned and "hunter2" not in cleaned and "webhooks" not in cleaned and "a" * 40 not in cleaned, cleaned
        log.log("ran gh auth login --with-token ghp_abcdefghijklmnopqrstuvwxyz0123456789")
        assert "ghp_" not in open(log.LOG_FILE, encoding="utf-8").read()
        assert "ghp_" not in report.redact("token ghp_abcdefghijklmnopqrstuvwxyz0123456789 and me@example.com")

        # an exception says what and where, in one line
        try:
            int("x")
        except ValueError as e:
            line = log.describe_exception(e)
        assert line.startswith("ValueError: ") and "test_reportlogs.py:" in line and "\n" not in line, line

        # the trail: the last commands, scrubbed, how they ended
        trail.clear()
        trail.record("ls", ["-l", "/tmp"], 0, 0.02, "sam")
        trail.record("login", ["--password=hunter2"], 1, 1.5, "sam")
        shown = "\n".join(trail.lines())
        assert "ls -l /tmp" in shown and "[ok," in shown and "[exit 1," in shown and "hunter2" not in shown, shown
        for i in range(60):
            trail.record("cmd", [str(i)], 0, 0.0)
        assert len(trail.recent(100)) == trail.KEEP

        # the shell: every command is recorded, a failing one is logged with its exit status, an unknown one quietly
        import shell
        shell.console.quiet = True
        shell.available_commands = shell.load_all_modules("commands")
        trail.clear()
        assert shell.run_stage(["definitely-not-a-command"]) == 127
        assert shell.run_stage(["whoami"]) in (0, 1)
        names = [item["line"].split()[0] for item in trail.recent(5)]
        assert names == ["definitely-not-a-command", "whoami"], names
        entries = [(e["level"], e["message"]) for e in log.entries()]
        assert ("DEBUG", "command not found: definitely-not-a-command") in entries, entries
        settings.get = lambda key, *a, **k: False if key == "report_commands" else real_get(key, *a, **k)
        trail.clear()
        shell.run_stage(["whoami"])
        assert trail.recent(5) == [], "report_commands off: nothing is remembered"
        settings.get = real_get

        # an app: how it ended goes to the log, with what it printed to stderr
        apprun.outcome("notes", 0, 1.234, "", "sam")
        apprun.outcome("notes", 1, 0.5, "Traceback (most recent call last):\n  File x\nKeyError: 'a'\n", "sam")
        apprun.outcome("big", -9, 3.0, "", "sam")
        text = open(log.LOG_FILE, encoding="utf-8").read()
        assert "app notes finished in 1.2s" in text and "app notes crashed: exit 1" in text and "KeyError: 'a'" in text
        assert "[WARN]" in text and "killed" in text
        code = apprun.run([sys.executable, "-c", "import sys; sys.stderr.write('boom\\n'); sys.exit(3)"], dict(os.environ), "tiny", "sam", quiet_stderr=True)
        assert code == 3 and "app tiny failed: exit 3" in open(log.LOG_FILE, encoding="utf-8").read()
        assert "boom" in open(log.LOG_FILE, encoding="utf-8").read()

        # the screen log: memory only, ANSI and in-place progress cleaned, capped, and off when the setting is off
        screenlog.clear()
        screenlog._state.update(on=True, checked=time.monotonic())
        screenlog.feed("sam@pyOS:~# ls\n")
        screenlog.feed("\x1b[1;32mhello\x1b[0m world\n")
        screenlog.feed("downloading 10%\rdownloading 50%\rdownloading 100%\ndone token=abc123secret\n")
        shown = screenlog.text()
        assert "sam@pyOS:~# ls" in shown and "hello world" in shown and "\x1b" not in shown
        assert "downloading 100%" in shown and "downloading 10%" not in shown, shown
        assert "abc123secret" not in shown
        for i in range(2000):
            screenlog.feed(f"line {i} " + "x" * 50 + "\n")
        assert screenlog._size <= screenlog.MAX_CHARS + 100 and screenlog.text(5).count("\n") == 4
        assert not any(os.path.exists(p) for p in ("terminal.log", os.path.join(".OSData", "terminal.log"))), "never written to disk"
        screenlog._state.update(on=False, checked=time.monotonic())
        screenlog.feed("must not be kept\n")
        assert not screenlog.available()

        # the report: the screen is included only when asked for, and the recent commands only when that setting is on
        trail.clear()
        trail.record("ls", [], 0, 0.1, "sam")
        screenlog._state.update(on=True, checked=time.monotonic())
        screenlog.clear()
        screenlog.feed("sam@pyOS:~# ls\nfile1\n")
        without = report.build("a problem")
        assert "## Recent commands" in without and "ls" in without and "What was on the screen" not in without
        with_screen = report.build("a problem", include_screen=True)
        assert "## What was on the screen" in with_screen and "file1" in with_screen

        # the command asks "Share your terminal log?" and honours the answer and the flags
        from commands import report as report_command
        report_command.console.quiet = True
        asked, built = [], []
        real_build = report.build
        report.build = lambda text="", include_log=True, include_screen=False: (built.append(include_screen), real_build(text, include_log, include_screen))[1]
        report_command.Confirm.ask = lambda question, **k: (asked.append(question), False)[1]
        report_command.Prompt.ask = lambda *a, **k: "n"
        report_command.execute(["a problem"])
        assert any("terminal log" in q for q in asked) and built == [False], (asked, built)
        asked.clear()
        built.clear()
        report_command.Confirm.ask = lambda question, **k: (asked.append(question), True)[1]
        report_command.execute(["a problem"])
        assert built == [True]
        built.clear()
        asked.clear()
        report_command.execute(["a problem", "--no-screen"])
        assert built == [False] and not any("terminal log" in q for q in asked)
        built.clear()
        report_command.execute(["a problem", "--screen"])
        assert built == [True]
        screenlog._state.update(on=False, checked=time.monotonic())
        screenlog.clear()
        asked.clear()
        built.clear()
        report_command.execute(["a problem"])
        assert not any("terminal log" in q for q in asked) and built == [False], "nothing recorded: no question"
        report.build = real_build
    finally:
        settings.get = real_get
        log.LOG_FILE = real_log
        screenlog._state.update(on=False, checked=0.0)
        screenlog.clear()
        trail.clear()
        shutil.rmtree(tmp, ignore_errors=True)
    print("report logging: all checks passed")


if __name__ == "__main__":
    main()
