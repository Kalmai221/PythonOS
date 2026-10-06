"""Install PythonOS from the live USB onto a disk of the computer (EXPERIMENTAL).

The live ISO stays a live system. This turns a spare disk into a PythonOS computer that boots by itself and keeps everything:
Alpine's own `setup-disk` partitions the disk, copies a base system and puts a boot loader on it; then this module adds
PythonOS, the same lockdown (no login or shell on any console, root locked, locked boot menu) and the services the live image runs.

Safety rules: only on the live system as root; only a whole disk that is not the one PythonOS booted from and has nothing mounted;
the person must type the disk's name to confirm; every system tool runs through core.hardware.run with a fixed argument list.
It has not been tried on every kind of hardware: the plan is shown first, and the result is checked at the end.
"""
import os
import re
import shutil
import sys
import time

from core import hardware, persist

TARGET = "/mnt/pyos-target"
SOURCE = "/opt/pythonos"          # the running live system
MIN_SIZE = 2 * 1024 ** 3
SERVICES = {
    "sysinit": ["devfs", "dmesg", "mdev", "hwdrivers"],
    "boot": ["hwclock", "modules", "sysctl", "hostname", "bootmisc", "syslog", "networking"],
    "default": ["bluetooth", "cupsd"],
    "shutdown": ["mount-ro", "killprocs", "savecache"],
}

INITTAB = """# /etc/inittab for an installed PythonOS.
# PythonOS is the only thing that ever runs on a console. There is deliberately NO getty and NO shell here.

::sysinit:/sbin/openrc sysinit
::sysinit:/sbin/openrc boot
::wait:/sbin/openrc default

# PythonOS on the first console; init restarts it if it ever stops
tty1::respawn:/usr/local/bin/pythonos-session

# Ctrl+Alt+Del restarts the machine
::ctrlaltdel:/sbin/reboot

# Before shutting down or rebooting
::shutdown:/sbin/openrc shutdown
"""

SESSION = """#!/bin/sh
# Runs PythonOS on the first console of an installed system. Never gives anyone a Linux shell:
#   - PythonOS ends normally (the shutdown command) -> power off
#   - PythonOS stops for any other reason          -> note it in a log, then exit; init restarts it

export PYOS_BUNDLED=1
export PYOS_INSTALLED=1
export PYOS_EXPORT_INFO=/opt/pythonos/export.json
export PYOS_LOCKDOWN=1
export HOME=/root
export TERM="${TERM:-linux}"
export LANG=C.UTF-8
export PYTHONIOENCODING=utf-8

stty susp undef quit undef 2>/dev/null
trap '' TSTP QUIT HUP

cd /opt/pythonos 2>/dev/null || { echo "PythonOS files are missing."; sleep 5; exit 1; }

clear
python3 main.py
code=$?

if [ "$code" -eq 0 ]; then
    sync
    echo "PythonOS has shut down. Powering off..."
    sleep 2
    poweroff
    exit 0
fi

mkdir -p /var/log
echo "$(date '+%Y-%m-%d %H:%M:%S') PythonOS stopped with exit code $code" >> /var/log/pythonos-crash.log
echo
echo "PythonOS stopped unexpectedly (code $code). Restarting..."
sleep 3
exit 1
"""

SYSCTL = """kernel.sysrq = 0
kernel.dmesg_restrict = 1
kernel.kptr_restrict = 2
kernel.core_pattern = |/bin/false
"""


# ------------------------------------------------------------------------------------------ choosing a disk
def available():
    """Why installing is not possible here, or None."""
    if os.environ.get("PYOS_LIVE") != "1":
        return "Installing is done from the live USB (this is not a live system)."
    if not hardware.have("setup-disk"):
        return "This image has no installer (the minimal image leaves it out). Use the full image to install."
    return hardware.unavailable_reason()


DATA_MOUNT = "/mnt/pyos-data"


def _family(devices, dev):
    """The device, its partitions and what sits on them (an unlocked encrypted disk), and its parent."""
    paths = {dev["path"]}
    grew = True
    while grew:
        grew = False
        for d in devices:
            if d["path"] not in paths and d["parent"] and d["parent"]["path"] in paths:
                paths.add(d["path"])
                grew = True
    related = [d for d in devices if d["path"] in paths]
    if dev["parent"]:
        related.append(dev["parent"])
    return related


