# pyos/textcmd.py - shared helpers for the small text commands (sort, uniq, cut, tr, tee, nl, rev, tac, less ...)
#
# Each of them reads the files named on the command line, or the text piped into it, and prints lines.
from rich.console import Console

import pyos.fs as fs
import pyos.stdio as stdio
from pyos import textfile

console = Console()


def read_text(files, name):
    """The text of the first file in `files`, else the piped text. None (after printing why) when there is neither or a file cannot be read."""
    if files:
        try:
            return textfile.read(files[0])[0]
        except Exception as e:                                         # noqa: BLE001 - say it the way every command does
            console.print(f"[bold red]{name}: {files[0]}: {fs.errtext(e)}[/bold red]")
            return None
    piped = stdio.read_stdin()
    if piped is None:
        console.print(f"[bold red]{name}:[/bold red] give a file name or pipe text into it (for example: cat notes.txt | {name})")
    return piped


def read_lines(files, name):
    text = read_text(files, name)
    return None if text is None else text.splitlines()


def emit(line):
    console.print(line, markup=False, highlight=False)


def flags(args, with_value=()):
    """Split an argument list into ({flag: value or True}, [other arguments]). Single-letter flags can be joined (-rn); the letters in
    `with_value` take the next argument (-n 5, -d,)."""
    options, rest = {}, []
    args = list(args or [])
    i = 0
    while i < len(args):
        word = args[i]
        if word.startswith("-") and len(word) > 1 and not word[1:].isdigit():
            letters = word[1:]
            for position, letter in enumerate(letters):
                if letter in with_value:
                    attached = letters[position + 1:]
                    if attached:
                        options[letter] = attached
                    elif i + 1 < len(args):
                        i += 1
                        options[letter] = args[i]
                    else:
                        options[letter] = ""
                    break
                options[letter] = True
        else:
            rest.append(word)
        i += 1
    return options, rest
