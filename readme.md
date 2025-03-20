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
4. **Extract** and run `app_windows.exe`.

---

### **🐧 Linux**
1. **Go to** [GitHub Actions](https://github.com/Kalmai221/PythonOS/actions).
2. Click on the latest successful **workflow run**.
3. Scroll down to **Artifacts** and download `linux-app.zip`.
4. **Extract** and **make it executable**:
   ```sh
   chmod +x app_linux.AppImage
   ```
5. **Run the application**:
   ```sh
   ./app_linux.AppImage
   ```

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
