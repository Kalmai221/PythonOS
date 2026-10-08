# pyos/richinput.py - make Rich's prompts work with readline
#
# Rich's console.input() (which Prompt.ask, Confirm.ask and IntPrompt.ask use) prints the prompt itself and then calls input() with nothing.
# Where the readline module is in use (Linux, the live ISO and virtual machines, macOS) readline therefore believes the line starts at the left
# edge of the screen. Every time it redraws the line - backspace in the middle of what you typed, a line long enough to wrap, Ctrl+U, the
# history keys - it returns to the left edge and rewrites only what you typed, so it writes over the prompt that Rich printed: "Install? [y/n]"
# is eaten by the backspace key.
#
# The fix is the one readline documents: give the prompt to input() itself, with every colour code wrapped in \001 ... \002 so that readline
# knows those characters take no room on the screen. patch() does that for console.input(). Anywhere readline is not in use (Windows, Android,
# a pipe, a password) Rich's own behaviour is kept.
import builtins
import re
import sys

_CODES = re.compile(r"(\x1b\[[0-9;?]*[A-Za-z])")


def readline_in_use():
    """True when input() will be handled by readline: the module is loaded (and is a real one) and stdin is a terminal."""
    module = sys.modules.get("readline")
    try:
        return module is not None and hasattr(module, "get_line_buffer") and module.__name__ == "readline" and sys.stdin.isatty()
    except Exception:                                      # noqa: BLE001
        return False


def wrap_codes(text):
    """The colour codes of `text` marked as taking no room (\\001 ... \\002), as readline wants them in a prompt."""
    return _CODES.sub("\001\\1\002", text)


def patch():
    """Replace Console.input with a readline-aware one (once)."""
    from rich.console import Console
    if getattr(Console, "_pyos_input", None):
        return
    original = Console.input

    def readline_input(self, prompt="", *, markup=True, emoji=True, password=False, stream=None):
        if stream is not None or password or not readline_in_use():
            return original(self, prompt, markup=markup, emoji=emoji, password=password, stream=stream)
        text = ""
        if prompt:
            with self.capture() as capture:
                self.print(prompt, markup=markup, emoji=emoji, end="")
            text = capture.get()
        head, _newline, last = text.rpartition("\n")
        if head:                                           # only the last line of a prompt belongs to readline; the lines above are plain output
            self.file.write(head + "\n")
            self.file.flush()
        return builtins.input(wrap_codes(last))

    readline_input._pyos_original = original
    Console.input = readline_input
    Console._pyos_input = True


def unpatch():
    """Put Rich's own input back (the tests)."""
    from rich.console import Console
    current = Console.input
    original = getattr(current, "_pyos_original", None)
    if original is not None:
        Console.input = original
        Console._pyos_input = False
