from pyos import textcmd

config = {"name": "uniq", "description": "Collapse repeated neighbouring lines (uniq [-c] [-d] [-u] [file]); sort first to find all repeats."}


def collapse(lines):
    """[(line, how many times in a row)]."""
    groups = []
    for line in lines:
        if groups and groups[-1][0] == line:
            groups[-1][1] += 1
        else:
            groups.append([line, 1])
    return [(line, n) for line, n in groups]


def execute(args=None):
    options, files = textcmd.flags(args)
    lines = textcmd.read_lines(files, "uniq")
    if lines is None:
        return False
    for line, count in collapse(lines):
        if "d" in options and count < 2 or "u" in options and count > 1:
            continue
        textcmd.emit(f"{count:>6} {line}" if "c" in options else line)
    return True
