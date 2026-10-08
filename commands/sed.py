from rich.console import Console

from pyos import sedlite, textcmd

console = Console()
config = {"name": "sed", "description": "Edit a stream of lines (sed [-n] [-e script] script [file]): s/old/new/g, d, p, q, with line or /regex/ addresses."}


def execute(args=None):
    args = list(args or [])
    scripts, rest, quiet, i = [], [], False, 0
    while i < len(args):
        word = args[i]
        if word == "-n":
            quiet = True
        elif word in ("-e", "--expression"):
            if i + 1 >= len(args):
                console.print("[bold red]sed: -e needs a script[/bold red]")
                return False
            i += 1
            scripts.append(args[i])
        elif word in ("-i", "-E", "-r") or word.startswith("-i"):
            if word.startswith("-i"):
                console.print("[bold red]sed: -i (editing a file in place) is not supported; use  sed ... file > new-file[/bold red]")
                return False
        else:
            rest.append(word)
        i += 1
    if not scripts:
        if not rest:
            console.print("[bold red]Usage:[/bold red] sed [-n] [-e script] script [file]    for example  sed 's/old/new/g' notes.txt")
            return False
        scripts.append(rest.pop(0))
    try:
        commands = sedlite.parse(";".join(scripts))
        lines = textcmd.read_lines(rest, "sed")
        if lines is None:
            return False
        output = sedlite.run(commands, lines, quiet)
    except sedlite.SedError as e:
        console.print(f"[bold red]sed: {e}[/bold red]")
        return False
    for line in output:
        textcmd.emit(line)
    return True
