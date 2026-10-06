"""curl: fetch a web address and show it or save it."""
import requests
from rich.console import Console

import pyos.fs as fs

console = Console()
config = {"name": "curl", "description": "Fetch a web address (curl [-I] [-o file] <url>); shows the page, its headers, or saves it."}
LIMIT = 50 * 1024 * 1024


def parse(args):
    """(url, headers only, output file) or None."""
    url, head, out = None, False, None
    args = list(args or [])
    i = 0
    while i < len(args):
        if args[i] in ("-I", "--head"):
            head = True
        elif args[i] in ("-o", "--output") and i + 1 < len(args):
            i += 1
            out = args[i]
        elif args[i].startswith("-") or url is not None:
            return None
        else:
            url = args[i]
        i += 1
    if not url:
        return None
    if "://" not in url:
        url = "https://" + url
    return (url, head, out) if url.startswith(("http://", "https://")) else None


def execute(args=None):
    plan = parse(args)
    if plan is None:
        console.print("[bold red]Usage:[/bold red] curl [-I] [-o file] <url>   for example: curl -I example.com")
        return False
    url, head, out = plan
    try:
        response = requests.head(url, timeout=15, allow_redirects=True) if head else requests.get(url, timeout=15, stream=True)
    except requests.RequestException as e:
        console.print(f"[bold red]curl: {e}[/bold red]")
        return False
    if head:
        console.print(f"{response.status_code} {response.reason}", highlight=False)
        for key, value in response.headers.items():
            console.print(f"{key}: {value}", markup=False, highlight=False)
        return response.ok
    body = b""
    for chunk in response.iter_content(65536):
        body += chunk
        if len(body) > LIMIT:
            console.print("[bold red]curl: that is bigger than 50 MB; not downloaded[/bold red]")
            return False
    if out:
        try:
            with open(fs.resolve(out, write=True), "wb") as f:
                f.write(body)
        except Exception as e:                                         # noqa: BLE001
            console.print(f"[bold red]curl: {out}: {fs.errtext(e)}[/bold red]")
            return False
        console.print(f"Saved {len(body)} bytes to {out}.")
    else:
        console.print(body.decode("utf-8", "replace"), markup=False, highlight=False, end="")
    return response.ok
