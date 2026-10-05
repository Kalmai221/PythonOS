#!/usr/bin/env bash
# Boot the PythonOS ISO in QEMU.   ./run-qemu.sh pythonos-<version>-x86_64.iso [--disk]
#   --disk   also attach a 2 GB data disk (pythonos-data.img, created once) so `persist create` has somewhere to keep your files
set -euo pipefail

ISO="${1:-}"
[ -f "$ISO" ] || { echo "Usage: $0 <pythonos .iso> [--disk]" >&2; exit 2; }
command -v qemu-system-x86_64 >/dev/null || { echo "QEMU is not installed (qemu-system-x86_64)." >&2; exit 1; }

ARGS=(-m 1024 -smp 2 -cdrom "$ISO" -boot d
      -nic user,model=virtio-net-pci
      -device virtio-rng-pci
      -chardev socket,id=qga0,path=/tmp/pythonos-qga.sock,server=on,wait=off
      -device virtio-serial -device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0)

# hardware acceleration when the computer has it
if [ -w /dev/kvm ]; then ARGS+=(-enable-kvm -cpu host); fi
case "$(uname -s)" in Darwin) ARGS+=(-accel hvf) ;; esac

if [ "${2:-}" = "--disk" ]; then
    [ -f pythonos-data.img ] || qemu-img create -f qcow2 pythonos-data.img 2G >/dev/null
    ARGS+=(-drive file=pythonos-data.img,if=virtio,format=qcow2)
fi

exec qemu-system-x86_64 "${ARGS[@]}"
