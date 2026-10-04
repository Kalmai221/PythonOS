#!/usr/bin/env python3
"""Decide which exports a release needs to build, and which can reuse the previous release's files.

    python OS_Export/plan.py --out plan.json            # CI: what to build for this tag
    python OS_Export/plan.py --fetch-reused plan.json DIR   # CI: copy the reused files into the new release

An export is reused when (a) this is a release build, (b) the previous release recorded a fingerprint for it,
(c) the fingerprint of its inputs is unchanged (see inputs.py) and (d) the old download links still work.
Anything else is built. The Android/Windows/Linux packages do not contain the core, so a core-only change
reuses all three; the ISO embeds the core, so it is rebuilt whenever the core changes.
"""
import argparse
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import inputs  # noqa: E402
import stage  # noqa: E402

RELEASES_URL = "https://github.com/Kalmai221/PythonOS/releases"
LATEST_MANIFEST = f"{RELEASES_URL}/latest/download/core-manifest.json"


def reachable(url, timeout=20):
    """True if a download link still works (follows GitHub's redirect to the file)."""
    try:
        request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "PythonOS-plan"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return 200 <= response.status < 300
    except Exception:
        return False


def load_previous(source):
    """The previous release's core-manifest.json (a file path or URL), or None if there is none."""
    try:
        if os.path.exists(source):
            with open(source, encoding="utf-8") as f:
                return json.load(f)
        request = urllib.request.Request(source, headers={"User-Agent": "PythonOS-plan"})
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def make_plan(version, is_release, hashes, previous, head=reachable):
    """-> {"version", "release", "exports": {platform: {build, reason, inputs_sha256, entry}}}"""
    if previous and str(previous.get("version")) == version:
        previous = None          # re-running a tag whose release already exists: compare with nothing
    plan = {"version": version, "release": is_release, "exports": {}}
    for platform, digest in hashes.items():
        item = {"build": True, "reason": "", "inputs_sha256": digest, "entry": None}
        old = ((previous or {}).get("exports") or {}).get(platform)
        if not is_release:
            item["reason"] = "not a release build"
        elif not previous:
            item["reason"] = "no previous release to reuse"
        elif not old or not old.get("inputs_sha256"):
            item["reason"] = "previous release has no fingerprint for it"
        elif old["inputs_sha256"] != digest:
            item["reason"] = "its inputs changed"
        elif not all(head(url) for url in (old.get("urls") or [old.get("url")])):
            item["reason"] = "the old download is no longer available"
        else:
            item.update(build=False, reason=f"unchanged since {old.get('version', '?')}", entry=old)
        plan["exports"][platform] = item
    return plan


def fetch_reused(plan, destination):
    """Download the files of every reused export, so the new release page still offers all four."""
    os.makedirs(destination, exist_ok=True)
    for platform, item in plan["exports"].items():
        if item["build"]:
            continue
        for url in item["entry"].get("urls") or [item["entry"]["url"]]:
            target = os.path.join(destination, url.rsplit("/", 1)[-1])
            print(f"Reusing {platform}: {url}")
            request = urllib.request.Request(url, headers={"User-Agent": "PythonOS-plan"})
            with urllib.request.urlopen(request, timeout=120) as response, open(target, "wb") as f:
                while True:
                    chunk = response.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="plan.json")
    parser.add_argument("--previous", default=LATEST_MANIFEST, help="previous core-manifest.json (path or URL)")
    parser.add_argument("--fetch-reused", nargs=2, metavar=("PLAN", "DIR"))
    args = parser.parse_args()

    if args.fetch_reused:
        with open(args.fetch_reused[0], encoding="utf-8") as f:
            fetch_reused(json.load(f), args.fetch_reused[1])
        return

    raw = os.environ.get("VERSION", "").strip()
    is_release = raw.startswith("v")
    version = stage.version()
    plan = make_plan(version, is_release, inputs.all_hashes(), load_previous(args.previous) if is_release else None)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(plan, f, indent=2)
        f.write("\n")

    print(f"Release plan for {version}:")
    for platform, item in plan["exports"].items():
        print(f"  {platform:8} {'BUILD' if item['build'] else 'reuse'}  ({item['reason']})")
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            for platform, item in plan["exports"].items():
                f.write(f"{platform}={'true' if item['build'] else 'false'}\n")


if __name__ == "__main__":
    main()
