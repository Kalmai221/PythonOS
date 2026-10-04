"""Fingerprints of what goes into each export, so unchanged exports can be reused instead of rebuilt.

An export (APK, Windows app, Linux package, ISO) only needs rebuilding when something that ends up in it
changed. Each export lists those inputs in exports.json; this hashes them (text normalised to LF, so the
result is the same on Windows and Linux). The release manifest records the hash, and the next release compares.

    python OS_Export/inputs.py            # print every export's fingerprint
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage  # noqa: E402

REPO = stage.REPO
SKIP_DIRS = {"__pycache__", "build", ".gradle", ".idea", "node_modules", "dist"}
SKIP_NAMES = {"local.properties", ".DS_Store", "Thumbs.db"}
SKIP_SUFFIXES = (".pyc", ".pyo", ".apk", ".iso", ".exe", ".zip", ".deb")
# files that the build generates inside the inputs - they are outputs, not inputs
GENERATED = {
    "OS_Export/Android/app/src/main/python/bootstrap.py",
    "OS_Export/Android/app/src/main/python/pyos_export.py",
}


def _read(path):
    with open(path, "rb") as f:
        data = f.read()
    return data if b"\0" in data[:8192] else data.replace(b"\r\n", b"\n")


def _files(entry):
    full = os.path.join(REPO, *entry.split("/"))
    if os.path.isfile(full):
        yield entry, full
        return
    for dirpath, dirnames, filenames in os.walk(full):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            if name in SKIP_NAMES or name.endswith(SKIP_SUFFIXES):
                continue
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, REPO).replace(os.sep, "/")
            if rel not in GENERATED:
                yield rel, path


def core_digest():
    """Fingerprint of the OS payload itself (what an export that embeds the core contains)."""
    import shutil
    import tempfile
    work = tempfile.mkdtemp()
    try:
        root = stage.stage(os.path.join(work, "core"))
        h = hashlib.sha256()
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames.sort()
            for name in sorted(filenames):
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, root).replace(os.sep, "/")
                if rel == "VERSION":
                    continue            # the version string changes every release; the content is what matters
                h.update(rel.encode() + b"\0" + hashlib.sha256(_read(path)).digest())
        return h.hexdigest()
    finally:
        shutil.rmtree(work, ignore_errors=True)


def inputs_hash(platform, core=None):
    """sha256 of an export's inputs. `core` is the core digest (computed if the export embeds the core)."""
    entry = stage.exports()[platform]
    h = hashlib.sha256()
    h.update(f"{platform}\0api={entry['api']}\0".encode())
    for item in sorted(entry.get("inputs", [])):
        for rel, path in _files(item):
            h.update(rel.encode() + b"\0" + hashlib.sha256(_read(path)).digest())
    if entry.get("embeds_core"):
        h.update(b"core\0" + (core or core_digest()).encode())
    return h.hexdigest()


def all_hashes():
    core = None
    out = {}
    for platform, entry in stage.exports().items():
        if entry.get("embeds_core") and core is None:
            core = core_digest()
        out[platform] = inputs_hash(platform, core)
    return out


if __name__ == "__main__":
    for platform, digest in all_hashes().items():
        print(f"{platform:8} {digest}")
