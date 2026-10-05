# Compatibility

What PythonOS runs on, and how much of that is actually tested. "CI" means the release workflow builds it on GitHub's machines;
"smoke" means a script starts PythonOS and checks it answers; "by hand" means a person tried it. Anything not marked is not tested.

| Platform | Minimum | Built by CI | Tested how |
|---|---|---|---|
| Windows app (installer, portable) | Windows 10 (64-bit) | yes | installer compiled in CI; started by hand on Windows 11 |
| Android app | Android 7.0 (API 24), arm64 or x86_64 | yes | built in CI; used by hand on a phone |
| Linux package (.deb, .tar.gz) | any Linux with Python 3.9+ | yes | smoke on Ubuntu in CI |
| Bootable ISO, full and minimal | 64-bit PC, 1 GB RAM (512 MB works in light mode), BIOS or UEFI | yes | built and lockdown-checked in CI; booted in QEMU in CI; real hardware by hand only |
| Virtual machine images (.ova, .qcow2) | VirtualBox 6+, VMware 15+, QEMU 5+ | yes | made from the ISO in CI; imported by hand |
| Docker image | linux/amd64 | yes | smoke in CI |
| `installos` (install to disk) | the full ISO, a disk of at least 2 GB | built in the ISO | experimental: virtual machines only |
| Python (running from source) | 3.9 or newer | - | developed on 3.12 to 3.14 |

Secure Boot: the ISO is not signed for Secure Boot; turn it off in the firmware or use legacy/CSM boot.
ARM computers (Raspberry Pi and similar): no ISO yet; the Linux package and Docker image work.
