import ast
import base64
import binascii
import difflib
import hashlib
import importlib
import json
import os
import re
import sys
import time
import urllib.parse

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table

import core
import pyos

console = Console()

config = {
    "name": "Developer Console",
    "description": "Developer tools: JSON, regex, diff, hashes, encoders, HTTP tester, package helper, log tail and system tests"
}

MENU = """[bold cyan]Developer tools[/bold cyan]

 [bold]Data[/bold]       json  regex  diff  hash  encode
 [bold]Network[/bold]    http
 [bold]Packages[/bold]   scaffold  check
 [bold]System[/bold]     tail  info  bench  bsod  shutdown  restart
 [bold]Other[/bold]      help  exit
"""


def is_admin():
    return pyos.userinfo()[1] == "admin"


def read_text(path_text):
    """Read a file from the PythonOS filesystem (permission checks apply)."""
    path = pyos.fs.resolve(path_text)
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def ask_text(label, allow_file=True):
    """Text typed in, or from a file when the answer starts with @ (for example @~/data.json)."""
    answer = Prompt.ask(label + (" [dim](or @file)[/dim]" if allow_file else "")).strip()
    if allow_file and answer.startswith("@"):
        return read_text(answer[1:])
    return answer


# ------------------------------------------------------------------ data
def tool_json():
    try:
        data = json.loads(ask_text("JSON"))
    except (ValueError, OSError, PermissionError) as e:
        console.print(f"[red]Invalid: {escape(str(e))}[/red]")
        return
    console.print(Syntax(json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False), "json", word_wrap=True))
    console.print(f"[green]Valid JSON[/green] [dim]({type(data).__name__}, {len(json.dumps(data))} characters compact)[/dim]")


def tool_regex():
    pattern = Prompt.ask("Pattern")
    flags = re.IGNORECASE if Confirm.ask("Ignore case?", default=False) else 0
    try:
        rx = re.compile(pattern, flags)
    except re.error as e:
        console.print(f"[red]Not a valid pattern: {escape(str(e))}[/red]")
        return
    console.print("[dim]Type test lines; blank to stop.[/dim]")
    while True:
        line = Prompt.ask("Text", default="")
        if not line:
            return
        matches = list(rx.finditer(line))
        if not matches:
            console.print("[yellow]no match[/yellow]")
            continue
        for m in matches[:20]:
            groups = f"  groups: {m.groups()}" if m.groups() else ""
            named = f"  named: {m.groupdict()}" if m.groupdict() else ""
            console.print(f"[green]match[/green] {m.start()}-{m.end()}: [bold]{escape(m.group(0))}[/bold]{escape(groups)}{escape(named)}")


def tool_diff():
    try:
        a_name, b_name = Prompt.ask("First file").strip(), Prompt.ask("Second file").strip()
        a, b = read_text(a_name).splitlines(), read_text(b_name).splitlines()
    except (OSError, PermissionError) as e:
        console.print(f"[red]{escape(pyos.fs.errtext(e))}[/red]")
        return
    lines = list(difflib.unified_diff(a, b, a_name, b_name, lineterm=""))
    if not lines:
        console.print("[green]The files are identical.[/green]")
        return
    for line in lines[:400]:
        style = "green" if line.startswith("+") and not line.startswith("+++") else "red" if line.startswith("-") and not line.startswith("---") else "cyan" if line.startswith("@@") else "dim"
        console.print(f"[{style}]{escape(line)}[/{style}]")
    if len(lines) > 400:
        console.print(f"[dim]... {len(lines) - 400} more lines[/dim]")


def tool_hash():
    text = ask_text("Text")
    data = text.encode("utf-8")
    table = Table(show_header=False, box=None)
    for name in ("md5", "sha1", "sha256", "sha512"):
        table.add_row(name, hashlib.new(name, data).hexdigest())
    table.add_row("length", f"{len(data)} bytes")
    console.print(table)


def tool_encode():
    mode = Prompt.ask("Mode", choices=["base64", "base64-decode", "url", "url-decode", "hex", "hex-decode"], default="base64")
    text = ask_text("Text")
    try:
        if mode == "base64":
            out = base64.b64encode(text.encode()).decode()
        elif mode == "base64-decode":
            out = base64.b64decode(text, validate=True).decode("utf-8", errors="replace")
        elif mode == "url":
            out = urllib.parse.quote(text, safe="")
        elif mode == "url-decode":
            out = urllib.parse.unquote(text)
        elif mode == "hex":
            out = text.encode().hex()
        else:
            out = bytes.fromhex(text).decode("utf-8", errors="replace")
    except (ValueError, binascii.Error) as e:
        console.print(f"[red]Could not convert: {escape(str(e))}[/red]")
        return
    console.print(Panel(escape(out), title=mode, border_style="blue"))


