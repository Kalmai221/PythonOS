#!/usr/bin/env python3
"""Regenerate online_packages/index.json - the catalog the PyOS marketplace reads.

Run this from anywhere after adding or changing a package, then commit and push
online_packages/index.json together with the package:

    python tools/build_index.py

Each package is a folder online_packages/<category>/<name>/ containing a data.json
(name, description, version, command, alias, tags, scripts) plus its files.
"""
import hashlib
import json
import os
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "online_packages")
ROOT = os.path.abspath(ROOT)
SKIP_DIRS = {"__pycache__"}
SKIP_FILES = {".DS_Store", "Thumbs.db"}


def digest(path):
    """SHA-256 of the file as stored in git (text normalised to LF)."""
    with open(path, "rb") as f:
        data = f.read()
    if b"\0" not in data:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest(), len(data)


def package_files(folder):
    files = []
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name in SKIP_FILES or name.endswith((".pyc", ".pyo")):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, folder).replace(os.sep, "/")
            sha, size = digest(full)
            files.append({"path": rel, "sha256": sha, "size": size})
    return files


def main():
    packages = []
    for category in sorted(os.listdir(ROOT)):
        cat_dir = os.path.join(ROOT, category)
        if not os.path.isdir(cat_dir) or category in SKIP_DIRS:
            continue
        for name in sorted(os.listdir(cat_dir)):
            folder = os.path.join(cat_dir, name)
            meta_path = os.path.join(folder, "data.json")
            if not os.path.isfile(meta_path):
                continue
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
            except ValueError as e:
                sys.exit(f"{meta_path}: invalid JSON ({e})")
            packages.append({
                "id": f"{category}/{name}",
                "category": category,
                "name": meta.get("name", name),
                "description": meta.get("description", ""),
                "version": str(meta.get("version", "0.0.0")),
                "command": meta.get("command", ""),
                "alias": meta.get("alias", []),
                "tags": meta.get("tags", []),
                "files": package_files(folder),
            })
    index = {"format": 1, "packages": packages}
    out = os.path.join(ROOT, "index.json")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(index, f, indent=2)
        f.write("\n")
    print(f"Wrote {out} ({len(packages)} packages)")


if __name__ == "__main__":
    main()
