from pyos import textcmd

config = {"name": "rev", "description": "Reverse every line (rev [file])."}


def execute(args=None):
    lines = textcmd.read_lines(args, "rev")
    if lines is None:
        return False
    for line in lines:
        textcmd.emit(line[::-1])
    return True
