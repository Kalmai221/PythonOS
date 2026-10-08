#!/usr/bin/env python3
"""Write the GitHub release page text for a version: what is new (from CHANGELOG.md), then every file with its size and what it is
for, how to verify it, and the compatibility table.

    VERSION=v1.2.0 python OS_Export/release_notes.py --plan plan.json --files artifacts --out body.md

Used by the release job in .github/workflows/build-os.yml. `--files` is the folder holding the release files, so the sizes are the real
ones; without it the sizes are left out. Nothing here needs the network.
"""
import argparse
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog  # noqa: E402
import make_core  # noqa: E402
import stage  # noqa: E402

# (file name pattern, export key, group, what it is, who it is for / how to use it). {v} is the version.
FILES = [
    ("PythonOS-{v}-web-setup.exe", "windows", "Windows", "Web installer", "Most Windows users. A tiny download that fetches the rest from GitHub, checks it, and offers Update, Repair or Uninstall. Light and dark, four languages."),
    ("PythonOS-{v}-setup.exe", "windows", "Windows", "Full installer (offline)", "Works without internet at install time (the PythonOS system itself still downloads on first start). Offers Update or Repair if PythonOS is already there."),
    ("PythonOS-{v}-windows-portable.zip", "windows", "Windows", "Portable zip", "No install: unzip anywhere (a USB stick works) and run PythonOS.exe."),
    ("PythonOS-{v}-arm64-setup.exe", "windows", "Windows", "Full installer for Windows on ARM", "Surface Pro X, Copilot+ PCs and ARM virtual machines. (The web installer picks the ARM64 package by itself.)"),
    ("PythonOS-{v}-windows-arm64-portable.zip", "windows", "Windows", "Portable zip for Windows on ARM", "No install: unzip and run PythonOS.exe on an ARM64 PC."),
    ("PythonOS-{v}-android-installer.apk", "android", "Android", "Installer app (about 1 MB)", "Start here on Android. A tiny app that finds out which processor your device has, downloads the right PythonOS app from this release, checks it and hands it to Android's installer."),
    ("PythonOS-{v}-android-arm64-v8a.apk", "android", "Android", "Phone APK (arm64)", "Nearly every phone and tablet made since 2016. Smallest full download."),
    ("PythonOS-{v}-android-x86_64.apk", "android", "Android", "APK for x86_64", "Chromebooks and Android emulators on PCs."),
    ("PythonOS-{v}-android.apk", "android", "Android", "Universal APK", "Works on any supported device, but is bigger. Use it if the arm64 one will not install."),
    ("pythonos_{v}_all.deb", "linux", "Linux", "Debian/Ubuntu package", "`sudo apt install ./pythonos_{v}_all.deb`; adds a menu entry and a `pythonos` command."),
    ("pythonos-{v}-linux.tar.gz", "linux", "Linux", "Tarball", "Any Linux, on any processor (Alpine, Void, Gentoo, NixOS...): unpack and run `./pythonos`."),
    ("pythonos-{v}-1-any.pkg.tar.zst", "linux", "Linux", "Arch package", "Arch, Manjaro, EndeavourOS: `sudo pacman -U pythonos-{v}-1-any.pkg.tar.zst`."),
    ("pythonos-{v}-1.noarch.rpm", "linux", "Linux", "RPM package", "Fedora, RHEL, Rocky, AlmaLinux, openSUSE: `sudo dnf install ./pythonos-{v}-1.noarch.rpm`."),
    ("pythonos-{v}-x86_64.iso", "iso", "Bootable", "Full live image", "Boot a PC from a USB stick or DVD without touching its disk. Includes Bluetooth, printing, the `installos` disk installer and VM guest tools. Needs 1 GB RAM."),
    ("pythonos-{v}-minimal-x86_64.iso", "iso", "Bootable", "Minimal live image", "The live system only: much smaller and lighter (runs in 512 MB). No Bluetooth, printing, installer or guest tools."),
    ("pythonos-{v}-aarch64.iso", "iso", "Bootable", "Full live image for 64-bit ARM", "UEFI ARM computers and virtual machines (ARM servers, Apple-silicon VMs, Raspberry Pi 4/5 with UEFI firmware). Same features as the PC image except the PC-only tools."),
    ("pythonos-{v}-minimal-aarch64.iso", "iso", "Bootable", "Minimal live image for 64-bit ARM", "The live system only, for ARM."),
    ("pythonos-{v}-vm.ova", "iso", "Virtual machine", "Appliance (OVA)", "VirtualBox or VMware: File > Import Appliance. 1 GB, 2 CPUs, NAT network, and a 2 GB data disk that keeps your accounts and files."),
    ("pythonos-{v}-vm.qcow2", "iso", "Virtual machine", "QEMU/KVM disk", "QEMU, KVM, libvirt, Proxmox: attach as a disk and boot."),
    ("pythonos-{v}-vm-data.qcow2", "iso", "Virtual machine", "QEMU/KVM data disk", "Attach it as a second disk next to the .qcow2: the VM then keeps your accounts, files and settings (2 GB)."),
    ("pythonos-{v}-vm-kit.zip", "iso", "Virtual machine", "Run scripts", "Scripts and a .vmx to boot the ISO in QEMU, VirtualBox or VMware yourself."),
    ("pythonos-core-{v}.zip", "", "System", "Core update package", "Not for people: PythonOS downloads this by itself when you run `updatecheck`."),
    ("core-manifest.json", "", "System", "Update manifest", "Not for people: tells installed copies what is new and how to verify it."),
    ("SHA256SUMS", "", "Verify", "Checksums", "SHA-256 of every file here. See 'Check your download' below."),
    ("SHA256SUMS.sigstore.json", "", "Verify", "Signature", "Proves SHA256SUMS was made by this repository's release workflow."),
]


