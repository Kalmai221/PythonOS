#!/usr/bin/env python3
"""Checks the virtual machine images that OS_Export/ISO/vm/make-images.sh made, without starting a VM (CI runs it right after make-images.sh).

    python tools/check_vm_images.py <folder with the images> <version>

  * the .ova is a tar whose FIRST member is the .ovf (VirtualBox and VMware read it that way), the .ovf is well-formed XML, every file it lists is in
    the tar with the size it says, every disk is a stream-optimised VMDK ("KDMV"), and the three disks of the appliance are there
  * the .qcow2 files are qcow2 ("QFI") and the data disk holds an ext4 filesystem labelled PYOS_DATA (needs qemu-img to read it; skipped without)
  * the kit zip holds the run and create scripts
A problem is printed and makes the exit code 1; nothing is changed.
"""
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import xml.etree.ElementTree as ET
import zipfile

KIT_FILES = {"README.md", "run-qemu.sh", "run-qemu.ps1", "create-virtualbox.sh", "create-virtualbox.ps1", "pythonos.vmx"}
OVF_NS = "{http://schemas.dmtf.org/ovf/envelope/1}"
LABEL = b"PYOS_DATA"


def check_ova(path, version, problems):
    with tarfile.open(path) as tar:
        names = tar.getnames()
        if not names or not names[0].endswith(".ovf"):
            problems.append(f"{os.path.basename(path)}: the first file in the archive must be the .ovf, it is {names[:1]}")
            return
        try:
            root = ET.fromstring(tar.extractfile(names[0]).read())
        except ET.ParseError as e:
            problems.append(f"{names[0]}: not well-formed XML ({e})")
            return
        files = {f.get(OVF_NS + "href"): int(f.get(OVF_NS + "size", "0")) for f in root.iter(OVF_NS + "File")}
        if len(files) != 3:
            problems.append(f"{names[0]}: expected 3 disks (system, data, spare), it lists {len(files)}")
        for href, size in files.items():
            if href not in names:
                problems.append(f"{names[0]} lists {href}, which is not in the archive")
                continue
            member = tar.getmember(href)
            if size and member.size != size:
                problems.append(f"{href}: the .ovf says {size} bytes, the archive holds {member.size}")
            if tar.extractfile(href).read(4) != b"KDMV":
                problems.append(f"{href}: not a stream-optimised VMDK (no KDMV signature)")
        for disk in root.iter(OVF_NS + "Disk"):
            if int(disk.get(OVF_NS + "capacity", "0")) <= 0:
                problems.append(f"{names[0]}: a disk has no capacity")
        system = next(root.iter(OVF_NS + "VirtualSystem"), None)
        if system is None or system.get(OVF_NS + "id") != f"PythonOS {version}":
            problems.append(f"{names[0]}: the virtual machine must be named 'PythonOS {version}' (it is named after its version)")


def check_qcow2(path, problems):
    with open(path, "rb") as f:
        if f.read(4) != b"QFI\xfb":
            problems.append(f"{os.path.basename(path)}: not a qcow2 image")


def check_data_label(path, problems):
    """The data disk must hold an ext4 filesystem labelled PYOS_DATA: the live system finds it by that label."""
    qemu_img = shutil.which("qemu-img")
    if not qemu_img:
        print("skip  data disk label (qemu-img is not installed)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        raw = os.path.join(tmp, "data.raw")
        subprocess.run([qemu_img, "convert", "-f", "qcow2", "-O", "raw", path, raw], check=True, capture_output=True)
        with open(raw, "rb") as f:
            f.seek(1024)                                    # the ext4 superblock
            block = f.read(1024)
    if block[56:58] != b"\x53\xef":
        problems.append(f"{os.path.basename(path)}: no ext4 filesystem on the data disk")
    elif block[120:136].rstrip(b"\0") != LABEL:
        problems.append(f"{os.path.basename(path)}: the data disk is labelled {block[120:136].rstrip(bytes(1))!r}, not PYOS_DATA")


def check_kit(path, problems):
    with zipfile.ZipFile(path) as z:
        missing = KIT_FILES - set(z.namelist())
    if missing:
        problems.append(f"{os.path.basename(path)}: missing {sorted(missing)}")


def main(argv):
    if len(argv) != 3:
        print(__doc__)
        return 2
    folder, version = argv[1], argv[2]
    problems = []
    wanted = {
        "ova": f"pythonos-{version}-vm.ova", "qcow2": f"pythonos-{version}-vm.qcow2",
        "data": f"pythonos-{version}-vm-data.qcow2", "kit": f"pythonos-{version}-vm-kit.zip",
    }
    for key, name in wanted.items():
        if not os.path.isfile(os.path.join(folder, name)):
            problems.append(f"{name} was not made")
    if not problems:
        check_ova(os.path.join(folder, wanted["ova"]), version, problems)
        check_qcow2(os.path.join(folder, wanted["qcow2"]), problems)
        check_qcow2(os.path.join(folder, wanted["data"]), problems)
        check_data_label(os.path.join(folder, wanted["data"]), problems)
        check_kit(os.path.join(folder, wanted["kit"]), problems)
    for p in problems:
        print("PROBLEM", p)
    if not problems:
        print("The virtual machine images look right.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
