#!/bin/sh
# PythonOS Setup Wizard for Linux and macOS: picks the right program for this computer and runs it.
#   ./wizard.sh                      the window (needs a desktop)
#   ./wizard.sh --cli --download     the terminal version: download the latest image and write it
#   ./wizard.sh --cli --help         every option
# Writing a drive needs administrator rights; the program asks for them (pkexec or sudo on Linux, a password prompt on macOS).
HERE="$(cd "$(dirname "$0")" && pwd)"
OS="$(uname -s)"

# The real processor of this computer, not just what `uname` of this shell says: a Terminal running under Rosetta on an Apple-silicon Mac
# reports Intel, and a 32-bit user space on a 64-bit ARM kernel reports armv7l/armv8l.
detect_arch() {
    machine="$(uname -m)"
    if [ "$OS" = Darwin ]; then
        if [ "$(sysctl -n hw.optional.arm64 2>/dev/null)" = "1" ] || [ "$(sysctl -n sysctl.proc_translated 2>/dev/null)" = "1" ]; then
            echo arm64
            return
        fi
    fi
    case "$machine" in
        x86_64|amd64) echo x86_64 ;;
        aarch64|arm64) [ "$OS" = Darwin ] && echo arm64 || echo aarch64 ;;
        armv7*|armv8l|armv6*|arm) echo arm32 ;;
        i386|i486|i586|i686) echo x86_32 ;;
        *) echo "$machine" ;;
    esac
}

ARCH="$(detect_arch)"
case "$OS" in
    Linux)
        case "$ARCH" in
            x86_64|aarch64) ;;
            arm32|x86_32)
                echo "This is a 32-bit system ($(uname -m)). PythonOS Setup needs a 64-bit one." >&2
                echo "Run it on a 64-bit computer instead, or write the ISO with another tool such as balenaEtcher." >&2
                exit 1 ;;
            *) echo "PythonOS Setup has no program for the $(uname -m) processor. Use balenaEtcher to write the ISO." >&2; exit 1 ;;
        esac
        # the programs are built for glibc systems; Alpine and other musl systems cannot run them
        if ldd --version 2>&1 | grep -qi musl; then
            echo "This system uses musl (Alpine and similar), which cannot run the PythonOS Setup program." >&2
            echo "Write the ISO from another computer, or with: dd if=pythonos.iso of=/dev/sdX bs=4M conv=fsync (as root, check the device first)." >&2
            exit 1
        fi
        BIN="$HERE/pythonos-wizard-linux-$ARCH" ;;
    Darwin)
        case "$ARCH" in
            arm64|x86_64) ;;
            *) echo "PythonOS Setup has no program for this Mac's processor." >&2; exit 1 ;;
        esac
        BIN="$HERE/pythonos-wizard-macos-$ARCH"
        xattr -dr com.apple.quarantine "$HERE" 2>/dev/null       # downloaded programs are blocked until this mark is removed
        ;;
    *) echo "On Windows, run wizard.bat." >&2; exit 1 ;;
esac

if [ ! -f "$BIN" ]; then
    echo "$(basename "$BIN") is missing from this folder (it may not be in this release for your system)." >&2
    if [ "$OS" = Darwin ] && [ "$ARCH" = x86_64 ]; then
        echo "There is no wizard program for Intel Macs. Run PythonOS with Docker: docker run -it --rm -v pythonos-data:/data ghcr.io/kalmai221/pythonos" >&2
        echo "or in a virtual machine (UTM, VirtualBox, VMware) with the .ova or .iso from the release page." >&2
    fi
    exit 1
fi
[ -x "$BIN" ] || chmod +x "$BIN" 2>/dev/null
exec "$BIN" "$@"