# "Which file do I download?": one table per system, by the situation the reader is in. Each row: (situation, [files], how to use it).
# {v} is the version. A row whose files are not in this release (a build that failed or was skipped) is left out.
GUIDE = [
    ("Windows", "Windows 10 (1809) or newer.", [
        ("Most PCs (Intel or AMD)", ["PythonOS-{v}-web-setup.exe"], "Run it. A tiny installer that fetches and checks the rest; it offers shortcuts, update, repair and uninstall."),
        ("Windows on ARM (Surface Pro X, Copilot+ PCs)", ["PythonOS-{v}-web-setup.exe", "PythonOS-{v}-arm64-setup.exe"], "The web installer picks the ARM package by itself; the second file is the full offline installer for ARM."),
        ("No internet while installing", ["PythonOS-{v}-setup.exe"], "The full installer (Intel/AMD)."),
        ("No install at all (for example from a USB stick)", ["PythonOS-{v}-windows-portable.zip", "PythonOS-{v}-windows-arm64-portable.zip"], "Unzip anywhere and run `PythonOS.exe`. The second is for ARM."),
    ]),
    ("Android", "Android 7 or newer. Allow installs from this source when Android asks; updates come from inside PythonOS.", [
        ("Any phone, tablet or Chromebook (easiest)", ["PythonOS-{v}-android-installer.apk"], "A tiny installer (about 1 MB) that downloads the right PythonOS app for your device, checks it and installs it."),
        ("A phone or tablet, the full app directly", ["PythonOS-{v}-android-arm64-v8a.apk"], "Nearly all phones. About 25 MB."),
        ("A Chromebook or an Android emulator on a PC", ["PythonOS-{v}-android-x86_64.apk"], "For Intel/AMD processors."),
        ("Older release without the installer app", ["PythonOS-{v}-android.apk"], "Works everywhere, but is bigger."),
    ]),
    ("Linux", "Any distribution. The packages add a `pythonos` command and a menu entry.", [
        ("Debian, Ubuntu, Linux Mint, Pop!_OS, Raspberry Pi OS", ["pythonos_{v}_all.deb"], "`sudo apt install ./pythonos_{v}_all.deb`"),
        ("Fedora, RHEL, Rocky, AlmaLinux, openSUSE", ["pythonos-{v}-1.noarch.rpm"], "`sudo dnf install ./pythonos-{v}-1.noarch.rpm`"),
        ("Arch, Manjaro, EndeavourOS", ["pythonos-{v}-1-any.pkg.tar.zst"], "`sudo pacman -U pythonos-{v}-1-any.pkg.tar.zst`"),
        ("Anything else (Alpine, Void, Gentoo, NixOS...)", ["pythonos-{v}-linux.tar.gz"], "Unpack and run `./pythonos`. Needs Python 3.8+ with venv. Works on any processor."),
    ]),
    ("macOS", "There is no Mac version. Docker and virtual machines work on a Mac:", [
        ("A Mac with Docker Desktop", [], "`docker run -it --rm -v pythonos-data:/data ghcr.io/kalmai221/pythonos` (Intel and Apple silicon)"),
        ("A virtual machine in UTM or Parallels, Apple silicon", ["pythonos-{v}-aarch64.iso"], "Boot the ARM live image in a new virtual machine."),
        ("A virtual machine in UTM, VirtualBox or VMware, Intel Mac", ["pythonos-{v}-vm.ova", "pythonos-{v}-x86_64.iso"], "Import the appliance, or boot the live image."),
    ]),
    ("Docker", "Amd64 and arm64 (PCs, Raspberry Pi, Apple silicon). Nothing to download: Docker fetches it.", [
        ("Any computer with Docker", [], "`docker run -it --rm -v pythonos-data:/data ghcr.io/kalmai221/pythonos` — the volume keeps your accounts, files and updates."),
    ]),
    ("Bootable USB stick (the live system)", "Starts PythonOS on a computer without touching its disk. Write the image to the stick with an image-writing program (Rufus or balenaEtcher on Windows, `dd` on Linux) and check the download against SHA256SUMS first.", [
        ("A PC (Intel or AMD), 1 GB of RAM or more", ["pythonos-{v}-x86_64.iso"], "The full image: Bluetooth, printing, the `installos` disk installer and virtual machine tools."),
        ("A PC with little memory (512 MB)", ["pythonos-{v}-minimal-x86_64.iso"], "The live system only."),
        ("An ARM computer with UEFI (Raspberry Pi 4/5 with UEFI firmware, ARM servers)", ["pythonos-{v}-aarch64.iso", "pythonos-{v}-minimal-aarch64.iso"], "Full and minimal images for 64-bit ARM."),
    ]),
    ("Virtual machines", "The ready-made images are for Intel/AMD computers. On an ARM computer (Apple silicon) use the ARM image above in any program.", [
        ("VirtualBox or VMware", ["pythonos-{v}-vm.ova"], "File > Import Appliance. 1 GB, 2 CPUs, NAT network, and a data disk that keeps your files."),
        ("QEMU / KVM, libvirt, Proxmox", ["pythonos-{v}-vm.qcow2", "pythonos-{v}-vm-data.qcow2", "pythonos-{v}-vm-kit.zip"], "Attach the first as the boot disk and the second as a data disk; the kit has run scripts."),
        ("Hyper-V, UTM, Parallels or any other program", ["pythonos-{v}-x86_64.iso", "pythonos-{v}-aarch64.iso"], "Boot the live image (Intel/AMD or ARM)."),
    ]),
]


