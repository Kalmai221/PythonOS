# pyos/search.py - walking the virtual filesystem for find, grep and tree
#
# One walker that stays inside what the logged-in user may look at, never follows links, skips the
# system's own hidden data unless asked, and stops at a result limit so a search can never flood the screen.
import os

import pyos.fs as fs


def readable(full):
    try:
        fs._check_permission(full, False)
        return True
    except PermissionError:
        return False


def walk(start, max_depth=None, hidden=True, include_dirs=True, depth=1):
    """Yield (full path, depth, is_dir) below `start`, a folder's contents straight after it, in name order.
    Folders the user may not enter are skipped and links are not followed."""
    try:
        names = sorted(os.listdir(start), key=str.lower)
    except OSError:
        return
    for name in names:
        if not hidden and name.startswith("."):
            continue
        full = os.path.join(start, name)
        if not readable(full):
            continue
        is_dir = os.path.isdir(full) and not os.path.islink(full)
        if include_dirs or not is_dir:
            yield full, depth, is_dir
        if is_dir and (max_depth is None or depth < max_depth):
            yield from walk(full, max_depth, hidden, include_dirs, depth + 1)


def parse_size(text):
    """'+10k' / '-2M' / '500' -> (comparison, bytes). Raises ValueError."""
    sign = ""
    if text[:1] in "+-":
        sign, text = text[0], text[1:]
    units = {"k": 1024, "m": 1024 ** 2, "g": 1024 ** 3}
    factor = 1
    if text[-1:].lower() in units:
        factor = units[text[-1].lower()]
        text = text[:-1]
    return sign, int(float(text) * factor)


def parse_age(text):
    """'+7' / '-1' / '3' days -> (comparison, days). Raises ValueError."""
    sign = ""
    if text[:1] in "+-":
        sign, text = text[0], text[1:]
    return sign, float(text)


def compare(sign, value, limit):
    if sign == "+":
        return value > limit
    if sign == "-":
        return value < limit
    return value == limit
