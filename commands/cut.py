from pyos import textcmd

config = {"name": "cut", "description": "Keep parts of each line (cut -d, -f1,3 [file]  or  cut -c1-5 [file])."}


def ranges(spec):
    """'1,3-5,7-' -> a function telling whether a 1-based position is wanted. None when the spec is wrong."""
    parts = []
    for piece in spec.split(","):
        low, dash, high = piece.partition("-")
        try:
            lo = int(low) if low else 1
            hi = (int(high) if high else 10 ** 9) if dash else lo
        except ValueError:
            return None
        parts.append((lo, hi))
    return lambda n: any(lo <= n <= hi for lo, hi in parts)


def cut_line(line, delimiter=None, fields=None, chars=None):
    if chars is not None:
        return "".join(ch for i, ch in enumerate(line, 1) if chars(i))
    if delimiter not in line:
        return line
    return delimiter.join(part for i, part in enumerate(line.split(delimiter), 1) if fields(i))


def execute(args=None):
    options, files = textcmd.flags(args, with_value="dfc")
    delimiter = options.get("d") or "\t"
    if "f" in options:
        fields = ranges(str(options["f"]))
        chars = None
    elif "c" in options:
        fields, chars = None, ranges(str(options["c"]))
    else:
        fields = chars = None
    if (fields is None and chars is None) or len(delimiter) != 1:
        textcmd.console.print("[bold red]Usage:[/bold red] cut -d<delimiter> -f<fields> [file]   or   cut -c<characters> [file]   (for example cut -d, -f1,3 data.csv)")
        return False
    lines = textcmd.read_lines(files, "cut")
    if lines is None:
        return False
    for line in lines:
        textcmd.emit(cut_line(line, delimiter, fields, chars))
    return True
