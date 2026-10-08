import difflib
import hashlib
import importlib
import json
import os
import re
import sys
import time
import zlib

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.table import Table

import core
import pyos
from pyos import devtools

console = Console()

config = {
    "name": "Developer Console",
    "description": "Developer tools: JSON, regex, diff, hashes, encoders, HTTP tester, package helper and checker, tests, profiler and system checks"
}

# (tool, group, one line, usage). The menu, `help <tool>` and running a tool straight from the shell (run developer <tool> ...) are made from this.
REGISTRY = [
    ("json", "Data", "check, pretty-print and query JSON", "json [text or @file] [path like .users[0].name] [-c minify] [-s sort keys]"),
    ("regex", "Data", "try a regular expression, and its replacement", "regex [pattern] [flags: i m s x] [-r replacement] [-f @file]"),
    ("diff", "Data", "compare two files", "diff [file1] [file2]"),
    ("hash", "Data", "every hash of some text or a file; compare with one you were given", "hash [text or @file] [expected hash]"),
    ("encode", "Data", "base64, base32, hex, url, html, rot13 ... both ways, with a guess for what you paste", "encode [mode] [text or @file] [-d decode]"),
    ("time", "Data", "Unix time, ISO dates and time zones", "time [now | seconds | 2026-10-08T12:00:00]"),
    ("http", "Network", "send a web request and see the status, timing, headers and body; keep requests as presets", "http [GET|POST ...] [url] | http save|load|list|delete <name>"),
    ("scaffold", "Packages", "start a new app from a template (basic, network, files, game, corecmd)", "scaffold [name] [template] [extra permissions]"),
    ("check", "Packages", "everything the marketplace and lockdown check about an app folder", "check [folder]"),
    ("run", "Packages", "run an app under the permission guard with the permissions you choose", "run [folder] [permissions, like files,network or none] [arguments...]"),
    ("pack", "Packages", "zip an app folder, ready to share, with its checksum", "pack [folder]"),
    ("deps", "Packages", "what an app imports, what provides it, and which PythonOS commands could do some of its work", "deps [folder]"),
    ("watch", "Packages", "check an app again every time one of its files changes", "watch [folder]"),
    ("api", "Packages", "the modules of PythonOS an app may import, and what is in each", "api [module name like corecmd]"),
    ("compat", "Quality", "does everything work on this system? (add --deep to also run things and look at the system)", "compat [--deep] [--network] [--save]"),
    ("fuzz", "Quality", "try the commands apps may use with odd input to find the ones that crash", "fuzz [--quick]"),
    ("profile", "Quality", "time a command and see where it spends its time and memory", "profile [command line]"),
    ("bench", "Quality", "time a few operations so a slow device shows up", "bench"),
    ("tail", "System", "follow the system log, with a word or a level to look for", "tail [word] [-l ERROR|WARN|INFO]"),
    ("info", "System", "versions, folders, settings and optional libraries", "info"),
    ("bsod", "System", "show the crash screen", "bsod"),
    ("shutdown", "System", "shut down", "shutdown"),
    ("restart", "System", "restart", "restart"),
]
GROUPS = ("Data", "Network", "Packages", "Quality", "System")


def _menu():
    lines = ["[bold cyan]Developer tools[/bold cyan]", ""]
    for group in GROUPS:
        names = "  ".join(name for name, g, _s, _u in REGISTRY if g == group)
        lines.append(f" [bold]{group:<9}[/bold] {names}")
    lines += [" [bold]Other[/bold]     help [dim]<tool>[/dim]  exit", "", "[dim]Type a tool's name. help <tool> says what it does. Or run one straight from the shell: run developer <tool> ...[/dim]"]
    return "\n".join(lines) + "\n"


MENU = _menu()


def is_admin():
    return pyos.userinfo()[1] == "admin"


def read_text(path_text):
    """Read a file from the PythonOS filesystem (permission checks apply)."""
    path = pyos.fs.resolve(path_text)
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def read_bytes(path_text):
    with open(pyos.fs.resolve(path_text), "rb") as f:
        return f.read()


def arg(args, index, label, default=None, **kwargs):
    """The argument at `index` when the tool was started with arguments, else the answer to a question."""
    if args and index < len(args):
        return args[index]
    return Prompt.ask(label, default=default, **kwargs) if default is not None else Prompt.ask(label, **kwargs)


def ask_text(label, allow_file=True, args=None, index=0):
    """Text typed in, or from a file when the answer starts with @ (for example @~/data.json)."""
    if args and index < len(args):
        answer = args[index].strip()
    else:
        answer = Prompt.ask(label + (" [dim](or @file)[/dim]" if allow_file else "")).strip()
    if allow_file and answer.startswith("@"):
        return read_text(answer[1:])
    return answer


def fail(text):
    console.print(f"[red]{escape(text)}[/red]")


def show_error_place(line, column):
    console.print("  " + escape(line[:200]))
    console.print("  " + " " * min(column, 200) + "[bold red]^[/bold red]")


