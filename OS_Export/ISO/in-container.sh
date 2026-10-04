#!/bin/sh
# Runs inside the Alpine container started by build-iso.sh. Builds the ISO with mkimage.
set -eu

ALPINE="${ALPINE_VERSION:-3.19}"
MIRROR="https://dl-cdn.alpinelinux.org/alpine/v$ALPINE"

apk add --no-cache alpine-sdk alpine-conf abuild xorriso squashfs-tools syslinux \
    grub grub-efi grub-bios mtools dosfstools git sudo

# mkimage must run as a normal user that owns a package-signing key
adduser -D build
addgroup build abuild
echo "build ALL=(ALL) NOPASSWD: ALL" > /etc/sudoers.d/build
su build -c "abuild-keygen -a -n"
cp /home/build/.abuild/*.rsa.pub /etc/apk/keys/

su build -c "git clone --quiet --depth=1 --branch ${ALPINE}-stable https://gitlab.alpinelinux.org/alpine/aports.git /home/build/aports"
cp /iso/mkimg.pythonos.sh /iso/genapkovl-pythonos.sh /home/build/aports/scripts/
mkdir -p /home/build/overlay
cp -R /iso/overlay/. /home/build/overlay/
chown -R build:build /home/build/aports /home/build/overlay

su build -c "cd /home/build/aports/scripts && \
    PYTHONOS_PAYLOAD=/payload PYTHONOS_OVERLAY=/home/build/overlay \
    sh mkimage.sh \
        --tag 'v$ALPINE' \
        --outdir /out \
        --workdir /home/build/work \
        --arch x86_64 \
        --repository $MIRROR/main \
        --repository $MIRROR/community \
        --profile pythonos"

ls -la /out
