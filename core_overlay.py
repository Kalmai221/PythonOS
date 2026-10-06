#!/usr/bin/env python3
"""Keep an updated copy of PythonOS's own files where the system itself cannot keep them.

On the live ISO and in a Docker container the program files live in an image that is rebuilt (or in memory) at every start, so an update made
with `updatecheck` would be gone at the next start - only the data disk (or volume) survives. When one is in use (PYOS_CORE_OVERLAY=1), an
update also saves the new program files into .OSData/core_overlay/ on that disk, and this program puts them back at the next start:

    python core_overlay.py          run before PythonOS starts (the ISO's session script and the Docker entrypoint do)

The rules:
  * the overlay is applied only when it is NEWER than the image that is starting. Start a new ISO or image and the image wins: the old
    overlay is deleted, so a new release is never held back by an old update
  * every file is checked against the SHA-256 the update recorded; anything that does not match is ignored and the overlay is deleted
  * only PythonOS's own code folders and root files are covered, never accounts, files or settings
  * it never raises and never prints: a problem leaves the image as it was
Standard library only: it runs before anything else is loaded.
"""
import hashlib
import json
import os
import re
import shutil
import sys

CODE_DIRS = ("commands", "core", "programs", "pyos")
OVERLAY = os.path.join(".OSData", "core_overlay")
MANIFEST = "overlay.json"


def enabled():
    return os.environ.get("PYOS_CORE_OVERLAY") == "1"


def version_key(text):
    numbers = [int(n) for n in re.findall(r"\d+", str(text).split("-")[0])]
    numbers += [0] * (4 - len(numbers))
    return tuple(numbers), 0 if "dev" in str(text).lower() else 1


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def image_version(root="."):
    try:
        with open(os.path.join(root, "config.json"), encoding="utf-8") as f:
            return str(json.load(f).get("version", "0"))
    except (OSError, ValueError):
        return "0"


def save(rels, version, root="."):
    """Remember the program files `rels` (paths relative to the root) as they are now, as the version `version`. Called after an update."""
    target = os.path.join(root, OVERLAY)
    shutil.rmtree(target, ignore_errors=True)
    files = []
    for rel in rels:
        rel = rel.replace("\\", "/")
        source = os.path.join(root, rel)
        if not os.path.isfile(source) or rel.startswith("/") or ".." in rel.split("/"):
            continue
        destination = os.path.join(target, "tree", rel)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        shutil.copy2(source, destination)
        files.append({"path": rel, "sha256": _sha(destination)})
    with open(os.path.join(target, MANIFEST), "w", encoding="utf-8") as f:
        json.dump({"version": str(version), "files": files}, f)
    return len(files)


def clear(root="."):
    shutil.rmtree(os.path.join(root, OVERLAY), ignore_errors=True)


def apply(root="."):
    """Put the saved update over the image if it is newer. Returns 'applied', 'superseded', 'invalid' or 'none'."""
    base = os.path.join(root, OVERLAY)
    try:
        with open(os.path.join(base, MANIFEST), encoding="utf-8") as f:
            manifest = json.load(f)
        version, files = str(manifest["version"]), list(manifest["files"])
    except (OSError, ValueError, KeyError, TypeError):
        return "none"
    if version_key(version) <= version_key(image_version(root)):
        clear(root)                                   # the image is as new or newer: it wins
        return "superseded"
    tree = os.path.join(base, "tree")
    try:
        for entry in files:
            rel = entry["path"]
            if rel.startswith("/") or ".." in rel.split("/") or not (rel.split("/")[0] in CODE_DIRS or "/" not in rel):
                raise ValueError(rel)
            if _sha(os.path.join(tree, rel)) != entry["sha256"]:
                raise ValueError(rel)
    except (OSError, ValueError, KeyError, TypeError):
        clear(root)
        return "invalid"
    for entry in files:
        rel = entry["path"]
        destination = os.path.join(root, rel)
        os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
        temporary = destination + ".overlay"
        shutil.copy2(os.path.join(tree, rel), temporary)
        os.replace(temporary, destination)
    # code folders: remove files the new version no longer has, so no stale module is left behind
    keep = {e["path"] for e in files}
    for name in CODE_DIRS:
        for folder, _dirs, names in os.walk(os.path.join(root, name)):
            for filename in names:
                rel = os.path.relpath(os.path.join(folder, filename), root).replace(os.sep, "/")
                if filename.endswith(".py") and rel not in keep:
                    try:
                        os.remove(os.path.join(folder, filename))
                    except OSError:
                        pass
    return "applied"


def main():
    try:
        apply(".")
    except Exception:                                 # never stop PythonOS from starting
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
