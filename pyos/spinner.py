# pyos/spinner.py - spinners that work on every screen
#
# Rich's and yaspin's default spinner ("dots") is made of Braille characters. The Linux text console (the live ISO and virtual machines, TERM=linux)
# and a serial console have a small built-in font with no Braille, so each frame shows as an empty box or nothing at all, and the spinner looks
# frozen. There the spinner is the plain "-\|/" one. Everywhere else (a terminal window, Windows Terminal, an SSH session, Android) the dots stay.
#
# ascii_only() decides; the environment variable PYTHONOS_SPINNER=ascii (or unicode) overrides it. patch() makes every console.status(...) in the
# system use the right one without changing its callers, and kind() / yaspin_spinner() are for code that uses yaspin.
import os
import sys

# terminals whose font cannot be trusted with Braille: the Linux console, serial terminals, and the plain ones
ASCII_TERMS = {"linux", "vt100", "vt102", "vt220", "ansi", "cons25", "dumb"}


def ascii_only(env=None, stream=None):
    """True when the spinner must use plain characters."""
    env = os.environ if env is None else env
    choice = env.get("PYTHONOS_SPINNER", "").strip().lower()
    if choice in ("ascii", "plain", "line"):
        return True
    if choice in ("unicode", "dots"):
        return False
    if env.get("TERM", "").strip().lower() in ASCII_TERMS:
        return True
    encoding = (getattr(stream if stream is not None else sys.stdout, "encoding", None) or "").lower()
    return bool(encoding) and "utf" not in encoding            # a terminal that cannot print Braille at all (a legacy code page)


def kind():
    """The name of the spinner for Rich and yaspin: 'line' (plain) or 'dots'."""
    return "line" if ascii_only() else "dots"


def yaspin_spinner():
    """The yaspin spinner object for this screen."""
    from yaspin.spinners import Spinners
    return Spinners.line if ascii_only() else Spinners.dots


def patch():
    """Make Console.status use the plain spinner where Braille cannot be shown (once). A caller that names a spinner of its own keeps it."""
    from rich.console import Console
    if getattr(Console, "_pyos_spinner", None):
        return
    original = Console.status

    def status(self, status, *, spinner="dots", **kwargs):
        if spinner == "dots" and ascii_only():
            spinner = "line"
        return original(self, status, spinner=spinner, **kwargs)

    status._pyos_original = original
    Console.status = status
    Console._pyos_spinner = True


def unpatch():
    """Put Rich's own status back (the tests)."""
    from rich.console import Console
    original = getattr(Console.status, "_pyos_original", None)
    if original is not None:
        Console.status = original
        Console._pyos_spinner = False
