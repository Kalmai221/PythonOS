# pyos/devtools.py - the working parts of the Developer Console (programs/developer.py shows them and asks the questions)
#
# Everything here takes plain values and returns plain values, so each can be tested without a screen: reading JSON and asking it questions, trying a
# regular expression, encodings, the checks of a package folder (the rules of the marketplace and of lockdown), a new package from a template, packing a
# package for sharing, timing and profiling a call, trying commands with odd input, and a map of PythonOS's own modules for people writing apps.
import ast
import base64
import binascii
import cProfile
import codecs
import hashlib
import html
import io
import json
import os
import pstats
import re
import sys
import sysconfig
import time
import tracemalloc
import urllib.parse
import zipfile
import zlib

# ---------------------------------------------------------------- JSON


def json_error(text, error):
    """('line 3, column 7: Expecting value', the line's text, the column) for a JSONDecodeError, so the place can be shown with a caret."""
    lines = text.splitlines() or [""]
    line = lines[min(error.lineno, len(lines)) - 1] if error.lineno else ""
    return f"line {error.lineno}, column {error.colno}: {error.msg}", line, max(0, error.colno - 1)


_PATH = re.compile(r"\.([A-Za-z_][\w-]*)|\[(\d+|\*|-\d+)\]|\[\"([^\"]*)\"\]|\['([^']*)'\]")


def json_query(data, path):
    """The values at a path like .users[0].name or .items[*].id (. alone is the whole thing). Raises ValueError with a sentence."""
    path = path.strip()
    if path in ("", "."):
        return [data]
    if not path.startswith((".", "[")):
        path = "." + path
    current, position = [data], 0
    while position < len(path):
        found = _PATH.match(path, position)
        if not found:
            raise ValueError(f"cannot read the path at '{path[position:position + 10]}' (use .name, [0] or [*])")
        position = found.end()
        key, index, quoted_a, quoted_b = found.groups()
        key = key if key is not None else (quoted_a if quoted_a is not None else quoted_b)
        nxt = []
        for item in current:
            if key is not None:
                if isinstance(item, dict) and key in item:
                    nxt.append(item[key])
                elif isinstance(item, list):
                    raise ValueError(f"{key} is not in a list; use [*].{key} to look in each item of it ({_describe(item)})")
                else:
                    raise ValueError(f"there is no '{key}' in {_describe(item)}")
            elif index == "*":
                if not isinstance(item, list):
                    raise ValueError(f"[*] needs a list, not {_describe(item)}")
                nxt.extend(item)
            else:
                if not isinstance(item, list):
                    raise ValueError(f"[{index}] needs a list, not {_describe(item)}")
                try:
                    nxt.append(item[int(index)])
                except IndexError:
                    raise ValueError(f"there is no item {index} (the list has {len(item)})") from None
        current = nxt
    return current


def _describe(value):
    if isinstance(value, dict):
        return "an object with " + (", ".join(list(value)[:5]) + ("..." if len(value) > 5 else "") or "nothing in it")
    return "a list of " + str(len(value)) if isinstance(value, list) else repr(value)[:40]


def json_stats(data):
    """{'type', 'items', 'depth', 'keys'} about a parsed JSON value."""
    def depth(value):
        if isinstance(value, dict):
            return 1 + max((depth(v) for v in value.values()), default=0)
        if isinstance(value, list):
            return 1 + max((depth(v) for v in value), default=0)
        return 0

    def count(value):
        if isinstance(value, dict):
            return 1 + sum(count(v) for v in value.values())
        if isinstance(value, list):
            return 1 + sum(count(v) for v in value)
        return 1
    return {"type": type(data).__name__, "items": count(data), "depth": depth(data), "keys": list(data)[:8] if isinstance(data, dict) else []}


# ---------------------------------------------------------------- regular expressions
FLAGS = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL, "x": re.VERBOSE}


def regex_flags(letters):
    value = 0
    for letter in letters.lower():
        if letter not in FLAGS:
            raise ValueError(f"the flag '{letter}' is not one of: " + " ".join(FLAGS))
        value |= FLAGS[letter]
    return value


