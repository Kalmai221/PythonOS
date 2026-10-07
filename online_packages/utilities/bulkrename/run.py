#!/usr/bin/env python3
"""Bulkrename: rename many files at once, after showing exactly what will change.

    bulkrename ~/Photos replace IMG_ holiday_        change a piece of every name that has it
    bulkrename ~/Photos number "photo_{n:03}"        photo_001.jpg, photo_002.jpg ... in name order (the extension stays)
    bulkrename ~/Photos lower                        lower case (also: upper, spaces -> underscores with "snake")
    bulkrename ~/Photos regex "^(\\d+)-(.*)$" "\\2-\\1"   regular expressions (groups as \\1 \\2)

Nothing is renamed until you add --apply. Files that would end up with the same name are refused.
"""
import os
import re
import sys

from rich.console import Console
from rich.markup import escape

console = Console()


def plan(names, mode, args):
    """[(old, new)] for the names that change. Raises ValueError for a bad pattern. Does not touch any file."""
    pairs = []
    if mode == "replace":
        if len(args) != 2 or not args[0]:
            raise ValueError("replace needs the text to find and the text to put there")
        for name in names:
            new = name.replace(args[0], args[1])
            pairs.append((name, new))
    elif mode == "number":
        if len(args) != 1:
            raise ValueError('number needs a pattern such as "photo_{n:03}"')
        for n, name in enumerate(sorted(names), 1):
            try:
                new = args[0].format(n=n) + os.path.splitext(name)[1]
            except (KeyError, IndexError, ValueError) as e:
                raise ValueError(f"the pattern is not valid ({e})") from None
            pairs.append((name, new))
    elif mode in ("lower", "upper", "snake"):
        for name in names:
            stem, ext = os.path.splitext(name)
            new = {"lower": stem.lower(), "upper": stem.upper(), "snake": re.sub(r"\s+", "_", stem.strip())}[mode] + ext
            pairs.append((name, new))
    elif mode == "regex":
        if len(args) != 2:
            raise ValueError("regex needs a pattern and a replacement")
        try:
            pattern = re.compile(args[0])
            pairs = [(name, pattern.sub(args[1], name)) for name in names]
        except re.error as e:
            raise ValueError(f"the pattern is not valid ({e})") from None
    else:
        raise ValueError(f"unknown mode '{mode}'")
    return [(a, b) for a, b in pairs if a != b]


def conflicts(pairs, existing):
    """Problems that would make the renaming unsafe: two files ending up with one name, a name already taken, an empty or path-like name."""
    problems, targets = [], {}
    staying = set(existing) - {a for a, _ in pairs}
    for old, new in pairs:
        if not new.strip() or "/" in new or "\\" in new or new in (".", ".."):
            problems.append(f"{old} -> '{new}' is not a usable name")
        if new in targets:
            problems.append(f"{old} and {targets[new]} would both become {new}")
        targets[new] = old
        if new in staying:
            problems.append(f"{old} -> {new}: a file with that name already exists")
    return problems


def apply(folder, pairs):
    """Rename through temporary names, so swaps and chains (a -> b, b -> c) cannot overwrite anything."""
    temp = []
    for i, (old, new) in enumerate(pairs):
        middle = f".bulkrename-{os.getpid()}-{i}"
        os.rename(os.path.join(folder, old), os.path.join(folder, middle))
        temp.append((middle, new))
    for middle, new in temp:
        os.rename(os.path.join(folder, middle), os.path.join(folder, new))


def main(argv):
    do_apply = "--apply" in argv
    args = [a for a in argv if a != "--apply"]
    if len(args) < 2 or not os.path.isdir(args[0]):
        console.print(__doc__)
        return 1
    folder, mode, rest = args[0], args[1].lower(), args[2:]
    names = sorted(n for n in os.listdir(folder) if os.path.isfile(os.path.join(folder, n)) and not n.startswith("."))
    try:
        pairs = plan(names, mode, rest)
    except ValueError as e:
        console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    if not pairs:
        console.print("Nothing would change.")
        return 0
    for old, new in pairs:
        console.print(f"  {escape(old)}  [bold]->[/bold]  [green]{escape(new)}[/green]")
    problems = conflicts(pairs, names)
    if problems:
        console.print("[bold red]Not safe, so nothing was renamed:[/bold red]")
        for p in problems:
            console.print("  " + escape(p))
        return 1
    if not do_apply:
        console.print(f"[dim]{len(pairs)} files would be renamed. Add --apply to do it.[/dim]")
        return 0
    apply(folder, pairs)
    console.print(f"[green]Renamed {len(pairs)} files.[/green]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
