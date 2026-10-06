import shlex

import pyos.stdio as stdio
from pyos import textcmd

config = {"name": "xargs", "description": "Run a command with piped words as its arguments (xargs [-n N] <command> [arguments])."}


def batches(words, size):
    return [words[i:i + size] for i in range(0, len(words), size)] if size else [words]


def execute(args=None):
    import shell
    options, rest = textcmd.flags(args, with_value="n")
    text = stdio.read_stdin()
    if not rest or text is None:
        textcmd.console.print("[bold red]Usage:[/bold red] ... | xargs [-n N] <command> [arguments]   (for example: find .txt | xargs wc)")
        return False
    try:
        size = int(options.get("n") or 0)
    except ValueError:
        size = 0
    ok = True
    for group in batches(text.split(), size):
        if shell.run_line(shlex.join(rest + group)) not in (0, None):
            ok = False
    return ok
