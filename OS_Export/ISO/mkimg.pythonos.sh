profile_pythonos() {
	profile_standard
	profile_abbrev="pythonos"
	title="PythonOS"
	desc="PythonOS live system. Boots straight into PythonOS."
	arch="x86_64"
	output_format="iso"

	# Kernel: "lts" is the full kernel and boots normal PCs (default). "virt" is a much smaller
	# kernel for virtual machines only.
	kernel_flavors="${PYTHONOS_KERNEL:-lts}"

	# Size: the standard profile also ships hundreds of MB of firmware (Wi-Fi, some network cards),
	# netfilter extras and CPU microcode. A console live image does not need them, so they are left
	# out unless PYTHONOS_FIRMWARE=1. Wired networking and the console/framebuffer still work.
	if [ "${PYTHONOS_FIRMWARE:-0}" != "1" ]; then
		kernel_addons=""
		boot_addons=""
		initrd_ucode=""
		apks="$(echo $apks | tr ' ' '\n' | grep -v -e '^linux-firmware' -e '^wireless-regdb' | tr '\n' ' ')"
	fi

	kernel_cmdline="console=tty0 console=ttyS0,115200"
	syslinux_serial="0 115200"
	# Python and the libraries PythonOS needs (yaspin and ping3 are bundled with the OS itself)
	apks="$apks python3 py3-rich py3-psutil py3-requests py3-pygments py3-prompt_toolkit nano"
	apkovl="genapkovl-pythonos.sh"
}
