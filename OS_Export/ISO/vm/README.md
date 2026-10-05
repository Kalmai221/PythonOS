# Try PythonOS in a virtual machine

No USB stick needed. The scripts here set up a ready-made VM that boots the PythonOS ISO. Use the **full** ISO: it includes the guest tools
(QEMU/KVM, VMware and VirtualBox) that make the mouse-less console, clipboard, time and shutdown work nicely in a VM.

| Program | How |
|---|---|
| QEMU / KVM | `./run-qemu.sh pythonos-<version>-x86_64.iso`  (Windows: `./run-qemu.ps1 <iso>`) |
| VirtualBox | `./create-virtualbox.sh <iso>`  (Windows: `./create-virtualbox.ps1 <iso>`), then start "PythonOS" |
| VMware (Workstation / Fusion / Player) | open `pythonos.vmx` after putting the ISO next to it as `pythonos.iso` |

All of them give the VM 1 GB of memory, 1 CPU core or more, a network card (so updates and the marketplace work) and sound.
The live system forgets everything at power off. To keep your files in a VM, attach a second (empty) virtual disk and run
`persist create` inside PythonOS; the QEMU script can add one for you with `--disk` (a file named `pythonos-data.img`, 2 GB, created once).

PythonOS needs UEFI **or** BIOS, both work. If the screen stays black in VirtualBox, set Display → Graphics Controller to VMSVGA.
