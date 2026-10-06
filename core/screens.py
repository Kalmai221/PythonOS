"""The shutdown, restart, factory-reset and crash screens - one themed implementation, scaled by the boot-speed setting."""
import json
import os
import re
import shutil
import subprocess
import sys
import time
import zlib

from rich import box
from rich.console import Console
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text
from yaspin import yaspin

import pyos
from pyos import jobs, log, settings, theme
from pyos.i18n import tr

console = Console()


def _clear():
    pyos.stdio.clear_screen(scrollback=False)


def pause(seconds):
    """Sleep for the given time scaled to the fixed boot pause (none in light mode)."""
    scale = settings.boot_pause() / 0.35
    if scale > 0 and seconds > 0:
        time.sleep(seconds * scale)


def _bar(done, total, width=14):
    filled = int(width * done / max(1, total))
    return "[cyan]" + "#" * filled + "[/cyan][dim]" + "-" * (width - filled) + "[/dim]"


PAST = {"Stopping": "Stopped", "Signing out": "Signed out", "Writing": "Wrote", "Flushing": "Flushed", "Marking": "Marked",
        "Saving": "Saved", "Erasing": "Erased", "Unmounting": "Unmounted", "Syncing": "Synced"}


def _past(label):
    """'Stopping Task Scheduler' -> 'Stopped Task Scheduler.' (the line a real system prints when the step is done)."""
    for present, past in PAST.items():
        if label.startswith(present):
            return past + label[len(present):] + "."
    return label + "."


def _ok(label, detail="", number=0, total=0, ms=None):
    suffix = f" [dim]{escape(detail)}[/dim]" if detail else ""
    slow = "did not answer" in detail
    mark = theme.tag("warning", "[ WARN ]") if slow else theme.tag("success", "[  OK  ]")
    console.print(f"{mark} {escape(tr(_past(label)))}{suffix}")


def _step(label, action=None, seconds=0.6, number=0, total=0):
    """Run one real step: a spinner while it works, then an [ OK ] line with a progress bar and how long it took.
    The action's return value (text) becomes the detail."""
    detail = ""
    t0 = time.perf_counter()
    if settings.boot_pause() > 0 and sys.stdout.isatty():
        with yaspin(text=tr(label) + "...", spinner="dots") as spinner:
            detail = action() if action else ""
            pause(seconds)
    else:
        detail = action() if action else ""
    _ok(label, detail or "", number, total, (time.perf_counter() - t0) * 1000)


def _record_closing():
    log.log("Shutdown: sessions closed")
    return ""


def _mark_session(kind):
    def action():
        from pyos import session
        session.end("clean" if kind != "wipe" else "clean")
        return ""
    return action


# --------------------------------------------------------------------- actions
def _stop_jobs():
    """Ask every background job to stop and give them a moment, saying so for the ones that take a while (like a real shutdown)."""
    running = [j for j in jobs.all_jobs() if j.status == "running"]
    for job in running:
        jobs.cancel(job.id)
    started = time.time()
    end = started + 3
    told = set()
    while time.time() < end and any(j.status == "running" for j in running):
        for job in running:
            if job.status == "running" and job.id not in told and time.time() - started > 0.4:
                told.add(job.id)
                console.print("[dim]" + escape(f"A stop job is running for [{job.id}] {job.command[:50]} (up to 3 s)") + "[/dim]")
        time.sleep(0.05)
    left = [j for j in running if j.status == "running"]
    if left:
        return f"{len(running) - len(left)} stopped, {len(left)} did not answer and were left"
    return f"{len(running)} stopped" if running else ""


def _close_sessions():
    try:
        os.remove("current_user.json")
    except OSError:
        pass


def _flush():
    if hasattr(os, "sync"):
        try:
            os.sync()
        except OSError:
            pass


# ------------------------------------------------------------- the live ISO: PythonOS is the whole system
def _live():
    return os.environ.get("PYOS_LIVE") == "1"


def _quiet(cmd, timeout=15):
    """Run a system command with no output at all (the Linux underneath never gets to write on the screen)."""
    try:
        subprocess.run(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout, check=False)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _save_data():
    """Write everything out and release the data disk (and lock it again if it is encrypted)."""
    _flush()
    try:
        os.chdir("/")
    except OSError:
        pass
    if os.path.ismount("/mnt/pyos-data"):
        _quiet(["umount", "/mnt/pyos-data"])
        if os.path.ismount("/mnt/pyos-data"):
            _quiet(["umount", "-l", "/mnt/pyos-data"])
        if os.path.exists("/dev/mapper/pyosdata"):
            _quiet(["cryptsetup", "close", "pyosdata"])
        return "data disk released"
    return ""


def _stop_services():
    """The system services (network, Bluetooth, printing...) stop now, with their messages hidden: PythonOS shows the progress."""
    for command in (["/sbin/openrc", "shutdown"], ["openrc", "shutdown"]):
        if _quiet(command, 20):
            break
    return ""


