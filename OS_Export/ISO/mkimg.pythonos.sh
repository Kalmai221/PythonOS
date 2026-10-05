profile_pythonos() {
	profile_standard
	profile_abbrev="pythonos"
	title="PythonOS"
	desc="PythonOS live system. Boots straight into PythonOS."
	arch="x86_64"
	output_format="iso"

	# "lts" is the full kernel and boots normal PCs (default); "virt" is a smaller kernel for virtual
	# machines only. The standard profile's firmware bundle is kept: the hardware setup in PythonOS
	# (hwsetup) needs it for Wi-Fi, some network cards and GPUs.
	kernel_flavors="${PYTHONOS_KERNEL:-lts}"
	# quiet: the kernel's own messages stay off the screen (PythonOS draws the boot progress itself; press D at the
	# PythonOS start for a diagnostic report that includes them)
	kernel_cmdline="console=tty0 console=ttyS0,115200 quiet loglevel=3"
	syslinux_serial="0 115200"
	syslinux_prompt=0

	# Python and the libraries PythonOS needs (yaspin and ping3 are bundled with the OS itself), plus
	# what the hardware setup uses: PCI/USB listing, ALSA audio tools, Wi-Fi tools and disk tools for
	# persistent storage. No editor (nano can run shell commands) - PythonOS has its own.
	apks="$apks python3 py3-rich py3-psutil py3-requests py3-pygments py3-prompt_toolkit tzdata"
	apks="$apks pciutils hwdata-pci usbutils alsa-utils alsa-ucm-conf iw wpa_supplicant lsblk e2fsprogs kbd-bkeymaps cryptsetup kbd font-terminus"

	# Two images are built from this profile (PYTHONOS_VARIANT):
	#   full    (default) everything: Bluetooth, printing, the "installos" installer (needs a boot loader, disk tools and Alpine's
	#           setup-disk) and the guest tools that make it behave in virtual machines (QEMU/KVM, VMware, VirtualBox)
	#   minimal the live system only: much smaller; no Bluetooth, printing, installer or guest tools
	case "${PYTHONOS_VARIANT:-full}" in
		full)
			apks="$apks bluez bluez-openrc cups cups-client cups-openrc"
			apks="$apks alpine-conf sfdisk syslinux grub grub-efi grub-bios dosfstools efibootmgr e2fsprogs-extra"
			apks="$apks qemu-guest-agent qemu-guest-agent-openrc open-vm-tools open-vm-tools-openrc virtualbox-guest-additions virtualbox-guest-additions-openrc"
			;;
		minimal) ;;
		*) echo "PYTHONOS_VARIANT must be full or minimal" >&2; return 1 ;;
	esac
	apkovl="genapkovl-pythonos.sh"
}

# ---------------------------------------------------------------------------------------------
# Locked-down boot menus. These replace mkimage's own generators (this file is read after
# mkimg.base.sh), so nobody at the boot menu can add "init=/bin/sh" or similar to the kernel
# command line:
#   BIOS (syslinux): no boot: prompt, Shift/Alt/Caps/Scroll cannot interrupt, options not allowed.
#   UEFI (GRUB):     editing entries and the GRUB command line need a password that is random per
#                    build and thrown away; the one entry boots without it.
# in-container.sh checks the finished ISO for all of this and fails the build if anything is missing.

syslinux_gen_config() {
	[ -z "$syslinux_serial" ] || echo "SERIAL $syslinux_serial"
	echo "TIMEOUT ${syslinux_timeout:-10}"
	echo "PROMPT 0"
	echo "NOESCAPE 1"
	echo "ALLOWOPTIONS 0"
	echo "DEFAULT ${kernel_flavors%% *}"

	local _f _p _initrd
	for _f in $kernel_flavors; do
		_initrd="/boot/initramfs-$_f"
		if [ -n "$initrd_ucode" ]; then
			for _p in $initrd_ucode; do
				_initrd="$_p,$_initrd"
			done
		fi
		echo ""
		echo "LABEL $_f"
		echo "	MENU LABEL PythonOS"
		echo "	KERNEL /boot/vmlinuz-$_f"
		echo "	INITRD $_initrd"
		echo "	FDTDIR /boot/dtbs-$_f"
		echo "	APPEND $initfs_cmdline $kernel_cmdline"
	done
}

grub_gen_config() {
	local _f _p _initrd
	echo "set timeout=1"
	echo 'set superusers="pyos"'
	echo "password_pbkdf2 pyos ${PYTHONOS_GRUB_PBKDF2:-MISSING-HASH-BUILD-MUST-FAIL}"
	for _f in $kernel_flavors; do
		_initrd="/boot/initramfs-$_f"
		if [ -n "$initrd_ucode" ]; then
			for _p in $initrd_ucode; do
				_initrd="$_p $_initrd"
			done
		fi
		echo ""
		echo "menuentry \"PythonOS\" --unrestricted {"
		echo "	linux	/boot/vmlinuz-$_f $initfs_cmdline $kernel_cmdline"
		echo "	initrd	$_initrd"
		echo "}"
	done
}
