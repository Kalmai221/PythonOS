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
	kernel_cmdline="console=tty0 console=ttyS0,115200"
	syslinux_serial="0 115200"

	# Python and the libraries PythonOS needs (yaspin and ping3 are bundled with the OS itself),
	# plus what the hardware setup uses: PCI/USB listing, ALSA audio tools and Wi-Fi tools.
	apks="$apks python3 py3-rich py3-psutil py3-requests py3-pygments py3-prompt_toolkit nano"
	apks="$apks pciutils hwdata-pci usbutils alsa-utils alsa-ucm-conf iw wpa_supplicant"
	apkovl="genapkovl-pythonos.sh"
}
