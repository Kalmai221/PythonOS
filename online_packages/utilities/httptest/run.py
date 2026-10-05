#!/usr/bin/env python3
"""HTTP request tester: send a GET, POST, PUT, PATCH, DELETE, HEAD or OPTIONS request and look at the answer - status, timing, headers,
redirects and a formatted body. Save requests you use often. Usage: httptest <url>  |  httptest <method> <url> [--header 'Name: value']
[--data text] [--json text]  |  httptest saved  |  httptest (menu)."""
import json
import sys
import time

import requests
from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt
from rich.syntax import Syntax
from rich.table import Table

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
MAX_BODY = 4000
TIMEOUT = 20


def normalise_url(url):
    url = url.strip()
    return url if url.startswith(("http://", "https://")) else "https://" + url


def send(method, url, headers=None, data=None, json_body=None):
    """Make the request. Returns (response, milliseconds) or raises requests.RequestException."""
    start = time.perf_counter()
    kwargs = {"headers": headers or {}, "timeout": TIMEOUT, "allow_redirects": True}
    if json_body is not None:
        kwargs["json"] = json_body
    elif data is not None:
        kwargs["data"] = data
    response = requests.request(method.upper(), normalise_url(url), **kwargs)
    return response, (time.perf_counter() - start) * 1000


def show(response, ms):
    colour = "green" if response.status_code < 300 else "yellow" if response.status_code < 400 else "red"
    console.print(f"[bold {colour}]{response.status_code} {escape(response.reason or '')}[/bold {colour}]  {ms:.0f} ms  "
                  f"{len(response.content)} bytes  {escape(response.headers.get('content-type', ''))}")
    if response.history:
        chain = " -> ".join([str(r.status_code) for r in response.history] + [str(response.status_code)])
        console.print(f"[dim]Redirects: {chain}  final: {escape(response.url)}[/dim]")
    table = Table(show_header=False, box=None)
    for key, value in list(response.headers.items())[:14]:
        table.add_row(f"[dim]{escape(key)}[/dim]", escape(value[:90]))
    console.print(table)
    if not response.content:
        return
    body = response.text
    kind = "text"
    if "json" in response.headers.get("content-type", ""):
        try:
            body, kind = json.dumps(response.json(), indent=2, ensure_ascii=False), "json"
        except ValueError:
            pass
    elif "html" in response.headers.get("content-type", ""):
        kind = "html"
    console.print(Syntax(body[:MAX_BODY], kind, word_wrap=True))
    if len(body) > MAX_BODY:
        console.print(f"[dim]... {len(body) - MAX_BODY} more characters[/dim]")


def parse_args(args):
    """['POST', url, '--header', 'A: b', '--json', '{...}'] -> (method, url, headers, data, json_body)."""
    method = "GET"
    if args and args[0].upper() in METHODS:
        method, args = args[0].upper(), args[1:]
    if not args:
        raise ValueError("give a URL")
    url, headers, data, json_body = args[0], {}, None, None
    i = 1
    while i < len(args):
        if args[i] in ("--header", "-H") and i + 1 < len(args):
            name, _, value = args[i + 1].partition(":")
            headers[name.strip()] = value.strip()
            i += 2
        elif args[i] == "--data" and i + 1 < len(args):
            data = args[i + 1]
            i += 2
        elif args[i] == "--json" and i + 1 < len(args):
            try:
                json_body = json.loads(args[i + 1])
            except ValueError as e:
                raise ValueError(f"--json is not valid JSON: {e}") from None
            i += 2
        else:
            raise ValueError(f"I did not understand '{args[i]}'")
    return method, url, headers, data, json_body


def run(args):
    method, url, headers, data, json_body = parse_args(args)
    try:
        response, ms = send(method, url, headers, data, json_body)
    except requests.RequestException as e:
        console.print(f"[red]Request failed: {escape(str(e)[:160])}[/red]")
        return
    show(response, ms)


def saved():
    return appdata.load("httptest", {}) if appdata else {}


def menu():
    book = saved()
    while True:
        choice = Prompt.ask("(n)ew request, (s)aved requests, (q)uit", choices=["n", "s", "q"], default="n")
        if choice == "q":
            return
        if choice == "s":
            if not book:
                console.print("[dim]Nothing saved yet.[/dim]")
                continue
            names = list(book)
            for i, name in enumerate(names, 1):
                console.print(f"  [cyan]{i}[/cyan] {escape(name)}  [dim]{escape(' '.join(book[name]))}[/dim]")
            pick = Prompt.ask("Number to send (blank to go back)", default="")
            if pick.isdigit() and 1 <= int(pick) <= len(names):
                run(book[names[int(pick) - 1]])
            continue
        method = Prompt.ask("Method", choices=METHODS, default="GET")
        url = Prompt.ask("URL")
        args = [method, url]
        while True:
            header = Prompt.ask("Header (Name: value, blank to finish)", default="").strip()
            if not header:
                break
            args += ["--header", header]
        if method in ("POST", "PUT", "PATCH"):
            body = Prompt.ask("Body (JSON or text, blank for none)", default="").strip()
            if body:
                try:
                    json.loads(body)
                    args += ["--json", body]
                except ValueError:
                    args += ["--data", body]
        run(args)
        name = Prompt.ask("Save this request as (blank to skip)", default="").strip()
        if name and appdata:
            book[name] = args
            appdata.save("httptest", book)


def main(args):
    if args and args[0] == "saved":
        for name, req in saved().items():
            console.print(f"[cyan]{escape(name)}[/cyan]  {escape(' '.join(req))}")
    elif args:
        run(args)
    else:
        menu()


def execute(args=None):
    try:
        main(list(args or []))
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]  Usage: httptest [method] <url> [--header 'A: b'] [--data text] [--json text]")
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
