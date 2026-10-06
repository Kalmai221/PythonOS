from pyos import textcmd

config = {"name": "seq", "description": "Print a run of numbers (seq [first [step]] last), for example seq 5 or seq 2 2 10."}


def numbers(args):
    """The list for `seq` arguments, or None when they are wrong."""
    try:
        values = [int(a) for a in args]
    except ValueError:
        return None
    if len(values) == 1:
        first, step, last = 1, 1, values[0]
    elif len(values) == 2:
        first, step, last = values[0], 1, values[1]
    elif len(values) == 3:
        first, step, last = values
    else:
        return None
    if step == 0 or abs(last - first) // abs(step) > 100000:
        return None
    if (step > 0 and first > last) or (step < 0 and first < last):
        return []
    return list(range(first, last + (1 if step > 0 else -1), step))


def execute(args=None):
    found = numbers(list(args or []))
    if found is None:
        textcmd.console.print("[bold red]Usage:[/bold red] seq [first [step]] last   (whole numbers; at most 100000 of them)")
        return False
    for n in found:
        textcmd.emit(str(n))
    return True