def is_data_disk(devices, dev):
    """True when the only thing in use on this disk is the PythonOS data disk (PYOS_DATA / PYOS_CRYPT): its files and accounts live there."""
    related = _family(devices, dev)
    mounts = {m for d in related for m in d["mounts"]}
    return bool(mounts) and mounts <= {DATA_MOUNT} and not any(d["fstype"] in ("iso9660", "squashfs") for d in related)


def disks(devices=None, with_data=True):
    """Whole disks PythonOS could be installed on: big enough, nothing in use, not the medium PythonOS booted from. The data disk counts too
    (with_data): installing there erases what it holds, which the person is told first. Each disk is {..., "is_data": bool}."""
    devices = devices if devices is not None else persist.lsblk()
    found = []
    for d in devices:
        if d["type"] != "disk" or not persist.DEVICE_RE.match(d["path"]) or d["size"] < MIN_SIZE:
            continue
        data = is_data_disk(devices, d)
        if persist._family_mounted(devices, d) and not (with_data and data):
            continue
        found.append(dict(d, is_data=data))
    return sorted(found, key=lambda d: (d["is_data"], d["removable"], d["size"]))


def skipped(devices=None):
    """[(path, size, why)] for every whole disk that cannot be used, so the person can see why."""
    devices = devices if devices is not None else persist.lsblk()
    usable = {d["path"] for d in disks(devices)}
    out = []
    for d in devices:
        if d["type"] != "disk" or not persist.DEVICE_RE.match(d["path"]) or d["path"] in usable:
            continue
        related = _family(devices, d)
        if any(r["fstype"] in ("iso9660", "squashfs") for r in related):
            why = "the disk PythonOS started from"
        elif d["size"] < MIN_SIZE:
            why = f"too small ({persist.human(d['size'])}; it needs at least 2 GB)"
        elif any(r["mounts"] for r in related):
            why = "in use (mounted)"
        else:
            why = "not usable"
        out.append((d["path"], d["size"], why))
    return out


def validate(path, devices=None):
    """(disk dict or None, why not)."""
    for d in disks(devices):
        if d["path"] == path:
            return d, ""
    return None, f"{path} is not a disk that can be used (it must be a whole disk of at least 2 GB that is not in use, and not the USB stick PythonOS started from)."


def release_data_disk(log=print):
    """Stop using the data disk so it can be erased: what PythonOS keeps on it (files, accounts, settings) is copied back into memory first,
    so the running system keeps working until the person restarts. Raises InstallError when it cannot be released."""
    log("Releasing the data disk (its files and accounts are erased by the installation)")
    hardware.run(["sync"])
    for name in ("files", ".OSData"):
        link = os.path.join(SOURCE, name)
        if os.path.islink(link):
            real = os.path.realpath(link)
            os.unlink(link)
            shutil.copytree(real, link, symlinks=True)
    for link, service in (("/var/lib/bluetooth", "bluetooth"), ("/etc/cups", "cupsd")):
        if os.path.islink(link):
            hardware.run(["rc-service", service, "stop"], timeout=30)
            os.unlink(link)
            os.makedirs(link, exist_ok=True)
    users = os.environ.get("PYOS_USERS_FILE", "")
    if users.startswith(DATA_MOUNT):
        fallback = os.path.join(SOURCE, "users.json")
        if os.path.exists(users):
            shutil.copy2(users, fallback)
        os.environ["PYOS_USERS_FILE"] = fallback
    for key in ("PYOS_PERSISTENT", "PYOS_CORE_OVERLAY", "PYOS_PERSIST_ENCRYPTED"):
        os.environ.pop(key, None)
    code, out = hardware.run(["umount", DATA_MOUNT], timeout=60)
    if code != 0:
        raise InstallError(f"could not release the data disk: {(out or '').strip()[-200:] or 'it is busy'}")
    if os.path.exists("/dev/mapper/pyosdata"):
        hardware.run(["cryptsetup", "close", "pyosdata"], timeout=30)


def firmware():
    return "UEFI" if os.path.isdir("/sys/firmware/efi") else "BIOS"


