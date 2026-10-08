#!/usr/bin/env bash
# Create a VirtualBox VM called "PythonOS" that boots the ISO, with a 2 GB data disk so your accounts and files are kept.
#   ./create-virtualbox.sh pythonos-<version>-x86_64.iso [--no-data]
#   --no-data   do not create the data disk (the live system then forgets everything at power off)
# The data disk is PythonOS-data.vdi, created next to where you run this; keep that file. The first time, run `persist create` inside PythonOS.
set -euo pipefail

ISO="${1:-}"
[ -f "$ISO" ] || { echo "Usage: $0 <pythonos .iso> [--no-data]" >&2; exit 2; }
command -v VBoxManage >/dev/null || { echo "VirtualBox (VBoxManage) is not installed." >&2; exit 1; }
ISO="$(cd "$(dirname "$ISO")" && pwd)/$(basename "$ISO")"
NAME="PythonOS"

VBoxManage showvminfo "$NAME" >/dev/null 2>&1 && { echo "A VM called $NAME already exists. Remove it first (VBoxManage unregistervm $NAME --delete)." >&2; exit 1; }

VBoxManage createvm --name "$NAME" --ostype Linux26_64 --register
VBoxManage modifyvm "$NAME" --memory 1024 --cpus 2 --vram 16 --graphicscontroller vmsvga \
    --firmware efi --nic1 nat --nictype1 virtio --audio-driver default --audio-controller ac97 --rtcuseutc on
VBoxManage storagectl "$NAME" --name "IDE" --add ide
VBoxManage storageattach "$NAME" --storagectl "IDE" --port 0 --device 0 --type dvddrive --medium "$ISO"

if [ "${2:-}" != "--no-data" ]; then
    DATA="$PWD/PythonOS-data.vdi"
    [ -f "$DATA" ] || VBoxManage createmedium disk --filename "$DATA" --size 2048 --format VDI >/dev/null
    VBoxManage storagectl "$NAME" --name "SATA" --add sata
    VBoxManage storageattach "$NAME" --storagectl "SATA" --port 0 --device 0 --type hdd --medium "$DATA"
    echo "Data disk: $DATA (keep it; the first time, run 'persist create' inside PythonOS)"
fi
echo "Created. Start it with:  VBoxManage startvm $NAME      (or from the VirtualBox window)"
