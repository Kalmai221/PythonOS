### **README.md**

# 🚀 MyApp - Cross-Platform Executable Builder

## 📜 Overview
MyApp is a simple Python-based application that can be used on **Windows, Linux, and Android**.  
This repository includes workflows to automatically build `.exe` (Windows), `.AppImage` (Linux), and also allows running on Android via **Termux**.

---

## 📥 Download & Run

### **🖥️ Windows**
1. **Go to** [GitHub Actions](https://github.com/Kalmai221/PythonOS/actions).
2. Click on the latest successful **workflow run**.
3. Scroll down to **Artifacts** and download `windows-exe.zip`.
4. **Extract** and run `app_windows.exe`. This will check if Python is installed and install the OS.PY

---
### **🐧 Linux**
This application is compatible with various Linux distributions, including but not limited to:

- **Ubuntu**: A user-friendly Linux distribution based on Debian.
- **Debian**: A stable and versatile Linux distribution.
- **Fedora**: A cutting-edge Linux distribution known for its innovation.
- **CentOS**: A community-driven distribution based on Red Hat Enterprise Linux (RHEL).
- **Arch Linux**: A lightweight and flexible Linux distribution.

#### Installation Instructions

1. **Go to** [GitHub Actions](https://github.com/Kalmai221/PythonOS/actions).
2. Click on the latest successful **workflow run**.
3. Scroll down to **Artifacts** and download `linux-executables.zip`.
4. **Extract** the downloaded zip file.
5. **Make the application executable**:
   ```sh
   chmod +x PyOSInstaller_linux
   ```
6. **Run the application**:
   ```sh
   ./PyOSInstaller_linux
   ```

#### Installation via Package Managers

For users who prefer to install via package managers, you can follow these instructions based on your distribution:

- **Ubuntu/Debian**:
  ```sh
  sudo apt update
  sudo apt install python3 python3-pip
  ```

- **Fedora**:
  ```sh
  sudo dnf install python3 python3-pip
  ```

- **CentOS**:
  ```sh
  sudo yum install epel-release
  sudo yum install python3 python3-pip
  ```

- **Arch Linux**:
  ```sh
  sudo pacman -S python python-pip
  ```

After installing Python and pip, you can run the application as described above.

---

### **📱 Android (Termux)**
Since Android does not natively support `.exe` or `.AppImage`, you can run the script directly using **Termux**.

1. **Install Termux** from [F-Droid](https://f-droid.org/packages/com.termux/) or another trusted source.
2. Open Termux and install Python:
   ```sh
   pkg update && pkg upgrade
   pkg install python python-pip
   ```
3. **Go to** [GitHub Actions](https://github.com/Kalmai221/PythonOS/actions).
4. Click on the latest successful **workflow run**.
5. Scroll down to **Artifacts** and download `run-py.zip`.
6. Extract and **run the script**:
   ```sh
   python run.py
   ```
