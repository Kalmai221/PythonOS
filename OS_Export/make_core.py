#!/usr/bin/env python3
"""Build the self-update package for a release.

    VERSION=v1.2.0 python OS_Export/make_core.py [--out dist/core]

Produces, in the output folder:

  pythonos-core-<version>.zip   the OS files (commands, core, programs, pyos, main.py, ...)
                                without config.json (that is the user's)
  core-manifest.json            version, checksums and download info

Attach both to the GitHub release. Every packaged build (Linux, Windows, Android, ISO) checks
the latest release's core-manifest.json, downloads the zip and replaces its core files with it
(see core/sysupdate.py). Always keep the manifest's file name as it is: the updater looks for
releases/latest/download/core-manifest.json.
"""
import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stage  # noqa: E402
import inputs  # noqa: E402

RELEASES_URL = "https://github.com/Kalmai221/PythonOS/releases"
EXCLUDE = {"config.json"}  # user settings are never overwritten by an update
MANIFEST_NAME = "core-manifest.json"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def requirements_hash(root):
    """Same recipe as core/sysupdate.py: LF-normalised requirements files, hashed together."""
    parts = []
    for name in ("requirements.txt", "boot-requirements.txt"):
        try:
            with open(os.path.join(root, name), "rb") as f:
                parts.append(f.read().replace(b"\r\n", b"\n"))
        except OSError:
            parts.append(b"")
    return sha256(b"\0".join(parts))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=os.path.join(stage.REPO, "dist", "core"))
    args = parser.parse_args()

    ver = stage.version()
    raw_tag = os.environ.get("VERSION", "").strip()
    tag = raw_tag if raw_tag.startswith("v") else f"v{ver}"
    out = os.path.abspath(args.out)
    os.makedirs(out, exist_ok=True)

    work = tempfile.mkdtemp()
    try:
        root = stage.stage(os.path.join(work, "core"))
        files = []
        archive = f"pythonos-core-{ver}.zip"
        zip_path = os.path.join(out, archive)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames.sort()
                for name in sorted(filenames):
                    full = os.path.join(dirpath, name)
                    rel = os.path.relpath(full, root).replace(os.sep, "/")
                    if rel in EXCLUDE:
                        continue
                    with open(full, "rb") as f:
                        data = f.read()
                    z.writestr(zipfile.ZipInfo(rel, date_time=(2020, 1, 1, 0, 0, 0)), data, zipfile.ZIP_DEFLATED)
                    files.append({"path": rel, "sha256": sha256(data), "size": len(data)})
        with open(zip_path, "rb") as f:
            zip_bytes = f.read()
        manifest = {
            "format": 1,
            "version": ver,
            "tag": tag,
            "asset": archive,
            "sha256": sha256(zip_bytes),
            "size": len(zip_bytes),
            "requirements_sha256": requirements_hash(root),
            "files": files,
        }
        # What each export (APK, Windows app, Linux package, ISO) is at in this release, so an installed
        # one can tell when a package it cannot update itself has a newer version to download.
        # Exports that did not change since an earlier release are not rebuilt: the plan (plan.py) says so, and
        # their entry is carried over, still pointing at the release that has the files.
        base = f"{RELEASES_URL}/download/{tag}/"
        plan = None
        plan_file = os.environ.get("PLAN_FILE", "")
        if plan_file and os.path.exists(plan_file):
            with open(plan_file, encoding="utf-8") as f:
                plan = json.load(f)
        hashes = None
        manifest["exports"] = {}
        for platform, entry in stage.exports().items():
            item = ((plan or {}).get("exports") or {}).get(platform)
            if item and not item["build"]:
                manifest["exports"][platform] = item["entry"]
                continue
            digest = (item or {}).get("inputs_sha256")
            if not digest:
                hashes = hashes or inputs.all_hashes()
                digest = hashes[platform]
            assets = [a.replace("{v}", ver) for a in entry["assets"]]
            manifest["exports"][platform] = {
                "title": entry["title"], "version": ver, "api": entry["api"],
                "assets": assets, "url": base + assets[0], "urls": [base + a for a in assets],
                "notes": entry.get("notes", ""), "inputs_sha256": digest,
            }
        notes = os.environ.get("RELEASE_NOTES", "").strip()
        if notes:
            manifest["notes"] = notes
        with open(os.path.join(out, MANIFEST_NAME), "w", encoding="utf-8", newline="\n") as f:
            json.dump(manifest, f, indent=2)
            f.write("\n")
        print(f"Built {zip_path} ({len(files)} files) and {MANIFEST_NAME} for {ver}")
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    main()
