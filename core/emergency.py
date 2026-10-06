"""The emergency console: a small, read-only way to find out what went wrong when PythonOS will not start or log in.

It is started from the boot menu (press M at the start on the ISO and VM images, or run `main.py --emergency` on any export) and offered
by itself after PythonOS has crashed several times in a row. It needs no login, so it can only do harmless things:

  * read the system log, crash reports, the boot log and a hardware/diagnostic report (nothing else: not accounts, files or settings)
  * pack those into one zip (`savelogs`) in your files, or onto a USB stick, so they can be sent for help
  * switch safe mode on or off for the next start, clear the crash counter, restart or shut down

It is not a shell: there is no way to run a program, read a user's files or change anything but those two switches.
"""
import os
import re
import time
import zipfile

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

console = Console()
USB_MOUNT = "/mnt/pyos-usb"
FS_OK = ("vfat", "exfat", "ext4", "ext3", "ext2", "ntfs")


def _safe_name(name):
    return bool(re.fullmatch(r"crash-[\w.-]+\.log", name))


def log_dir():
    import pyos
    return os.path.join(pyos.fs.BASE_DIR, "var", "log")


def crash_reports():
    try:
        return sorted(n for n in os.listdir(log_dir()) if _safe_name(n))
    except OSError:
        return []


def tail(path, lines):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()[-lines:]
    except OSError:
        return []


def status_lines():
    lines = []
    try:
        from pyos import report
        lines.append(f"PythonOS {report._version()}   package: {report._package()}")
    except Exception:                                  # noqa: BLE001
        lines.append("PythonOS (version unknown)")
    try:
        from core import whathappened
        headline, details = whathappened.describe()
        lines.append(headline or "The last session ended normally.")
        lines += details[:4]
    except Exception:                                  # noqa: BLE001
        pass
    lines.append(f"Crash reports: {len(crash_reports())}    Safe mode next start: {'on' if safe_flag() else 'off'}")
    return lines


def safe_flag():
    return os.path.exists(os.path.join(".OSData", "safemode"))


def set_safe(on):
    path = os.path.join(".OSData", "safemode")
    if on:
        os.makedirs(".OSData", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("on\n")
    elif os.path.exists(path):
        os.remove(path)


def clear_crash_counter():
    for name in ("crashes.json",):
        try:
            os.remove(os.path.join(".OSData", name))
        except OSError:
            pass


def diagnostics():
    try:
        from core import liveboot
        return liveboot.diagnostics_text()
    except Exception as e:                             # noqa: BLE001
        return f"(the hardware report could not be made: {e})\n"


def bundle(folder=None):
    """Pack the logs and the diagnostic report into one zip. Returns its path."""
    import pyos
    folder = folder or os.path.join(pyos.fs.BASE_DIR, "var", "emergency")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"pythonos-logs-{time.strftime('%Y%m%d-%H%M%S')}.zip")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        if os.path.exists(pyos.log.LOG_FILE):
            z.write(pyos.log.LOG_FILE, "system.log")
        for name in crash_reports()[-10:]:
            z.write(os.path.join(log_dir(), name), name)
        z.writestr("diagnostics.txt", diagnostics())
        z.writestr("status.txt", "\n".join(status_lines()) + "\n")
    return path


def usb_partitions(devices=None):
    """Removable partitions with a filesystem we can write to, nothing mounted: [dict]."""
    from core import persist
    devices = devices if devices is not None else persist.lsblk()
    found = []
    for d in devices:
        parent = d.get("parent") or {}
        if d["type"] == "part" and d["fstype"] in FS_OK and not d["mounts"] and (d["removable"] or parent.get("removable")) and persist.DEVICE_RE.match(d["path"]):
            found.append(d)
    return found


def copy_to_usb(zip_path, device):
    """Copy the zip to a USB partition (mounted noexec for a moment). Returns (ok, message)."""
    from core import hardware
    if hardware.unavailable_reason():
        return False, hardware.unavailable_reason()
    os.makedirs(USB_MOUNT, exist_ok=True)
    code, out = hardware.run(["mount", "-o", "nosuid,nodev,noexec", device, USB_MOUNT], timeout=30)
    if code != 0:
        return False, f"could not open {device}: {out.strip()[-120:]}"
    try:
        target = os.path.join(USB_MOUNT, os.path.basename(zip_path))
        with open(zip_path, "rb") as source, open(target, "wb") as dest:
            dest.write(source.read())
        hardware.run(["sync"], timeout=30)
    except OSError as e:
        return False, f"could not write to {device}: {e}"
    finally:
        hardware.run(["umount", USB_MOUNT], timeout=30)
    return True, f"copied to {device} as {os.path.basename(zip_path)}; you can remove the stick"