def power(action):
    """Switch the machine off or restart it (live ISO only), without a single line from the system. Returns only if that failed."""
    _flush()
    try:
        with open("/proc/sys/kernel/printk", "w") as f:
            f.write("0 0 0 0")                       # no kernel message ("reboot: Power down") on the screen either
    except OSError:
        pass
    try:
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
    except (OSError, ValueError):
        pass
    verb = "reboot" if action == "restart" else "poweroff"
    for command in ([verb, "-f"], ["/sbin/" + verb, "-f"]):
        _quiet(command, 30)


def factory_reset():
    """Erase accounts, settings, every user's files and installed packages. Returns a short description."""
    for name in ("current_user.json", pyos.paths.USER_DB, "current_directory.txt"):
        try:
            os.remove(name)
        except OSError:
            pass
    shutil.rmtree(".OSData", ignore_errors=True)            # settings, schedule, notifications, lockout, package records, caches
    base = pyos.fs.BASE_DIR
    if os.path.isdir(base):
        for entry in os.listdir(base):
            if entry in ("etc", "var"):
                continue                                        # the system layout stays
            target = os.path.join(base, entry)
            shutil.rmtree(target, ignore_errors=True) if os.path.isdir(target) else os.remove(target)
        for sub in ("tmp",):
            shutil.rmtree(os.path.join(base, sub), ignore_errors=True)
        shutil.rmtree(os.path.join(base, "var", "log"), ignore_errors=True)
    return "accounts, settings, files and packages"


# ------------------------------------------------------------------- sequences
def shutdown_sequence(kind="shutdown"):
    """kind: 'shutdown', 'restart' or 'wipe'. Shutdown and wipe end the process; restart returns so the caller can relaunch."""
    restarting, wiping = kind == "restart", kind == "wipe"
    log.log("System restarting" if restarting else "System factory reset" if wiping else "System shutting down", "WARN" if wiping else "INFO")
    _clear()
    title = "Restarting" if restarting else "Resetting to factory settings" if wiping else "Shutting down"
    console.print(Panel(f"[bold]{tr(title)}[/bold]", border_style=theme.style("border"), expand=False))

    steps = []
    try:
        from pyos import tasks
        for service in tasks.services():                       # the services that are really running, newest first, like a real system
            steps.append((f"Stopping {tasks.describe(service)}", (lambda s=service: tasks.stop_service(s)), 0.15))
    except Exception:
        pass
    steps += [("Stopping background jobs", _stop_jobs, 0.5), ("Signing out", _close_sessions, 0.4),
              ("Writing the system log", _record_closing, 0.2)]
    if wiping:
        steps.append(("Erasing accounts, settings, files and packages", factory_reset, 1.0))
    steps.append(("Flushing the filesystem", _flush, 0.5))
    if not wiping:
        steps.append(("Marking the session as closed", _mark_session(kind), 0.2))
    if _live():
        steps += [("Saving your data", _save_data, 0.4), ("Stopping system services", _stop_services, 0.4)]
    for number, (label, action, seconds) in enumerate(steps, 1):
        _step(label, action, seconds, number, len(steps))

    console.print(f"{theme.tag('success', '[  OK  ]')} Reached target {'Reboot' if restarting else 'Power-Off'}.")
    if restarting:
        console.print(f"\n{theme.tag('warning', tr('Restarting now...'))}")
        pause(0.8)
        if _live():
            power("restart")                          # a real restart of the machine; returns only if that failed
        return
    countdown = max(0, round(3 * settings.boot_pause() / 0.35))
    if countdown and sys.stdout.isatty():
        with yaspin(text=tr("Powering off in {n}...", n=countdown), spinner="dots") as spinner:
            for remaining in range(countdown, 0, -1):
                spinner.text = tr("Powering off in {n}...", n=remaining)
                time.sleep(1)
    console.print("[dim]pyos: Power down.[/dim]")
    console.print(f"\n{theme.tag('error', tr('Shutdown complete.'))}")
    if wiping:
        console.print(f"\n{theme.tag('warning', tr('Power on the device for first-time setup.'))}")
    if _live():
        power("shutdown")
    sys.exit(0)


def relaunch():
    """Start PythonOS again as a fresh process (so updated files are really loaded). On Linux and macOS the new process replaces this
    one, so repeated restarts never pile up; elsewhere this process waits for the new one and passes its exit code on."""
    try:
        sys.stdout.flush()
    except (OSError, ValueError):
        pass
    if os.name == "posix" and os.environ.get("PYOS_BUNDLED") != "1":
        try:
            os.execv(sys.executable, [sys.executable, "main.py"])
        except OSError:
            pass
    sys.exit(subprocess.call([sys.executable, "main.py"]))


