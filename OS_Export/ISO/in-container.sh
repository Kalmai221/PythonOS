#!/bin/sh
# Runs inside the Alpine container started by build-iso.sh. Builds the ISO with mkimage.
set -eu

ALPINE="${ALPINE_VERSION:-3.19}"
KERNEL="${ISO_KERNEL:-lts}"
FIRMWARE="${ISO_FIRMWARE:-0}"
case "$KERNEL" in
    virt|lts) ;;
    *) echo "ISO_KERNEL must be 'virt' or 'lts' (got '$KERNEL')" >&2; exit 1 ;;
esac
MIRROR="https://dl-cdn.alpinelinux.org/alpine/v$ALPINE"

apk add --no-cache alpine-sdk alpine-conf abuild xorriso squashfs-tools syslinux \
    grub grub-efi grub-bios mtools dosfstools git sudo

# mkimage must run as a normal user that owns a package-signing key
adduser -D build
addgroup build abuild
echo "build ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/build
su build -c "abuild-keygen -a -n"
cp /home/build/.abuild/*.rsa.pub /etc/apk/keys/

# gitlab.alpinelinux.org blocks some CI networks (HTTP 418), so try the official GitHub
# mirror first and retry a few times before giving up.
cloned=""
for attempt in 1 2 3; do
    for url in https://github.com/alpinelinux/aports.git https://gitlab.alpinelinux.org/alpine/aports.git; do
        rm -rf /home/build/aports
        if su build -c "git clone --quiet --depth=1 --branch ${ALPINE}-stable $url /home/build/aports"; then
            cloned=yes
            break 2
        fi
        echo "Could not clone aports from $url (attempt $attempt)" >&2
    done
    sleep 10
done
[ -n "$cloned" ] || { echo "Could not download Alpine's aports (mkimage scripts)." >&2; exit 1; }
cp /iso/mkimg.pythonos.sh /iso/genapkovl-pythonos.sh /home/build/aports/scripts/
# mkimage runs the overlay script directly (through fakeroot), so it must be executable;
# a checkout from Windows does not preserve the executable bit.
chmod 755 /home/build/aports/scripts/genapkovl-pythonos.sh /home/build/aports/scripts/mkimg.pythonos.sh
# Alpine's mkimage hard-codes the full firmware bundle into every kernel module image
# ("linux-$_f linux-firmware wireless-regdb"), which is most of the ISO's size and build time and
# cannot be switched off from a profile. Swap it for the empty linux-firmware-none package.
if [ "$FIRMWARE" != "1" ]; then
    BASE=/home/build/aports/scripts/mkimg.base.sh
    if grep -q 'linux-firmware wireless-regdb' "$BASE"; then
        sed -i 's/linux-firmware wireless-regdb/linux-firmware-none/' "$BASE"
        echo "Firmware bundle left out of the kernel modules image (ISO_FIRMWARE=1 keeps it)."
    else
        echo "WARNING: mkimg.base.sh no longer lists linux-firmware; the ISO will be larger than expected." >&2
    fi
fi
mkdir -p /home/build/overlay
cp -R /iso/overlay/. /home/build/overlay/
chown -R build:build /home/build/aports /home/build/overlay

su build -c "cd /home/build/aports/scripts && \
    PYTHONOS_PAYLOAD=/payload PYTHONOS_OVERLAY=/home/build/overlay PYTHONOS_KERNEL=$KERNEL PYTHONOS_FIRMWARE=$FIRMWARE \
    sh mkimage.sh \
        --tag 'v$ALPINE' \
        --outdir /out \
        --workdir /home/build/work \
        --arch x86_64 \
        --repository $MIRROR/main \
        --repository $MIRROR/community \
        --profile pythonos"

ls -la /out
