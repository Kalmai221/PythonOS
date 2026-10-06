#!/usr/bin/env python3
"""Change the console resolution of the live ISO / VM by starting the kernel again with a video= option (kexec).

The graphics drivers of virtual machines (bochs, virtio, vmwgfx, VirtualBox) do not obey fbset; the one thing they all honour is the
kernel's own `video=<width>x<height>` option. So a resolution change is: load the same kernel and initramfs from the boot medium with the
current command line plus video=WxH, then jump into it (kexec). It takes seconds, not a full reboot, and the data disk is kept.

    python3 core_video.py apply      run by the session script before PythonOS starts: switch once to the saved resolution, or, in a virtual
                                     machine whose console came up small, to a better one (automatic resolution; `display auto off` stops it)

The rules:
  * the only text ever added to the kernel command line is video=<digits>x<digits>, checked here; nothing else is passed through
  * the kernel is loaded (kexec -l) and checked before anything is shut down: if that fails, nothing changes
  * no loop: once the command line holds video=, a saved resolution is not applied again, even if the driver ignored it
  * apply() never raises and never prints: a problem leaves the system as it is
Standard library only: it runs before anything else is loaded.
"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys

PREFS_FILE = os.path.join(".OSData", "hardware.json")
MODE_RE = re.compile(r"^(\d{3,5})x(\d{3,5})$")
VIDEO_RE = re.compile(r"(^|\s)video=\S+")


def valid(mode):
    """True for a resolution like 1280x720 within what a screen can have."""
    match = MODE_RE.match(str(mode or ""))
    return bool(match) and 320 <= int(match.group(1)) <= 7680 and 200 <= int(match.group(2)) <= 4320


def cmdline_with(current, mode):
    """The kernel command line `current` with video=<mode> instead of any video= it had."""
    if not valid(mode):
        raise ValueError("not a resolution")
    return (VIDEO_RE.sub("", current).strip() + f" video={mode}").strip()


def current_mode(cmdline=None):
    """The resolution the kernel was started with (video=WxH), or None."""
    if cmdline is None:
        try:
            with open("/proc/cmdline", encoding="utf-8") as f:
                cmdline = f.read()
        except OSError:
            return None
    found = re.search(r"(?:^|\s)video=(?:[^\s:=]+:)?(\d+x\d+)", cmdline)
    return found.group(1) if found else None


def boot_files(root="/media"):
    """(kernel, initramfs) of the running kernel flavour on the boot medium, or None."""
    flavour = ""
    try:
        flavour = os.uname().release.rsplit("-", 1)[-1]
    except (OSError, AttributeError):
        pass
    for kind in ([flavour] if flavour else []) + ["lts", "virt"]:
        for kernel in sorted(glob.glob(os.path.join(root, "*", "boot", f"vmlinuz-{kind}"))):
            initramfs = os.path.join(os.path.dirname(kernel), f"initramfs-{kind}")
            if os.path.isfile(initramfs):
                return kernel, initramfs
    return None


def unavailable_reason():
    """Why the resolution cannot be changed from inside, or None."""
    if not sys.platform.startswith("linux") or os.environ.get("PYOS_LIVE") != "1":
        return "The resolution can only be changed from inside on the live ISO and the virtual machine images."
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return "Changing the resolution needs root."
    if shutil.which("kexec") is None:
        return "This image has no kexec tool, so it cannot restart the kernel with another resolution."
    if boot_files() is None:
        return "The kernel files were not found on the boot medium (it may have been removed)."
    return None


def prepare(mode):
    """Load the kernel with video=<mode> (kexec -l). Returns (ok, message). Nothing is shut down yet."""
    reason = unavailable_reason()
    if reason:
        return False, reason
    if not valid(mode):
        return False, "Give a resolution like 1280x720."
    kernel, initramfs = boot_files()
    try:
        with open("/proc/cmdline", encoding="utf-8") as f:
            command = cmdline_with(f.read().strip(), mode)
        done = subprocess.run(["kexec", "-l", kernel, f"--initrd={initramfs}", f"--command-line={command}"],
                              capture_output=True, text=True, timeout=60)
    except (OSError, ValueError, subprocess.SubprocessError) as e:
        return False, f"Could not prepare the restart: {e}"
    if done.returncode != 0:
        return False, "This computer's firmware does not allow restarting the kernel this way" + (f" ({done.stderr.strip()[:120]})" if done.stderr.strip() else "") + "."
    return True, ""


def jump():
    """Leave the data disk clean and start the loaded kernel. Does not return when it works."""
    try:
        os.sync()
        if os.path.ismount("/mnt/pyos-data"):
            subprocess.run(["umount", "/mnt/pyos-data"], capture_output=True, timeout=30)
        subprocess.run(["kexec", "-e"], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass
    return False


def saved_mode():
    try:
        with open(PREFS_FILE, encoding="utf-8") as f:
            return str((json.load(f).get("display") or {}).get("mode") or "")
    except (OSError, ValueError, AttributeError):
        return ""


def drm_modes():
    """Resolutions the connected screens report, as 'WxH' strings."""
    modes = set()
    for status in glob.glob("/sys/class/drm/card*-*/status"):
        try:
            with open(status, encoding="utf-8") as f:
                if f.read().strip() != "connected":
                    continue
            with open(os.path.join(os.path.dirname(status), "modes"), encoding="utf-8") as f:
                modes.update(l.strip() for l in f if MODE_RE.match(l.strip()))
        except OSError:
            continue
    return sorted(modes)


def screen_size():
    try:
        with open("/sys/class/graphics/fb0/virtual_size", encoding="utf-8") as f:
            width, height = f.read().strip().split(",")
        return int(width), int(height)
    except (OSError, ValueError):
        return None


def is_vm(cpuinfo="", dmi=""):
    """True inside a virtual machine: the processor says it is virtualised, or the firmware names a known hypervisor."""
    if re.search(r"\bhypervisor\b", cpuinfo):
        return True
    return bool(re.search(r"virtualbox|vmware|qemu|kvm|bochs|xen|hyper-v|parallels|virtual machine", dmi, re.I))


def read_vm_hints():
    texts = []
    for path in ("/proc/cpuinfo",):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                texts.append(f.read(20000))
        except OSError:
            texts.append("")
    dmi = []
    for name in ("sys_vendor", "product_name", "board_vendor"):
        try:
            with open(f"/sys/class/dmi/id/{name}", encoding="utf-8") as f:
                dmi.append(f.read().strip())
        except OSError:
            pass
    return texts[0], " ".join(dmi)


def pick_auto_mode(current, modes):
    """The resolution to switch to when the console came up small: the biggest the screen offers up to 1920x1080 (at least 1024 wide).
    None when the console is already at least 1024 wide, or nothing better is offered."""
    if current and current[0] >= 1024:
        return None
    best = None
    for text in modes:
        match = MODE_RE.match(text)
        if not match or not valid(text):
            continue
        width, height = int(match.group(1)), int(match.group(2))
        if 1024 <= width <= 1920 and 600 <= height <= 1080 and (best is None or width * height > best[0] * best[1]):
            best = (width, height)
    return f"{best[0]}x{best[1]}" if best else None


def auto_enabled():
    try:
        with open(PREFS_FILE, encoding="utf-8") as f:
            return (json.load(f).get("display") or {}).get("auto", True) is not False
    except (OSError, ValueError, AttributeError):
        return True


def apply():
    """At boot: switch once to the saved resolution (or, in a virtual machine with a small console, an automatic one) when the kernel is
    not already using a video= option."""
    try:
        if current_mode() or unavailable_reason():
            return False
        mode = saved_mode()
        if not valid(mode):
            mode = None
            if auto_enabled() and is_vm(*read_vm_hints()):
                mode = pick_auto_mode(screen_size(), drm_modes())
        if not mode:
            return False
        ok, _ = prepare(mode)
        return jump() if ok else False
    except Exception:
        return False


if __name__ == "__main__":
    if sys.argv[1:] == ["apply"]:
        apply()
