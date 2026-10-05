#!/bin/sh -e
# Creates the "overlay" that turns a stock Alpine live system into PythonOS:
# hostname, networking, services, the OS files in /opt/pythonos, and an autostart on tty1.
# mkimage runs this and expects it to write <hostname>.apkovl.tar.gz into the current directory.

HOSTNAME="$1"
if [ -z "$HOSTNAME" ]; then
	echo "usage: $0 hostname" >&2
	exit 1
fi

PAYLOAD="${PYTHONOS_PAYLOAD:-/payload}"
VARIANT="${PYTHONOS_VARIANT:-full}"
OVERLAY="${PYTHONOS_OVERLAY:-/home/build/overlay}"

cleanup() {
	rm -rf "$tmp"
}

makefile() {
	OWNER="$1"
	PERMS="$2"
	FILENAME="$3"
	cat > "$FILENAME"
	chown "$OWNER" "$FILENAME"
	chmod "$PERMS" "$FILENAME"
}

rc_add() {
	mkdir -p "$tmp"/etc/runlevels/"$2"
	ln -sf /etc/init.d/"$1" "$tmp"/etc/runlevels/"$2"/"$1"
}

tmp="$(mktemp -d)"
trap cleanup EXIT

mkdir -p "$tmp"/etc "$tmp"/etc/apk "$tmp"/etc/network "$tmp"/opt "$tmp"/usr/local/bin

makefile root:root 0644 "$tmp"/etc/hostname <<EOF
pyOS
EOF

makefile root:root 0644 "$tmp"/etc/network/interfaces <<EOF
auto lo
iface lo inet loopback

auto eth0
iface eth0 inet dhcp
EOF

# Packages installed at boot from the ISO's own /apks repository
makefile root:root 0644 "$tmp"/etc/apk/world <<EOF
alpine-base
python3
py3-rich
py3-psutil
py3-requests
py3-pygments
py3-prompt_toolkit
tzdata
pciutils
hwdata-pci
usbutils
alsa-utils
alsa-ucm-conf
iw
wpa_supplicant
lsblk
e2fsprogs
kbd-bkeymaps
cryptsetup
kbd
font-terminus
EOF
if [ "$VARIANT" = "full" ]; then
	cat >> "$tmp"/etc/apk/world <<EOF
bluez
bluez-openrc
cups
cups-client
cups-openrc
alpine-conf
sfdisk
syslinux
grub
grub-efi
grub-bios
dosfstools
efibootmgr
e2fsprogs-extra
qemu-guest-agent
qemu-guest-agent-openrc
open-vm-tools
open-vm-tools-openrc
virtualbox-guest-additions
virtualbox-guest-additions-openrc
EOF
fi

makefile root:root 0644 "$tmp"/etc/motd <<EOF
PythonOS live system ($VARIANT) - changes are lost when you power off.
EOF

# Hardening. There is no login on this system at all (no getty in inittab), and root may not log in
# on any terminal even if one were ever started. SysRq and kernel info are switched off.
: > "$tmp"/etc/securetty
mkdir -p "$tmp"/etc/sysctl.d
makefile root:root 0644 "$tmp"/etc/sysctl.d/90-pythonos.conf <<EOF
kernel.sysrq = 0
kernel.dmesg_restrict = 1
kernel.kptr_restrict = 2
kernel.core_pattern = |/bin/false
EOF

# Boot services
rc_add devfs sysinit
rc_add dmesg sysinit
rc_add mdev sysinit
rc_add hwdrivers sysinit
rc_add modloop sysinit

rc_add hwclock boot
rc_add modules boot
rc_add sysctl boot
rc_add hostname boot
rc_add bootmisc boot
rc_add syslog boot
rc_add networking boot
if [ "$VARIANT" = "full" ]; then
	rc_add bluetooth default
	rc_add cupsd default
	rc_add qemu-guest-agent default
	rc_add open-vm-tools default
	rc_add virtualbox-guest-additions default
fi

rc_add mount-ro shutdown
rc_add killprocs shutdown
rc_add savecache shutdown

# The OS itself, and the script that starts it on the first console
cp -R "$PAYLOAD" "$tmp"/opt/pythonos
cp "$OVERLAY"/pythonos-session "$tmp"/usr/local/bin/pythonos-session
chmod 755 "$tmp"/usr/local/bin/pythonos-session
cp "$OVERLAY"/pythonos-persist "$tmp"/usr/local/bin/pythonos-persist
chmod 644 "$tmp"/usr/local/bin/pythonos-persist
cp "$OVERLAY"/inittab "$tmp"/etc/inittab
chmod 644 "$tmp"/etc/inittab

tar -c -C "$tmp" . | gzip -9n > "$HOSTNAME".apkovl.tar.gz
