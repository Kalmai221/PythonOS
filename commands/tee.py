import pyos.fs as fs
import pyos.stdio as stdio
from pyos import textcmd

config = {"name": "tee", "description": "Show piped text and also save it to a file (tee [-a] <file>)."}


def execute(args=None):
    options, files = textcmd.flags(args)
    text = stdio.read_stdin()
    if not files or text is None:
        textcmd.console.print("[bold red]Usage:[/bold red] ... | tee [-a] <file>")
        return False
    try:
        with open(fs.resolve(files[0], write=True), "a" if "a" in options else "w", encoding="utf-8") as f:
            f.write(text)
    except Exception as e:                                             # noqa: BLE001
        textcmd.console.print(f"[bold red]tee: {files[0]}: {fs.errtext(e)}[/bold red]")
        return False
    textcmd.console.print(text, markup=False, highlight=False, end="")
    return True
