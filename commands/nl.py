from pyos import textcmd

config = {"name": "nl", "description": "Number the lines (nl [file])."}


def execute(args=None):
    lines = textcmd.read_lines(args, "nl")
    if lines is None:
        return False
    for number, line in enumerate(lines, 1):
        textcmd.emit(f"{number:>6}  {line}")
    return True
