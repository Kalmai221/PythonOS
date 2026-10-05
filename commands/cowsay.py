import textwrap

from rich.console import Console

from pyos import stdio

console = Console()
config = {"name": "cowsay", "description": "A cow says what you tell it (cowsay <text>, or pipe text in: fortune | cowsay)."}

COW = r"""
        \   ^__^
         \  (oo)\_______
            (__)\       )\/\
                ||----w |
                ||     ||"""


def bubble(text, width=40):
    lines = []
    for paragraph in text.strip().splitlines() or [""]:
        lines.extend(textwrap.wrap(paragraph, width) or [""])
    w = max(len(l) for l in lines)
    if len(lines) == 1:
        body = [f"< {lines[0].ljust(w)} >"]
    else:
        body = []
        for i, l in enumerate(lines):
            left, right = ("/", "\\") if i == 0 else ("\\", "/") if i == len(lines) - 1 else ("|", "|")
            body.append(f"{left} {l.ljust(w)} {right}")
    return "\n".join([" " + "_" * (w + 2), *body, " " + "-" * (w + 2)])


def execute(args=None):
    text = " ".join(args) if args else (stdio.read_stdin() or "")
    if not text.strip():
        console.print("[bold red]Usage:[/bold red] cowsay <text>   or   fortune | cowsay")
        return False
    console.print(bubble(text) + "\n" + COW.strip("\n").replace("\n", "\n"), markup=False, highlight=False)
    return True
