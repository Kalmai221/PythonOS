#!/usr/bin/env bash
# Build a bootable PythonOS live ISO (x86_64, BIOS + UEFI):  dist/iso/pythonos-<version>-x86_64.iso
#
#   VERSION=1.2.0 bash OS_Export/ISO/build-iso.sh
#
# Needs: Linux with Docker, python3 and pip. The image is built with Alpine Linux's own
# "mkimage" tooling inside an Alpine container, so nothing is installed on the host.
#
# Kernel: ISO_KERNEL=lts (default, normal PCs) or ISO_KERNEL=virt (much smaller, virtual machines only).
# ISO_FIRMWARE=1 adds back the large firmware bundle (Wi-Fi and some network cards).
#
# What you get: a live system (runs from RAM) that boots straight into PythonOS and powers
# off when you shut PythonOS down. Anything you create is lost at power off - it is a live CD.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="${OUT:-$REPO/dist/iso}"
ALPINE="${ALPINE_VERSION:-3.19}"
VERSION="$(python3 "$REPO/OS_Export/stage.py" --print-version)"

command -v docker >/dev/null 2>&1 || { echo "Docker is required to build the ISO." >&2; exit 1; }

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$OUT"
chmod 777 "$OUT"

# The OS plus the pure-Python dependencies Alpine does not package (the rest come from apk)
python3 "$REPO/OS_Export/stage.py" "$WORK/payload" --vendor yaspin ping3
chmod -R a+rX "$WORK/payload"

docker run --rm \
    -e ALPINE_VERSION="$ALPINE" -e ISO_VERSION="$VERSION" -e ISO_KERNEL="${ISO_KERNEL:-lts}" -e ISO_FIRMWARE="${ISO_FIRMWARE:-0}" \
    -v "$WORK/payload:/payload:ro" \
    -v "$HERE:/iso:ro" \
    -v "$OUT:/out" \
    "alpine:$ALPINE" sh /iso/in-container.sh

ISO_FILE="$(ls -t "$OUT"/*.iso | head -n1)"
FINAL="$OUT/pythonos-$VERSION-x86_64.iso"
[ "$ISO_FILE" = "$FINAL" ] || mv "$ISO_FILE" "$FINAL"
ls -la "$OUT"
echo "Built $FINAL"
echo "Kernel: ${ISO_KERNEL:-lts}   Size: $(du -h "$FINAL" | cut -f1)"
echo "Try it:  qemu-system-x86_64 -m 1024 -cdrom '$FINAL'"
