#!/usr/bin/env python3
"""Rich's prompts and readline: console.input() must hand the prompt to input() with its colour codes wrapped in \\001 ... \\002, so that readline
knows where the line starts and backspace, wrapping and the history keys do not write over the prompt. Without readline (Windows, Android, a
pipe) Rich's own behaviour is kept. readline and the keyboard are faked."""
import builtins
import io
import os
import re
import sys
import types

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO_ROOT)
os.chdir(REPO_ROOT)

from rich.console import Console  # noqa: E402
from rich.prompt import Confirm, IntPrompt, Prompt  # noqa: E402

import pyos  # noqa: E402,F401  (importing it installs the fix)
from pyos import richinput  # noqa: E402

CSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


class Terminal(io.StringIO):
    def isatty(self):
        return True


def main():
    assert Console._pyos_input is True, "importing pyos installs the fix"
    real_input, real_stdin = builtins.input, sys.stdin
    real_readline = sys.modules.get("readline")
    prompts = []
    answers = []

    def fake_input(prompt=""):
        prompts.append(prompt)
        return answers.pop(0)

    builtins.input = fake_input
    sys.stdin = Terminal()
    try:
        screen = Terminal()
        console = Console(file=screen, force_terminal=True, color_system="standard", width=80)

        # readline is in use: the prompt goes to input(), every colour code is marked as taking no room, and Rich prints nothing itself
        fake_readline = types.ModuleType("readline")
        fake_readline.get_line_buffer = lambda: ""
        sys.modules["readline"] = fake_readline
        assert richinput.readline_in_use()
        answers[:] = ["bob"]
        assert Prompt.ask("[bold]Name?[/bold]", console=console, default="x") == "bob"
        prompt = prompts[-1]
        assert screen.getvalue() == "", "Rich must not print the prompt itself: readline would write over it"
        assert CSI.sub("", prompt.replace("\x01", "").replace("\x02", "")).startswith("Name?"), repr(prompt)
        assert "\x01\x1b[1m\x02Name?\x01\x1b[0m\x02" in prompt, repr(prompt)
        # every colour code is wrapped, and nothing else is: what readline counts as visible is exactly what the screen shows
        assert not CSI.sub("", re.sub(r"\x01\x1b\[[0-9;?]*[A-Za-z]\x02", "", prompt)).count("\x1b")
        visible = re.sub(r"\x01[^\x02]*\x02", "", prompt)
        assert "\x1b" not in visible and visible == "Name? (x): ", repr(visible)

        # the other prompts of Rich take the same road
        answers[:] = ["y"]
        assert Confirm.ask("Install?", console=console) is True
        assert re.sub(r"\x01[^\x02]*\x02", "", prompts[-1]) == "Install? [y/n]: ", repr(prompts[-1])
        answers[:] = ["7"]
        assert IntPrompt.ask("How many?", console=console) == 7 and screen.getvalue() == ""

        # a prompt of several lines: the lines above are printed, only the last one is readline's prompt
        answers[:] = ["ok"]
        console.input("first line\nsecond line: ")
        assert screen.getvalue().startswith("first line\n") and "second line" not in screen.getvalue()
        assert re.sub(r"\x01[^\x02]*\x02", "", prompts[-1]) == "second line: "

        # no colour (a console that is not a terminal): the plain prompt, still handed to input()
        plain_screen = io.StringIO()
        plain = Console(file=plain_screen, force_terminal=False, color_system=None)
        answers[:] = ["v"]
        plain.input("Plain: ")
        assert prompts[-1] == "Plain: " and plain_screen.getvalue() == ""

        # a password and a given stream keep Rich's own way (getpass is not readline's business)
        import getpass
        real_getpass, count = getpass.getpass, len(prompts)
        getpass.getpass = lambda prompt="", stream=None: "secret"
        try:
            assert console.input("Password: ", password=True) == "secret"
        finally:
            getpass.getpass = real_getpass
        assert console.input("From a file: ", stream=io.StringIO("typed" + chr(10))).strip() == "typed"
        assert len(prompts) == count, "neither went through input()"

        # without readline (Windows, Android, a minimal Linux): Rich prints the prompt and input() gets nothing, as before
        del sys.modules["readline"]
        screen.truncate(0)
        screen.seek(0)
        assert not richinput.readline_in_use()
        answers[:] = ["z"]
        assert Prompt.ask("Plain old?", console=console) == "z"
        assert prompts[-1] == "" and "Plain old?" in screen.getvalue()
        # a stand-in readline (the stub some builds use) is not real readline either
        stub = types.ModuleType("pyos.readline_stub")
        stub.__name__ = "pyos.readline_stub"
        stub.get_line_buffer = lambda: ""
        sys.modules["readline"] = stub
        assert not richinput.readline_in_use()
        del sys.modules["readline"]
        # a pipe: not a terminal, so Rich's way
        sys.modules["readline"] = fake_readline
        sys.stdin = io.StringIO()
        assert not richinput.readline_in_use()
        sys.stdin = Terminal()

        # patching twice changes nothing, and unpatch gives Rich's own input back
        before = Console.input
        richinput.patch()
        assert Console.input is before
        richinput.unpatch()
        assert not hasattr(Console.input, "_pyos_original") and Console._pyos_input is False
        richinput.patch()
        assert Console._pyos_input is True and hasattr(Console.input, "_pyos_original")
    finally:
        builtins.input, sys.stdin = real_input, real_stdin
        if real_readline is not None:
            sys.modules["readline"] = real_readline
        else:
            sys.modules.pop("readline", None)
    assert richinput.wrap_codes("\x1b[1mhi\x1b[0m") == "\x01\x1b[1m\x02hi\x01\x1b[0m\x02"
    print("rich prompts and readline: all checks passed")


if __name__ == "__main__":
    main()
