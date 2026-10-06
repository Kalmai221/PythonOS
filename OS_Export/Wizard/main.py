#!/usr/bin/env python3
"""PythonOS Setup Wizard - installs PythonOS the way that fits your computer. Opens a window by default; --cli uses the terminal.

    PythonOS-Wizard                          the wizard: it looks at this computer, asks what you want (install here, Android phone, bootable
                                             USB stick, virtual machine, Docker), downloads the right file, checks it, and does the next step
    PythonOS-Wizard --flash [file.iso]       straight to writing a USB stick (window)
    PythonOS-Wizard --cli                    the wizard in the terminal
    PythonOS-Wizard --cli --goal vm --vm virtualbox --yes        no questions: goal is install, android, usb, vm, docker or download
    PythonOS-Wizard --cli --list             show which USB drives could be used
    PythonOS-Wizard --cli --download         write the latest image to a stick (terminal): --arch x86_64|aarch64, --minimal, --device ID, --yes
    PythonOS-Wizard --cli pythonos.iso       write a file you have to a stick (checked against SHA256SUMS next to it)

Writing a USB drive needs administrator rights: Windows asks (UAC) when the program starts; Linux and macOS ask when the writing starts.
"""
import argparse
import os
import platform
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import flashlib as flash  # noqa: E402


def hide_own_console():
    """On Windows a double-clicked console program owns a console window it does not need when it shows a window: hide it (but never
    hide a terminal the user started it from)."""
    if platform.system() != "Windows":
        return
    try:
        import ctypes
        kernel = ctypes.windll.kernel32
        processes = (ctypes.c_uint * 4)()
        if kernel.GetConsoleProcessList(processes, 4) <= 1:
            window = kernel.GetConsoleWindow()
            if window:
                ctypes.windll.user32.ShowWindow(window, 0)
    except Exception:
        pass


def pause_if_own_console():
    """A terminal program started by double-click (or elevated through UAC) lives in a console window that closes the moment it ends: wait
    for Enter so its last words can be read. Never when it was started from a terminal the user already has."""
    if platform.system() != "Windows" or not getattr(sys, "frozen", False):
        return
    try:
        import ctypes
        processes = (ctypes.c_uint * 4)()
        if ctypes.windll.kernel32.GetConsoleProcessList(processes, 4) <= 1:
            input("\nPress Enter to close this window...")
    except Exception:
        pass


def parser():
    p = argparse.ArgumentParser(prog="PythonOS-Wizard", description="Install PythonOS the way that fits your computer.")
    p.add_argument("iso", nargs="?", help="an .iso file to write to a USB stick")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--gui", action="store_true", help="open the window (the default)")
    mode.add_argument("--cli", action="store_true", help="use the terminal instead of a window")
    p.add_argument("--flash", action="store_true", help="go straight to writing a USB stick")
    p.add_argument("--goal", choices=["install", "android", "usb", "vm", "docker", "download"], help="(terminal) what to do, without asking")
    p.add_argument("--vm", choices=[k for k, *_ in __import__("wizardlib").VM_SOFTWARE], help="with --goal vm: the virtual machine program")
    p.add_argument("--abi", choices=["aarch64", "x86_64", "universal"], help="with --goal android: the kind of device")
    p.add_argument("--folder", help="where downloads are saved (default: your Downloads folder)")
    p.add_argument("--dry-run", action="store_true", help="show what would happen and stop")
    p.add_argument("--list", action="store_true", help="only list the USB drives that could be used")
    p.add_argument("--download", action="store_true", help="download the latest image for a USB stick (terminal)")
    p.add_argument("--arch", choices=["x86_64", "aarch64"], help="the processor of the computer that will start from the stick")
    p.add_argument("--minimal", action="store_true", help="the smaller image without Bluetooth, printing and the installer")
    p.add_argument("--device", help="the drive to write to (Linux /dev/sdX, macOS /dev/diskN, Windows the disk number)")
    p.add_argument("--sha256", help="the expected SHA-256 of the ISO (otherwise SHA256SUMS next to it is used)")
    p.add_argument("--yes", action="store_true", help="do not ask (with --device for a drive; with --goal for the extra step)")
    p.add_argument("--no-verify", action="store_true", help="skip reading the stick back")
    p.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)           # the privileged writer the window starts
    p.add_argument("--progress-file", help=argparse.SUPPRESS)
    p.add_argument("--version", action="store_true", help="print the version")
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    if args.version:
        print("PythonOS Setup Wizard")
        return 0
    if args.worker:
        if not (args.iso and args.device and args.progress_file):
            return 2
        return flash.worker(args.iso, args.device, not args.no_verify, args.progress_file)
    flash_terminal = args.list or args.download or args.device or (args.iso and args.cli)
    terminal = args.cli or args.goal or flash_terminal
    if not terminal:
        try:
            hide_own_console()
            if args.flash or args.iso:
                import flashgui
                return flashgui.run(args.iso)
            import wizardgui
            return wizardgui.run()
        except Exception as e:                                  # no display, or no tkinter: say so and fall back
            print(f"Could not open the window ({type(e).__name__}: {e}). Using the terminal instead.\n")
    if flash_terminal or args.flash:
        code = flash.run_cli(args)
    else:
        import wizardcli
        code = wizardcli.run(args)
    pause_if_own_console()
    return code


if __name__ == "__main__":
    sys.exit(main())