def plan(device):
    """The steps, in plain words, shown before anything is touched."""
    return [f"Erase {device['path']} ({persist.human(device['size'])}) and create the partitions for a {firmware()} computer",
            "Install a base system and the boot loader (Alpine's setup-disk)",
            "Add PythonOS, its packages and its services",
            "Lock the system down the same way as the live USB: no login or shell, root locked, boot menu locked",
            "Check the result, then it is ready to boot from the disk"]


# ------------------------------------------------------------------------------------------ boot loader lock
def lock_extlinux(text):
    """extlinux.conf with no prompt, no escape and no editable options; everything else kept."""
    keep = [line for line in text.splitlines() if not re.match(r"^\s*(PROMPT|NOESCAPE|ALLOWOPTIONS|TIMEOUT|UI|MENU\s+(TITLE|AUTOBOOT))\b", line, re.I)]
    head = ["PROMPT 0", "NOESCAPE 1", "ALLOWOPTIONS 0", "TIMEOUT 10"]
    return "\n".join(head + keep) + "\n"


def lock_grub(text, pbkdf2):
    """grub.cfg with a superuser password (random, thrown away) and every menu entry bootable without it."""
    lines = [l for l in text.splitlines() if not l.startswith(("set superusers", "password_pbkdf2"))]
    out = ['set superusers="pyos"', f"password_pbkdf2 pyos {pbkdf2}"]
    for line in lines:
        if re.match(r"^\s*menuentry\b", line) and "--unrestricted" not in line:
            line = re.sub(r"\s*\{\s*$", " --unrestricted {", line)
        out.append(line)
    return "\n".join(out) + "\n"


def _grub_hash():
    """A PBKDF2 hash of a random password that nobody ever sees. None if grub's tool is missing."""
    import secrets
    if not hardware.have("grub-mkpasswd-pbkdf2"):
        return None
    password = secrets.token_urlsafe(30)
    code, out = hardware.run(["grub-mkpasswd-pbkdf2"], timeout=60, text_input=f"{password}\n{password}\n")
    found = re.search(r"(grub\.pbkdf2\.sha512\.\S+)", out or "")
    return found.group(1) if code == 0 and found else None


# ------------------------------------------------------------------------------------------ doing it
class InstallError(Exception):
    pass


def _step(log, text):
    log(text)


def _must(code_out, what):
    code, out = code_out
    if code != 0:
        raise InstallError(f"{what} failed: {(out or '').strip()[-300:] or 'exit code ' + str(code)}")
    return out


def root_partition(device_path):
    """The ext4 partition setup-disk made for the system (the biggest ext4 one on the disk)."""
    devices = persist.lsblk()
    parts = [d for d in devices if d["parent"] and d["parent"]["path"] == device_path and d["fstype"] == "ext4"]
    if not parts:
        raise InstallError("could not find the new system partition")
    return max(parts, key=lambda d: d["size"])["path"]


def apk_packages():
    """What the live system installs on top of Alpine's base: its own world file minus the base system itself."""
    names = []
    try:
        with open("/etc/apk/world", encoding="utf-8") as f:
            names = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    except OSError:
        pass
    return [n for n in names if n not in ("alpine-base",)]


