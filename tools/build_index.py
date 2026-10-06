#!/usr/bin/env python3
"""Regenerate online_packages/index.json - the catalog the PyOS marketplace reads.

Run this from anywhere after adding or changing a package, then commit and push
online_packages/index.json together with the package:

    python tools/build_index.py

Required: permissions (a list; [] for an app that needs nothing special). Optional: requires (package ids or commands, with
version ranges such as "utilities/notes>=1.1"), optional (nice-to-have packages), categories, changelog (a string or {version: notes}),
featured (true).

Marketplace API versions (pyos/marketapi.py): a package may say "api": N in its data.json (default 1). The catalog is published as
index-api<N>.json for every N up to the current API (each lists the packages written for API N or older), and index.json is the API 1
catalog that the oldest systems still read.

Each package is a folder online_packages/<category>/<name>/ containing a data.json
(name, description, version, command, alias, tags, scripts) plus its files.
"""
import hashlib
import json
import os
import re
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


PERMISSIONS = {"network", "files", "notifications", "schedule", "system", "exec"}


def permissions_of(meta, pid):
    """The declared permissions, checked: every package must say what it needs, and a lockdown-safe one cannot run programs."""
    perms = meta.get("permissions")
    if perms is None:
        sys.exit(f"{pid}: data.json has no 'permissions' list (use [] for an app that needs nothing special)")
    unknown = [p for p in perms if p not in PERMISSIONS]
    if unknown:
        sys.exit(f"{pid}: unknown permission(s) {unknown} (known: {sorted(PERMISSIONS)})")
    if meta.get("lockdown_safe") and "exec" in perms:
        sys.exit(f"{pid}: a lockdown_safe package cannot ask for the 'exec' permission")
    return list(perms)


def check_settings(meta, pid):
    """Options an app offers (data.json "settings") must all be valid: a bad entry would silently not show up."""
    # load the module straight from its file: importing the pyos package would need rich and the other OS dependencies
    import importlib.util
    spec = importlib.util.spec_from_file_location("appsettings", os.path.join(os.path.dirname(ROOT), "pyos", "appsettings.py"))
    appsettings = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(appsettings)
    declared = meta.get("settings") or []
    if len(appsettings.schema(meta)) != len(declared):
        sys.exit(f"{pid}: a 'settings' entry is invalid (needs key, type bool|int|choice|text, and choices for a choice)")
    for entry in declared:
        try:
            appsettings.parse(entry, entry.get("default", ""))
        except ValueError as e:
            sys.exit(f"{pid}: the default of option '{entry['key']}' is not valid ({e})")


def load_categories():
    path = os.path.join(ROOT, "categories.json")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def load_marketapi():
    """pyos/marketapi.py loaded from its file (importing the pyos package would need rich and the other OS dependencies)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("marketapi", os.path.join(os.path.dirname(ROOT), "pyos", "marketapi.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_export():
    """pyos/export.py loaded from its file (it needs nothing else)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("pyos_export", os.path.join(os.path.dirname(ROOT), "pyos", "export.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    marketapi = load_marketapi()
    export = load_export()
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
            check_settings(meta, f"{category}/{name}")
            api = marketapi.package_api(meta)
            try:
                pip = marketapi.pip_specs(meta)
            except ValueError as e:
                sys.exit(f"{category}/{name}: {e}")
            if pip and api < 2:
                sys.exit(f"{category}/{name}: a package that needs Python libraries ('pip') must say \"api\": 2")
            if pip and meta.get("lockdown_safe"):
                sys.exit(f"{category}/{name}: a lockdown_safe package cannot ask for Python libraries (they run code that was not reviewed here)")
            try:
                exports = export.valid_exports(meta.get("exports"))
            except ValueError as e:
                sys.exit(f"{category}/{name}: {e}")
            if exports and "iso" not in exports:
                sys.exit(f"{category}/{name}: an app must run on the bootable ISO (and the VM images made from it) as well as anything else it lists")
            if str(meta.get("api", api)) != str(api) or not marketapi.OLDEST <= api <= marketapi.CURRENT:
                sys.exit(f"{category}/{name}: data.json 'api' must be a whole number from {marketapi.OLDEST} to {marketapi.CURRENT} (the marketplace API versions that exist)")
            packages.append({
                "api": api,
                "pip": pip,
                "exports": exports or list(export.TITLES),
                "id": f"{category}/{name}",
                "category": category,
                "name": meta.get("name", name),
                "description": meta.get("description", ""),
                "version": str(meta.get("version", "0.0.0")),
                "command": meta.get("command", ""),
                "alias": meta.get("alias", []),
                "tags": meta.get("tags", []),
                # Only packages that cannot give access to the machine underneath (no shells, no code
                # execution, no pip) may be marked safe; locked-down systems refuse everything else.
                "lockdown_safe": bool(meta.get("lockdown_safe", False)),
                # other packages this one needs (ids like "utilities/notes", or their command names)
                "requires": list(meta.get("requires", [])),
                # nice to have, offered but not installed automatically: strings or {"ref": ..., "why": ...}
                "optional": list(meta.get("optional", [])),
                # what the app may do (see pyos/sandbox.py); the store shows it before installing and the guard enforces it
                "permissions": permissions_of(meta, f"{category}/{name}"),
                "settings": [e["key"] for e in (meta.get("settings") or []) if isinstance(e, dict) and "key" in e],
                # display categories (online_packages/categories.json); falls back to the folder name
                "categories": list(meta.get("categories") or [category]),
                # shown in the store before installing and on update: a string, or {version: notes}
                "changelog": meta.get("changelog", ""),
                "featured": bool(meta.get("featured", False)),
                "files": package_files(folder),
            })
    known = {c["id"] for c in load_categories()}
    for p in packages:
        for c in p["categories"]:
            if known and c not in known and c != p["category"]:
                sys.exit(f"{p['id']}: category '{c}' is not in categories.json")
    ids = {p["id"] for p in packages}
    for p in packages:
        for spec in p["requires"]:
            ref = re.split(r"[<>=!,\s]", spec, maxsplit=1)[0]
            if not any(ref in (i, i.split("/")[-1]) for i in ids):
                sys.exit(f"{p['id']}: requires '{spec}' which is not in the catalog")
    # one catalog per API version: the packages written for that version or older. index.json is API 1 and stays readable by every
    # system ever released; a newer catalog layout goes in index-api<N>.json only.
    categories = load_categories()
    names = {1: "index.json"}
    for version in range(1, marketapi.CURRENT + 1):
        names[version] = names.get(version) or f"index-api{version}.json"
    written = []
    for version in range(1, marketapi.CURRENT + 1):
        listed = [p for p in packages if p["api"] <= version]
        index = {"format": 2, "api": version, "categories": categories, "packages": listed}
        files = [names[version]] + (["index-api1.json"] if version == 1 else [])
        for name in files:
            out = os.path.join(ROOT, name)
            with open(out, "w", encoding="utf-8", newline="\n") as f:
                json.dump(index, f, indent=2)
                f.write("\n")
            written.append((name, len(listed)))
    for name, count in written:
        print(f"Wrote {os.path.join(ROOT, name)} ({count} packages)")


if __name__ == "__main__":
    main()
