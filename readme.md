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

## 🖥️ Using PyOS

PyOS behaves like a small Unix-style system:

* **Filesystem** – `files/` is `/`, with `/home/<user>`, `/etc`, `/tmp` and `/var/log`. Every login starts in your home (`~`).
* **Permissions** – regular users can write only in their own home and `/tmp` and cannot enter other homes; admins can do everything (prompt ends in `#` instead of `$`).
* **Shell** – quotes, pipes (`ls | grep txt`), redirects (`echo hi > a.txt`, `>>`), `;` to chain commands, tab completion and command history.
* **Commands** – `ls cd pwd cat head tail wc grep touch mkdir rm cp mv tree edit echo date uname hostname uptime free df whoami history logs` and more; run `help` for the full list or `help <name>` for details.
* **Marketplace** – `run marketplace` opens the store (browse, search, update, remove). From the shell, `pkg search <words>`, `pkg install <name>`, `pkg update`, `pkg remove <name>` and `pkg list` do the same. Packages are verified with checksums and usable straight away.
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
