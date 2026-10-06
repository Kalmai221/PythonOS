#!/usr/bin/env python3
"""Check the website: every local link, script, style and image the pages mention must exist, every page must have a title, and the
JavaScript must parse (when node is installed). Run it from anywhere:

    python tools/check_site.py
"""
import html.parser
import os
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
SITE = os.path.join(ROOT, "site")
# files the deploy workflow adds next to the pages (see .github/workflows/site.yml)
GENERATED = {"data/catalog.json", "data/release-catalog.json"}


class Page(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.title, self._in_title, self.ids = [], "", False, set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "title":
            self._in_title = True
        for key in ("href", "src"):
            if attrs.get(key) and tag in ("a", "link", "script", "img", "source"):
                self.links.append((tag, attrs[key]))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data


def main():
    problems = []
    pages = sorted(os.path.relpath(os.path.join(b, n), SITE).replace(os.sep, "/") for b, _d, files in os.walk(SITE) for n in files if n.endswith(".html"))
    if not pages:
        problems.append("the site folder has no pages")
    parsed = {}
    for name in pages:
        parser = Page()
        with open(os.path.join(SITE, name), encoding="utf-8") as f:
            parser.feed(f.read())
        parsed[name] = parser
        if not parser.title.strip():
            problems.append(f"{name}: no <title>")
    for name, parser in parsed.items():
        for tag, link in parser.links:
            if link.startswith(("http://", "https://", "mailto:", "data:", "javascript:")):
                continue
            target, _, fragment = link.partition("#")
            target = target.split("?")[0]
            if not target:
                if fragment and fragment not in parser.ids:
                    problems.append(f"{name}: #{fragment} is not an id on the page")
                continue
            here = os.path.dirname(name)
            relative = os.path.normpath(os.path.join(here, target)).replace(os.sep, "/") if target else "index.html"
            if relative in (".", ""):
                relative = "index.html"
            if relative.endswith("/"):
                relative += "index.html"
            if relative in GENERATED:
                continue
            if not os.path.exists(os.path.join(SITE, relative)):
                problems.append(f"{name}: <{tag}> points at {link}, which does not exist")
            elif fragment and relative in parsed and fragment not in parsed[relative].ids:
                problems.append(f"{name}: {link}: #{fragment} is not an id on {relative}")
    node = shutil.which("node")
    for name in sorted(n for n in os.listdir(SITE) if n.endswith(".js")):
        if name.endswith(".js"):
            if node:
                result = subprocess.run([node, "--check", os.path.join(SITE, name)], capture_output=True, text=True)
                if result.returncode != 0:
                    problems.append(f"{name}: does not parse: {result.stderr.strip()[:200]}")
            else:
                print(f"(node is not installed: {name} not parsed)")
    if problems:
        print("Site check FAILED:")
        for p in problems:
            print("  " + p)
        return 1
    print(f"Site check passed ({len(pages)} pages).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
