#!/usr/bin/env python3
"""Checks the recovery tools: the emergency console, offline crash reports, safe mode and the boot menu (in a temporary folder)."""
import os
import sys
import tempfile
import zipfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def main():
    work = tempfile.mkdtemp(prefix="pyos-recovery-")
    os.chdir(work)
    sys.path.insert(0, REPO)
    os.environ["PYOS_BUNDLED"] = "1"
    import pyos
    import pyos.fs as fs
    from core import bootmenu, emergency, liveboot
    from pyos import report, safemode
    fs.ensure_layout()

    # offline crash report: written at the crash, redacted, listed, read back, then handled
    path = report.save_pending("PythonOS crashed: TEST_ERROR: something broke")
    assert path and os.path.exists(path)
    assert [n for n, _p in report.pending()] == [os.path.basename(path)]
    title, body = report.read_pending(path)
    assert title.startswith("PythonOS crashed") and "## Versions" in body
    report.finish_pending(path)
    assert report.pending() == [] and os.path.exists(os.path.join(os.path.dirname(path), "done", os.path.basename(path)))

    # the emergency console: log and crash reading, the zip, the safe-mode switch
    os.makedirs(emergency.log_dir(), exist_ok=True)
    pyos.log.log("emergency test line")
    with open(os.path.join(emergency.log_dir(), "crash-20260101-000000.log"), "w") as f:
        f.write("Traceback...\nValueError: boom\n")
    with open(os.path.join(emergency.log_dir(), "notes.txt"), "w") as f:
        f.write("must never be listed")
    assert emergency.crash_reports() == ["crash-20260101-000000.log"]
    assert emergency.handle("status") is True and emergency.handle("logs 5") is True and emergency.handle("crashes") is True
    assert emergency.handle("crash 1") is True and emergency.handle("nonsense") is True
    assert emergency.handle("quit") is False
    assert not emergency.safe_flag()
    emergency.handle("safe on")
    assert emergency.safe_flag()
    emergency.handle("safe off")
    assert not emergency.safe_flag()
    zipped = emergency.bundle()
    with zipfile.ZipFile(zipped) as z:
        names = z.namelist()
    assert "system.log" in names and "diagnostics.txt" in names and "crash-20260101-000000.log" in names and "notes.txt" not in names
    assert not any("users" in n or "hardware" in n for n in names), "accounts and saved Wi-Fi keys must never go into the bundle"

    # USB partitions: only removable, unmounted, writable filesystems
    def dev(name, kind, fs_type="", mounts=(), removable=False, parent=None):
        return {"name": name, "path": "/dev/" + name, "type": kind, "size": 8 * 1024 ** 3, "fstype": fs_type, "label": "", "mounts": list(mounts),
                "removable": removable, "model": "", "parent": parent}
    stick = dev("sdb", "disk", removable=True)
    good = dev("sdb1", "part", "vfat", parent=stick)
    busy = dev("sdb2", "part", "vfat", mounts=["/mnt/x"], parent=stick)
    fixed = dev("sda", "disk")
    internal = dev("sda1", "part", "ext4", parent=fixed)
    iso = dev("sdb3", "part", "iso9660", parent=stick)
    assert [d["path"] for d in emergency.usb_partitions([stick, good, busy, fixed, internal, iso])] == ["/dev/sdb1"]

    # safe mode keeps marketplace apps out and the shell quiet
    import shell
    os.makedirs(os.path.join("files", "installed_x", "app"), exist_ok=True)
    with open(os.path.join("files", "installed_x", "app", "data.json"), "w") as f:
        f.write('{"command": "zzapp", "scripts": {"run": "run.py"}}')
    with open(os.path.join("files", "installed_x", "app", "run.py"), "w") as f:
        f.write("print(1)")
    os.environ.pop("PYOS_SAFE", None)
    assert "zzapp" in shell.load_installed_packages("files")
    safemode.turn_on()
    assert safemode.enabled() and shell.load_installed_packages("files") == {} and liveboot.light_mode()
    os.environ.pop("PYOS_SAFE", None)

    # the boot menu
    answers = iter(["", ])
    assert bootmenu.show(lambda prompt: next(answers)) == "normal"
    assert bootmenu.show(lambda prompt: "2") == "safe" and bootmenu.show(lambda prompt: "3") == "diagnostics"
    picks = iter(["9", "1"])
    assert bootmenu.show(lambda prompt: next(picks)) == "normal"
    assert liveboot.keys_pressed("dm", 0.1) is None          # not a terminal: never waits
    print("recovery tools: all checks passed")


if __name__ == "__main__":
    sys.exit(main() or 0)