def _stop_info(detail):
    """(stop code, one-line summary, short code) from the text of a traceback or message."""
    lines = [l for l in str(detail).strip().splitlines() if l.strip()]
    last = next((l for l in reversed(lines) if re.match(r"^[A-Za-z_][\w.]*(Error|Exception|Interrupt|Exit)\b", l)), "")
    if last:
        kind, _, message = last.partition(":")
        code = re.sub(r"(?<!^)(?=[A-Z])", "_", kind.split(".")[-1]).upper()
        summary = message.strip() or "No further details were given."
    else:
        code = "SYSTEM_ERROR"
        summary = (lines[0] if lines else "Something went wrong.").removeprefix("Error:").strip()
    short = "0x%08X" % (zlib.crc32((code + summary).encode()) & 0xFFFFFFFF)
    return code, summary[:160], short


def _save_crash_report(detail, code, short):
    """Keep the full trace in /var/log (the 10 newest) so the screen can stay short. Returns the path shown to the user."""
    folder = os.path.join(pyos.fs.BASE_DIR, "var", "log")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    name = f"crash-{stamp}.log"
    try:
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
            f.write(f"PythonOS crash report\nTime: {time.strftime('%Y-%m-%d %H:%M:%S')}\nStop code: {code} ({short})\n\n{detail}\n")
        old = sorted(n for n in os.listdir(folder) if n.startswith("crash-") and n.endswith(".log"))
        for n in old[:-10]:
            os.remove(os.path.join(folder, n))
    except OSError:
        return None
    return f"/var/log/{name}"


def _bsod(code, summary, short, report, footer, looping=False):
    """The whole screen: blue, with the short story at the top and the footer (countdown) at the bottom."""
    body = Text(style="white on blue")
    body.append(":(\n\n", style="bold white on blue")
    body.append(tr("PythonOS ran into a problem and has stopped.") + "\n\n", style="bold white on blue")
    body.append(tr("What happened") + "\n", style="bold white on blue")
    body.append(f"  {summary}\n\n", style="white on blue")
    body.append(tr("Stop code") + "\n", style="bold white on blue")
    body.append(f"  {code}  ({short})\n\n", style="white on blue")
    if report:
        body.append(tr("Details") + "\n", style="bold white on blue")
        body.append(f"  Saved to {report}. Open it with: cat {report}\n\n", style="white on blue")
    body.append(tr("Your files and accounts were not touched.") + "\n\n", style="white on blue")
    body.append(footer, style="bold black on white" if looping else "bold white on blue")
    height = max(12, console.height - 1)
    return Panel(body, style="white on blue", border_style="white", box=box.DOUBLE, height=height, padding=(1, 3),
                 title="[bold white on blue] STOP [/bold white on blue]")


def crash_screen(error_message):
    """The blue screen: say what happened in a few words, keep the full trace in a log file, then restart PythonOS
    (unless it keeps crashing)."""
    detail = str(error_message).strip()
    code, summary, short = _stop_info(detail)
    log.log(f"PythonOS crashed: {code}: {summary[:160]}", "ERROR")
    report = _save_crash_report(detail, code, short)
    try:
        from pyos import report as problem_report
        problem_report.save_pending(f"PythonOS crashed: {code}: {summary[:120]}")     # ready to send later, even with no network
    except Exception:                                  # noqa: BLE001
        pass

    # crash-loop guard: remember recent crashes
    record = os.path.join(".OSData", "crashes.json")
    now = time.time()
    try:
        with open(record, encoding="utf-8") as f:
            recent = [t for t in json.load(f) if now - t < 120]
    except (OSError, ValueError):
        recent = []
    recent.append(now)
    try:
        os.makedirs(".OSData", exist_ok=True)
        with open(record, "w", encoding="utf-8") as f:
            json.dump(recent, f)
    except OSError:
        pass
    looping = len(recent) >= 4

    try:
        from pyos import session
        session.end("crashed", code)
    except Exception:
        pass
    _clear()
    if looping:
        console.print(_bsod(code, summary, short, report,
                            " PythonOS keeps crashing, so it will not restart by itself. Start it again when you are ready. ",
                            looping=True))
        try:
            from core import emergency
            emergency.offer()                          # the logs and crash reports can be read, and packed for sending, without logging in
        except Exception:                              # noqa: BLE001
            pass
        sys.exit(1)

    wait = max(1, round(5 * settings.boot_pause() / 0.35)) if settings.boot_pause() > 0 else 1
    with Live(_bsod(code, summary, short, report, tr("Restarting in {n}...", n=wait) + f"  [{'-' * wait}]"), console=console,
              refresh_per_second=4, transient=False) as live:
        for remaining in range(wait, 0, -1):
            done = wait - remaining
            live.update(_bsod(code, summary, short, report,
                              tr("Restarting in {n}...", n=remaining) + f"  [{'#' * done}{'-' * remaining}]"))
            time.sleep(1)
    _clear()
    relaunch()
