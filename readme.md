# 🚀 PythonOS - Cross-Platform Executable Builder

## 📜 Overview
**PythonOS** is a versatile Python-based application designed to run seamlessly on **Windows, Linux, and Android (via Termux)**.  
This repository includes automated workflows that build platform-specific executables:  
- Windows: `.exe`  
- Linux: Script execution via Terminal
- Android: Script execution via Termux  

Whether you're a developer or user, this guide will help you download, install, and run MyApp on your preferred platform with ease.

---

## 📥 Download & Installation

### 🖥️ Windows
1. Navigate to the [GitHub Actions page](https://github.com/Kalmai221/PythonOS/actions).
2. Select the latest **successful workflow run**.
3. Scroll to **Artifacts** and download `windows-exe.zip`.
4. Extract the ZIP archive.
5. Run `app_windows.exe`.  
   This executable will check for Python installation and handle OS.PY setup automatically.

---

### 🐧 Linux

MyApp supports popular Linux distributions such as:

- Ubuntu  
- Debian  
- Fedora  
- CentOS  
- Arch Linux  

#### Installation Steps:
1. Visit the [GitHub Actions page](https://github.com/Kalmai221/PythonOS/actions).
2. Open the latest **successful workflow run**.
3. Download the artifact named `installer-runpy.zip`.
4. Ensure Python is installed on your system (`python --version`).
5. Extract `installer-runpy.zip`.
6. Run the application with:
   ```bash
   python run.py
   ```

---

### 📱 Android (Termux)

Since Android does not support `.exe` natively, use **Termux** to run the Python script directly.

#### Setup Termux and Python:

```bash
pkg update && pkg upgrade
pkg install python python-pip
```

#### Installation Steps:

1. Go to the [GitHub Actions page](https://github.com/Kalmai221/PythonOS/actions).
2. Download the latest `installer-runpy.zip` from the most recent successful run.
3. Extract the ZIP file inside Termux.
4. Run the application:

   ```bash
   python run.py
   ```

---

## ⚙️ Notes & Best Practices

* **Python Version:** Ensure Python 3.7+ is installed for compatibility.
* **Permissions:** On Linux and Android, you might need appropriate permissions to execute scripts or access certain directories.
* **File Paths:** The application expects to be run with access to the current working directory; avoid moving extracted files arbitrarily.
* **Security:** Download artifacts only from trusted releases to prevent security risks.
* **Feedback & Issues:** For bugs, feature requests, or support, please open an issue on the repository.

---

Thank you for choosing **PythonOS**!
We welcome contributions and community involvement to keep improving cross-platform Python experiences.

---

*Made with ❤️ by Kalmai221*
[GitHub Repository](https://github.com/Kalmai221/PythonOS)
