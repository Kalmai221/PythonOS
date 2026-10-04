# pyos/stdio.py - lets commands read piped input ("ls | grep txt")
stdin = None  # text piped into the running command, or None


def read_stdin():
    """Return piped text, or None when the command is not receiving a pipe."""
    return stdin
