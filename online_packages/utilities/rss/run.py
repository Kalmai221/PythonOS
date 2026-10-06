#!/usr/bin/env python3
"""RSS reader: follow feeds, read headlines and article summaries. Feeds are saved per user; the last copy of each
feed is kept so you can still read it offline."""
import re
import time
import xml.etree.ElementTree as ET
from html import unescape

import requests
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
DEFAULT_FEEDS = {"BBC News": "https://feeds.bbci.co.uk/news/rss.xml",
                 "Hacker News": "https://hnrss.org/frontpage",
                 "Python Insider": "https://blog.python.org/feeds/posts/default?alt=rss",
                 "NASA": "https://www.nasa.gov/rss/dyn/breaking_news.rss"}
MAX_BYTES = 2_000_000


def load(name, default):
    return (appdata.load(name, default) if appdata else default)


def save(name, data):
    if appdata:
        appdata.save(name, data)


def strip_html(text):
    text = re.sub(r"<(script|style).*?</\1>", "", text or "", flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\n{3,}", "\n\n", unescape(text)).strip()


def tag(el, name):
    """Text of the first child whose tag (ignoring XML namespaces) is `name`."""
    for child in el:
        if child.tag.split("}")[-1] == name:
            return (child.text or "").strip(), child
    return "", None


def parse_with_feedparser(xml_bytes):
    """The feed through the feedparser library (when installed), or None: it copes with feeds that are not quite valid XML."""
    try:
        import feedparser
    except ImportError:
        return None
    try:
        parsed = feedparser.parse(xml_bytes)
        if not parsed.entries:
            return None
        items = [{"title": strip_html(e.get("title", "")), "link": e.get("link", ""), "summary": strip_html(e.get("summary", "")),
                  "date": (e.get("published") or e.get("updated") or "")[:25]} for e in parsed.entries]
        return strip_html(parsed.feed.get("title", "")), items
    except Exception:                                      # noqa: BLE001 - fall back to the built-in reader
        return None


def parse_feed(xml_bytes):
    """Return (title, [{title, link, summary, date}]) for RSS 2.0 or Atom."""
    if b"<!DOCTYPE" in xml_bytes[:2000] and b"<!ENTITY" in xml_bytes[:4000]:
        raise ValueError("feed uses XML entities, which are not allowed")
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        found = parse_with_feedparser(xml_bytes)             # not valid XML: the library may still make sense of it
        if found is None:
            raise
        return found
    channel = root.find("channel") if root.tag.split("}")[-1] == "rss" else root
    title, _ = tag(channel, "title")
    items = []
    for el in channel.iter():
        kind = el.tag.split("}")[-1]
        if kind not in ("item", "entry"):
            continue
        t, _ = tag(el, "title")
        link, link_el = tag(el, "link")
        if not link and link_el is not None:
            link = link_el.get("href", "")
        else:
            _, atom = tag(el, "link")
            if atom is not None and atom.get("href") and not link:
                link = atom.get("href")
        summary = tag(el, "description")[0] or tag(el, "summary")[0] or tag(el, "content")[0]
        date = tag(el, "pubDate")[0] or tag(el, "published")[0] or tag(el, "updated")[0]
        items.append({"title": strip_html(t), "link": link, "summary": strip_html(summary), "date": date[:25]})
    return title, items


def fetch(url, cache):
    """(items, from_cache). Downloads the feed, falling back to the saved copy when offline."""
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "PythonOS-RSS/1.0"}, stream=True)
        response.raise_for_status()
        data = response.raw.read(MAX_BYTES + 1, decode_content=True)
        if len(data) > MAX_BYTES:
            raise ValueError("feed is too large")
        _, items = parse_feed(data)
        cache[url] = {"fetched": time.time(), "items": items[:40]}
        save("rss_cache", cache)
        return items, False
    except Exception as e:
        if url in cache:
            console.print(f"[yellow]Could not refresh ({escape(str(e)[:60])}); showing the saved copy.[/yellow]")
            return cache[url]["items"], True
        console.print(f"[red]Could not read that feed: {escape(str(e)[:80])}[/red]")
        return None, False


def read_feed(name, url, cache):
    items, _ = fetch(url, cache)
    if not items:
        return
    page = 0
    while True:
        chunk = items[page * 10:page * 10 + 10]
        table = Table(title=name, header_style="bold blue", expand=True)
        table.add_column("#", justify="right")
        table.add_column("Headline")
        table.add_column("When", style="dim", no_wrap=True)
        for i, item in enumerate(chunk, page * 10 + 1):
            table.add_row(str(i), escape(item["title"][:90]), escape(item["date"][5:16]))
        console.print(table)
        choice = Prompt.ask("Number to read, (n)ext page, (p)revious, (b)ack", default="b").strip().lower()
        if choice == "b":
            return
        if choice == "n" and (page + 1) * 10 < len(items):
            page += 1
        elif choice == "p" and page:
            page -= 1
        elif choice.isdigit() and 1 <= int(choice) <= len(items):
            item = items[int(choice) - 1]
            console.print(Panel(escape(item["summary"][:1500]) or "[dim]No summary in this feed.[/dim]",
                                title=escape(item["title"]), subtitle=escape(item["link"]), border_style="blue"))


def main():
    feeds = load("rss_feeds", None) or dict(DEFAULT_FEEDS)
    cache = load("rss_cache", {})
    while True:
        names = list(feeds)
        table = Table(title="Your feeds", header_style="bold blue")
        table.add_column("#", justify="right")
        table.add_column("Feed", style="cyan")
        table.add_column("Address", style="dim")
        for i, n in enumerate(names, 1):
            table.add_row(str(i), escape(n), escape(feeds[n][:60]))
        console.print(table)
        choice = Prompt.ask("Number to open, (a)dd, (r)emove, (q)uit", default="q").strip().lower()
        if choice == "q":
            return
        if choice == "a":
            url = Prompt.ask("Feed address (https://...)").strip()
            if not url.startswith(("http://", "https://")):
                console.print("[red]A feed address starts with http:// or https://[/red]")
                continue
            items, _ = fetch(url, cache)
            if items is not None:
                name = Prompt.ask("Name", default=url.split("/")[2]).strip()
                feeds[name] = url
                save("rss_feeds", feeds)
        elif choice == "r":
            num = Prompt.ask("Number to remove")
            if num.isdigit() and 1 <= int(num) <= len(names):
                feeds.pop(names[int(num) - 1])
                save("rss_feeds", feeds)
        elif choice.isdigit() and 1 <= int(choice) <= len(names):
            read_feed(names[int(choice) - 1], feeds[names[int(choice) - 1]], cache)


def execute():
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute()
