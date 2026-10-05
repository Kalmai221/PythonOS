# Compatibility

What PythonOS runs on, and how much of that is actually tested. "CI" means the release workflow builds it on GitHub's machines;
"smoke" means a script starts PythonOS and checks it answers; "by hand" means a person tried it. Anything not marked is not tested.

| Platform | Minimum | Built by CI | Tested how |
|---|---|---|---|
| Windows app (installer, portable), Intel/AMD | Windows 10 1809 (64-bit) | yes | installer compiled in CI; started by hand on Windows 11 |
| Windows app, ARM64 | Windows 10 1809 on ARM | yes (assembled from ARM64 Python and wheels) | **not run on an ARM PC** |
| Android app | Android 7.0 (API 24), arm64 or x86_64 | yes | built in CI; used by hand on a phone |
| Linux packages (.deb, Arch .pkg.tar.zst, .rpm, .tar.gz) | any Linux with Python 3.9+, any processor (the packages are architecture independent) | yes | smoke on Ubuntu x86_64 in CI; the other formats are built, not installed |
| Bootable ISO x86_64, full and minimal | 64-bit PC, 1 GB RAM (512 MB works in light mode), BIOS or UEFI | yes | built and lockdown-checked in CI; booted in QEMU in CI (informational); real hardware by hand only |
| Bootable ISO aarch64, full and minimal | 64-bit ARM with UEFI, 1 GB RAM | yes (on GitHub's ARM runners) | built and lockdown-checked in CI; **never booted** |
| Virtual machine images (.ova, .qcow2) | VirtualBox 6+, VMware 15+, QEMU 5+ | yes | made from the ISO in CI; imported by hand |
| Docker image | linux/amd64 and linux/arm64 | yes | amd64 smoke-tested in CI; arm64 built under emulation |
| `installos` (install to disk) | the full ISO, a disk of at least 2 GB | built in the ISO | experimental: virtual machines only |
| Python (running from source) | 3.9 or newer | - | developed on 3.12 to 3.14 |

Secure Boot: the ISO is not signed for Secure Boot; turn it off in the firmware or use legacy/CSM boot.
ARM: the aarch64 ISO needs UEFI firmware (many ARM servers and VMs; a Raspberry Pi 4/5 with the UEFI firmware installed). A Pi booting from its own firmware cannot use an ISO: use the Linux package or the Docker image.
Android: arm64-v8a and x86_64, the processors Chaquopy supports for Python 3.13 (32-bit ARM and x86 are not available for it).
