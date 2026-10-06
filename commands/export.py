from rich.console import Console

from pyos import shellvars

console = Console()
config = {"name": "export", "description": "Set a variable and list it in env (export NAME=value); use it later as $NAME. export alone lists them."}


def execute(args=None):
    args = list(args or [])
    if not args:
        for name, value in shellvars.exported().items():
            console.print(f"export {name}={value}", markup=False, highlight=False)
        return True
    ok = True
    for item in args:
        name, sep, value = item.partition("=")
        try:
            shellvars.set_variable(name, value if sep else shellvars.get(name), export=True)
        except ValueError as e:
            console.print(f"[bold red]export: {e}[/bold red]")
            ok = False
    return ok
