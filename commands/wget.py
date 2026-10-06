"""wget: download a file into the current folder."""
import os
from urllib.parse import urlparse

import requests
from rich.console import Console

import pyos.fs as fs

console = Console()
config = {"name": "wget", "description": "Download a file (wget <url> [file])."}
LIMIT = 500 * 1024 * 1024


def file_name(url):
    return os.path.basename(urlparse(url).path.rstrip("/")) or "index.html"


def execute(args=None):
    args = list(args or [])
    if not args or len(args) > 2:
        console.print("[bold red]Usage:[/bold red] wget <url> [file]")
        return False
    url = args[0] if "://" in args[0] else "https://" + args[0]
    if not url.startswith(("http://", "https://")):
        console.print("[bold red]wget: only http and https addresses[/bold red]")
        return False
    name = args[1] if len(args) > 1 else file_name(url)
    try:
        path = fs.resolve(name, write=True)
        with requests.get(url, timeout=20, stream=True) as response:
            response.raise_for_status()
            total, done = int(response.headers.get("Content-Length") or 0), 0
            with open(path, "wb") as f:
                for chunk in response.iter_content(65536):
                    done += len(chunk)
                    if done > LIMIT:
                        raise OSError("bigger than 500 MB")
                    f.write(chunk)
    except requests.RequestException as e:
        console.print(f"[bold red]wget: {e}[/bold red]")
        return False
    except Exception as e:                                             # noqa: BLE001
        console.print(f"[bold red]wget: {name}: {fs.errtext(e)}[/bold red]")
        return False
    console.print(f"Saved {done} bytes to {name}" + (f" (of {total})" if total and total != done else "") + ".")
    return True
