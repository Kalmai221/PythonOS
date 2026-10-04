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
nano
EOF

makefile root:root 0644 "$tmp"/etc/motd <<EOF
PythonOS live system - changes are lost when you power off.
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

rc_add mount-ro shutdown
rc_add killprocs shutdown
rc_add savecache shutdown

# The OS itself, and the script that starts it on the first console
cp -R "$PAYLOAD" "$tmp"/opt/pythonos
cp "$OVERLAY"/pythonos-session "$tmp"/usr/local/bin/pythonos-session
chmod 755 "$tmp"/usr/local/bin/pythonos-session
cp "$OVERLAY"/inittab "$tmp"/etc/inittab
chmod 644 "$tmp"/etc/inittab

tar -c -C "$tmp" . | gzip -9n > "$HOSTNAME".apkovl.tar.gz
