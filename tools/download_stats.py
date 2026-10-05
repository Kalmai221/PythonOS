#!/usr/bin/env python3
"""Download counts of every release file, from GitHub's own numbers (nothing is tracked inside PythonOS).

    python tools/download_stats.py            # table, newest releases first
    python tools/download_stats.py --json     # the same as JSON
    python tools/download_stats.py --by-platform   # totals per kind of file
"""
import argparse
import json
import re
import urllib.request

REPO = "Kalmai221/PythonOS"
KINDS = [("Windows", r"(setup\.exe|windows-portable\.zip)$"), ("Android", r"\.apk$"), ("Linux", r"(\.deb|-linux\.tar\.gz)$"),
         ("ISO full", r"(?<!minimal-)x86_64\.iso$"), ("ISO minimal", r"minimal-x86_64\.iso$"), ("VM image", r"(\.ova|\.qcow2)$")]


def releases():
    request = urllib.request.Request(f"https://api.github.com/repos/{REPO}/releases?per_page=100", headers={"User-Agent": "pythonos-stats"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--by-platform", action="store_true")
    args = parser.parse_args()
    data = releases()
    rows = [{"release": r["tag_name"], "file": a["name"], "downloads": a["download_count"], "bytes": a["size"]} for r in data for a in r["assets"]]
    if args.by_platform:
        totals = {label: sum(r["downloads"] for r in rows if re.search(pattern, r["file"])) for label, pattern in KINDS}
        if args.json:
            print(json.dumps(totals, indent=2))
        else:
            for label, n in sorted(totals.items(), key=lambda kv: -kv[1]):
                print(f"{label:<12} {n:>8}")
        return
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    for r in rows:
        print(f"{r['release']:<10} {r['downloads']:>7}  {r['file']}")
    print(f"\nTotal downloads: {sum(r['downloads'] for r in rows)}")


if __name__ == "__main__":
    main()