def quick_guide(version, sizes, tag):
    """The 'Which file do I download?' tables: one per system, by the reader's situation, with links to the files that exist."""
    out = []
    for title, intro, rows in GUIDE:
        lines = []
        for situation, patterns, how in rows:
            names = [p.replace("{v}", version) for p in patterns]
            if patterns and sizes:
                names = [n for n in names if n in sizes]
                if not names:
                    continue
            files = "<br>".join(f"[`{n}`]({download_link(tag, n)})" + (f" ({human(sizes[n])})" if n in sizes else "") for n in names) if names else "nothing to download"
            lines.append(f"| {situation} | {files} | {how.replace('{v}', version)} |")
        if lines:
            out += [f"### {title}", "", intro, "", "| You have | Download | How |", "|---|---|---|"] + lines + [""]
    return out


def write_catalog(path, version, sizes, tag):
    """release-catalog.json: every file of the release with its system, processor, kind and size, for the website."""
    entries = []
    for name in sorted(sizes):
        entry = catalog.classify(name)
        if entry:
            entry["size"] = sizes[name]
            entry["url"] = download_link(tag, name)
            entries.append(entry)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"format": 1, "version": version, "tag": tag, "files": entries}, f, indent=2)
        f.write("\n")
    return len(entries)


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def compatibility_table():
    try:
        with open(os.path.join(stage.REPO, "COMPATIBILITY.md"), encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return ""
    return "\n".join(l for l in text.splitlines() if l.startswith("|"))


def sizes_of(folder):
    """{file name: bytes} for the files in `folder` ({} if there is none)."""
    if not folder or not os.path.isdir(folder):
        return {}
    return {n: os.path.getsize(os.path.join(folder, n)) for n in os.listdir(folder) if os.path.isfile(os.path.join(folder, n))}


REPO_URL = "https://github.com/Kalmai221/PythonOS"


def release_tag(version):
    """The tag the files are attached to: v1.2.0 (from the VERSION variable of the workflow when it is a tag, otherwise built from the version)."""
    raw = os.environ.get("VERSION", "").strip()
    return raw if raw.startswith("v") else "v" + version


def download_link(tag, name):
    return f"{REPO_URL}/releases/download/{tag}/{name}"


def file_table(version, sizes, exports):
    """Markdown table(s): one row per file, grouped, with size and purpose. Files that are not known are listed under 'Other'."""
    known = {}
    for pattern, key, group, title, use in FILES:
        known[pattern.replace("{v}", version)] = (key, group, title, use.replace("{v}", version))
    rows, seen = {}, set()
    order = []
    tag = release_tag(version)
    for name, (key, group, title, use) in known.items():
        if sizes and name not in sizes:
            continue                       # not part of this release (for example a platform that was not built)
        seen.add(name)
        if group not in rows:
            rows[group] = []
            order.append(group)
        item = exports.get(key) or {}
        note = ""
        if key and item and not item.get("build", True) and item.get("entry"):
            note = f" _(same file as {item['entry'].get('version', 'an earlier release')}: nothing in it changed)_"
        size = human(sizes[name]) if name in sizes else ""
        rows[group].append((name, title, size, use + note))
    other = [n for n in sorted(sizes) if n not in seen]
    out = []
    for group in order:
        out += [f"### {group}", "", "| File | What it is | Size | Use it for |", "|---|---|---|---|"]
        for name, title, size, use in rows[group]:
            out.append(f"| [`{name}`]({download_link(tag, name)}) | {title} | {size or '-'} | {use} |")
        out.append("")
    if other:
        out += ["### Other", "", "| File | Size |", "|---|---|"] + [f"| [`{n}`]({download_link(tag, n)}) | {human(sizes[n])} |" for n in other] + [""]
    return out


def build(version, plan, sizes=None):
    exports = (plan or {}).get("exports", {})
    parts = make_core.changelog_parts(version)
    out = [f"# PythonOS {version}", ""]
    out += ["## What's new", ""]
    titles = {"PythonOS": "PythonOS updates (installed by `updatecheck`, no new download)",
              "Apps": "App updates (the marketplace: `pkg update all`; already live, no PythonOS update needed)",
              "Exports": "Export updates (the packages: a new download is needed to get these)",
              "Website": "Website updates", "Development": "Development"}
    if len(parts) == 1 and "PythonOS" in parts:
        out += [make_core.changelog_notes(version), ""]
    elif parts:
        for part in make_core.PARTS:
            if parts.get(part):
                out += [f"### {titles[part]}", "", make_core.changelog_notes(version, part), ""]
    else:
        out += ["See the commit history for this release.", ""]
    out += ["## Which file do I download?", "",
            "Pick one line for your device. Everything below also updates itself from inside PythonOS later (run `updatecheck`); "
            "you only download a new package when it says it has to be reinstalled.", ""]
    out += quick_guide(version, sizes or {}, release_tag(version))
    out += ["## Every file", "", "The same files with their size and what each one is for.", ""]
    out += file_table(version, sizes or {}, exports)
    out += ["## Check your download", "",
            "Every file is listed in `SHA256SUMS`. Compare with `sha256sum -c SHA256SUMS --ignore-missing` (Linux/macOS) or "
            "`Get-FileHash <file>` (Windows PowerShell). `SHA256SUMS.sigstore.json` is a signature made by this repository's release workflow "
            "(verify with `cosign verify-blob --bundle SHA256SUMS.sigstore.json --certificate-identity-regexp 'github.com/Kalmai221/PythonOS' "
            "--certificate-oidc-issuer https://token.actions.githubusercontent.com SHA256SUMS`). Build provenance is attached to the files "
            "(`gh attestation verify <file> --repo Kalmai221/PythonOS`).", ""]
    pin = os.path.join(stage.REPO, "OS_Export", "Android", "signing.sha256")
    if os.path.isfile(pin):
        with open(pin, encoding="utf-8") as f:
            fingerprint = f.read().strip()
        out += ["Every Android APK of every release is signed with one key, so each installs over the one before it. Its certificate SHA-256 is "
                f"`{fingerprint}` (check an APK with `apksigner verify --print-certs <apk>`).", ""]
    table = compatibility_table()
    if table:
        out += ["## Compatibility", "", table, ""]
    out += ["---", "Found a problem? Run `report` inside PythonOS, or open an issue."]
    return "\n".join(out) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", default="")
    parser.add_argument("--files", default="", help="folder with the release files (for real sizes)")
    parser.add_argument("--out", default="body.md")
    parser.add_argument("--catalog", default="", help="also write release-catalog.json here (the files of the release, classified)")
    args = parser.parse_args()
    plan = None
    if args.plan and os.path.exists(args.plan):
        with open(args.plan, encoding="utf-8") as f:
            plan = json.load(f)
    sizes = sizes_of(args.files)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(build(stage.version(), plan, sizes))
    print(f"Wrote {args.out}")
    if args.catalog:
        print(f"Wrote {args.catalog} ({write_catalog(args.catalog, stage.version(), sizes, release_tag(stage.version()))} files)")


if __name__ == "__main__":
    main()
