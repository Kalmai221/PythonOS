# 🚀 PythonOS (PyOS) — A Terminal-Based Operating System Simulator

## 📖 Overview

**PythonOS** (PyOS) is a terminal-based pseudo-operating system built entirely in Python. It offers a modular, extensible environment for simulating basic OS-like functionality — including command execution, package management, and interactive shells — designed to work on:

* **Windows**
* **Linux**
* **Android (via Termux)**

---

## 📥 Installation Guide

### ✅ Requirements

* Python 3.7 or higher
* GitHub access to download latest builds
* Basic terminal usage knowledge

---

### 💻 Linux Installation

1. Ensure Python 3.7+ is installed:

```bash
sudo apt update && sudo apt install python3 python3-pip
```

2. Download the launcher script directly:

```bash
curl -O https://raw.githubusercontent.com/Kalmai221/PythonOS/main/installer/run.py
```

3. Run PythonOS:

```bash
python3 run.py
```

> The `run.py` script is the official PythonOS launcher, managing initialization, package installation, and the terminal interface.

---

### 🪟 Windows Installation

1. Install [Python 3.7+](https://www.python.org/downloads/) (tick "Add Python to PATH").

2. Download the launcher script (PowerShell):

```powershell
curl.exe -O https://raw.githubusercontent.com/Kalmai221/PythonOS/main/installer/run.py
```

3. Run PythonOS:

```powershell
python run.py
```

---

### 📱 Android Installation (via Termux)

1. Install Termux from [F-Droid](https://f-droid.org/en/packages/com.termux/).

2. Update packages and install Python:

```bash
pkg update && pkg upgrade
pkg install python curl
```

3. Download and run the launcher script:

```bash
curl -O https://raw.githubusercontent.com/Kalmai221/PythonOS/main/installer/run.py
python3 run.py
```

---

---

## ✨ Newer features

* **Undo**: `rm` sends things to a trash; `undo` brings the last one back (`trash` lists, restores, empties)
* **Finding things**: `find -name "*.txt" -size +1M`, `grep -rn word folder`, `tree -L 2`, `diff a b`
* **Learn**: `tutorial` (28 lessons that check what you type, saves your place), `quickstart` (two minutes), `help <category>`
* **When things go wrong**: `whathappened` (after a power cut or crash), `doctor`, `report` (a redacted report you read before sending), `diag`
* **Languages**: `settings set language es|fr|de|en` changes the system's own messages (commands stay in English)
* **Live USB / installed**: `installos` copies PythonOS to a disk (experimental); `persist` keeps your data; press D at start for diagnostics
* **Windows**: PythonOS opens in its own window; the web installer checks every download; `updatecheck` can update the app in place

## 🖥️ Using PyOS

PyOS behaves like a small Unix-style system:

* **Filesystem** – `files/` is `/`, with `/home/<user>`, `/etc`, `/tmp` and `/var/log`. Every login starts in your home (`~`).
* **Permissions** – regular users can write only in their own home and `/tmp` and cannot enter other homes; admins can do everything (prompt ends in `#` instead of `$`).
* **Shell** – quotes, pipes (`ls | grep txt`), redirects (`echo hi > a.txt`, `>>`), `;`, `&&`, `||` and `&` (background jobs), `$?`, tab completion and history. Commands report success or failure, so `make && echo ok` works.
* **Commands** – `ls cd pwd cat head tail wc grep find touch mkdir rm cp mv tree edit echo date uname hostname uptime free df whoami history logs` and more; run `help` for the list, `man <command>` for the manual and `tutorial` for a guided tour.
* **Editor** – `edit <file>` is a built-in editor (full screen on a real terminal, a line editor elsewhere).
* **Jobs and scheduling** – `sleep 30 &`, `jobs`, `fg`, `kill`; `schedule add daily 08:00 backup create`; results arrive as notifications.
* **Settings and themes** – `settings` (themes, prompt style, boot speed, auto-lock, `auto_clear_lines` to keep the screen tidy). `clear` wipes the screen and scrollback (`clear -x` keeps it).
* **Backup and sharing** – `backup create|restore`, and `share send|receive` to move files between devices on the same network.
* **Accounts and security** – salted password hashes, escalating lockout after wrong passwords, `passwd`, `su`, `lock` and `last`.
* **Marketplace** – `market` opens the store (browse, featured, search, update, remove); `pkg install <name>`, `pkg update all`. Packages are verified with checksums, can depend on each other (installed together), show what changed in an update, and reinstall offline from a local cache. Apps include Clock (timer, stopwatch, alarms), Calendar, Converter, Snippets, Files, Notes, Markdown Viewer, RSS Reader, Network Tools, System Monitor, Weather, Chess, Snake, 2048, Wordle, Trivia and more.
* **Updates** – PythonOS updates itself from GitHub releases; installers (APK, Windows, Linux package, ISO) cannot, so PythonOS tells you when a newer one is available.
* **Live ISO** – a locked-down, PythonOS-only system: hardware, audio, Wi-Fi, keyboard and time-zone setup (`hwsetup`) and optional persistent storage on a USB stick (`persist create`).
* **Logs** – logins, account changes, crashes and boot/shutdown are recorded in `/var/log/system.log` (view with `logs`).

---

## 🛠️ Developer Notes

* ✅ **Python Version**: Python 3.7+ is required
* 🔒 **Permissions**: May require `chmod +x` for certain scripts
* 📂 **Do Not Move Files**: All files must remain in their extracted structure
* ☢️ **Security Tip**: Only download artifacts from trusted workflow runs
* 🐛 **Bugs or Feature Requests?** [Open an issue](https://github.com/Kalmai221/PythonOS/issues)

---

## 🤝 Contributing

Adding a marketplace package: put it in `online_packages/<category>/<name>/` with a `data.json` (name, description, version, command, tags, scripts), then run `python tools/build_index.py` and commit the regenerated `online_packages/index.json`.



Pull requests are welcome! Whether you're improving code, fixing bugs, or adding features, feel free to get involved.

---

**Made with ❤️ by [Kalmai221](https://github.com/Kalmai221)**
👉 [View the Repo](https://github.com/Kalmai221/PythonOS)