def install(device_path, log=print, hostname="pyOS"):
    """Do the installation. Returns None on success or raises InstallError with what went wrong. `device_path` must have been validated."""
    reason = available()
    if reason:
        raise InstallError(reason)
    device, why = validate(device_path)
    if device is None:
        raise InstallError(why)
    if device.get("is_data"):
        release_data_disk(lambda text: _step(log, text))

    _step(log, f"Partitioning and installing the base system on {device_path} (a few minutes)")
    _must(hardware.run(["setup-disk", "-m", "sys", "-s", "0", device_path], timeout=1800, text_input="y\n",
                       env={"ERASE_DISKS": device_path}), "setup-disk")
    time.sleep(2)

    root = root_partition(device_path)
    os.makedirs(TARGET, exist_ok=True)
    _must(hardware.run(["mount", root, TARGET], timeout=60), "mounting the new system")
    try:
        _step(log, "Adding PythonOS and its packages")
        packages = apk_packages()
        if packages:
            _must(hardware.run(["apk", "add", "--root", TARGET, "--keys-dir", "/etc/apk/keys", "--repositories-file", "/etc/apk/repositories",
                                "--no-progress"] + packages, timeout=1200), "adding packages")
        source = SOURCE
        if not os.path.isdir(source):
            raise InstallError("the live system has no /opt/pythonos to copy")
        shutil.copytree(source, os.path.join(TARGET, "opt", "pythonos"), dirs_exist_ok=True, symlinks=False,
                        ignore=shutil.ignore_patterns(".OSData", "files", "current_user.json", "users.json", "__pycache__"))

        _step(log, "Locking the system down")
        _write(os.path.join(TARGET, "etc", "inittab"), INITTAB, 0o644)
        _write(os.path.join(TARGET, "usr", "local", "bin", "pythonos-session"), SESSION, 0o755)
        _write(os.path.join(TARGET, "etc", "securetty"), "", 0o644)
        _write(os.path.join(TARGET, "etc", "sysctl.d", "90-pythonos.conf"), SYSCTL, 0o644)
        _write(os.path.join(TARGET, "etc", "hostname"), hostname + "\n", 0o644)
        _write(os.path.join(TARGET, "etc", "motd"), "PythonOS\n", 0o644)
        _write(os.path.join(TARGET, "etc", "network", "interfaces"), "auto lo\niface lo inet loopback\n\nauto eth0\niface eth0 inet dhcp\n", 0o644)
        for level, names in SERVICES.items():
            folder = os.path.join(TARGET, "etc", "runlevels", level)
            os.makedirs(folder, exist_ok=True)
            for name in names:
                link = os.path.join(folder, name)
                if not os.path.lexists(link) and os.path.exists(os.path.join(TARGET, "etc", "init.d", name)):
                    os.symlink(f"/etc/init.d/{name}", link)
        _lock_root(os.path.join(TARGET, "etc", "shadow"))
        _lock_bootloader()
        _verify()
    finally:
        hardware.run(["sync"])
        hardware.run(["umount", TARGET], timeout=60)
    _step(log, "Done. Remove the USB stick and restart the computer.")


def _write(path, text, mode):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.chmod(path, mode)


def _lock_root(shadow):
    """Root has no password hash at all (a '*' never matches), so it cannot log in even if a login were ever started."""
    try:
        with open(shadow, encoding="utf-8") as f:
            lines = f.read().splitlines()
    except OSError:
        raise InstallError("the new system has no /etc/shadow") from None
    out = []
    for line in lines:
        parts = line.split(":")
        if parts and parts[0] == "root" and len(parts) > 1:
            parts[1] = "*"
            line = ":".join(parts)
        out.append(line)
    with open(shadow, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")


def _lock_bootloader():
    extlinux = os.path.join(TARGET, "boot", "extlinux.conf")
    grub = os.path.join(TARGET, "boot", "grub", "grub.cfg")
    locked = False
    if os.path.isfile(extlinux):
        with open(extlinux, encoding="utf-8") as f:
            text = f.read()
        with open(extlinux, "w", encoding="utf-8", newline="\n") as f:
            f.write(lock_extlinux(text))
        locked = True
    if os.path.isfile(grub):
        pbkdf2 = _grub_hash()
        if not pbkdf2:
            raise InstallError("the boot menu could not be locked (grub-mkpasswd-pbkdf2 is missing), so the install was stopped: "
                               "anyone at an unlocked boot menu could open a shell")
        with open(grub, encoding="utf-8") as f:
            text = f.read()
        with open(grub, "w", encoding="utf-8", newline="\n") as f:
            f.write(lock_grub(text, pbkdf2))
        locked = True
    if not locked:
        raise InstallError("no boot loader configuration was found to lock")


def _verify():
    """The installed system must have exactly the lockdown properties the live ISO is checked for."""
    inittab = os.path.join(TARGET, "etc", "inittab")
    with open(inittab, encoding="utf-8") as f:
        active = [l for l in f.read().splitlines() if l.strip() and not l.lstrip().startswith("#")]
    if any(re.search(r"getty|login|/bin/a?sh|ttyS", l) for l in active):
        raise InstallError("verification failed: the inittab starts a login or a shell")
    if sum("pythonos-session" in l for l in active) != 1:
        raise InstallError("verification failed: the inittab must start exactly one PythonOS session")
    if os.path.getsize(os.path.join(TARGET, "etc", "securetty")) != 0:
        raise InstallError("verification failed: root may log in on a terminal")
    if not os.path.isfile(os.path.join(TARGET, "opt", "pythonos", "main.py")):
        raise InstallError("verification failed: PythonOS is missing from the new system")
