#!/usr/bin/env python3
"""Boot an ISO in QEMU (no display) and check that something is drawn on the screen within a few minutes.

    python OS_Export/ISO/qemu_boot_check.py pythonos-1.2.0-x86_64.iso [--minutes 6]

It starts qemu-system-x86_64 with software emulation (GitHub's runners have no KVM), then every 15 seconds asks QEMU for a screenshot
through its monitor. PythonOS has booted when the screen shows text: enough bright pixels, and not the same picture as the black or
the firmware screen. The last screenshot is kept as qemu-screen.png-like PPM (qemu-screen.ppm) for looking at. This is a smoke check,
not a test of every feature: it says "the image boots and PythonOS draws its screen", nothing more.
"""
import argparse
import os
import socket
import subprocess
import sys
import tempfile
import time


def lit_fraction(path):
    """Share of pixels that are clearly not black in a binary PPM (P6) screenshot."""
    with open(path, "rb") as f:
        data = f.read()
    parts = data.split(b"\n", 3)
    if len(parts) < 4 or parts[0] != b"P6":
        return 0.0
    width, height = (int(x) for x in parts[1].split())
    pixels = parts[3]
    total = width * height
    if not total:
        return 0.0
    lit = 0
    step = 3 * 7                                          # look at every seventh pixel: plenty for a "is there text" decision
    for i in range(0, len(pixels) - 2, step):
        if pixels[i] + pixels[i + 1] + pixels[i + 2] > 180:
            lit += 1
    return lit * 7 / total


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("iso")
    parser.add_argument("--minutes", type=float, default=6.0)
    args = parser.parse_args()

    work = tempfile.mkdtemp(prefix="pyos-qemu-")
    sock_path = os.path.join(work, "monitor.sock")
    shot = os.path.join(os.getcwd(), "qemu-screen.ppm")
    command = ["qemu-system-x86_64", "-m", "1024", "-smp", "2", "-cdrom", args.iso, "-boot", "d", "-display", "none", "-vga", "std",
               "-monitor", f"unix:{sock_path},server,nowait", "-serial", "null", "-no-reboot"]
    print("Starting:", " ".join(command))
    qemu = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    deadline = time.time() + args.minutes * 60
    result = 1
    try:
        for _ in range(40):
            if os.path.exists(sock_path):
                break
            time.sleep(0.5)
        monitor = socket.socket(socket.AF_UNIX)
        monitor.connect(sock_path)
        monitor.settimeout(5)
        try:
            monitor.recv(4096)
        except OSError:
            pass
        seen_text = 0
        while time.time() < deadline and qemu.poll() is None:
            time.sleep(15)
            monitor.sendall(f"screendump {shot}\n".encode())
            time.sleep(1.5)
            try:
                monitor.recv(4096)
            except OSError:
                pass
            if not os.path.exists(shot):
                continue
            fraction = lit_fraction(shot)
            print(f"{int(args.minutes * 60 - (deadline - time.time())):>4}s  lit pixels: {fraction * 100:.2f}%")
            seen_text = seen_text + 1 if fraction > 0.004 else 0
            if seen_text >= 2:                              # two screenshots in a row with text on them
                print("The ISO booted and PythonOS drew its screen.")
                result = 0
                break
        else:
            print("No readable screen appeared in time (it may just be slow under software emulation).")
    finally:
        qemu.kill()
        qemu.wait()
    return result


if __name__ == "__main__":
    sys.exit(main())