# --------------------------------------------------------------- network
def tool_http():
    import requests
    method = Prompt.ask("Method", choices=["GET", "HEAD", "POST", "PUT", "DELETE"], default="GET")
    url = Prompt.ask("URL").strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    headers = {}
    console.print("[dim]Headers as Name: value, one per line; blank to finish.[/dim]")
    while True:
        line = Prompt.ask("Header", default="").strip()
        if not line:
            break
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()
    body = Prompt.ask("Body (blank for none)", default="") if method in ("POST", "PUT") else None
    start = time.perf_counter()
    try:
        r = requests.request(method, url, headers=headers, data=body or None, timeout=15, allow_redirects=True)
    except requests.RequestException as e:
        console.print(f"[red]Request failed: {escape(str(e)[:150])}[/red]")
        return
    ms = (time.perf_counter() - start) * 1000
    colour = "green" if r.ok else "red"
    console.print(f"[{colour}]{r.status_code} {escape(r.reason or '')}[/{colour}]  {ms:.0f} ms  {len(r.content)} bytes"
                  + (f"  [dim]redirected: {escape(r.url)}[/dim]" if r.history else ""))
    for k, v in list(r.headers.items())[:12]:
        console.print(f"  [dim]{escape(k)}:[/dim] {escape(v[:100])}")
    if method != "HEAD" and r.content:
        text = r.text[:3000]
        kind = "json" if "json" in r.headers.get("content-type", "") else "text"
        if kind == "json":
            try:
                text = json.dumps(r.json(), indent=2)[:3000]
            except ValueError:
                pass
        console.print(Syntax(text, kind, word_wrap=True))


