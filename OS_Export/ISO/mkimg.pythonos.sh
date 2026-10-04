profile_pythonos() {
	profile_standard
	profile_abbrev="pythonos"
	title="PythonOS"
	desc="PythonOS live system. Boots straight into PythonOS."
	arch="x86_64"
	output_format="iso"

	# Size: the standard profile ships the full "lts" kernel plus hundreds of MB of firmware,
	# wireless and netfilter extras. A console live image with wired networking needs none of that.
	#   virt (default) - small kernel for virtual machines (QEMU, VirtualBox, VMware, Hyper-V, ...)
	#   lts            - full kernel for real hardware (still without the firmware bundle)
	kernel_flavors="${PYTHONOS_KERNEL:-virt}"
	kernel_addons=""
	boot_addons=""
	initrd_ucode=""
	apks="$(echo $apks | tr ' ' '\n' | grep -v -e '^linux-firmware' -e '^wireless-regdb' | tr '\n' ' ')"

	kernel_cmdline="console=tty0 console=ttyS0,115200"
	syslinux_serial="0 115200"
	# Python and the libraries PythonOS needs (yaspin and ping3 are bundled with the OS itself)
	apks="$apks python3 py3-rich py3-psutil py3-requests py3-pygments py3-prompt_toolkit nano"
	apkovl="genapkovl-pythonos.sh"
}
