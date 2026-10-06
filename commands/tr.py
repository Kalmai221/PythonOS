import pyos.stdio as stdio
from pyos import textcmd

config = {"name": "tr", "description": "Change or delete characters in piped text (tr [-d] set1 [set2]); ranges like a-z work."}


def expand(spec):
    out, i = [], 0
    while i < len(spec):
        if i + 2 < len(spec) and spec[i + 1] == "-" and ord(spec[i]) <= ord(spec[i + 2]):
            out.extend(chr(c) for c in range(ord(spec[i]), ord(spec[i + 2]) + 1))
            i += 3
        else:
            out.append(spec[i])
            i += 1
    return out


def translate(text, first, second=None, delete=False):
    source = expand(first)
    if delete:
        return "".join(ch for ch in text if ch not in source)
    target = expand(second)
    if not target:
        return text
    target += [target[-1]] * (len(source) - len(target))
    table = {ord(s): t for s, t in zip(source, target)}
    return text.translate(table)


def execute(args=None):
    options, rest = textcmd.flags(args)
    delete = "d" in options
    if not rest or (not delete and len(rest) < 2):
        textcmd.console.print("[bold red]Usage:[/bold red] tr set1 set2   or   tr -d set   (text comes from a pipe: cat a.txt | tr a-z A-Z)")
        return False
    text = stdio.read_stdin()
    if text is None:
        textcmd.console.print("[bold red]tr:[/bold red] pipe text into it, for example: cat a.txt | tr a-z A-Z")
        return False
    result = translate(text, rest[0], rest[1] if len(rest) > 1 else None, delete)
    textcmd.console.print(result, markup=False, highlight=False, end="")
    return True
