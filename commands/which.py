from pyos import textcmd

config = {"name": "which", "description": "Say whether a name is a command or an app, and what it is (which <name>)."}


def execute(args=None):
    import shell
    if not args:
        textcmd.console.print("[bold red]Usage:[/bold red] which <name>")
        return False
    found = True
    for name in args:
        if name in shell.BUILTINS:
            textcmd.emit(f"{name}: built into the shell")
            continue
        command = shell.find_entry(shell.available_commands, name)
        program = shell.find_entry(shell.available_programs, name)
        if command:
            textcmd.emit(f"{name}: command {command}" + (f" (also called {', '.join(shell.available_commands[command]['aliases'])})" if shell.available_commands[command]["aliases"] else ""))
        elif program:
            textcmd.emit(f"{name}: app {program} (start it with: run {program})")
        else:
            textcmd.emit(f"{name}: not found")
            found = False
    return found