HELP = """status           what happened last time and the state of the system
logs [n]         the last n lines of the system log (30 by default)
crashes          the crash reports; crash <number> shows one
bootlog          how the last starts went, step by step
diag             a hardware and driver report
savelogs         pack the logs and the report into a zip (in your files, or on a USB stick if you plug one in)
safe on|off     start in safe mode next time (no apps, startup commands or background checks)
reset            clear the crash counter, so the crash-loop guard starts fresh
restart          start PythonOS again          shutdown   switch off
help, quit"""


def handle(line):
    """Run one emergency command. Returns False to leave."""
    word, _s, rest = line.strip().partition(" ")
    word, rest = word.lower(), rest.strip()
    if word in ("quit", "exit", "q", "continue"):
        return False
    if word in ("help", "?"):
        console.print(HELP, markup=False)
    elif word == "status":
        for text in status_lines():
            console.print(text, markup=False)
    elif word == "logs":
        import pyos
        count = int(rest) if rest.isdigit() else 30
        for text in tail(pyos.log.LOG_FILE, min(count, 400)) or ["(the system log is empty)"]:
            console.print(text, markup=False, highlight=False)
    elif word in ("crashes", "crash"):
        names = crash_reports()
        if word == "crash" and rest.isdigit() and 1 <= int(rest) <= len(names):
            for text in tail(os.path.join(log_dir(), names[int(rest) - 1]), 60):
                console.print(text, markup=False, highlight=False)
        else:
            for number, name in enumerate(names, 1):
                console.print(f"{number:>3}  {name}", markup=False)
            console.print("crash <number> shows one." if names else "No crash reports.", markup=False)
    elif word == "bootlog":
        try:
            from core import bootlog
            for boot in bootlog.load()[-3:]:
                console.print(f"-- boot, {boot.get('total_ms', 0):.0f} ms", markup=False)
                for step in boot.get("steps", []):
                    console.print(f"  {step.get('status', '?'):<5} {step.get('ms', 0):>6.0f} ms  {step.get('name', '')}  {step.get('detail', '')}", markup=False, highlight=False)
        except Exception as e:                         # noqa: BLE001
            console.print(f"(no boot log: {e})", markup=False)
    elif word == "diag":
        console.print(diagnostics(), markup=False, highlight=False)
    elif word == "savelogs":
        path = bundle()
        console.print(f"Saved {path}", markup=False)
        sticks = usb_partitions()
        if sticks:
            for number, d in enumerate(sticks, 1):
                console.print(f"  {number}) {d['path']}  {d['label'] or d['fstype']}", markup=False)
            pick = input("Copy it to a USB stick? Number (blank = no): ").strip()
            if pick.isdigit() and 1 <= int(pick) <= len(sticks):
                console.print(copy_to_usb(path, sticks[int(pick) - 1]["path"])[1], markup=False)
    elif word == "safe" and rest in ("on", "off"):
        set_safe(rest == "on")
        console.print(f"Safe mode will be {rest} at the next start.", markup=False)
    elif word == "reset":
        clear_crash_counter()
        console.print("The crash counter is cleared.", markup=False)
    elif word == "restart":
        from core import screens
        screens.relaunch()
    elif word == "shutdown":
        import core
        core.simulate_shutdown()
        return False
    elif word:
        console.print("I did not understand that. help lists the commands.", markup=False)
    return True


def run():
    """The emergency console. Returns when the person leaves it (the caller then carries on or stops)."""
    console.print(Panel("[bold yellow]Emergency console[/bold yellow]\n"
                        "For finding out why PythonOS does not start or log in. It can read the logs and crash reports and pack them for sending; "
                        "it cannot run programs or read your files.\nType [bold]help[/bold] for the commands, [bold]quit[/bold] to carry on.",
                        border_style="yellow", expand=False))
    for text in status_lines():
        console.print(escape(text))
    try:
        while True:
            line = input("emergency> ")
            if handle(line) is False:
                break
    except (EOFError, KeyboardInterrupt):
        console.print()
    return True


def offer(seconds=10):
    """After repeated crashes: wait a few seconds for E, then open the emergency console. True when it was opened."""
    console.print(f"[bold]Press E within {seconds} seconds for the emergency console[/bold] (logs and crash reports); anything else leaves.")
    from core import liveboot
    if liveboot.key_pressed("e", seconds):
        run()
        return True
    return False
