from pyos import textcmd

config = {"name": "sort", "description": "Sort lines (sort [-r] [-n] [-u] [-f] [file])."}


def key_number(line):
    word = line.strip().split(None, 1)[0] if line.strip() else ""
    try:
        return (0, float(word))
    except ValueError:
        return (1, 0.0)


def sort_lines(lines, reverse=False, numeric=False, unique=False, fold=False):
    key = key_number if numeric else ((lambda s: s.lower()) if fold else None)
    result = sorted(lines, key=key, reverse=reverse)
    if unique:
        seen, kept = set(), []
        for line in result:
            marker = line.lower() if fold else line
            if marker not in seen:
                seen.add(marker)
                kept.append(line)
        result = kept
    return result


def execute(args=None):
    options, files = textcmd.flags(args)
    lines = textcmd.read_lines(files, "sort")
    if lines is None:
        return False
    for line in sort_lines(lines, "r" in options, "n" in options, "u" in options, "f" in options):
        textcmd.emit(line)
    return True