def regex_try(pattern, text, letters="", replacement=None):
    """A dict for one text: the matches (position, text, groups, named groups), and the text with the replacement applied when one is given.
    Raises ValueError for a pattern that is not valid."""
    try:
        rx = re.compile(pattern, regex_flags(letters))
    except re.error as e:
        raise ValueError(f"not a valid pattern: {e}") from None
    matches = [{"start": m.start(), "end": m.end(), "text": m.group(0), "groups": list(m.groups()), "named": m.groupdict()} for m in rx.finditer(text)][:200]
    result = {"matches": matches, "groups": rx.groups, "names": list(rx.groupindex)}
    if replacement is not None:
        try:
            result["replaced"] = rx.sub(replacement, text)
        except (re.error, IndexError) as e:
            raise ValueError(f"the replacement does not fit the pattern: {e}") from None
    return result


# ---------------------------------------------------------------- hashes and encodings
HASHES = ("md5", "sha1", "sha224", "sha256", "sha384", "sha512", "sha3_256", "blake2b")


def hash_all(data):
    """{algorithm: hex digest} for some bytes, plus the checksums crc32 and adler32."""
    out = {name: hashlib.new(name, data).hexdigest() for name in HASHES}
    out["crc32"] = f"{zlib.crc32(data) & 0xffffffff:08x}"
    out["adler32"] = f"{zlib.adler32(data) & 0xffffffff:08x}"
    return out


def which_hash(digest):
    """The algorithms whose digest has the length of `digest` (a hint when somebody pastes a hash)."""
    digest = digest.strip().lower()
    if not re.fullmatch(r"[0-9a-f]+", digest):
        return []
    sizes = {8: ["crc32", "adler32"], 32: ["md5"], 40: ["sha1"], 56: ["sha224"], 64: ["sha256", "sha3_256"], 96: ["sha384"], 128: ["sha512", "blake2b"]}
    return sizes.get(len(digest), [])


ENCODINGS = ("base64", "base32", "hex", "url", "html", "unicode-escape", "rot13", "gzip-base64")


def encode(mode, text):
    """text encoded by `mode`. Raises ValueError."""
    data = text.encode("utf-8")
    if mode == "base64":
        return base64.b64encode(data).decode("ascii")
    if mode == "base32":
        return base64.b32encode(data).decode("ascii")
    if mode == "hex":
        return data.hex()
    if mode == "url":
        return urllib.parse.quote(text, safe="")
    if mode == "html":
        return html.escape(text)
    if mode == "unicode-escape":
        return text.encode("unicode_escape").decode("ascii")
    if mode == "rot13":
        return codecs.encode(text, "rot13")
    if mode == "gzip-base64":
        import gzip
        return base64.b64encode(gzip.compress(data)).decode("ascii")
    raise ValueError(f"unknown mode '{mode}'")


def decode(mode, text):
    """The text that `mode` encoded into `text`. Raises ValueError with a sentence."""
    text = text.strip()
    try:
        if mode == "base64":
            return base64.b64decode(text + "=" * (-len(text) % 4), validate=True).decode("utf-8", errors="replace")
        if mode == "base32":
            return base64.b32decode(text + "=" * (-len(text) % 8)).decode("utf-8", errors="replace")
        if mode == "hex":
            return bytes.fromhex(text).decode("utf-8", errors="replace")
        if mode == "url":
            return urllib.parse.unquote(text)
        if mode == "html":
            return html.unescape(text)
        if mode == "unicode-escape":
            return text.encode("ascii", errors="backslashreplace").decode("unicode_escape")
        if mode == "rot13":
            return codecs.decode(text, "rot13")
        if mode == "gzip-base64":
            import gzip
            return gzip.decompress(base64.b64decode(text + "=" * (-len(text) % 4), validate=True)).decode("utf-8", errors="replace")
    except (ValueError, binascii.Error, OSError, EOFError, UnicodeError) as e:
        raise ValueError(f"that is not valid {mode} ({type(e).__name__})") from None
    raise ValueError(f"unknown mode '{mode}'")


def guess_encoding(text):
    """Modes that `text` looks like it is written in, most likely first (to say 'this looks like base64')."""
    text = text.strip()
    guesses = []
    if re.fullmatch(r"[A-Za-z0-9+/]+={0,2}", text) and len(text) % 4 == 0 and len(text) >= 4:
        guesses.append("base64")
    if re.fullmatch(r"[A-Z2-7]+=*", text) and len(text) % 8 == 0:
        guesses.append("base32")
    if re.fullmatch(r"([0-9a-fA-F]{2})+", text):
        guesses.append("hex")
    if re.search(r"%[0-9a-fA-F]{2}", text):
        guesses.append("url")
    if re.search(r"&(#\d+|#x[0-9a-fA-F]+|[a-zA-Z]+);", text):
        guesses.append("html")
    if "\\u" in text or "\\x" in text:
        guesses.append("unicode-escape")
    return guesses


