# Try PythonOS in a virtual machine

No USB stick needed. The scripts here set up a ready-made VM that boots the PythonOS ISO. Use the **full** ISO: it includes the guest tools
(QEMU/KVM, VMware and VirtualBox) that make the mouse-less console, clipboard, time and shutdown work nicely in a VM.

| Program | How |
|---|---|
| QEMU / KVM | `./run-qemu.sh pythonos-<version>-x86_64.iso`  (Windows: `./run-qemu.ps1 <iso>`). It also boots the `-vm.qcow2` disk image: `./run-qemu.sh pythonos-<version>-vm.qcow2` |
| VirtualBox | `./create-virtualbox.sh <iso>`  (Windows: `./create-virtualbox.ps1 <iso>`), then start "PythonOS". It also creates a 2 GB data disk (`PythonOS-data.vdi`, keep it) so your files are kept; add `--no-data` (Windows: `-NoData`) to skip it |
| VMware (Workstation / Fusion / Player) | open `pythonos.vmx` after putting the ISO next to it as `pythonos.iso` |

All of them give the VM 1 GB of memory, 1 CPU core or more, a network card (so updates and the marketplace work) and sound.
The live system forgets everything at power off, unless a data disk is attached. The `.ova` already includes one (a second 2 GB disk labelled PYOS_DATA, plus a third, empty 8 GB disk that `installos` can install PythonOS on), so accounts, files and settings are kept between runs; keep that disk when you move or clone the VM. With the `.qcow2`, attach
`pythonos-<version>-vm-data.qcow2` as a second disk (it is the same ready-made data disk). With your own VM, attach a second (empty) virtual disk and run
`persist create` inside PythonOS; the QEMU script can add one for you with `--disk` (a file named `pythonos-data.img`, 2 GB, created once).

PythonOS needs UEFI **or** BIOS, both work. If the screen stays black in VirtualBox, set Display → Graphics Controller to VMSVGA.

## Importing a newer version

The virtual machine is named after its version (`PythonOS 1.0.12`), so importing a newer `.ova` does not collide with an older one. If VirtualBox says *"Machine settings file ... already exists"*, a machine with that name is already there: change the **Name** in the import dialog, or remove the old machine first (right-click it, **Remove**, **Delete all files**; copy anything you want from its data disk first).
