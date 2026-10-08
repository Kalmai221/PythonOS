#!/usr/bin/env python3
"""PyPI info: what a Python package is and how it is doing (pypi.org, no account or key).

    pypi requests                 the latest version, licence, requirements and recent releases
    pypi requests 2.31.0          one particular version
"""
import re
import sys

import requests
from rich.console import Console
from rich.markup import escape

console = Console()
HEADERS = {"User-Agent": "PythonOS-pypi/1.0 (https://github.com/Kalmai221/PythonOS)"}


def url_for(name, version=None):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
        raise ValueError("A package name has letters, digits, dots, dashes and underscores.")
    if version is not None and not re.fullmatch(r"[A-Za-z0-9.!+_-]+", version):
        raise ValueError("That does not look like a version number.")
    return f"https://pypi.org/pypi/{name}/" + (f"{version}/" if version else "") + "json"


def parse(data):
    """A dict with the facts shown, from PyPI's JSON."""
    info = data.get("info") or {}
    releases = data.get("releases") or {}
    dated = []
    for version, files in releases.items():
        stamps = [f.get("upload_time_iso_8601") or f.get("upload_time") or "" for f in files if not f.get("yanked")]
        if stamps:
            dated.append((min(stamps), version))
    dated.sort()
    requires = info.get("requires_dist") or []
    return {
        "name": info.get("name") or "?", "version": info.get("version") or "?", "summary": info.get("summary") or "",
        "licence": (info.get("license_expression") or info.get("license") or "").strip().splitlines()[0][:80] if (info.get("license_expression") or info.get("license")) else "not stated",
        "python": info.get("requires_python") or "any", "author": info.get("author") or info.get("maintainer") or "",
        "home": next(iter((info.get("project_urls") or {}).values()), None) or info.get("home_page") or "",
        "requires": [r.split(";")[0].strip() for r in requires if "extra ==" not in r],
        "recent": [(v, stamp[:10]) for stamp, v in dated[-5:]][::-1], "releases": len(releases), "yanked": bool(info.get("yanked")),
    }


def main(argv):
    if not argv or len(argv) > 2:
        console.print(__doc__)
        return 1
    try:
        url = url_for(argv[0], argv[1] if len(argv) > 1 else None)
        response = requests.get(url, timeout=10, headers=HEADERS)
        if response.status_code == 404:
            console.print(f"[red]No package '{escape(' '.join(argv))}' on PyPI.[/red]")
            return 1
        response.raise_for_status()
        facts = parse(response.json())
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    except requests.RequestException as e:
        console.print(f"[red]Could not reach PyPI ({escape(type(e).__name__)}). Check the internet connection.[/red]")
        return 1
    console.print(f"[bold]{escape(facts['name'])} {escape(facts['version'])}[/bold]" + ("  [red](yanked)[/red]" if facts["yanked"] else ""))
    if facts["summary"]:
        console.print(escape(facts["summary"]))
    console.print(f"\nLicence {escape(facts['licence'])}   Python {escape(facts['python'])}   Releases {facts['releases']}")
    if facts["author"]:
        console.print(f"By {escape(facts['author'])}")
    if facts["home"]:
        console.print(f"[dim]{escape(facts['home'])}[/dim]")
    if facts["requires"]:
        console.print("\nRequires: " + escape(", ".join(facts["requires"][:12])) + (f" and {len(facts['requires']) - 12} more" if len(facts["requires"]) > 12 else ""))
    else:
        console.print("\nNo other packages required.")
    if facts["recent"]:
        console.print("\nRecent releases: " + escape(",  ".join(f"{v} ({d})" for v, d in facts["recent"])))
    console.print(f"\nInstall:  pip install {escape(facts['name'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