# ---------------------------------------------------------------- packages (the rules of the marketplace and of lockdown)
RISKY_CALLS = {"eval", "exec", "compile", "__import__", "breakpoint"}
RISKY_MODULES = {"subprocess", "pty", "ctypes", "code", "pdb", "cmd", "telnetlib", "multiprocessing", "socketserver"}
RISKY_OS = {"system", "popen", "execv", "execve", "execl", "execvp", "spawnl", "spawnv", "posix_spawn", "startfile", "fork", "forkpty"}
PROVIDED = {"rich", "requests", "psutil", "yaspin", "ping3", "prompt_toolkit", "pygments", "tzdata", "pyos", "core", "commands", "programs", "shell", "users",
            "urllib3", "certifi", "idna", "charset_normalizer", "markdown_it", "mdurl", "wcwidth", "colorama"}
OPTIONAL_PROVIDED = {"dateutil", "humanize", "zxcvbn", "filetype", "bs4", "yaml", "rapidfuzz", "feedparser", "distro", "cpuinfo", "dns", "py7zr", "watchfiles"}
SECRETS = re.compile(r"(?i)(api[_-]?key|secret|token|passwd|password)\s*[:=]\s*[\"'][^\"']{8,}[\"']")


def is_stdlib(name):
    if name in getattr(sys, "stdlib_module_names", ()):
        return True
    if name in sys.builtin_module_names:
        return True
    try:
        import importlib.util
        spec = importlib.util.find_spec(name)
    except (ImportError, ValueError, AttributeError):
        return False
    origin = getattr(spec, "origin", None) or ""
    standard = sysconfig.get_paths().get("stdlib", "")
    return bool(origin) and bool(standard) and origin.startswith(standard) and "site-packages" not in origin


def _imports(tree):
    """(modules imported at the top of a try/except ImportError (optional), the others)."""
    optional_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                kinds = []
                if handler.type is None:
                    kinds = ["Exception"]
                else:
                    for t in (handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]):
                        kinds.append(getattr(t, "id", getattr(t, "attr", "")))
                if {"ImportError", "ModuleNotFoundError", "Exception", "BaseException"} & set(kinds):
                    for child in node.body:
                        optional_nodes.update(id(inner) for inner in ast.walk(child))
    required, optional = set(), set()
    for node in ast.walk(tree):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name.split(".")[0] for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names = [node.module.split(".")[0]]
        (optional if id(node) in optional_nodes else required).update(names)
    return required, optional