# -------------------------------------------------------------- packages
def tool_scaffold():
    name = re.sub(r"[^a-z0-9_-]", "", Prompt.ask("Package name (letters and digits)").strip().lower())
    if not name:
        return
    category = Prompt.ask("Category", default="utilities").strip().lower() or "utilities"
    folder = pyos.fs.resolve(f"~/{name}", write=True)
    if os.path.exists(folder):
        console.print("[red]That folder already exists.[/red]")
        return
    os.makedirs(folder)
    meta = {"name": name.title(), "description": "Describe your package here.", "version": "0.1.0",
            "scripts": {"run": "run.py"}, "command": name, "alias": [], "tags": [category],
            "lockdown_safe": False, "changelog": "First version."}
    with open(os.path.join(folder, "data.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        f.write("\n")
    with open(os.path.join(folder, "run.py"), "w", encoding="utf-8") as f:
        f.write('"""' + name.title() + '"""\nfrom rich.console import Console\n\nconsole = Console()\n\n\n'
                "def execute(args=None):\n    console.print(\"[bold green]Hello from " + name + "![/bold green]\")\n\n\n"
                "if __name__ == \"__main__\":\n    execute()\n")
    console.print(f"[green]Created ~/{name}[/green] with data.json and run.py. Edit them, then run the [bold]check[/bold] tool.")


def tool_check():
    folder_text = Prompt.ask("Package folder", default="~").strip()
    try:
        folder = pyos.fs.resolve(folder_text)
    except PermissionError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        return
    problems, notes = [], []
    meta_path = os.path.join(folder, "data.json")
    meta = {}
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError) as e:
        problems.append(f"data.json: {e}")
    for key in ("name", "description", "version", "command", "scripts"):
        if meta and key not in meta:
            problems.append(f"data.json has no '{key}'")
    if meta and not re.fullmatch(r"\d+(\.\d+){0,3}", str(meta.get("version", ""))):
        problems.append("version should look like 1.0.0")
    for key, script in (meta.get("scripts") or {}).items():
        path = os.path.join(folder, script)
        if not os.path.isfile(path):
            problems.append(f"script '{script}' ({key}) is missing")
            continue
        try:
            ast.parse(open(path, encoding="utf-8").read(), path)
        except SyntaxError as e:
            problems.append(f"{script}: syntax error line {e.lineno}: {e.msg}")
    if meta and not meta.get("changelog"):
        notes.append("no changelog (shown to users when they update)")
    if meta and meta.get("lockdown_safe"):
        notes.append("lockdown_safe is true: the package must not run commands or code (the catalog audit enforces this)")
    for p in problems:
        console.print(f"[red]x[/red] {escape(p)}")
    for n in notes:
        console.print(f"[yellow]![/yellow] {escape(n)}")
    if not problems:
        console.print("[bold green]Package looks good.[/bold green]")


# ---------------------------------------------------------------- system
def tool_tail():
    path = os.path.join(pyos.fs.BASE_DIR, "var", "log", "system.log")
    term = Prompt.ask("Only lines containing (blank for all)", default="").lower()
    console.print("[dim]Following the system log. Press Ctrl+C to stop.[/dim]")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f.readlines()[-15:]:
                if term in line.lower():
                    console.print(escape(line.rstrip()))
            while True:
                line = f.readline()
                if line:
                    if term in line.lower():
                        console.print(escape(line.rstrip()))
                else:
                    time.sleep(0.5)
    except OSError:
        console.print("[yellow]There is no system log yet.[/yellow]")
    except KeyboardInterrupt:
        console.print()


def tool_info():
    import platform
    from pyos import settings
    table = Table(show_header=False, box=None)
    for k, v in (("PythonOS", _version()), ("Python", sys.version.split()[0]), ("Platform", platform.platform()),
                 ("Working folder", os.getcwd()), ("Bundled", os.environ.get("PYOS_BUNDLED", "0")),
                 ("Live ISO", os.environ.get("PYOS_LIVE", "0")), ("Lockdown", os.environ.get("PYOS_LOCKDOWN", "0")),
                 ("Persistent", os.environ.get("PYOS_PERSISTENT", "0")), ("User", " / ".join(str(x) for x in pyos.userinfo()))):
        table.add_row(k, escape(str(v)))
    console.print(table)
    console.print("[bold]Settings[/bold]  " + ", ".join(f"{k}={v}" for k, v in settings.load().items()))


def _version():
    try:
        with open("config.json", encoding="utf-8") as f:
            return json.load(f).get("version", "?")
    except (OSError, ValueError):
        return "?"


def tool_bench():
    """Time a few operations so a slow device shows up."""
    import tempfile
    results = []

    def timed(label, fn, n=1):
        start = time.perf_counter()
        for _ in range(n):
            fn()
        results.append((label, (time.perf_counter() - start) * 1000 / n))

    timed("import rich.table", lambda: importlib.import_module("rich.table"))
    timed("1,000,000 loop steps", lambda: sum(range(1_000_000)))
    timed("sha256 of 1 MB", lambda: hashlib.sha256(b"x" * 1_000_000).hexdigest())
    with tempfile.NamedTemporaryFile(delete=True) as tmp:
        timed("write+read 1 MB file", lambda: (tmp.seek(0), tmp.write(b"x" * 1_000_000), tmp.flush(), tmp.seek(0), tmp.read()))
    table = Table(header_style="bold blue")
    table.add_column("Test")
    table.add_column("ms", justify="right")
    for label, ms in results:
        table.add_row(label, f"{ms:.1f}")
    console.print(table)


def tool_bsod():
    core.simulate_bsod("Developer triggered BSOD\n\nThis is normal, no problems are current in the system")


def tool_shutdown():
    pyos.shutdown()


def tool_restart():
    pyos.system("restart")


TOOLS = {"json": tool_json, "regex": tool_regex, "diff": tool_diff, "hash": tool_hash, "encode": tool_encode,
         "http": tool_http, "scaffold": tool_scaffold, "check": tool_check, "tail": tool_tail, "info": tool_info,
         "bench": tool_bench, "bsod": tool_bsod, "shutdown": tool_shutdown, "restart": tool_restart}


def dev_commands():
    if not is_admin():
        console.print("[bold red]The developer tools are for administrators.[/bold red]")
        return
    console.print(MENU)
    while True:
        try:
            cmd = Prompt.ask("[bold green]tool[/bold green]").strip().lower()
        except (KeyboardInterrupt, EOFError):
            console.print()
            return
        if cmd in ("exit", "quit", "q"):
            console.print("[bold blue]Leaving the developer tools.[/bold blue]")
            return
        if cmd in ("help", "?", "menu"):
            console.print(MENU)
        elif cmd in TOOLS:
            try:
                TOOLS[cmd]()
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped.[/yellow]")
            except pyos.ShutdownRequested:
                raise
            except Exception as e:
                console.print(f"[red]{type(e).__name__}: {escape(str(e))}[/red]")
        else:
            console.print("[bold red]Unknown tool.[/bold red] Type [bold]help[/bold] for the list.")


def execute():
    console.print(f"[bold green]{config['name']}[/bold green]")
    dev_commands()
