profile_pythonos() {
	profile_standard
	profile_abbrev="pythonos"
	title="PythonOS"
	desc="PythonOS live system. Boots straight into PythonOS."
	arch="x86_64"
	output_format="iso"
	kernel_flavors="lts"
	kernel_cmdline="console=tty0 console=ttyS0,115200"
	syslinux_serial="0 115200"
	# Python and the libraries PythonOS needs (yaspin and ping3 are bundled with the OS itself)
	apks="$apks python3 py3-rich py3-psutil py3-requests py3-pygments py3-prompt_toolkit nano"
	apkovl="genapkovl-pythonos.sh"
}
