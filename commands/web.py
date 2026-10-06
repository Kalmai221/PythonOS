"""web: read a web page as text, with its links numbered."""
import html.parser
import re

import requests
from rich.console import Console
from rich.markup import escape

from pyos import optional

console = Console()
config = {"name": "web", "description": "Read a web page as text (web [-l] <url>); -l lists only its links.", "alias": ["browse"]}
BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "header", "footer", "pre", "blockquote", "ul", "ol", "table"}
SKIP = {"script", "style", "noscript", "svg", "head", "nav", "form", "button"}
LIMIT = 4 * 1024 * 1024


class Reader(html.parser.HTMLParser):
    """Text and links of a page using only the standard library (used when beautifulsoup4 is not installed)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.title, self._skip, self._in_title, self._href = [], [], "", 0, False, None

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self._skip += 1
        if tag == "title":
            self._in_title = True
        if tag in BLOCK:
            self.parts.append("\n")
        if tag == "a":
            self._href = dict(attrs).get("href")

    def handle_endtag(self, tag):
        if tag in SKIP and self._skip:
            self._skip -= 1
        if tag == "title":
            self._in_title = False
        if tag in BLOCK:
            self.parts.append("\n")
        if tag == "a":
            self._href = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._skip or not data.strip():
            return
        self.parts.append(data)
        if self._href:
            self.links.append((data.strip(), self._href))


def extract(markup):
    """(title, text, [(label, address)]) of a page. Uses beautifulsoup4 when it is installed."""
    bs = optional.get("bs4")
    if bs is not None:
        try:
            soup = bs.BeautifulSoup(markup, "html.parser")
            title = soup.title.get_text(strip=True) if soup.title else ""
            for tag in soup(list(SKIP)):
                tag.decompose()
            links = [(a.get_text(" ", strip=True), a["href"]) for a in soup.find_all("a", href=True) if a.get_text(strip=True)]
            text = soup.get_text("\n")
            return title, tidy(text), links
        except Exception:                                  # noqa: BLE001
            pass
    reader = Reader()
    reader.feed(markup)
    return reader.title.strip(), tidy("".join(reader.parts)), reader.links


def tidy(text):
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" ?\n ?", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def absolute(base, link):
    from urllib.parse import urljoin
    return urljoin(base, link)


def execute(args=None):
    args = list(args or [])
    only_links = "-l" in args
    args = [a for a in args if a != "-l"]
    if len(args) != 1:
        console.print("[bold red]Usage:[/bold red] web [-l] <url>   for example: web example.com")
        return False
    url = args[0] if "://" in args[0] else "https://" + args[0]
    if not url.startswith(("http://", "https://")):
        console.print("[bold red]web: only http and https addresses[/bold red]")
        return False
    try:
        response = requests.get(url, timeout=15, headers={"User-Agent": "PythonOS-web"}, stream=True)
        body = response.raw.read(LIMIT + 1, decode_content=True)
    except requests.RequestException as e:
        console.print(f"[bold red]web: {escape(str(e))}[/bold red]")
        return False
    if len(body) > LIMIT:
        console.print("[bold red]web: that page is bigger than 4 MB; not shown[/bold red]")
        return False
    kind = response.headers.get("Content-Type", "")
    if "html" not in kind and "xml" not in kind and not kind.startswith("text/"):
        console.print(f"[yellow]web: that is {escape(kind or 'not a web page')}: use wget to save it.[/yellow]")
        return False
    title, text, links = extract(body.decode(response.encoding or "utf-8", "replace"))
    seen, numbered = set(), []
    for label, link in links:
        address = absolute(response.url, link)
        if address.startswith(("http://", "https://")) and address not in seen:
            seen.add(address)
            numbered.append((label[:70], address))
    if not only_links:
        if title:
            console.print(f"[bold]{escape(title)}[/bold]\n", highlight=False)
        console.print(text, markup=False, highlight=False)
    if numbered:
        console.print("\nLinks:" if not only_links else "Links:")
        for number, (label, address) in enumerate(numbered[:60], 1):
            console.print(f"{number:>3}. {label}  {address}", markup=False, highlight=False)
        if len(numbered) > 60:
            console.print(f"... {len(numbered) - 60} more", markup=False)
        console.print("[dim]Open one with: web <address>[/dim]")
    return response.ok