def risky_uses(tree):
    """[(line, what)] for each call that starts a process or evaluates code, which a lockdown_safe package may not do."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in RISKY_CALLS:
                found.append((node.lineno, f"{func.id}()"))
            elif isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
                if func.value.id == "os" and func.attr in RISKY_OS:
                    found.append((node.lineno, f"os.{func.attr}()"))
                elif func.value.id == "subprocess":
                    found.append((node.lineno, f"subprocess.{func.attr}()"))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                if name.split(".")[0] in RISKY_MODULES:
                    found.append((node.lineno, f"import {name}"))
    return found


def check_package(folder):
    """Everything wrong or doubtful about a package folder, as [(level, text)] where level is 'error', 'warn' or 'note', plus the catalog entry it would
    have as a dict (or None when data.json cannot be read). Reads the code; nothing is run."""
    from . import compat, sandbox
    findings, entry = [], None

    def add(level, text):
        findings.append((level, text))
    meta_path = os.path.join(folder, "data.json")
    try:
        with open(meta_path, encoding="utf-8") as f:
            meta = json.load(f)
        if not isinstance(meta, dict):
            raise ValueError("it is not a JSON object")
    except (OSError, ValueError) as e:
        return [("error", f"data.json: {e}")], None
    for key in ("name", "description", "version", "command", "scripts"):
        if key not in meta:
            add("error", f"data.json has no '{key}'")
    for note in compat.check_metadata(meta):
        add("warn", note)
    if not meta.get("changelog"):
        add("note", "no changelog (it is shown to people when they update)")
    declared = meta.get("permissions")
    if declared is None:
        add("warn", "data.json has no 'permissions' list (use [] for an app that needs nothing special); the marketplace refuses a package without it")
        declared = []
    unknown = [p for p in declared if p not in sandbox.PERMISSIONS]
    if unknown:
        add("error", "unknown permission(s): " + ", ".join(unknown) + " (known: " + ", ".join(sorted(sandbox.PERMISSIONS)) + ")")
    needed, third_party, total_size = set(), set(), 0
    scripts = meta.get("scripts") or {}
    if not isinstance(scripts, dict) or not scripts:
        add("error", "data.json lists no scripts")
        scripts = {}
    pip_names = {re.split(r"[<>=!~\[; ]", str(x), maxsplit=1)[0].lower().replace("-", "_") for x in (meta.get("pip") or [])}
    for key, script in scripts.items():
        path = os.path.join(folder, script)
        if not os.path.isfile(path):
            add("error", f"script '{script}' ({key}) is missing")
            continue
        try:
            with open(path, encoding="utf-8") as f:
                source = f.read()
            tree = ast.parse(source, path)
        except SyntaxError as e:
            add("error", f"{script}: syntax error on line {e.lineno}: {e.msg}")
            continue
        except (OSError, UnicodeDecodeError) as e:
            add("error", f"{script}: cannot be read ({type(e).__name__})")
            continue
        total_size += len(source)
        notes, uses = compat.deeper(source)
        for note in notes:
            add("warn", f"{script}: {note}")
        needed |= uses
        required, optional = _imports(tree)
        for module in sorted(required | optional):
            if module in PROVIDED or is_stdlib(module):
                continue
            if module in OPTIONAL_PROVIDED and module in optional:
                continue
            if module.lower() in pip_names or module.lower().replace("_", "-") in {n.replace("_", "-") for n in pip_names}:
                continue
            if os.path.isfile(os.path.join(folder, module + ".py")) or os.path.isdir(os.path.join(folder, module)):
                continue
            third_party.add((module, module in optional))
        if "if __name__" not in source and "def execute" not in source and "def main" not in source:
            add("note", f"{script} has neither a main() nor an execute() nor an 'if __name__ == \"__main__\"' block")
        if SECRETS.search(source):
            add("warn", f"{script} looks like it has a password or key written in it")
        if meta.get("lockdown_safe"):
            for line, what in risky_uses(tree):
                add("error", f"{script} line {line}: {what}, but lockdown_safe is true (such a package must not start programs or evaluate code)")
    for module, soft in sorted(third_party):
        add("warn" if soft else "error", f"imports {module}, which PythonOS does not provide" + (" (optional here)" if soft else "; list it under 'pip' in data.json (API 2) or the app cannot start"))
    wording = {"network": "the internet", "system": "system information", "exec": "other programs", "notifications": "notifications", "schedule": "scheduling"}
    for permission in sorted(needed - set(declared)):
        add("warn", f"uses {wording.get(permission, permission)} but does not ask for the '{permission}' permission, so the guard will refuse it")
    for permission in sorted(set(declared) - needed - {"files"}):
        if permission in wording:
            add("note", f"asks for the '{permission}' permission but the code does not seem to use it (people see every permission before installing)")
    if total_size > 400_000:
        add("note", f"{total_size // 1024} KB of code is large for a terminal app")
    entry = {"id": os.path.basename(os.path.abspath(folder)), "name": meta.get("name"), "version": meta.get("version"), "command": meta.get("command"),
             "permissions": declared, "pip": meta.get("pip") or [], "lockdown_safe": bool(meta.get("lockdown_safe")), "api": meta.get("api", 1),
             "exports": meta.get("exports") or "all", "code_bytes": total_size}
    return findings, entry


# ---------------------------------------------------------------- new packages
TEMPLATES = {
    "basic": ("A minimal app that greets you.", [], '''console.print("[bold green]Hello from {name}![/bold green]")
    if args:
        console.print("You typed: " + " ".join(args))'''),
    "network": ("Fetches something from the internet and shows it.", ["network"], '''import requests
    try:
        response = requests.get("https://example.com", timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        console.print(f"[red]Could not reach the server ({{type(e).__name__}}).[/red]")
        return 1
    console.print(f"Got {{len(response.text)}} characters, status {{response.status_code}}.")'''),
    "files": ("Reads a file the person names and counts its lines.", ["files"], '''if not args:
        console.print("Usage: {name} <file>")
        return 1
    try:
        with open(args[0], encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
    except OSError as e:
        console.print(f"[red]Cannot read it: {{e.strerror or e}}[/red]")
        return 1
    console.print(f"{{len(lines)}} lines")'''),
    "game": ("A turn-based guessing game to build on.", [], '''import random
    secret = random.randint(1, 20)
    console.print("I am thinking of a number from 1 to 20.")
    for turn in range(1, 6):
        try:
            guess = int(console.input(f"Guess {{turn}}/5: "))
        except (ValueError, EOFError, KeyboardInterrupt):
            break
        if guess == secret:
            console.print("[bold green]Yes![/bold green]")
            return 0
        console.print("higher" if guess < secret else "lower")
    console.print(f"It was {{secret}}.")'''),
    "corecmd": ("Uses PythonOS's own commands (pyos.corecmd).", ["files"], '''try:
        from pyos import corecmd
    except ImportError:
        console.print("This app needs PythonOS.")
        return 1
    result = corecmd.run("sha256sum", args or ["data.json"])
    console.print(result.output if result.ok else "[red]" + result.output + "[/red]")'''),
}


def valid_name(name):
    return bool(re.fullmatch(r"[a-z][a-z0-9_-]{1,30}", name))


def create_package(folder, name, template="basic", extra_permissions=()):
    """Write a new package folder (data.json, run.py, test_run.py, README.md). Raises ValueError/FileExistsError. Returns the files written."""
    if not valid_name(name):
        raise ValueError("a package name is 2 to 31 lower-case letters, digits, - or _, starting with a letter")
    if template not in TEMPLATES:
        raise ValueError("the templates are: " + ", ".join(TEMPLATES))
    if os.path.exists(folder):
        raise FileExistsError(folder)
    summary, permissions, body = TEMPLATES[template]
    permissions = sorted(set(permissions) | set(extra_permissions))
    os.makedirs(folder)
    meta = {"name": name.replace("-", " ").replace("_", " ").title(), "description": summary, "version": "0.1.0", "scripts": {"run": "run.py"}, "command": name,
            "alias": [], "tags": [template], "permissions": permissions, "lockdown_safe": not (set(permissions) & {"exec"}) and template != "network", "changelog": "First version."}
    if template == "network":
        meta["lockdown_safe"] = True
    files = {
        "data.json": json.dumps(meta, indent=2) + "\n",
        "run.py": ('#!/usr/bin/env python3\n"""' + meta["name"] + ": " + summary + '"""\nimport sys\n\nfrom rich.console import Console\n\nconsole = Console()\n\n\n'
                   "def main(args):\n    " + body.format(name=name).replace("\n    ", "\n    ") + "\n    return 0\n\n\n"
                   'if __name__ == "__main__":\n    sys.exit(main(sys.argv[1:]))\n'),
        "test_run.py": ('"""A first test: run it with  python test_run.py  (or let `developer` -> check look at the package)."""\nimport importlib.util\nimport os\n\n\n'
                        'def main():\n    spec = importlib.util.spec_from_file_location("app", os.path.join(os.path.dirname(os.path.abspath(__file__)), "run.py"))\n'
                        '    module = importlib.util.module_from_spec(spec)\n    spec.loader.exec_module(module)\n    assert callable(module.main), "run.py needs a main(args)"\n'
                        '    print("ok")\n\n\nif __name__ == "__main__":\n    main()\n'),
        "README.md": f"# {meta['name']}\n\n{summary}\n\nRun it with `{name}` once installed. Edit `data.json` (name, description, tags, permissions) and `run.py`, then use the "
                     f"Developer Console: `check` for the rules, `run` to try it with the permissions it asks for, `pack` to make a file to share.\n",
    }
    for file_name, text in files.items():
        with open(os.path.join(folder, file_name), "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
    return sorted(files)


def pack_package(folder, destination):
    """Zip a package folder into `destination` (a .zip path), leaving out caches and libraries. Returns (files packed, bytes, sha256 of the zip)."""
    skip_dirs, skip_ext = {"__pycache__", ".git", ".libs", ".venv", "node_modules"}, (".pyc", ".pyo", ".tmp")
    count = 0
    with zipfile.ZipFile(destination, "w", zipfile.ZIP_DEFLATED) as z:
        for base, dirs, names in os.walk(folder):
            dirs[:] = sorted(d for d in dirs if d not in skip_dirs)
            for name in sorted(names):
                if name.endswith(skip_ext) or name.startswith("."):
                    continue
                full = os.path.join(base, name)
                if os.path.abspath(full) == os.path.abspath(destination):
                    continue
                z.write(full, os.path.relpath(full, folder).replace(os.sep, "/"))
                count += 1
    with open(destination, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    return count, os.path.getsize(destination), digest


# ---------------------------------------------------------------- timing and profiling
def measure(call):
    """Run `call()` and return {'seconds', 'peak_kb', 'top': text of the busiest functions, 'result'}. Exceptions of the call are in 'error'."""
    profiler = cProfile.Profile()
    tracemalloc.start()
    started = time.perf_counter()
    result = error = None
    try:
        profiler.enable()
        try:
            result = call()
        finally:
            profiler.disable()
    except BaseException as e:                                          # noqa: BLE001 - the call's own failure is part of the measurement
        error = f"{type(e).__name__}: {e}"
    seconds = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.strip_dirs().sort_stats("cumulative").print_stats(12)
    text = stream.getvalue()
    start = text.find("ncalls")
    return {"seconds": seconds, "peak_kb": peak // 1024, "top": text[start:].strip() if start >= 0 else "", "result": result, "error": error}


# ---------------------------------------------------------------- odd input (the commands apps can ask for)
FUZZ_ARGS = [[], [""], ["-"], ["--"], ["-x"], ["--help"], ["--bogus"], ["0"], ["-1"], ["999999999999999999999"], ["a" * 3000], ["../../../etc/passwd"],
             ["~"], ["%s%n%d"], ["é日本語\u202e"], ["\x00"], ["-n", "x"], ["-d"], ["a", "b", "c", "d", "e", "f", "g"], ["*"], ["--", "-x"]]
FUZZ_STDIN = [None, "", "\n", "x" * 100_000, "\x00\x01\x02\n", "éè\n日本\n", "a\r\nb\r\n", "1\n2\n3\n"]
FUZZ_SKIP = {"curl", "wget", "ping", "nslookup", "whois", "tracert", "ipinfo", "touch", "mkdir", "cp", "mv", "rm", "zip", "unzip", "tar", "gzip", "gunzip", "tee",
             "schedule", "calc", "shuf", "uuidgen", "date", "cal"}


def fuzz_cases(commands, per_command=None):
    """[(command, arguments, text)] covering the odd arguments, and the odd text for the commands that read text."""
    cases = []
    for command in commands:
        if command in FUZZ_SKIP:
            continue
        mixed = [(args, None) for args in FUZZ_ARGS] + [([], text) for text in FUZZ_STDIN[1:]] + [(["-n", "1"], "a\nb\n"), (["a"], "abc\nxyz\n")]
        cases += [(command, args, text) for args, text in (mixed[:per_command] if per_command else mixed)]
    return cases


# ---------------------------------------------------------------- the map of PythonOS for people writing apps
def api_modules(package="pyos"):
    """[(module name, first line of its header comment or docstring)] for the modules of PythonOS an app may import."""
    base = os.path.join(os.getcwd(), package)
    out = []
    try:
        names = sorted(n[:-3] for n in os.listdir(base) if n.endswith(".py") and not n.startswith("_"))
    except OSError:
        return out
    for name in names:
        try:
            with open(os.path.join(base, name + ".py"), encoding="utf-8") as f:
                lines = f.read().splitlines()[:12]
        except OSError:
            continue
        summary = ""
        for line in lines:
            text = line.strip().lstrip("#").strip().strip('"').strip()
            if text and not text.startswith("!"):
                summary = text.split(" - ", 1)[-1] if " - " in text else text
                break
        out.append((name, summary[:110]))
    return out


def api_members(module_name, package="pyos"):
    """[(kind, name, signature, first line of the docstring)] for the public functions and classes of a module, read from its source (nothing is imported)."""
    path = os.path.join(os.getcwd(), package, module_name.replace(".", os.sep) + ".py")
    try:
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError):
        raise ValueError(f"there is no module {package}.{module_name}") from None
    out = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
            out.append(("def", node.name, "(" + ", ".join(a.arg for a in node.args.args) + ")", (ast.get_docstring(node) or "").splitlines()[0] if ast.get_docstring(node) else ""))
        elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            out.append(("class", node.name, "", (ast.get_docstring(node) or "").splitlines()[0] if ast.get_docstring(node) else ""))
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and node.targets[0].id.isupper():
            out.append(("value", node.targets[0].id, "", ""))
    return out
