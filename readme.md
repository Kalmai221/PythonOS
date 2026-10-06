# 🚀 PythonOS (PyOS) — A Terminal-Based Operating System

[![Build](https://github.com/Kalmai221/PythonOS/actions/workflows/build-os.yml/badge.svg)](https://github.com/Kalmai221/PythonOS/actions/workflows/build-os.yml)
[![Tests](https://github.com/Kalmai221/PythonOS/actions/workflows/test.yml/badge.svg)](https://github.com/Kalmai221/PythonOS/actions/workflows/test.yml)

## 📖 Overview

**PythonOS** (PyOS) is a small operating system you drive with typed commands, written in Python. It has a filesystem with permissions, user accounts, a shell with pipes and background jobs, a built-in editor, an app marketplace, games, a scheduler and an update system. It runs:

* on **Windows** (Intel/AMD and ARM64), in its own window
* on **Android** (a real app, arm64 and x86_64)
* on **Linux** (any distribution, any processor)
* from a **bootable USB stick** (a locked-down live system for PCs and 64-bit ARM), or installed to a disk
* in a **virtual machine** (VirtualBox, VMware, QEMU) or a **Docker** container

> Downloads and a build status page: **<https://kalmai221.github.io/PythonOS/>** · all files: [Releases](https://github.com/Kalmai221/PythonOS/releases/latest)

---

## 📥 Download and install

Pick the line for your device. Every release lists each file with its size and what it is for, and PythonOS updates its own system from inside (`updatecheck`).

| Device | What to get | How |
|---|---|---|
| **Not sure?** | `pythonos-wizard-<version>.zip` | The Setup Wizard (Windows, macOS, Linux; no Python needed): run `wizard.bat`, `wizard.command` or `wizard.sh`. It looks at your computer, asks what you want (install here, Android, bootable USB stick, virtual machine, Docker), downloads the right file and checks it. `--cli` is the terminal version. |
| **Windows 10/11** | `PythonOS-<version>-web-setup.exe` | Run it. A ~100 KB installer that downloads PythonOS, checks it, installs for your user (no administrator), offers Start menu and desktop shortcuts, and can update, repair or uninstall later. Four languages, light and dark. It picks the ARM64 package on Windows on ARM. |
| Windows (offline / no install) | `…-setup.exe` (Inno Setup) or `…-windows-portable.zip` | Full installer, or unzip anywhere (a USB stick works) and run `PythonOS.exe`. |
| **Android 7+** | `PythonOS-<version>-android-arm64-v8a.apk` | Nearly every phone. `…-android-x86_64.apk` is for Chromebooks and emulators; `…-android.apk` works anywhere but is bigger. |
| **Debian, Ubuntu, Mint, Raspberry Pi OS** | `pythonos_<version>_all.deb` | `sudo apt install ./pythonos_<version>_all.deb`, then `pythonos` |
| **Arch, Manjaro** | `pythonos-<version>-1-any.pkg.tar.zst` | `sudo pacman -U pythonos-<version>-1-any.pkg.tar.zst` |
| **Fedora, RHEL, Rocky, openSUSE** | `pythonos-<version>-1.noarch.rpm` | `sudo dnf install ./pythonos-<version>-1.noarch.rpm` |
| **Any other Linux** | `pythonos-<version>-linux.tar.gz` | Unpack, run `./pythonos` (needs Python 3.8+ with venv) |
| **Boot from USB** | `pythonos-<version>-x86_64.iso` (PCs) or `…-aarch64.iso` (64-bit ARM, UEFI) | Write it with the Setup Wizard (`pythonos-wizard-<version>.zip`: checks the download, only offers USB sticks, reads the stick back). `…-minimal-…iso` is the small version. |
| **Virtual machine** | `pythonos-<version>-vm.ova` or `…-vm.qcow2` | VirtualBox/VMware: File → Import Appliance (comes with a data disk, so your accounts and files are kept). QEMU/KVM/Proxmox: attach the `.qcow2` and, as a second disk, `…-vm-data.qcow2` to keep your files. `…-vm-kit.zip` has run scripts. |
| **Docker** | `ghcr.io/kalmai221/pythonos` | `docker run -it --rm -v pythonos-data:/data ghcr.io/kalmai221/pythonos` (amd64 and arm64). The volume keeps your accounts, files, settings and updates; without `-v` everything is forgotten when the container stops |

Every installer and launcher checks what PythonOS needs (its system files and Python libraries) and downloads whatever is missing.

**Check your download.** Each release has `SHA256SUMS` (signed with Sigstore) and build provenance:

```bash
sha256sum -c SHA256SUMS --ignore-missing          # Linux / macOS
Get-FileHash .\PythonOS-<version>-web-setup.exe   # Windows PowerShell
gh attestation verify <file> --repo Kalmai221/PythonOS
```

What each platform is tested on, and what is not, is in [COMPATIBILITY.md](COMPATIBILITY.md).

### Run from source

```bash
git clone https://github.com/Kalmai221/PythonOS.git
cd PythonOS
python3 -m pip install -r requirements.txt
python3 main.py
```

Python 3.9 or newer. (The older single-file launcher `installer/run.py` still works too.)

---

## ✨ Features

* **Undo**: `rm` sends things to a per-user trash; `undo` brings the last one back; `trash` lists, restores and empties
* **Finding things**: `find -name "*.txt" -size +1M`, `grep -rn word folder`, `tree -L 2`, `diff a b`
* **Learn**: `tutorial` (28 lessons that check what you type and save your place), `quickstart` (two minutes), `help <category>`, `man <command>`
* **When things go wrong**: `whathappened` (after a power cut or crash), `doctor`, `report` (a redacted report you read before sending), `diag` (hardware report)
* **Safe by default**: administrators are asked for their password before risky actions and their actions are logged (`logs --admin`)
* **Languages**: `settings set language es|fr|de|en` changes the system's own messages (commands stay in English)
* **Apps with settings**: installed apps can have option pages (`settings apps`)
* **Live USB / installed**: `installos` copies PythonOS to a disk (experimental); `persist` keeps your data (optionally encrypted); press **D** at start for a diagnostic boot; the clock is set from the network; low-memory machines run in light mode; batteries are watched with a clean shutdown when critical
* **Windows**: PythonOS opens in its own window (no Command Prompt), with colour, a slim scrollbar, smooth and keyboard scrolling and a "Latest" button; `updatecheck` can update the app in place after checking the installer

---

## 🖥️ Using PyOS

PyOS behaves like a small Unix-style system:

* **Filesystem** – `files/` is `/`, with `/home/<user>`, `/etc`, `/tmp` and `/var/log`. Every login starts in your home (`~`).
* **Permissions** – regular users can write only in their own home and `/tmp` and cannot enter other homes; admins can do everything (prompt ends in `#` instead of `$`).
* **Shell** – quotes, pipes (`ls | grep txt`), redirects (`echo hi > a.txt`, `>>`), `;`, `&&`, `||` and `&` (background jobs), `$?`, tab completion and history. Commands report success or failure, so `make && echo ok` works.
* **Commands** – `ls cd pwd cat head tail wc grep find touch mkdir rm cp mv tree diff zip unzip tar edit echo date uname hostname uptime free df whoami history logs` and more; run `help` for the groups, `man <command>` for the manual and `tutorial` for a guided tour.
* **Editor** – `edit <file>` is a built-in editor (full screen on a real terminal, a line editor elsewhere).
* **Jobs and scheduling** – `sleep 30 &`, `jobs`, `fg`, `kill`; `schedule add daily 08:00 backup create`; results arrive as notifications.
* **Settings and themes** – `settings` (themes, prompt style, boot speed, language, auto-lock, idle logout, `auto_clear_lines`, trash). `clear` wipes the screen and scrollback (`clear -x` keeps it).
* **Backup and sharing** – `backup create|restore`, and `share send|receive` to move files between devices on the same network.
* **Accounts and security** – salted password hashes, escalating lockout after wrong passwords, `passwd`, `su`, `lock` and `last`.
* **Marketplace** – `market` opens the store (browse, featured, search, update, remove); `pkg install <name>`, `pkg update all`, `pkg why`, `pkg permissions`, `pkg rollback`. Packages are verified with checksums, declare what they may do (network, files, notifications…) and are held to it while they run, can depend on each other, show what changed in an update, and reinstall offline from a local cache. There are 60+ apps: games (Chess, Tetris, Minesweeper, Sudoku, Snake, 2048, Wordle…), utilities (QR codes, password generator, hash tool, JSON formatter, Markdown editor…), system tools (speed test, LAN and port scanners, disk usage, process inspector, theme designer…).
* **Updates** – PythonOS updates itself from GitHub releases, downloading only the files that changed, resuming if interrupted, and rolling back on request (`updatecheck`, `whatsnew`, `rollback`). The package around it (APK, installer, ISO) cannot replace itself, so PythonOS tells you when a newer one is available.
* **Live ISO** – a locked-down, PythonOS-only system: hardware, audio, Wi-Fi, Bluetooth, printer, display and keyboard setup (`hwsetup`) and optional persistent storage (`persist create`).
* **Logs** – logins, account changes, crashes and boot/shutdown are recorded in `/var/log/system.log` (view with `logs`, filter by user, level, date).

---

## 🛠️ Developer Notes

* **Layout**: `commands/` (one file per command), `core/` (boot, shutdown, updates, hardware), `pyos/` (libraries: filesystem, shell helpers, trash, i18n, power…), `programs/`, `online_packages/` (the marketplace), `OS_Export/` (everything that builds the packages), `site/` (the download and status pages), `tools/`.
* **Tests**: `python tools/smoke_test.py` starts PythonOS in a scratch copy and runs real commands (including the login path); `python tools/audit_lockdown.py` fails if OS code could open a way out of PythonOS on the ISO. CI runs both on Linux and Windows for every push.
* **Building packages**: see [OS_Export/README.md](OS_Export/README.md) (how releases are built, which files exist, how a failed build is recovered from earlier runs).
* **Adding a language**: a dictionary in `pyos/locales.py`; the English text is the key.
* **Problem reports**: run `report` inside PythonOS, or [open an issue](https://github.com/Kalmai221/PythonOS/issues). Security problems: see the report relay notes in `OS_Export/relay/README.md`.

---

## 🤝 Contributing

Adding a marketplace package: put it in `online_packages/<category>/<name>/` with a `data.json` (name, description, version, command, permissions, categories, tags, scripts; optional `settings` for an options page), then run `python tools/build_index.py` and commit the regenerated `online_packages/index.json`.

**Marketplace API versions.** The marketplace is versioned (`pyos/marketapi.py`) so it can change without breaking systems already out there. A package may say `"api": N` in its `data.json` (default 1); the catalog is published as `index-api<N>.json` for every version (each lists the packages written for that version or older) while `index.json` stays the API 1 catalog for the oldest systems. A PythonOS asks for the file of its own version, falls back to `index.json`, and refuses (with a clear message) packages that need a newer API. To change the marketplace in a way old systems cannot follow: raise `CURRENT` in `marketapi.py`, add an adapter for the old version, run `python tools/build_index.py`, and mark the packages that need the new behaviour with the new `api`.

Pull requests are welcome! Whether you're improving code, fixing bugs, or adding features, feel free to get involved.

---

**Made with ❤️ by [Kalmai221](https://github.com/Kalmai221)**
👉 [View the Repo](https://github.com/Kalmai221/PythonOS)
