from pyos import textcmd

config = {"name": "tac", "description": "Show the lines last to first (tac [file])."}


def execute(args=None):
    lines = textcmd.read_lines(args, "tac")
    if lines is None:
        return False
    for line in reversed(lines):
        textcmd.emit(line)
    return True
