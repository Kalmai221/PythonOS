#!/bin/sh
# Runs inside the Alpine container started by build-iso.sh. Builds the ISO with mkimage.
set -eu

ALPINE="${ALPINE_VERSION:-3.19}"
KERNEL="${ISO_KERNEL:-lts}"
ARCH="${ISO_ARCH:-x86_64}"
case "$ARCH" in
    x86_64|aarch64) ;;
    *) echo "ISO_ARCH must be 'x86_64' or 'aarch64' (got '$ARCH')" >&2; exit 1 ;;
esac
VARIANT="${ISO_VARIANT:-full}"
case "$VARIANT" in
    full|minimal) ;;
    *) echo "ISO_VARIANT must be 'full' or 'minimal' (got '$VARIANT')" >&2; exit 1 ;;
esac
case "$KERNEL" in
    virt|lts) ;;
    *) echo "ISO_KERNEL must be 'virt' or 'lts' (got '$KERNEL')" >&2; exit 1 ;;
esac
MIRROR="https://dl-cdn.alpinelinux.org/alpine/v$ALPINE"

mkdir -p /var/cache/apk && ln -sf /var/cache/apk /etc/apk/cache      # downloads are kept here when the host mounts it
# The build tools. syslinux and grub-bios (the BIOS boot loader) exist only for PCs; an ARM image boots through UEFI and GRUB alone.
TOOLS="alpine-sdk alpine-conf abuild xorriso squashfs-tools grub grub-efi mtools dosfstools git sudo"
[ "$ARCH" = "x86_64" ] && TOOLS="$TOOLS syslinux grub-bios"
apk add $TOOLS

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
mkdir -p /home/build/overlay
cp -R /iso/overlay/. /home/build/overlay/
chown -R build:build /home/build/aports /home/build/overlay

# GRUB menu lock: editing entries / the GRUB command line needs this password. It is random, used
# once to make the hash and then thrown away - nobody ever knows it, so the lock cannot be opened.
GRUB_PW="$(head -c 64 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 40)"
GRUB_HASH="$(printf '%s\n%s\n' "$GRUB_PW" "$GRUB_PW" | grub-mkpasswd-pbkdf2 2>/dev/null | grep 'grub.pbkdf2' | awk '{print $NF}')"
unset GRUB_PW
case "$GRUB_HASH" in
    grub.pbkdf2.sha512.*) ;;
    *) echo "Could not create the GRUB menu lock - refusing to build an unlocked ISO." >&2; exit 1 ;;
esac

su build -c "cd /home/build/aports/scripts && \
    PYTHONOS_PAYLOAD=/payload PYTHONOS_OVERLAY=/home/build/overlay PYTHONOS_KERNEL=$KERNEL PYTHONOS_VARIANT=$VARIANT PYTHONOS_ARCH=$ARCH \
    PYTHONOS_GRUB_PBKDF2=$GRUB_HASH \
    sh mkimage.sh \
        --tag 'v$ALPINE' \
        --outdir /out \
        --workdir /home/build/work \
        --arch $ARCH \
        --repository $MIRROR/main \
        --repository $MIRROR/community \
        --profile pythonos"

ls -la /out

# ---------------------------------------------------------------------------------------------
# Check the finished image. The whole point of this ISO is that nobody can get to the Linux side
# underneath PythonOS, so if any of these properties is missing the build must fail.
# ---------------------------------------------------------------------------------------------
fail() { echo "LOCKDOWN CHECK FAILED: $1" >&2; exit 1; }
ISO_FILE="$(ls /out/*.iso | head -n1)"
V=/tmp/verify
rm -rf "$V"; mkdir -p "$V"
xorriso -osirrox on -indev "$ISO_FILE" -extract / "$V/iso" >/dev/null 2>&1 || fail "could not read the ISO"

SYS="$V/iso/boot/syslinux/syslinux.cfg"
GRUBCFG="$V/iso/boot/grub/grub.cfg"
[ -f "$GRUBCFG" ] || fail "no grub.cfg"
if [ "$ARCH" = "x86_64" ]; then      # only PCs have the BIOS (syslinux) boot menu; ARM images boot through UEFI and GRUB only
    [ -f "$SYS" ] || fail "no syslinux.cfg"
    for want in "PROMPT 0" "NOESCAPE 1" "ALLOWOPTIONS 0"; do
        grep -q "^$want\$" "$SYS" || fail "syslinux.cfg lacks '$want'"
    done
fi
grep -q '^set superusers=' "$GRUBCFG" || fail "grub.cfg has no superuser lock"
grep -q '^password_pbkdf2 pyos grub.pbkdf2.sha512' "$GRUBCFG" || fail "grub.cfg has no password hash"
grep -q -- '--unrestricted' "$GRUBCFG" || fail "grub.cfg entry is not unrestricted (the machine could not boot)"
grep -q 'MISSING-HASH' "$GRUBCFG" && fail "grub.cfg was built without its lock"
grep -q -E 'init=|single|rescue|emergency' "$GRUBCFG" && fail "boot config contains init=/single/rescue"
[ -f "$SYS" ] && grep -q -E 'init=|single|rescue|emergency' "$SYS" && fail "boot config contains init=/single/rescue"

OVL="$(ls "$V"/iso/*.apkovl.tar.gz 2>/dev/null | head -n1)"
[ -n "$OVL" ] || fail "no overlay (apkovl) on the ISO"
mkdir -p "$V/ovl" && tar -xzf "$OVL" -C "$V/ovl" || fail "could not unpack the overlay"
INITTAB="$V/ovl/etc/inittab"
[ -f "$INITTAB" ] || fail "overlay has no inittab"
grep -v '^[[:space:]]*#' "$INITTAB" | grep -q -E 'getty|login|/bin/sh|/bin/ash|ttyS|agetty' && fail "inittab starts a login or a shell"
[ "$(grep -c 'pythonos-session' "$INITTAB")" -eq 1 ] || fail "inittab must start exactly one PythonOS session"
[ -f "$V/ovl/etc/securetty" ] && [ ! -s "$V/ovl/etc/securetty" ] || fail "root is allowed to log in on a terminal"
SESSION="$V/ovl/usr/local/bin/pythonos-session"
grep -q 'PYOS_LOCKDOWN=1' "$SESSION" || fail "session does not enable lockdown"
grep -v '^[[:space:]]*#' "$SESSION" | grep -q -E 'exec /bin/(a)?sh|exec sh' && fail "session can fall back to a shell"
PERSIST="$V/ovl/usr/local/bin/pythonos-persist"
[ -f "$PERSIST" ] || fail "overlay has no persistent-storage script"
grep -q 'nosuid,nodev,noexec' "$PERSIST" || fail "persistent storage would be mounted without noexec,nosuid,nodev"
grep -v '^[[:space:]]*#' "$PERSIST" | grep -q -E '(^|[;&| ])(sh|ash|bash)([ ;]|$)' && fail "persistent-storage script starts a shell"
grep -q -E '(nano|openssh|dropbear|telnet|busybox-extras|sudo|doas)' "$V/ovl/etc/apk/world" && fail "world file installs a tool that gives shell access"
ls "$V"/ovl/etc/runlevels/*/ 2>/dev/null | grep -q -E 'sshd|dropbear|telnetd|ttyd' && fail "a remote-access service is enabled"
rm -rf "$V"
echo "Lockdown check passed: boot menu locked, no login or shell on any console, PythonOS only."
