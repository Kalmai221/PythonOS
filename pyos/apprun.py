# pyos/apprun.py - running a marketplace app (or program) as a process, and logging how it went
#
# Apps run in a process of their own. This starts one and writes a line to the system log when it ends: its name, how long it ran and its
# exit code, and for a failure also the last lines it printed to stderr (the traceback, "stopped: memory limit", a permission it was denied).
# The app's own output still goes to the screen as before; stderr is passed on line by line while the last few are kept.
import collections
import subprocess
import sys
import threading
import time

from pyos import log

TAIL_LINES = 8


def remember_answers(env, name):
    """After an app ended: keep the "always" and "never" answers it was given (pyos.sandbox.apply_decisions) and say what was remembered."""
    try:
        from pyos import sandbox
        from pyos.i18n import tr
        for perm, decision in sandbox.apply_decisions(env):
            print(tr("PythonOS will {verb} {name} to use: {what}. Change it with: pkg permissions {name}",
                     verb=tr("always allow") if decision == "always" else tr("never allow"), name=name, what=tr(sandbox.PERMISSIONS.get(perm, perm))))
            log.log(f"app {name}: permission {perm} set to {decision}")
    except Exception:                                      # noqa: BLE001 - remembering must never break the shell
        pass


def outcome(name, code, seconds, stderr_text, user=None):
    """Log how an app ended when its output was captured (a pipe or a redirect): `stderr_text` is what it printed to stderr."""
    _log_result(name, code, seconds, (stderr_text or "").splitlines()[-TAIL_LINES:], user)


def _log_result(name, code, seconds, tail, user):
    if code == 0:
        log.log(f"app {name} finished in {seconds:.1f}s", user=user)
        return
    reason = " | ".join(line.strip() for line in tail if line.strip())[-400:]
    if code in (-9, 137):
        reason = (reason + " | " if reason else "") + "killed (out of memory, or stopped by the system)"
    # a traceback is a bug in the app (or in PythonOS under it); a plain non-zero exit is the app saying it did not succeed
    crashed = any(line.startswith("Traceback (most recent call last)") for line in tail)
    log.log(f"app {name} {'crashed' if crashed else 'failed'}: exit {code} after {seconds:.1f}s" + (f": {reason}" if reason else ""),
            "ERROR" if crashed else "WARN", user=user)


def run(command, env, name, user=None, quiet_stderr=False):
    """Run `command` with the terminal as its screen and log the outcome. Returns the exit code (130 for Ctrl+C).

    Where processes cannot be started the normal way (the Android app runs scripts in-process), the plain call is used and only the exit code
    is logged."""
    started = time.monotonic()
    tail = collections.deque(maxlen=TAIL_LINES)
    try:
        if _in_process_only():
            code = subprocess.call(command, env=env)
        else:
            process = subprocess.Popen(command, env=env, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")

            def pump():
                for line in process.stderr:
                    tail.append(line.rstrip("\n"))
                    if not quiet_stderr:
                        sys.stderr.write(line)
                        sys.stderr.flush()
            reader = threading.Thread(target=pump, daemon=True)
            reader.start()
            try:
                code = process.wait()
            except KeyboardInterrupt:
                process.terminate()
                code = 130
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            reader.join(timeout=2)
    except OSError as e:
        log.log(f"app {name} could not start: {log.describe_exception(e)}", "ERROR", user=user)
        raise
    _log_result(name, code, time.monotonic() - started, tail, user)
    remember_answers(env, name)
    return code


def _in_process_only():
    """True where subprocess.Popen cannot start a Python script (the Android app replaces call/run by in-process shims, not Popen)."""
    import os
    return bool(os.environ.get("ANDROID_DATA") or os.environ.get("ANDROID_ROOT"))
