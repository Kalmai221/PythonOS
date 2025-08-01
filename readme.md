# 🚀 PythonOS (PyOS) — A Terminal-Based Operating System Simulator

## 📖 Overview

**PythonOS** (PyOS) is a terminal-based pseudo-operating system built entirely in Python. It offers a modular, extensible environment for simulating basic OS-like functionality — including command execution, package management, and interactive shells — designed to work on:

* **Linux**
* **Android (via Termux)**

Windows was previously supported however it is easier to create this OS having access to ``pkg``

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

## 🛠️ Developer Notes

* ✅ **Python Version**: Python 3.7+ is required
* 🔒 **Permissions**: May require `chmod +x` for certain scripts
* 📂 **Do Not Move Files**: All files must remain in their extracted structure
* ☢️ **Security Tip**: Only download artifacts from trusted workflow runs
* 🐛 **Bugs or Feature Requests?** [Open an issue](https://github.com/Kalmai221/PythonOS/issues)

---

## 🤝 Contributing

Pull requests are welcome! Whether you're improving code, fixing bugs, or adding features, feel free to get involved.

---

**Made with ❤️ by [Kalmai221](https://github.com/Kalmai221)**
👉 [View the Repo](https://github.com/Kalmai221/PythonOS)
