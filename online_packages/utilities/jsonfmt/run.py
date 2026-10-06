#!/usr/bin/env python3
"""JSON formatter: check that JSON is valid (with the line and column of the first mistake), pretty-print it, shrink it to one line, sort
its keys, look inside with a path like  users[0].name , and show its structure as a tree.
Usage: jsonfmt <file> [--minify] [--sort] [--path a.b[0]] [--tree] [--out file]  |  jsonfmt (interactive: paste JSON, end with a line containing a dot)."""
import json
import re
import sys

from rich.console import Console
from rich.markup import escape
from rich.syntax import Syntax
from rich.tree import Tree

try:
    from pyos import fs
except ImportError:
    fs = None

console = Console()


def parse(text):
    """Returns (value, None) or (None, message with the position of the first mistake and a hint). Text that is not JSON but is valid YAML
    is accepted too when PyYAML is installed (JSON is YAML, and so are most config files)."""
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        if not text.lstrip().startswith(("{", "[")):
            try:
                import yaml  # noqa: F401
                value = yaml.safe_load(text)
                if isinstance(value, (dict, list)):
                    return value, None
            except Exception:                              # noqa: BLE001 - not YAML either: report the JSON mistake
                pass
        lines = text.splitlines()
        context = lines[e.lineno - 1] if 0 < e.lineno <= len(lines) else ""
        hint = ""
        if "Expecting property name" in e.msg:
            hint = " (a trailing comma, or a key that is not in double quotes?)"
        elif "Expecting ',' delimiter" in e.msg:
            hint = " (a missing comma or bracket?)"
        elif "Expecting value" in e.msg:
            hint = " (a missing value, or single quotes instead of double quotes?)"
        elif "Invalid control character" in e.msg or "Extra data" in e.msg:
            hint = " (text after the end of the JSON, or a stray character?)"
        pointer = " " * max(0, e.colno - 1) + "^"
        return None, f"line {e.lineno}, column {e.colno}: {e.msg}{hint}\n{context}\n{pointer}"


def lookup(value, path):
    """Follow a path like users[0].name through parsed JSON. Raises KeyError/IndexError/ValueError with a readable message."""
    current = value
    for part in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        if part.startswith("["):
            index = int(part[1:-1])
            if not isinstance(current, list) or not -len(current) <= index < len(current):
                raise IndexError(f"no item {index} here")
            current = current[index]
        else:
            if not isinstance(current, dict) or part not in current:
                raise KeyError(f"no key '{part}' here")
            current = current[part]
    return current


def tree(value, label="$"):
    def describe(v):
        if isinstance(v, dict):
            return f"object ({len(v)} keys)"
        if isinstance(v, list):
            return f"array ({len(v)} items)"
        return f"{type(v).__name__}: {json.dumps(v, ensure_ascii=False)[:40]}"

    root = Tree(f"[bold]{escape(label)}[/bold] [dim]{describe(value)}[/dim]")

    def walk(node, v, depth=0):
        if depth > 6:
            node.add("[dim]...[/dim]")
            return
        items = v.items() if isinstance(v, dict) else enumerate(v[:20]) if isinstance(v, list) else []
        for key, child in items:
            branch = node.add(f"[cyan]{escape(str(key))}[/cyan] [dim]{escape(describe(child))}[/dim]")
            if isinstance(child, (dict, list)):
                walk(branch, child, depth + 1)
        if isinstance(v, list) and len(v) > 20:
            node.add(f"[dim]... {len(v) - 20} more[/dim]")

    walk(root, value)
    return root


def render(value, minify=False, sort=False, as_yaml=False):
    if as_yaml:
        import yaml
        return yaml.safe_dump(value, allow_unicode=True, sort_keys=sort, default_flow_style=False).rstrip("\n")
    if minify:
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False, sort_keys=sort)
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=sort)


def process(text, minify=False, sort=False, path=None, show_tree=False, out=None, as_yaml=False):
    value, error = parse(text)
    if error:
        console.print(f"[bold red]Not valid JSON:[/bold red] {escape(error)}", highlight=False)
        return False
    if path:
        try:
            value = lookup(value, path)
        except (KeyError, IndexError, ValueError) as e:
            console.print(f"[red]{escape(str(e))}[/red]")
            return False
    if show_tree:
        console.print(tree(value))
        return True
    if as_yaml:
        try:
            import yaml  # noqa: F401
        except ImportError:
            console.print("[red]--yaml needs the PyYAML library, which is not installed here.[/red]")
            return False
    text_out = render(value, minify, sort, as_yaml)
    if out:
        try:
            with open(fs.resolve(out, write=True) if fs else out, "w", encoding="utf-8") as f:
                f.write(text_out + "\n")
            console.print(f"[green]Saved {escape(out)}[/green]")
        except (OSError, PermissionError) as e:
            console.print(f"[red]{escape(fs.errtext(e) if fs else str(e))}[/red]")
            return False
        return True
    console.print(Syntax(text_out, "yaml" if as_yaml else "json", word_wrap=True))
    console.print(f"[green]Valid[/green] [dim]({len(text_out)} characters)[/dim]")
    return True


def main(args):
    flags = {"--minify": False, "--sort": False, "--tree": False, "--yaml": False}
    path = out = None
    rest = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in flags:
            flags[a] = True
        elif a in ("--path", "--out") and i + 1 < len(args):
            if a == "--path":
                path = args[i + 1]
            else:
                out = args[i + 1]
            i += 1
        else:
            rest.append(a)
        i += 1
    if rest:
        try:
            with open(fs.resolve(rest[0]) if fs else rest[0], encoding="utf-8") as f:
                text = f.read()
        except (OSError, PermissionError) as e:
            console.print(f"[red]{escape(rest[0])}: {escape(fs.errtext(e) if fs else str(e))}[/red]")
            return
        process(text, flags["--minify"], flags["--sort"], path, flags["--tree"], out, flags["--yaml"])
        return
    console.print("[dim]Paste JSON, then a line with just a dot (.) to finish; blank to quit.[/dim]")
    while True:
        lines = []
        while True:
            try:
                line = input()
            except EOFError:
                return
            if line.strip() == ".":
                break
            lines.append(line)
        if not "".join(lines).strip():
            return
        process("\n".join(lines), flags["--minify"], flags["--sort"], path, flags["--tree"], out, flags["--yaml"])


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
