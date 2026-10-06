"""Boot-time helpers for the live ISO (and any small computer): the clock, memory, a diagnostics key and a diagnostics report.

Nothing here starts a program itself: system tools are run through core.hardware.run (fixed argument lists, never a shell),
so the lockdown audit has nothing new to review.
"""
import os
import select
import socket
import struct
import sys
import threading
import time

from core import hardware

NTP_HOSTS = ("pool.ntp.org", "time.cloudflare.com", "time.google.com")
NTP_EPOCH_OFFSET = 2208988800          # seconds between 1900 (NTP) and 1970 (Unix)
MAX_DRIFT = 5                          # a clock closer than this is left alone
LOW_RAM = 768 * 1024 ** 2
VERY_LOW_RAM = 384 * 1024 ** 2


# ------------------------------------------------------------------------------------------ the clock
def sntp_time(host, timeout=3):
    """Ask an NTP server for the time (SNTP over UDP). Returns Unix seconds, or None."""
    packet = b"\x1b" + 47 * b"\0"                 # version 3, client mode
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.sendto(packet, (host, 123))
            data, _ = sock.recvfrom(512)
    except OSError:
        return None
    if len(data) < 48:
        return None
    seconds = struct.unpack("!I", data[40:44])[0]
    return seconds - NTP_EPOCH_OFFSET if seconds else None


def network_time(timeout=3):
    for host in NTP_HOSTS:
        value = sntp_time(host, timeout)
        if value and value > 1_700_000_000:        # a sane answer (after late 2023)
            return value
    return None


def sync_clock():
    """Set the system clock from the network when it is wrong by more than a few seconds. Returns (state, text):
    state is 'ok', 'set', 'offline' or 'denied'."""
    now = network_time()
    if now is None:
        return "offline", "no time server could be reached"
    drift = abs(now - time.time())
    if drift <= MAX_DRIFT:
        return "ok", "the clock is already right"
    if hardware.unavailable_reason():
        return "denied", f"the clock is {int(drift)} s off, but only an administrator system can change it"
    code, out = hardware.run(["date", "-u", "-s", f"@{int(now)}"])
    if code != 0:
        return "denied", f"could not set the clock ({out.strip()[-80:]})"
    hardware.run(["hwclock", "-w", "-u"])          # keep the hardware clock too (ignored if the machine has none)
    return "set", f"the clock was {int(drift)} s off and is now set from the network"


def sync_clock_in_background(log=None, notify=None):
    """Wait for the network (up to a minute), then sync the clock once. Never blocks the boot."""
    def work():
        for _ in range(12):
            if hardware.check_internet()[0]:
                break
            time.sleep(5)
        else:
            return
        state, text = sync_clock()
        if log:
            log(f"Clock: {text}")
        if state == "set" and notify:
            notify("Time and date were set from the network.")
    threading.Thread(target=work, name="clock-sync", daemon=True).start()


# ------------------------------------------------------------------------------------------ memory
def memory_total():
    try:
        from pyos import resources
        return int(resources.budget())             # the memory PythonOS owns (the whole machine on the live ISO)
    except Exception:
        return 0


def memory_state(total=None):
    """('ok'|'low'|'very-low', text). Low memory is advice only: the system runs, with fewer extras."""
    total = memory_total() if total is None else total
    if not total:
        return "ok", "memory size unknown"
    gb = total / 1024 ** 3
    text = f"{gb:.1f} GB"
    if total < VERY_LOW_RAM:
        return "very-low", f"{text} - very little: PythonOS runs in light mode (no background checks, shorter animations)"
    if total < LOW_RAM:
        return "low", f"{text} - on the low side: PythonOS runs in light mode"
    return "ok", text


def light_mode():
    """True when background extras should be skipped: the light_mode setting, PYOS_LIGHT=1, or the memory check set it."""
    if os.environ.get("PYOS_LIGHT") == "1":
        return True
    try:
        from pyos import settings
        return bool(settings.get("light_mode"))
    except Exception:
        return False


# ------------------------------------------------------------------------------------------ diagnostics key
def key_pressed(letter="d", seconds=1.5):
    """Wait up to `seconds` for the key; True if it was pressed. Only on a real terminal (never blocks scripts or pipes)."""
    try:
        if not sys.stdin.isatty():
            return False
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
    except Exception:
        return False
    try:
        tty.setcbreak(fd)
        end = time.time() + seconds
        while time.time() < end:
            ready, _, _ = select.select([sys.stdin], [], [], max(0.0, end - time.time()))
            if ready and sys.stdin.read(1).lower() == letter:
                return True
        return False
    except Exception:
        return False
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except Exception:
            pass


# ------------------------------------------------------------------------------------------ diagnostics report
def diagnostics_text():
    """Everything useful for finding out why a computer misbehaves: hardware, drivers, disks, memory, network, boot log."""
    lines = [f"PythonOS diagnostics - {time.strftime('%Y-%m-%d %H:%M:%S')}", ""]
    summary = hardware.system_summary()
    lines += [f"Machine : {summary['machine']}", f"CPU     : {summary['cpu']}", f"Memory  : {summary['ram']}  ({memory_state()[0]})",
              f"Kernel  : {summary['kernel']}", ""]
    lines.append("== PCI devices and drivers ==")
    try:
        for d in hardware.pci_devices():
            lines.append(f"{d['cls']:<18} {d['desc']}  [{d['driver'] or 'no driver'}]")
    except Exception as e:
        lines.append(f"(could not list: {e})")
    for title, command in (("Disks", ["lsblk", "-o", "NAME,SIZE,TYPE,FSTYPE,LABEL,MOUNTPOINT"]), ("USB devices", ["lsusb"]),
                           ("Network", ["ip", "-brief", "address"]), ("Wi-Fi", ["iw", "dev"])):
        code, out = hardware.run(command)
        lines += ["", f"== {title} ==", out.strip() if code == 0 else f"(not available: exit {code})"]
    code, out = hardware.run(["dmesg"])
    if code == 0:
        failures = hardware.parse_firmware_failures(out)
        lines += ["", "== Firmware the kernel could not load ==", "\n".join(failures) if failures else "none reported"]
        lines += ["", "== Last 80 kernel messages ==", "\n".join(out.strip().splitlines()[-80:])]
    try:
        import psutil
        battery = psutil.sensors_battery()
        if battery:
            lines += ["", "== Battery ==", f"{battery.percent:.0f}% {'charging' if battery.power_plugged else 'on battery'}"]
    except Exception:
        pass
    try:
        from core import bootlog
        lines += ["", "== Last boot (step timings) =="]
        boots = bootlog.load()
        for step in (boots[-1] if boots else {}).get("steps", []):
            lines.append(f"{step.get('status', '?'):<5} {step.get('ms', 0):>7.0f} ms  {step.get('name', '')}  {step.get('detail', '')}")
    except Exception:
        pass
    return "\n".join(lines) + "\n"


def save_diagnostics():
    """Write the report where it will be found again: your home folder (on persistent storage if that is active). Returns the path."""
    import pyos.fs as fs
    name = f"diagnostics-{time.strftime('%Y%m%d-%H%M%S')}.txt"
    user, _role = fs.current_user()
    folder = fs.home_dir(user) if user else os.path.join(fs.BASE_DIR, "tmp")
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(diagnostics_text())
    return path
