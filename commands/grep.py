import os
import re

from rich.console import Console

import pyos.fs as fs
import pyos.stdio as stdio
from pyos import search

console = Console()
config = {"name": "grep", "description": "Search files or piped input: grep [-inrvwclF] [-A n] [-B n] [-C n] <pattern> [file|folder...]"}

USAGE = "[bold red]Usage:[/bold red] grep \\[-i -n -r -v -w -c -l -F] \\[-A n] \\[-B n] \\[-C n] <pattern> \\[file or folder...]"
MAX_LINES = 1000
MAX_FILE = 5 * 1024 * 1024


def parse(args):
    """-> (flags set, {A,B}, rest list, error)."""
    flags, context, rest, i = set(), {"A": 0, "B": 0}, [], 0
    args = list(args)
    while i < len(args):
        a = args[i]
        if a in ("-A", "-B", "-C"):
            if i + 1 >= len(args) or not args[i + 1].isdigit():
                return flags, context, rest, f"{a} needs a number"
            n = int(args[i + 1])
            for side in ("A", "B") if a == "-C" else (a[1],):
                context[side] = n
            i += 2
        elif a.startswith("-") and len(a) > 1 and a[1:].isalpha() and not rest:
            for ch in a[1:]:
                if ch not in "inrvwclF":
                    return flags, context, rest, f"unknown option -{ch}"
                flags.add(ch)
            i += 1
        else:
            rest.append(a)
            i += 1
    return flags, context, rest, None


def build_regex(pattern, flags):
    text = re.escape(pattern) if "F" in flags else pattern
    if "w" in flags:
        text = rf"\b(?:{text})\b"
    return re.compile(text, re.IGNORECASE if "i" in flags else 0)


def files_under(path, recursive):
    if os.path.isdir(path):
        if not recursive:
            return None
        return [full for full, _d, is_dir in search.walk(path, hidden=False, include_dirs=False)]
    return [path]


def scan(lines, regex, flags, context):
    """Yield (line number, text, is_match) for every match and its context lines, with None as a gap marker."""
    invert = "v" in flags
    hits = [n for n, line in enumerate(lines) if bool(regex.search(line)) != invert]
    if not hits:
        return
    keep, last = {}, -2
    for n in hits:
        for k in range(max(0, n - context["B"]), min(len(lines), n + context["A"] + 1)):
            keep.setdefault(k, k == n or k in hits)
    previous = None
    for k in sorted(keep):
        if previous is not None and k != previous + 1 and (context["A"] or context["B"]):
            yield None, None, False
        yield k + 1, lines[k], keep[k]
        previous = k


def execute(args=None):
    flags, context, rest, error = parse(args or [])
    piped = stdio.read_stdin()
    if error or not rest or (len(rest) < 2 and piped is None and "r" not in flags):
        if error:
            console.print(f"[bold red]grep: {error}[/bold red]")
        console.print(USAGE)
        return False
    try:
        regex = build_regex(rest[0], flags)
    except re.error as e:
        console.print(f"[bold red]grep: invalid pattern: {e}[/bold red]")
        return False

    sources = []                       # (label, lines)
    errors = False
    names = rest[1:] or (["."] if "r" in flags and piped is None else [])
    if not names:
        sources.append((None, piped.splitlines()))
    for name in names:
        try:
            path = fs.resolve(name)
            targets = files_under(path, "r" in flags)
            if targets is None:
                console.print(f"[bold red]grep: {name}: is a folder (use -r)[/bold red]")
                errors = True
                continue
            for target in targets:
                if os.path.getsize(target) > MAX_FILE:
                    continue
                with open(target, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
                if "\0" in text[:2000]:
                    continue                                    # a binary file
                sources.append((fs.display(target, tilde=True) if (len(names) > 1 or os.path.isdir(path)) else None, text.splitlines()))
        except Exception as e:
            console.print(f"[bold red]grep: {name}: {fs.errtext(e)}[/bold red]")
            errors = True

    matched, printed = False, 0
    for label, lines in sources:
        count = 0
        for number, text, is_match in scan(lines, regex, flags, context):
            if number is None:
                console.print("--", markup=False)
                continue
            if is_match:
                count += 1
                matched = True
            if "c" in flags or "l" in flags:
                continue
            sep = ":" if is_match else "-"
            prefix = (f"{label}{sep}" if label else "") + (f"{number}{sep}" if "n" in flags or label else "")
            console.print(f"{prefix}{text}", markup=False, highlight=False)
            printed += 1
            if printed >= MAX_LINES:
                console.print(f"... stopped after {MAX_LINES} lines (narrow the search)", markup=False)
                return True
        if "c" in flags:
            console.print(f"{label}:{count}" if label else str(count), markup=False)
        elif "l" in flags and count:
            console.print(label or "(standard input)", markup=False)
    return matched and not errors
