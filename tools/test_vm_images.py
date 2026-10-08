#!/usr/bin/env python3
"""tools/check_vm_images.py: it accepts good images and names what is wrong with bad ones. The images are built by hand here (no qemu-img, no VM),
and the .ovf is the real one that OS_Export/ISO/vm/make-images.sh writes (its template, filled in). Also the kit scripts must parse."""
import io
import os
import re
import string
import subprocess
import sys
import tarfile
import tempfile
import zipfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, os.path.join(REPO, "tools"))

import check_vm_images as c  # noqa: E402

VERSION = "9.9.9"


def real_ovf(sizes):
    """The OVF that make-images.sh writes, with its shell variables filled in."""
    with open(os.path.join(REPO, "OS_Export", "ISO", "vm", "make-images.sh"), encoding="utf-8") as f:
        script = f.read()
    template = re.search(r"<<EOF\n(.*?)\nEOF\n", script, re.S).group(1)
    values = {"VERSION": VERSION, "DISK": f"pythonos-{VERSION}-disk1.vmdk", "DATA": f"pythonos-{VERSION}-data.vmdk",
              "SPARE": f"pythonos-{VERSION}-spare.vmdk", "BYTES": "1000", "DATA_BYTES": "2000", "SPARE_BYTES": "8000",
              "FILE_SIZE": str(sizes[0]), "DATA_FILE_SIZE": str(sizes[1]), "SPARE_FILE_SIZE": str(sizes[2])}
    return string.Template(template).safe_substitute(values), values


def make_ova(path, ovf_first=True, wrong_size=False, bad_disk=False):
    disks = {}
    for i, key in enumerate(("DISK", "DATA", "SPARE")):
        disks[key] = (b"KDMV" if not (bad_disk and key == "DATA") else b"XXXX") + bytes(100 + i)
    sizes = [len(disks["DISK"]) + (5 if wrong_size else 0), len(disks["DATA"]), len(disks["SPARE"])]
    ovf, values = real_ovf(sizes)
    members = [(f"pythonos-{VERSION}.ovf", ovf.encode())] + [(values[k], disks[k]) for k in ("DISK", "DATA", "SPARE")]
    if not ovf_first:
        members.reverse()
    with tarfile.open(path, "w") as tar:
        for name, data in members:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))


def problems_of(**kw):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "x.ova")
        make_ova(path, **kw)
        found = []
        c.check_ova(path, VERSION, found)
        return found


def main():
    assert problems_of() == [], problems_of()
    assert any("first file" in p for p in problems_of(ovf_first=False)), "the .ovf must come first in the archive"
    assert any("says" in p for p in problems_of(wrong_size=True)), "a size that differs from the .ovf is caught"
    assert any("KDMV" in p for p in problems_of(bad_disk=True)), "a disk that is not a VMDK is caught"
    with tempfile.TemporaryDirectory() as tmp:
        good = os.path.join(tmp, "a.qcow2")
        with open(good, "wb") as f:
            f.write(b"QFI\xfb" + bytes(100))
        found = []
        c.check_qcow2(good, found)
        assert found == []
        with open(good, "wb") as f:
            f.write(b"nope")
        c.check_qcow2(good, found)
        assert found
        kit = os.path.join(tmp, "kit.zip")
        with zipfile.ZipFile(kit, "w") as z:
            for n in c.KIT_FILES:
                z.writestr(n, "x")
        found = []
        c.check_kit(kit, found)
        assert found == []
        with zipfile.ZipFile(kit, "w") as z:
            z.writestr("README.md", "x")
        c.check_kit(kit, found)
        assert found and "run-qemu.sh" in found[0]
        # the whole thing through main(): a folder with nothing in it reports every image missing
        assert c.main(["check", tmp, VERSION]) == 1
    # the kit scripts: bash must parse them, and PowerShell must not have been given $args (an automatic variable) as a variable of its own
    vm = os.path.join(REPO, "OS_Export", "ISO", "vm")
    for name in () if os.name == "nt" else ("run-qemu.sh", "create-virtualbox.sh", "make-images.sh"):
        result = subprocess.run(["bash", "-n", os.path.join(vm, name)], capture_output=True, text=True)
        assert result.returncode == 0, (name, result.stderr)
    for name in ("run-qemu.ps1", "create-virtualbox.ps1"):
        with open(os.path.join(vm, name), encoding="utf-8") as f:
            assert not re.search(r"^\s*\$args\s*[+=]", f.read(), re.M), f"{name}: do not assign to $args"
    print("vm images: all checks passed")


if __name__ == "__main__":
    main()
