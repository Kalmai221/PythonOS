"""Which processor this computer really has, as far as it can be told: the one place the answer comes from.

Reading platform.machine() is not enough. A program can run emulated (an x64 program on Windows on ARM, an Intel program on an Apple-silicon
Mac under Rosetta, a 32-bit program on a 64-bit system), and then it reports the processor it was built for, not the one it runs on. For
choosing a download (an APK, an ISO, an installer) the real processor matters, so detect() asks the system: IsWow64Process2 on Windows,
sysctl on macOS, the primary ABI on Android, the kernel on Linux.

Standard library only (the Flash program and the installers load this file on their own).
"""
import functools
import os
import platform
import struct
import subprocess

ALIASES = {
    "x86_64": "x86_64", "amd64": "x86_64", "x64": "x86_64", "x86-64": "x86_64", "em64t": "x86_64",
    "aarch64": "aarch64", "arm64": "aarch64", "arm64e": "aarch64", "armv8": "aarch64", "armv8-a": "aarch64", "arm64-v8a": "aarch64",
    "armv7l": "armv7", "armv7": "armv7", "armhf": "armv7", "armeabi-v7a": "armv7", "armv8l": "armv7", "armv6l": "armv6", "arm": "armv7",
    "i386": "x86", "i486": "x86", "i586": "x86", "i686": "x86", "x86": "x86",
    "riscv64": "riscv64", "ppc64le": "ppc64le", "s390x": "s390x", "loongarch64": "loongarch64",
}
LABELS = {"x86_64": "Intel / AMD (64-bit)", "aarch64": "ARM (64-bit)", "armv7": "ARM (32-bit)", "armv6": "ARM (32-bit, old)", "x86": "Intel / AMD (32-bit)",
          "riscv64": "RISC-V (64-bit)", "ppc64le": "PowerPC (64-bit)", "s390x": "IBM Z", "loongarch64": "LoongArch (64-bit)"}
SUPPORTED = ("x86_64", "aarch64")                       # the processors PythonOS packages (Windows, ISO, Android, Docker) are built for
WINDOWS_MACHINES = {0x8664: "x86_64", 0xAA64: "aarch64", 0x014C: "x86", 0x01C4: "armv7", 0x01C0: "armv7"}
ANDROID_ABIS = {"arm64-v8a": "aarch64", "x86_64": "x86_64", "armeabi-v7a": "armv7", "x86": "x86"}


def normalize(raw):
    """A processor name as the systems spell it (AMD64, arm64, armv8l, i686...) -> x86_64, aarch64, armv7, x86... ('' stays '')."""
    text = str(raw or "").strip().lower()
    return ALIASES.get(text, text)


def _windows_native():
    """The processor Windows runs on, even for an emulated program (IsWow64Process2, Windows 10 1709 and newer)."""
    try:
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.windll.kernel32
        function = getattr(kernel, "IsWow64Process2", None)
        if function is not None:
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            function.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.USHORT), ctypes.POINTER(wintypes.USHORT)]
            process, native = wintypes.USHORT(), wintypes.USHORT()
            if function(kernel.GetCurrentProcess(), ctypes.byref(process), ctypes.byref(native)):
                found = WINDOWS_MACHINES.get(native.value)
                if found:
                    return found
    except Exception:
        pass
    return normalize(os.environ.get("PROCESSOR_ARCHITEW6432") or os.environ.get("PROCESSOR_ARCHITECTURE"))


def _sysctl(name):
    try:
        out = subprocess.run(["sysctl", "-n", name], capture_output=True, text=True, timeout=3)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _mac_native():
    """aarch64 on an Apple-silicon Mac (even for a program running translated by Rosetta), else ''."""
    if _sysctl("hw.optional.arm64") == "1" or _sysctl("sysctl.proc_translated") == "1":
        return "aarch64"
    return ""


def _android_abi():
    """The processor of an Android device from its primary ABI (Build.SUPPORTED_ABIS), when this runs inside the app; else ''."""
    try:
        from java import jclass
        abis = list(jclass("android.os.Build").SUPPORTED_ABIS)
        return ANDROID_ABIS.get(str(abis[0]), normalize(str(abis[0]))) if abis else ""
    except Exception:
        return ""


@functools.lru_cache(maxsize=1)
def detect():
    """{'arch': the processor of the computer, 'process': the one this program was built for, 'emulated': the two differ, 'bits': of this
    program, 'label': words for people, 'supported': PythonOS has packages for it, 'note': what to know, or ''}."""
    system = platform.system()
    process = normalize(platform.machine()) or normalize(os.environ.get("PROCESSOR_ARCHITECTURE"))
    native = process
    abi = _android_abi()
    if abi:
        native = abi
    elif system == "Windows":
        native = _windows_native() or process
    elif system == "Darwin":
        native = _mac_native() or process
    bits = struct.calcsize("P") * 8
    note = ""
    if native != process:
        note = f"this program is built for {LABELS.get(process, process)} but the computer is {LABELS.get(native, native)}"
    elif bits == 32 and native in ("aarch64", "x86_64"):
        note = "a 32-bit program is running on a 64-bit processor"
    if native == "armv7" and system == "Linux":
        note = note or "32-bit ARM (a Raspberry Pi running a 32-bit system? the 64-bit images need a 64-bit system)"
    return {"arch": native, "process": process, "emulated": native != process, "bits": bits, "label": LABELS.get(native, native or "unknown"),
            "supported": native in SUPPORTED, "note": note}


def arch():
    """The computer's processor: x86_64, aarch64, armv7, x86, riscv64..."""
    return detect()["arch"]


def describe():
    """One line for people: 'ARM (64-bit)', or 'ARM (64-bit) (this program runs emulated as Intel / AMD (64-bit))'."""
    info = detect()
    text = info["label"]
    if info["emulated"]:
        text += f" (this program runs emulated as {LABELS.get(info['process'], info['process'])})"
    return text