def flag(args, *names):
    """True if one of `names` is among the arguments; the arguments with it removed."""
    found = any(n in (args or []) for n in names)
    return found, [a for a in (args or []) if a not in names]


# ------------------------------------------------------------------ data
def tool_json(args=None):
    minify, args = flag(args, "-c")
    ordered, args = flag(args, "-s")
    try:
        text = ask_text("JSON", args=args)
    except (OSError, PermissionError) as e:
        fail(pyos.fs.errtext(e))
        return
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        message, line, column = devtools.json_error(text, e)
        fail("Invalid: " + message)
        show_error_place(line, column)
        return
    path = args[1] if args and len(args) > 1 else (Prompt.ask("Path to look at, like .users[0].name (blank for all)", default="") if not args else "")
    try:
        values = devtools.json_query(data, path)
    except ValueError as e:
        fail(str(e))
        return
    for value in values[:50]:
        shown = json.dumps(value, ensure_ascii=False, sort_keys=ordered, **({"separators": (",", ":")} if minify else {"indent": 2}))
        console.print(Syntax(shown, "json", word_wrap=True))
    if len(values) > 50:
        console.print(f"[dim]... {len(values) - 50} more[/dim]")
    stats = devtools.json_stats(data)
    console.print(f"[green]Valid JSON[/green] [dim]({stats['type']}, {stats['items']} values, {stats['depth']} deep, {len(json.dumps(data))} characters compact)"
                  + (f"; keys: {', '.join(stats['keys'])}" if stats["keys"] else "") + "[/dim]")


def tool_regex(args=None):
    replace = None
    args = list(args or [])
    if "-r" in args:
        i = args.index("-r")
        replace = args[i + 1] if i + 1 < len(args) else ""
        del args[i:i + 2]
    source_text = None
    if "-f" in args:
        i = args.index("-f")
        try:
            source_text = read_text(args[i + 1].lstrip("@"))
        except (IndexError, OSError, PermissionError) as e:
            fail(pyos.fs.errtext(e) if isinstance(e, OSError) else "-f needs a file")
            return
        del args[i:i + 2]
    pattern = arg(args, 0, "Pattern")
    letters = arg(args, 1, "Flags (i ignore case, m multi-line, s dot matches newline, x verbose; blank for none)", default="")
    if replace is None and not args:
        answer = Prompt.ask("Replacement (blank to only find)", default="")
        replace = answer or None
    try:
        devtools.regex_try(pattern, "", letters)
    except ValueError as e:
        fail(str(e))
        return

    def test(line):
        result = devtools.regex_try(pattern, line, letters, replace)
        if not result["matches"]:
            console.print("[yellow]no match[/yellow]")
            return
        for m in result["matches"][:20]:
            groups = f"  groups: {m['groups']}" if m["groups"] else ""
            named = f"  named: {m['named']}" if m["named"] else ""
            console.print(f"[green]match[/green] {m['start']}-{m['end']}: [bold]{escape(m['text'])}[/bold]{escape(groups)}{escape(named)}")
        if len(result["matches"]) > 20:
            console.print(f"[dim]... {len(result['matches']) - 20} more matches[/dim]")
        if "replaced" in result:
            console.print("[cyan]after replacing:[/cyan] " + escape(result["replaced"]))
    if source_text is not None:
        for number, line in enumerate(source_text.splitlines()[:200], 1):
            result = devtools.regex_try(pattern, line, letters, replace)
            if result["matches"]:
                console.print(f"[dim]{number:>4}[/dim] " + escape(line[:160]))
                test(line)
        return
    console.print("[dim]Type test lines; blank to stop.[/dim]")
    while True:
        line = Prompt.ask("Text", default="")
        if not line:
            return
        test(line)


def tool_diff(args=None):
    try:
        a_name, b_name = arg(args, 0, "First file").strip(), arg(args, 1, "Second file").strip()
        a, b = read_text(a_name).splitlines(), read_text(b_name).splitlines()
    except (OSError, PermissionError) as e:
        fail(pyos.fs.errtext(e))
        return
    lines = list(difflib.unified_diff(a, b, a_name, b_name, lineterm=""))
    if not lines:
        console.print("[green]The files are identical.[/green]")
        return
    added = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
    removed = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))
    for line in lines[:400]:
        style = "green" if line.startswith("+") and not line.startswith("+++") else "red" if line.startswith("-") and not line.startswith("---") else "cyan" if line.startswith("@@") else "dim"
        console.print(f"[{style}]{escape(line)}[/{style}]")
    if len(lines) > 400:
        console.print(f"[dim]... {len(lines) - 400} more lines[/dim]")
    console.print(f"[green]+{added}[/green] [red]-{removed}[/red]  [dim]similarity {difflib.SequenceMatcher(None, a, b).quick_ratio() * 100:.0f}%[/dim]")


