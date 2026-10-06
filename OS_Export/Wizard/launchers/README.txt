PythonOS Setup Wizard {version}
===============================

Installs PythonOS the way that fits your computer. It looks at this computer (system and processor), asks what you want, downloads the
right file from the latest release, checks it against the release's SHA256SUMS, and does the next step. Nothing needs to be installed
first, and Python is not needed.

Start it
  Windows   double-click wizard.bat  (or PythonOS-Wizard.exe)
  macOS     double-click wizard.command  (or run ./wizard.sh)   Apple silicon Macs only; Intel Macs: Docker or a virtual machine
  Linux     run ./wizard.sh   (or double-click it, if your file manager runs scripts)

What it can set up
  * PythonOS on this computer      Windows: the installer.  Linux: the package for your distribution (deb, rpm, Arch) or the portable
                                   launcher.  macOS: the portable launcher (needs Python 3), or use Docker / a virtual machine.
  * An Android phone or tablet     downloads the app; installs it on a phone connected with a cable (adb) if you want.
  * A bootable USB stick           writes the live system to a stick and checks it. Only USB sticks are listed, never the drive the
                                   computer runs from, and you confirm the drive before anything is erased.
  * A virtual machine              you pick VirtualBox, VMware, QEMU/KVM, Proxmox, UTM, Hyper-V, Parallels or another program, and the wizard
                                   downloads the file that program needs (and imports it into VirtualBox if you like).
  * Docker                         one command, with a volume that keeps your accounts and files.
  * Any file                       a list of everything in the release.

The terminal version
  ./wizard.sh --cli                                  the same questions as a numbered list
  ./wizard.sh --cli --goal vm --vm virtualbox --yes  answer everything on the command line; goals: install, android, usb, vm, docker, download
  ./wizard.sh --cli --goal install --dry-run         show what would happen and stop
  ./wizard.sh --cli --download                       write the latest image to a USB stick (also --arch aarch64, --minimal)
  ./wizard.sh --cli --list                           show which USB drives could be used
  ./wizard.sh --flash                                straight to the USB stick window
  Windows: use PythonOS-Wizard.exe in place of ./wizard.sh.

Good to know
  * Only the part that writes a USB stick runs with administrator rights, and Windows / Linux / macOS ask you for them at that moment
    (UAC, polkit or sudo, a password prompt). Everything else runs as you.
  * Windows may warn that the program is from an unknown publisher (it is not signed). Check the file against SHA256SUMS on the release
    page first; "More info", then "Run anyway".
  * macOS blocks downloaded programs until their quarantine mark is removed; wizard.sh does that for this folder. If macOS still refuses,
    open System Settings > Privacy & Security and choose "Open Anyway".
  * Linux: the window needs pkexec (polkit, present on desktops) to write a stick. Without it use ./wizard.sh --cli (it uses sudo).
  * Other ways to write the image: balenaEtcher, or Rufus in "DD image" mode.

Included
  PythonOS-Wizard.exe                 Windows (64-bit; also runs on Windows on ARM)
  pythonos-wizard-linux-x86_64        Linux, PCs
  pythonos-wizard-linux-aarch64       Linux, 64-bit ARM
  pythonos-wizard-macos-arm64         macOS, Apple silicon
  (no program for Intel Macs: use Docker or a virtual machine, see the release page)
  (a release may leave out one of these if it could not be built; the others still work)
