"""What every file of a PythonOS release is: which system it is for, which processor, and what kind of file it is.

One place that knows it, used by the release notes (release_notes.py), which also publishes it as release-catalog.json, and by the website,
which reads that catalog to choose the right download instead of guessing from file names. For a release made before the
catalog existed, classify() works it out from the name.

Fields of an entry:
    name      the file name
    os        windows | android | linux | bootable | vm | docker | system
    arch      x86_64 | aarch64 | any     (the processor the file is for; "any" works on both)
    kind      installer-web, installer, portable, apk, deb, rpm, pacman, tarball, iso, ova, qcow2, qcow2-data, vm-kit, ...
    variant   full | minimal | ""        (ISOs)
Standard library only.
"""
import re

# (regular expression for the name, os, arch, kind, variant)
RULES = [
    (r"^PythonOS-[\d.]+-web-setup\.exe$", "windows", "any", "installer-web", ""),
    (r"^PythonOS-[\d.]+-arm64-setup\.exe$", "windows", "aarch64", "installer", ""),
    (r"^PythonOS-[\d.]+-setup\.exe$", "windows", "x86_64", "installer", ""),
    (r"^PythonOS-[\d.]+-windows-arm64-portable\.zip$", "windows", "aarch64", "portable", ""),
    (r"^PythonOS-[\d.]+-windows-portable\.zip$", "windows", "x86_64", "portable", ""),
    (r"^PythonOS-[\d.]+-android-arm64-v8a\.apk$", "android", "aarch64", "apk", ""),
    (r"^PythonOS-[\d.]+-android-x86_64\.apk$", "android", "x86_64", "apk", ""),
    (r"^PythonOS-[\d.]+-android-installer\.apk$", "android", "any", "apk-installer", ""),
    (r"^PythonOS-[\d.]+-android\.apk$", "android", "any", "apk-universal", ""),   # releases before the installer app existed
    (r"^pythonos_[\d.]+_all\.deb$", "linux", "any", "deb", ""),
    (r"^pythonos-[\d.]+-1-any\.pkg\.tar\.zst$", "linux", "any", "pacman", ""),
    (r"^pythonos-[\d.]+-1\.noarch\.rpm$", "linux", "any", "rpm", ""),
    (r"^pythonos-[\d.]+-linux\.tar\.gz$", "linux", "any", "tarball", ""),
    (r"^pythonos-[\d.]+-minimal-x86_64\.iso$", "bootable", "x86_64", "iso", "minimal"),
    (r"^pythonos-[\d.]+-minimal-aarch64\.iso$", "bootable", "aarch64", "iso", "minimal"),
    (r"^pythonos-[\d.]+-x86_64\.iso$", "bootable", "x86_64", "iso", "full"),
    (r"^pythonos-[\d.]+-aarch64\.iso$", "bootable", "aarch64", "iso", "full"),
    (r"^pythonos-[\d.]+-vm\.ova$", "vm", "x86_64", "ova", "full"),
    (r"^pythonos-[\d.]+-vm-data\.qcow2$", "vm", "x86_64", "qcow2-data", ""),
    (r"^pythonos-[\d.]+-vm\.qcow2$", "vm", "x86_64", "qcow2", "full"),
    (r"^pythonos-[\d.]+-vm-kit\.zip$", "vm", "any", "vm-kit", ""),
    (r"^pythonos-core-[\d.]+\.zip$", "system", "any", "core", ""),
    (r"^core-manifest\.json$", "system", "any", "manifest", ""),
    (r"^SHA256SUMS(\.sigstore\.json)?$", "system", "any", "checksums", ""),
    (r"^release-catalog\.json$", "system", "any", "catalog", ""),
]


def classify(name):
    """{'name', 'os', 'arch', 'kind', 'variant'} for a release file name, or None when it is not a file this knows."""
    for pattern, os_name, arch, kind, variant in RULES:
        if re.match(pattern, name):
            return {"name": name, "os": os_name, "arch": arch, "kind": kind, "variant": variant}
    return None


def build(names):
    """The catalog entries of a list of file names (unknown names are left out)."""
    return [e for e in (classify(n) for n in names) if e]


def find(entries, os_name=None, kind=None, arch=None, variant=None):
    """The first entry that matches every given field. An entry for "any" processor matches whichever processor is asked for."""
    for e in entries:
        if os_name and e["os"] != os_name:
            continue
        if kind and e["kind"] != kind:
            continue
        if arch and e["arch"] not in (arch, "any"):
            continue
        if variant is not None and variant != "" and e["variant"] != variant:
            continue
        return e
    return None