def tool_hash(args=None):
    answer = (args[0] if args else Prompt.ask("Text [dim](or @file)[/dim]")).strip()
    try:
        data = read_bytes(answer[1:]) if answer.startswith("@") else answer.encode("utf-8")
    except (OSError, PermissionError) as e:
        fail(pyos.fs.errtext(e))
        return
    table = Table(show_header=False, box=None)
    digests = devtools.hash_all(data)
    for name, value in digests.items():
        table.add_row(name, value)
    table.add_row("length", f"{len(data)} bytes")
    console.print(table)
    expected = (args[1] if args and len(args) > 1 else Prompt.ask("Hash you were given, to compare (blank to skip)", default="")).strip().lower()
    if expected:
        matches = [n for n, v in digests.items() if v == expected]
        if matches:
            console.print(f"[bold green]Match:[/bold green] it is the {matches[0]} of this.")
        else:
            guess = devtools.which_hash(expected)
            console.print("[bold red]No match.[/bold red]" + (f" It looks like a {' or '.join(guess)} (that is {len(expected)} characters)." if guess else " That is not a hash I know the length of."))


def tool_encode(args=None):
    direct = bool(args)
    decoding, args = flag(args, "-d")
    mode = arg(args, 0, "Mode", choices=list(devtools.ENCODINGS), default="base64")
    if mode not in devtools.ENCODINGS:
        fail("The modes are: " + ", ".join(devtools.ENCODINGS))
        return
    try:
        text = ask_text("Text", args=args, index=1)
    except (OSError, PermissionError) as e:
        fail(pyos.fs.errtext(e))
        return
    if not direct:
        decoding = Confirm.ask("Decode it (instead of encode)?", default=False)
    guesses = devtools.guess_encoding(text) if decoding else []
    try:
        out = devtools.decode(mode, text) if decoding else devtools.encode(mode, text)
    except ValueError as e:
        fail(str(e))
        if guesses:
            console.print("[dim]It looks more like: " + ", ".join(guesses) + "[/dim]")
        return
    console.print(Panel(escape(out), title=f"{mode} {'decoded' if decoding else 'encoded'}", border_style="blue"))
    if decoding and guesses and mode not in guesses:
        console.print("[dim]This text looks like " + " or ".join(guesses) + ", not " + mode + ".[/dim]")


