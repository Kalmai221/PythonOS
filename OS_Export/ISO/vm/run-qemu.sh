#!/usr/bin/env bash
# Boot PythonOS in QEMU.   ./run-qemu.sh <pythonos .iso or .qcow2> [--disk]
#   <file>   the ISO (boots like a CD), or the pythonos-<version>-vm.qcow2 disk image (boots like a disk)
#   --disk   also attach a 2 GB data disk (pythonos-data.img, created once) so `persist create` has somewhere to keep your files
#            (not needed with the ready-made pythonos-<version>-vm-data.qcow2: attach that yourself as a second -drive)
set -euo pipefail

IMAGE="${1:-}"
[ -f "$IMAGE" ] || { echo "Usage: $0 <pythonos .iso or .qcow2> [--disk]" >&2; exit 2; }
command -v qemu-system-x86_64 >/dev/null || { echo "QEMU is not installed (qemu-system-x86_64)." >&2; exit 1; }

ARGS=(-m 1024 -smp 2
      -nic user,model=virtio-net-pci
      -device virtio-rng-pci
      -chardev socket,id=qga0,path=/tmp/pythonos-qga.sock,server=on,wait=off
      -device virtio-serial -device virtserialport,chardev=qga0,name=org.qemu.guest_agent.0)

case "$IMAGE" in
    *.qcow2) ARGS+=(-drive "file=$IMAGE,format=qcow2" -boot c) ;;
    *.vmdk)  ARGS+=(-drive "file=$IMAGE,format=vmdk" -boot c) ;;
    *)       ARGS+=(-cdrom "$IMAGE" -boot d) ;;
esac

# hardware acceleration when the computer has it
if [ -w /dev/kvm ]; then ARGS+=(-enable-kvm -cpu host); fi
case "$(uname -s)" in Darwin) ARGS+=(-accel hvf) ;; esac

if [ "${2:-}" = "--disk" ]; then
    [ -f pythonos-data.img ] || qemu-img create -f qcow2 pythonos-data.img 2G >/dev/null
    ARGS+=(-drive file=pythonos-data.img,if=virtio,format=qcow2)
fi

exec qemu-system-x86_64 "${ARGS[@]}"
