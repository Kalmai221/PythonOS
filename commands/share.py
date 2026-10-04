import os
import urllib.parse
import requests
from rich.console import Console
from rich.markup import escape
from rich.progress import BarColumn, DownloadColumn, Progress, TextColumn
import pyos
import pyos.fs as fs
from pyos import share as engine

console = Console()
config = {
    "name": "share",
    "description": "Send files between devices on your network: share send <file> | receive [folder] | get <link>",
    "alias": ["transfer"],
}

HELP = """[bold]share[/bold] - move files between your phone, PC and other PythonOS devices on the same network

  share send <file>        gives a link; open it on any device (or `share get <link>`) to download the file once
  share receive \\[folder]   gives a link with an upload page; open it on a phone or PC and pick files to send here
  share get <link> \\[folder]   download from a link (a share link or any http/https address)

Links contain a random code and stop working after one download / after 10 minutes (Ctrl+C stops sooner).
Only devices on your own network can reach them. Add --keep to `send` to allow more than one download."""


def _announce(servers_urls, what):
    console.print(f"\n[bold green]{what}[/bold green] Open this on the other device:")
    for url in servers_urls:
        console.print(f"  [bold cyan]{url}[/bold cyan]", soft_wrap=True)
    console.print("[dim]Waiting... (Ctrl+C to cancel)[/dim]")


def _print_event(kind, text):
    colour = {"sent": "green", "received": "green", "error": "red"}.get(kind, "white")
    console.print(f"[{colour}]{escape(text)}[/{colour}]")


def execute(args=None):
    args = list(args or [])
    flags = {a for a in args if a.startswith("-")}
    rest = [a for a in args if not a.startswith("-")]
    if not rest:
        console.print(HELP)
        return True
    sub, rest = rest[0].lower(), rest[1:]
    if not pyos.userinfo()[0]:
        console.print("[bold red]share: you are not logged in.[/bold red]")
        return False

    if sub == "send":
        if not rest:
            console.print("[bold red]Usage:[/bold red] share send <file>")
            return False
        try:
            path = fs.resolve(rest[0])
        except PermissionError as e:
            console.print(f"[bold red]share: {escape(str(e))}[/bold red]")
            return False
        if not os.path.isfile(path):
            console.print(f"[bold red]share: {escape(rest[0])} is not a file[/bold red]")
            return False
        server = engine.SendServer(path, keep="--keep" in flags).start()
        try:
            _announce(server.urls(), f"Ready to send {os.path.basename(path)}.")
            outcome = server.wait(600, _print_event)
        finally:
            server.stop()
        console.print("[green]Done.[/green]" if server.downloads else f"[yellow]Stopped ({outcome}) - nothing was downloaded.[/yellow]")
        return server.downloads > 0

    if sub in ("receive", "recv"):
        try:
            folder = fs.resolve(rest[0] if rest else ".", write=True)
        except PermissionError as e:
            console.print(f"[bold red]share: {escape(str(e))}[/bold red]")
            return False
        if not os.path.isdir(folder):
            console.print(f"[bold red]share: {escape(rest[0] if rest else '.')} is not a folder[/bold red]")
            return False
        server = engine.ReceiveServer(folder).start()
        try:
            _announce(server.urls(), f"Ready to receive files into {fs.display(folder, tilde=True)}.")
            console.print("[dim]From a computer you can also use: curl -T file <link>up/[/dim]")
            server.wait(600, _print_event)
        finally:
            server.stop()
        console.print(f"[green]Received {server.count} file(s).[/green]" if server.count else "[yellow]Stopped - nothing was received.[/yellow]")
        return server.count > 0

    if sub == "get":
        if not rest:
            console.print("[bold red]Usage:[/bold red] share get <link> \\[folder]")
            return False
        return _get(rest[0], rest[1] if len(rest) > 1 else ".", "-f" in flags or "--force" in flags)

    console.print(f"[bold red]share: unknown subcommand '{escape(sub)}'[/bold red]")
    console.print(HELP)
    return False


def _get(url, destination, force):
    if urllib.parse.urlsplit(url).scheme not in ("http", "https"):
        console.print("[bold red]share: the link must start with http:// or https://[/bold red]")
        return False
    try:
        folder = fs.resolve(destination, write=True)
    except PermissionError as e:
        console.print(f"[bold red]share: {escape(str(e))}[/bold red]")
        return False
    if not os.path.isdir(folder):
        console.print(f"[bold red]share: {escape(destination)} is not a folder[/bold red]")
        return False
    part = None
    try:
        with requests.get(url, stream=True, timeout=20) as response:
            response.raise_for_status()
            disposition = response.headers.get("Content-Disposition", "")
            name = disposition.split("filename=")[-1].strip('"; ') if "filename=" in disposition else \
                urllib.parse.unquote(urllib.parse.urlsplit(url).path.rsplit("/", 1)[-1])
            name = engine.safe_filename(name or "download")
            target = os.path.join(folder, name) if force else engine.unique_path(folder, name)
            total = int(response.headers.get("Content-Length") or 0) or None
            part = target + ".part"
            with Progress(TextColumn("[cyan]{task.description}"), BarColumn(), DownloadColumn(), console=console, transient=True) as bar:
                task = bar.add_task(name, total=total)
                with open(part, "wb") as f:
                    for chunk in response.iter_content(engine.CHUNK):
                        f.write(chunk)
                        bar.advance(task, len(chunk))
            os.replace(part, target)
    except (requests.RequestException, OSError) as e:
        console.print(f"[bold red]share: download failed: {escape(str(e))}[/bold red]")
        if part and os.path.exists(part):
            os.remove(part)
        return False
    console.print(f"[green]Saved {escape(os.path.basename(target))}[/green] in {escape(fs.display(folder, tilde=True))}")
    return True
