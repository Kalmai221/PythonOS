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
import make_core  # noqa: E402
import stage  # noqa: E402

# (file name pattern, export key, group, what it is, who it is for / how to use it). {v} is the version.
FILES = [
    ("PythonOS-{v}-web-setup.exe", "windows", "Windows", "Web installer", "Most Windows users. A tiny download that fetches the rest from GitHub, checks it, and offers Update, Repair or Uninstall. Light and dark, four languages."),
    ("PythonOS-{v}-setup.exe", "windows", "Windows", "Full installer (offline)", "Works without internet at install time (the PythonOS system itself still downloads on first start). Offers Update or Repair if PythonOS is already there."),
    ("PythonOS-{v}-windows-portable.zip", "windows", "Windows", "Portable zip", "No install: unzip anywhere (a USB stick works) and run PythonOS.exe."),
    ("PythonOS-{v}-android-arm64-v8a.apk", "android", "Android", "Phone APK (arm64)", "Nearly every phone and tablet made since 2016. Smallest download."),
    ("PythonOS-{v}-android-x86_64.apk", "android", "Android", "APK for x86_64", "Chromebooks and Android emulators on PCs."),
    ("PythonOS-{v}-android.apk", "android", "Android", "Universal APK", "Works on any supported device, but is bigger. Use it if the arm64 one will not install."),
    ("pythonos_{v}_all.deb", "linux", "Linux", "Debian/Ubuntu package", "`sudo apt install ./pythonos_{v}_all.deb`; adds a menu entry and a `pythonos` command."),
    ("pythonos-{v}-linux.tar.gz", "linux", "Linux", "Tarball", "Any Linux: unpack and run `./pythonos`."),
    ("pythonos-{v}-x86_64.iso", "iso", "Bootable", "Full live image", "Boot a PC from a USB stick or DVD without touching its disk. Includes Bluetooth, printing, the `installos` disk installer and VM guest tools. Needs 1 GB RAM."),
    ("pythonos-{v}-minimal-x86_64.iso", "iso", "Bootable", "Minimal live image", "The live system only: much smaller and lighter (runs in 512 MB). No Bluetooth, printing, installer or guest tools."),
    ("pythonos-flash-tool-{v}.py", "iso", "Bootable", "USB writer", "Run with Python on Windows/Linux/macOS: checks the ISO against its checksum, writes the stick (only removable drives), reads it back."),
    ("pythonos-{v}-vm.ova", "iso", "Virtual machine", "Appliance (OVA)", "VirtualBox or VMware: File > Import Appliance. 1 GB, 2 CPUs, NAT network."),
    ("pythonos-{v}-vm.qcow2", "iso", "Virtual machine", "QEMU/KVM disk", "QEMU, KVM, libvirt, Proxmox: attach as a disk and boot."),
    ("pythonos-{v}-vm-kit.zip", "iso", "Virtual machine", "Run scripts", "Scripts and a .vmx to boot the ISO in QEMU, VirtualBox or VMware yourself."),
    ("pythonos-core-{v}.zip", "", "System", "Core update package", "Not for people: PythonOS downloads this by itself when you run `updatecheck`."),
    ("core-manifest.json", "", "System", "Update manifest", "Not for people: tells installed copies what is new and how to verify it."),
    ("SHA256SUMS", "", "Verify", "Checksums", "SHA-256 of every file here. See 'Check your download' below."),
    ("SHA256SUMS.sigstore.json", "", "Verify", "Signature", "Proves SHA256SUMS was made by this repository's release workflow."),
]


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


def file_table(version, sizes, exports):
    """Markdown table(s): one row per file, grouped, with size and purpose. Files that are not known are listed under 'Other'."""
    known = {}
    for pattern, key, group, title, use in FILES:
        known[pattern.replace("{v}", version)] = (key, group, title, use.replace("{v}", version))
    rows, seen = {}, set()
    order = []
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
            out.append(f"| `{name}` | {title} | {size or '-'} | {use} |")
        out.append("")
    if other:
        out += ["### Other", "", "| File | Size |", "|---|---|"] + [f"| `{n}` | {human(sizes[n])} |" for n in other] + [""]
    return out


def build(version, plan, sizes=None):
    exports = (plan or {}).get("exports", {})
    notes = make_core.changelog_notes(version)
    out = [f"# PythonOS {version}", ""]
    out += ["## What's new", "", notes or "See the commit history for this release.", ""]
    out += ["## Which file do I download?", "",
            "Pick one line for your device. Everything below also updates itself from inside PythonOS later (run `updatecheck`); "
            "you only download a new package when it says it has to be reinstalled.", ""]
    out += file_table(version, sizes or {}, exports)
    out += ["## Check your download", "",
            "Every file is listed in `SHA256SUMS`. Compare with `sha256sum -c SHA256SUMS --ignore-missing` (Linux/macOS) or "
            "`Get-FileHash <file>` (Windows PowerShell). `SHA256SUMS.sigstore.json` is a signature made by this repository's release workflow "
            "(verify with `cosign verify-blob --bundle SHA256SUMS.sigstore.json --certificate-identity-regexp 'github.com/Kalmai221/PythonOS' "
            "--certificate-oidc-issuer https://token.actions.githubusercontent.com SHA256SUMS`). Build provenance is attached to the files "
            "(`gh attestation verify <file> --repo Kalmai221/PythonOS`).", ""]
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
    args = parser.parse_args()
    plan = None
    if args.plan and os.path.exists(args.plan):
        with open(args.plan, encoding="utf-8") as f:
            plan = json.load(f)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(build(stage.version(), plan, sizes_of(args.files)))
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