def tool_time(args=None):
    import datetime
    word = (args[0] if args else Prompt.ask("Seconds since 1970, an ISO date, or 'now'", default="now")).strip()
    try:
        if word == "now":
            moment = datetime.datetime.now(datetime.timezone.utc)
        elif re.fullmatch(r"-?\d+(\.\d+)?", word):
            value = float(word)
            moment = datetime.datetime.fromtimestamp(value / 1000 if abs(value) > 1e11 else value, datetime.timezone.utc)
        else:
            moment = datetime.datetime.fromisoformat(word.replace("Z", "+00:00"))
            if moment.tzinfo is None:
                moment = moment.astimezone()
    except (ValueError, OverflowError, OSError) as e:
        fail(f"I cannot read that as a time ({e})")
        return
    local = moment.astimezone()
    table = Table(show_header=False, box=None)
    table.add_row("Unix seconds", str(int(moment.timestamp())))
    table.add_row("Unix milliseconds", str(int(moment.timestamp() * 1000)))
    table.add_row("UTC", moment.astimezone(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
    table.add_row("Local", local.strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)"))
    table.add_row("ISO 8601", moment.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z"))
    table.add_row("Weekday", local.strftime("%A"))
    delta = moment - datetime.datetime.now(datetime.timezone.utc)
    seconds = int(abs(delta.total_seconds()))
    span = f"{seconds // 86400} days, {seconds % 86400 // 3600} hours" if seconds >= 86400 else f"{seconds // 3600} hours, {seconds % 3600 // 60} minutes" if seconds >= 3600 else f"{seconds // 60} minutes, {seconds % 60} seconds"
    table.add_row("Relative", span + (" from now" if delta.total_seconds() > 0 else " ago"))
    console.print(table)


# --------------------------------------------------------------- network
PRESET_FILE = "devhttp"


def _presets():
    return pyos.appdata.load(PRESET_FILE, {}) or {}


def tool_http(args=None):
    import requests
    args = list(args or [])
    if args and args[0] in ("save", "load", "list", "delete"):
        action, rest = args[0], args[1:]
        presets = _presets()
        if action == "list" or (action in ("load", "delete") and not rest and not presets):
            if not presets:
                console.print("[yellow]No saved requests yet. Make one and answer yes to 'save it'.[/yellow]")
                return
            for name, p in sorted(presets.items()):
                console.print(f"[bold]{escape(name)}[/bold]  {p['method']} {escape(p['url'])}")
            return
        name = rest[0] if rest else Prompt.ask("Name")
        if action == "delete":
            if presets.pop(name, None) is None:
                fail("There is no saved request called " + name)
            else:
                pyos.appdata.save(PRESET_FILE, presets)
                console.print("Deleted.")
            return
        if action == "load":
            if name not in presets:
                fail("There is no saved request called " + name + " (http list shows them)")
                return
            return send_request(presets[name], name)
        args = []
    method = arg(args, 0, "Method", choices=["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE"], default="GET").upper() if (not args or args[0].upper() in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE")) else "GET"
    rest = args[1:] if args and args[0].upper() in ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE") else args
    url = (rest[0] if rest else Prompt.ask("URL")).strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    headers = {}
    if len(rest) <= 1:
        console.print("[dim]Headers as Name: value, one per line; blank to finish.[/dim]")
        while True:
            line = Prompt.ask("Header", default="").strip()
            if not line:
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()
    body = Prompt.ask("Body (blank for none)", default="") if method in ("POST", "PUT", "PATCH") and len(rest) <= 1 else None
    preset = {"method": method, "url": url, "headers": headers, "body": body or ""}
    send_request(preset)
    if len(rest) <= 1 and Confirm.ask("Save this request to use again?", default=False):
        name = Prompt.ask("Name for it")
        presets = _presets()
        presets[name] = preset
        pyos.appdata.save(PRESET_FILE, presets)
        console.print(f"Saved as [bold]{escape(name)}[/bold]. Use it with: http load {escape(name)}")


SECRET_HEADERS = ("authorization", "cookie", "set-cookie", "x-api-key", "proxy-authorization")


def send_request(preset, name=None):
    import requests
    start = time.perf_counter()
    try:
        r = requests.request(preset["method"], preset["url"], headers=preset.get("headers") or {}, data=preset.get("body") or None, timeout=15, allow_redirects=True)
    except requests.RequestException as e:
        fail(f"Request failed: {str(e)[:150]}")
        return
    ms = (time.perf_counter() - start) * 1000
    colour = "green" if r.ok else "red"
    console.print(f"[{colour}]{r.status_code} {escape(r.reason or '')}[/{colour}]  {ms:.0f} ms  {len(r.content)} bytes"
                  + (f"  [dim]redirected {len(r.history)}x to {escape(r.url)}[/dim]" if r.history else ""))
    for k, v in list(r.headers.items())[:14]:
        shown = "(hidden)" if k.lower() in SECRET_HEADERS else v[:100]
        console.print(f"  [dim]{escape(k)}:[/dim] {escape(shown)}")
    if preset["method"] != "HEAD" and r.content:
        text = r.text[:4000]
        kind = "json" if "json" in r.headers.get("content-type", "") else "text"
        if kind == "json":
            try:
                text = json.dumps(r.json(), indent=2, ensure_ascii=False)[:4000]
            except ValueError:
                pass
        console.print(Syntax(text, kind, word_wrap=True))


# -------------------------------------------------------------- packages
def _folder(args, index=0, label="Package folder", default="~"):
    text = (args[index] if args and index < len(args) else Prompt.ask(label, default=default)).strip()
    try:
        folder = pyos.fs.resolve(text)
    except PermissionError as e:
        fail(str(e))
        return None
    if not os.path.isdir(folder):
        fail(f"{text} is not a folder")
        return None
    return folder


def tool_scaffold(args=None):
    name = re.sub(r"[^a-z0-9_-]", "", arg(args, 0, "Package name (lower-case letters, digits, - and _)").strip().lower())
    if not devtools.valid_name(name):
        fail("A package name is 2 to 31 lower-case letters, digits, - or _, starting with a letter.")
        return
    from pyos import compat
    clash = compat.core_words().get(name)
    if clash:
        console.print(f"[yellow]'{escape(name)}' is already the PythonOS command {escape(clash)}; the command would win. Pick another word.[/yellow]")
    for line in [f"  [bold]{t}[/bold]  [dim]{info[0]}[/dim]" for t, info in devtools.TEMPLATES.items()]:
        console.print(line)
    template = arg(args, 1, "Template", choices=list(devtools.TEMPLATES), default="basic")
    extra = [p for p in (args[2].split(",") if args and len(args) > 2 else []) if p]
    try:
        folder = pyos.fs.resolve(f"~/{name}", write=True)
        files = devtools.create_package(folder, name, template, extra)
    except (ValueError, FileExistsError, PermissionError) as e:
        fail("That folder already exists." if isinstance(e, FileExistsError) else str(e))
        return
    console.print(f"[green]Created ~/{escape(name)}[/green]: {', '.join(files)}. Edit them, then try [bold]check {escape(name)}[/bold], [bold]run ~/{escape(name)}[/bold] and [bold]pack ~/{escape(name)}[/bold].")


def tool_check(args=None):
    folder = _folder(args)
    if folder is None:
        return
    findings, entry = devtools.check_package(folder)
    marks = {"error": "[bold red]x[/bold red]", "warn": "[yellow]![/yellow]", "note": "[dim]-[/dim]"}
    for level in ("error", "warn", "note"):
        for found_level, text in findings:
            if found_level == level:
                console.print(f"{marks[level]} {escape(text)}")
    errors = sum(1 for lvl, _t in findings if lvl == "error")
    warns = sum(1 for lvl, _t in findings if lvl == "warn")
    if errors:
        console.print(f"[bold red]{errors} problem(s) to fix[/bold red]" + (f", {warns} warning(s)" if warns else ""))
    elif warns:
        console.print(f"[bold yellow]Fine to publish, with {warns} warning(s) worth reading.[/bold yellow]")
    else:
        console.print("[bold green]Package looks good.[/bold green]")
    if entry:
        console.print("[dim]Catalog entry: " + escape(json.dumps(entry, ensure_ascii=False)) + "[/dim]")


def tool_run(args=None):
    from pyos import lockdown
    if lockdown.enabled():
        fail("Running apps by hand is switched off while lockdown is on.")
        return
    folder = _folder(args, 0, "Package folder to run", default="~")
    if folder is None:
        return
    try:
        with open(os.path.join(folder, "data.json"), encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError) as e:
        fail(f"data.json: {e}")
        return
    declared = meta.get("permissions") or []
    answer = (args[1] if args and len(args) > 1 else Prompt.ask("Permissions to give it (none, or a list like files,network)", default=",".join(declared) or "none")).strip()
    perms = [] if answer in ("", "none") else [p.strip() for p in answer.split(",") if p.strip()]
    from pyos import sandbox
    unknown = [p for p in perms if p not in sandbox.PERMISSIONS]
    if unknown:
        fail("Unknown permission(s): " + ", ".join(unknown))
        return
    scripts = meta.get("scripts") or {}
    script = os.path.join(folder, scripts.get("run") or next(iter(scripts.values()), "run.py"))
    if not os.path.isfile(script):
        fail("The run script is missing.")
        return
    import subprocess
    command = [sys.executable, os.path.join(os.path.dirname(os.path.abspath(pyos.sandbox.__file__)), "sandbox_run.py"), "--perms", ",".join(perms), "--dir", folder,
               "--id", "dev/" + os.path.basename(folder), "--", script] + list(args[2:] if args and len(args) > 2 else Prompt.ask("Arguments", default="").split())
    env = dict(os.environ, PYTHONPATH=os.getcwd() + os.pathsep + os.environ.get("PYTHONPATH", ""))
    console.print(f"[dim]Running with permissions: {', '.join(perms) or 'none'} (anything else is refused)[/dim]")
    started = time.time()
    code = subprocess.call(command, env=env)
    console.print(f"[dim]Ended with exit code {code} after {time.time() - started:.1f} s[/dim]")


def tool_pack(args=None):
    folder = _folder(args)
    if folder is None:
        return
    findings, entry = devtools.check_package(folder)
    if any(level == "error" for level, _t in findings):
        console.print("[yellow]This package has problems (run check). Packing it anyway.[/yellow]")
    name = (entry or {}).get("id") or os.path.basename(folder)
    version = (entry or {}).get("version") or "0"
    try:
        destination = pyos.fs.resolve(f"~/{name}-{version}.zip", write=True)
        count, size, digest = devtools.pack_package(folder, destination)
    except (OSError, PermissionError) as e:
        fail(pyos.fs.errtext(e))
        return
    console.print(f"[green]Packed {count} file(s)[/green] into ~/{escape(name)}-{escape(str(version))}.zip ({size:,} bytes)")
    console.print(f"[dim]sha256 {digest}[/dim]")


SUGGESTIONS = {
    "requests": ("curl, wget", "downloads with size limits"), "urllib": ("curl, wget", "downloads with size limits"), "zipfile": ("zip, unzip", "safe archives"),
    "tarfile": ("tar", "safe archives"), "hashlib": ("sha256sum, md5sum", "checksums that can be checked with -c"), "gzip": ("gzip, gunzip, zcat", "compression with a size limit"),
    "difflib": ("diff, cmp", "the diff people know"), "shutil": ("cp, mv, rm", "trash and undo"), "psutil": ("ps, free, df, uptime", "the numbers the rest of PythonOS shows"),
    "base64": ("base64", "the same behaviour as the command"), "glob": ("find, tree", "one idea of hidden files"), "socket": ("ping, nslookup, whois, tracert", "the commands' timeouts and messages"),
}


def tool_deps(args=None):
    folder = _folder(args)
    if folder is None:
        return
    try:
        with open(os.path.join(folder, "data.json"), encoding="utf-8") as f:
            meta = json.load(f)
    except (OSError, ValueError) as e:
        fail(f"data.json: {e}")
        return
    import ast
    required, optional = set(), set()
    for script in (meta.get("scripts") or {}).values():
        try:
            with open(os.path.join(folder, script), encoding="utf-8") as f:
                r, o = devtools._imports(ast.parse(f.read()))
        except (OSError, SyntaxError):
            continue
        required |= r
        optional |= o
    table = Table(header_style="bold blue")
    for column in ("Import", "Needed", "Comes from"):
        table.add_column(column)
    pip_names = {re.split(r"[<>=!~\[; ]", str(x), maxsplit=1)[0].lower().replace("-", "_") for x in (meta.get("pip") or [])}
    for module in sorted(required | optional):
        if devtools.is_stdlib(module):
            source = "Python itself"
        elif module in devtools.PROVIDED:
            source = "PythonOS"
        elif module in devtools.OPTIONAL_PROVIDED:
            source = "PythonOS (an optional library: see extras)"
        elif module.lower() in pip_names:
            source = "installed with the app (pip)"
        elif os.path.exists(os.path.join(folder, module + ".py")) or os.path.isdir(os.path.join(folder, module)):
            source = "the app's own file"
        else:
            source = "[red]nothing: declare it under pip[/red]"
        table.add_row(module, "optional" if module in optional and module not in required else "yes", source)
    console.print(table)
    hints = sorted({(", ".join(SUGGESTIONS[m][0].split(", ")), SUGGESTIONS[m][1]) for m in required | optional if m in SUGGESTIONS})
    if hints:
        console.print("[bold]PythonOS commands that could do some of this (from pyos import corecmd):[/bold]")
        for commands, gain in hints:
            console.print(f"  {escape(commands)} [dim]- {escape(gain)}[/dim]")


def tool_watch(args=None):
    folder = _folder(args)
    if folder is None:
        return
    from pyos import filewatch
    console.print("[dim]Checking now and every time a file in the folder changes. Ctrl+C stops.[/dim]")
    try:
        changes = filewatch.changes(folder)
        while True:
            console.print(f"\n[bold]{time.strftime('%H:%M:%S')}[/bold]")
            tool_check([folder])
            next(changes)
    except (KeyboardInterrupt, StopIteration):
        console.print()


def tool_api(args=None):
    name = (args[0] if args else Prompt.ask("Module (blank for the list)", default="")).strip().replace("pyos.", "")
    if not name:
        table = Table(header_style="bold blue")
        table.add_column("pyos.")
        table.add_column("What it is")
        for module, summary in devtools.api_modules():
            table.add_row(module, escape(summary))
        console.print(table)
        console.print("[dim]api <module> lists what is in one. Apps may import pyos modules they have the permission for; corecmd, appdata, notify, fs and i18n are the usual ones.[/dim]")
        return
    try:
        members = devtools.api_members(name)
    except ValueError as e:
        fail(str(e))
        return
    for kind, member, signature, doc in members:
        console.print(f"[cyan]{kind:<5}[/cyan] [bold]{escape(member)}[/bold]{escape(signature)}" + (f"  [dim]{escape(doc)}[/dim]" if doc else ""))
    if not members:
        console.print("[yellow]Nothing public in it.[/yellow]")


# ---------------------------------------------------------------- compatibility and quality
def tool_compat(args=None):
    """Check every installed command, built-in program and app against this export, then offer to send the result to the developers through the
    Discord feedback channel. Quick: the code is read. Deep: commands are imported, the safe ones run on test input, every installed app is started with
    --help, and the system itself is looked at."""
    from pyos import compat, export, log, report, reportsend
    args = list(args or [])
    deep, _ = flag(args, "--deep")
    network, _ = flag(args, "--network")
    save, _ = flag(args, "--save")
    if not args:
        deep = Confirm.ask("Also run things: import every command, try the safe ones on test input, start every installed app for a moment, look at the system? (about a minute)", default=False)
        if deep:
            network = Confirm.ask("Include the internet checks too?", default=False)
    with console.status("Testing every command and app against this system..." + (" (running things as well)" if deep else "")):
        results = compat.run(deep=deep, network=network)
    counts = compat.summary(results)
    table = Table(header_style="bold blue", expand=True)
    table.add_column("", no_wrap=True)
    table.add_column("What", style="cyan", no_wrap=True)
    table.add_column("Result")
    marks = {"fail": "[bold red]FAIL[/bold red]", "warn": "[yellow]WARN[/yellow]", "skip": "[dim]skip[/dim]"}
    shown = [r for r in results if r.level != "ok"]
    for r in sorted(shown, key=lambda item: compat.LEVELS.index(item.level)):
        table.add_row(marks[r.level], f"{r.kind} {r.name}", escape("; ".join(r.notes)))
    where = export.title(export.current()) if export.current() else "a source checkout"
    console.print(f"[bold]Compatibility with this system ({escape(where)})[/bold]")
    if shown:
        console.print(table)
    facts = [r for r in results if r.kind == "system" and r.level == "ok" and r.notes]
    if facts:
        info = Table(show_header=False, box=None)
        for r in facts:
            info.add_row("[dim]" + escape(r.name) + "[/dim]", escape("; ".join(r.notes)))
        console.print(info)
    for kind, label in (("command", "commands"), ("program", "built-in programs"), ("app", "apps"), ("system", "system checks")):
        c = counts.get(kind) or {}
        if sum(c.values()):
            console.print(f"  {label}: {sum(c.values())} tested - [green]{c['ok']} ok[/green], [yellow]{c['warn']} warnings[/yellow], "
                          f"[red]{c['fail']} failing[/red], [dim]{c['skip']} for another export[/dim]")
    console.print("[dim]" + ("Commands were imported and run on test input, and apps were started with --help; the code was read as well." if deep
                              else "Nothing was run: the code was read and checked against what this system has. Add --deep to run things too.") + "[/dim]")

    text = report.redact(compat.report(results, version=report._version(), package=report._package()))
    problems = sum(1 for r in results if r.level in ("fail", "warn"))
    if save or (not args and Confirm.ask("Save the full report to a file in your home folder?", default=False)):
        try:
            path = pyos.fs.resolve("~/compat-report.txt", write=True)
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
            console.print("[green]Saved ~/compat-report.txt[/green]")
        except (OSError, PermissionError) as e:
            fail(pyos.fs.errtext(e))
    if args:
        return
    if not reportsend.can_discord():
        console.print("[dim]Sending feedback is not set up in this copy of PythonOS.[/dim]")
        return
    if not Confirm.ask("Send this result to the PythonOS developers (Discord feedback)?", default=False):
        return
    console.print(Panel(escape(text), title="[bold]This is everything that will be sent[/bold]", border_style="blue"))
    if not Confirm.ask("Send it now?", default=False):
        console.print("[yellow]Nothing was sent.[/yellow]")
        return
    try:
        reportsend.send_discord(f"Compatibility test: {report._package()} ({problems} to look at)", text)
    except reportsend.SendError as e:
        log.log(f"compat: feedback not sent: {str(e)[:200]}", "WARN")
        console.print(f"[bold red]{escape(str(e))}[/bold red]")
        return
    log.log(f"compat: sent to Discord ({problems} to look at)")
    console.print("[green]Sent. Thank you.[/green]")


def tool_fuzz(args=None):
    """Try the commands an app may use with odd arguments and odd text. A command that raises an error of its own is a bug worth fixing."""
    from pyos import compatdeep
    quick, _ = flag(args, "--quick")
    why = compatdeep.refused()
    if why:
        fail(why)
        return
    with console.status("Trying odd input on the commands..."):
        results = compatdeep.fuzz_check(per_command=6 if quick else None)
    for r in results:
        colour = "red" if r.level == "fail" else "green"
        console.print(f"[{colour}]{r.level.upper():<4}[/{colour}] {escape(r.kind)} {escape(r.name)}: {escape('; '.join(r.notes))}")


def tool_profile(args=None):
    """Run a command line and say how long it took, how much memory it used at its peak and which functions it spent its time in."""
    line = " ".join(args) if args else Prompt.ask("Command to measure (for example: sysinfo)").strip()
    if not line:
        return
    import shell
    outcome = devtools.measure(lambda: shell.run_line(line))
    if outcome["error"]:
        console.print(f"[red]It raised {escape(outcome['error'])}[/red]")
    console.print(f"[bold]{outcome['seconds'] * 1000:.0f} ms[/bold], peak memory {outcome['peak_kb']:,} KB")
    if outcome["top"]:
        console.print(Panel(escape(outcome["top"][:3500]), title="where the time went (cumulative)", border_style="blue"))


def tool_bench(args=None):
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
    timed("sort 200,000 numbers", lambda: sorted(range(200_000, 0, -1)))
    timed("sha256 of 1 MB", lambda: hashlib.sha256(b"x" * 1_000_000).hexdigest())
    timed("build and parse JSON (20,000 items)", lambda: json.loads(json.dumps([{"id": i, "name": "item%d" % i} for i in range(20_000)])))
    timed("regex over 200 KB", lambda: re.findall(r"\b\w{5}\b", "lorem ipsum dolor sit amet " * 8000))
    with tempfile.NamedTemporaryFile(delete=True) as tmp:
        timed("write+read 1 MB file", lambda: (tmp.seek(0), tmp.write(b"x" * 1_000_000), tmp.flush(), tmp.seek(0), tmp.read()))
        timed("write+sync 1 MB file", lambda: (tmp.seek(0), tmp.write(b"x" * 1_000_000), tmp.flush(), os.fsync(tmp.fileno())))
    timed("zlib compress 1 MB", lambda: zlib.compress(b"hello world " * 90_000))
    table = Table(header_style="bold blue")
    table.add_column("Test")
    table.add_column("ms", justify="right")
    table.add_column("", style="dim")
    slowest = max(ms for _l, ms in results)
    for label, ms in results:
        table.add_row(label, f"{ms:.1f}", "#" * max(1, int(20 * ms / slowest)))
    console.print(table)


# ---------------------------------------------------------------- system
LEVELS = ("DEBUG", "INFO", "WARN", "ERROR")


def tool_tail(args=None):
    args = list(args or [])
    level = None
    if "-l" in args:
        i = args.index("-l")
        level = args[i + 1].upper() if i + 1 < len(args) else None
        del args[i:i + 2]
    if level and level not in LEVELS:
        fail("The levels are " + ", ".join(LEVELS))
        return
    path = os.path.join(pyos.fs.BASE_DIR, "var", "log", "system.log")
    term = (args[0] if args else Prompt.ask("Only lines containing (blank for all)", default="")).lower()
    wanted = LEVELS[LEVELS.index(level):] if level else LEVELS

    def keep(line):
        lowered = line.lower()
        if term and term not in lowered:
            return False
        return not level or any(f" {l.lower()} " in lowered or f"[{l.lower()}]" in lowered or lowered.lstrip().startswith(l.lower()) for l in wanted)
    console.print("[dim]Following the system log. Press Ctrl+C to stop.[/dim]")
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f.readlines()[-30:]:
                if keep(line):
                    console.print(escape(line.rstrip()))
            while True:
                line = f.readline()
                if line:
                    if keep(line):
                        console.print(escape(line.rstrip()))
                else:
                    time.sleep(0.5)
    except OSError:
        console.print("[yellow]There is no system log yet.[/yellow]")
    except KeyboardInterrupt:
        console.print()


def tool_info(args=None):
    import platform
    from pyos import extras, settings
    table = Table(show_header=False, box=None)
    for k, v in (("PythonOS", _version()), ("Python", f"{sys.version.split()[0]} ({platform.python_implementation()})"), ("Platform", platform.platform()),
                 ("Working folder", os.getcwd()), ("Bundled", os.environ.get("PYOS_BUNDLED", "0")),
                 ("Live ISO", os.environ.get("PYOS_LIVE", "0")), ("Lockdown", os.environ.get("PYOS_LOCKDOWN", "0")),
                 ("Persistent", os.environ.get("PYOS_PERSISTENT", "0")), ("User", " / ".join(str(x) for x in pyos.userinfo())),
                 ("Optional libraries", ", ".join(e.name + ("" if e.installed() else " (missing)") for e in extras.catalog()) or "none listed"),
                 ("Library choice", (extras.load_choice() or {}).get("mode", "not chosen"))):
        table.add_row(k, escape(str(v)))
    console.print(table)
    console.print("[bold]Settings[/bold]  " + ", ".join(f"{k}={v}" for k, v in settings.load().items()))


def _version():
    try:
        with open("config.json", encoding="utf-8") as f:
            return json.load(f).get("version", "?")
    except (OSError, ValueError):
        return "?"


def tool_bsod(args=None):
    core.simulate_bsod("Developer triggered BSOD\n\nThis is normal, no problems are current in the system")


def tool_shutdown(args=None):
    pyos.shutdown()


def tool_restart(args=None):
    pyos.system("restart")


TOOLS = {"json": tool_json, "regex": tool_regex, "diff": tool_diff, "hash": tool_hash, "encode": tool_encode, "time": tool_time,
         "http": tool_http, "scaffold": tool_scaffold, "check": tool_check, "run": tool_run, "pack": tool_pack, "deps": tool_deps, "watch": tool_watch, "api": tool_api,
         "compat": tool_compat, "fuzz": tool_fuzz, "profile": tool_profile, "bench": tool_bench,
         "tail": tool_tail, "info": tool_info, "bsod": tool_bsod, "shutdown": tool_shutdown, "restart": tool_restart}
INFO = {name: (group, summary, usage) for name, group, summary, usage in REGISTRY}


def explain(name):
    group, summary, usage = INFO[name]
    console.print(f"[bold]{name}[/bold]  [dim]({group})[/dim]\n  {escape(summary)}\n  [cyan]{escape(usage)}[/cyan]")


def run_tool(name, args=None):
    """Run a tool by name; errors are shown, not raised (except a requested shutdown). False for an unknown name."""
    if name not in TOOLS:
        close = pyos.fuzzy.close_matches(name, list(TOOLS), n=2) if hasattr(pyos, "fuzzy") else []
        console.print("[bold red]Unknown tool.[/bold red] " + (f"Did you mean: {', '.join(close)}? " if close else "") + "Type [bold]help[/bold] for the list.")
        return False
    try:
        TOOLS[name](args or None)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopped.[/yellow]")
    except pyos.ShutdownRequested:
        raise
    except Exception as e:                                                  # noqa: BLE001 - a tool's own failure is shown, not a crash of the console
        console.print(f"[red]{type(e).__name__}: {escape(str(e))}[/red]")
    return True


def dev_commands():
    if not is_admin():
        console.print("[bold red]The developer tools are for administrators.[/bold red]")
        return
    console.print(MENU)
    while True:
        try:
            line = Prompt.ask("[bold green]tool[/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print()
            return
        words = line.split()
        cmd = words[0].lower() if words else ""
        if cmd in ("exit", "quit", "q"):
            console.print("[bold blue]Leaving the developer tools.[/bold blue]")
            return
        if not cmd:
            continue
        if cmd in ("help", "?", "menu"):
            if len(words) > 1 and words[1].lower() in INFO:
                explain(words[1].lower())
            else:
                console.print(MENU)
        else:
            import shlex
            try:
                parsed = shlex.split(line)[1:]
            except ValueError:
                parsed = words[1:]
            run_tool(cmd, parsed)


def execute(args=None):
    console.print(f"[bold green]{config['name']}[/bold green]")
    if args:
        if not is_admin():
            console.print("[bold red]The developer tools are for administrators.[/bold red]")
            return
        if args[0] in ("help", "?") and len(args) > 1 and args[1] in INFO:
            explain(args[1])
            return
        run_tool(args[0].lower(), list(args[1:]))
        return
    dev_commands()
