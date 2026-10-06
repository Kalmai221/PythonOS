#!/usr/bin/env python3
"""Checks the main prompt: history recall, the shared history file, command colouring, and a real prompt_toolkit session driven by piped keys."""
import os
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def main():
    work = tempfile.mkdtemp(prefix="pyos-prompt-")
    os.chdir(work)
    sys.path.insert(0, REPO)
    os.environ["PYOS_BUNDLED"] = "1"
    from pyos import prompt

    # recall
    items = ["ls", "cd docs", "cat a.txt"]
    assert prompt.expand_bang("!!", items + ["!!"]) == "cat a.txt" and prompt.expand_bang("!2", items) == "cd docs"
    assert prompt.expand_bang("!-2", items) == "cd docs" and prompt.expand_bang("!c", items) == "cat a.txt" and prompt.expand_bang("!cd", items) == "cd docs"
    assert prompt.expand_bang("!nothing", items) is None and prompt.expand_bang("!9", items) is None and prompt.expand_bang("hello", items) is None
    assert prompt.expand_bang("! x", items) is None and prompt.expand_bang("!", items) is None
    assert prompt.search_history(items, "CD") == [(2, "cd docs")]

    # the history file: one command per line, no duplicates in a row
    prompt.append_history("ls")
    prompt.append_history("ls")
    prompt.append_history("echo hi")
    prompt.append_history("")
    assert prompt.read_history() == ["ls", "echo hi"]

    # colouring
    known = lambda w: w in ("ls", "grep")                                          # noqa: E731
    spans = prompt.command_spans("ls | grep x && zz", known, lambda w: "echo".startswith(w))
    assert spans[0] == ("ansigreen", "ls") and ("ansigreen", "grep") in spans and ("ansired", "zz") in spans
    assert prompt.command_spans("ec", known, lambda w: "echo".startswith(w))[0] == ("", "ec")
    assert prompt.command_spans("NAME=1", known, lambda w: False)[0][0] == "ansigreen"

    # cat colours known file types on a terminal and prints everything else exactly as it is
    import importlib.util
    from rich.console import Console
    spec = importlib.util.spec_from_file_location("cat_cmd", os.path.join(REPO, "commands", "cat.py"))
    cat = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cat)
    assert cat.lexer_for("a.py", "x=1") == "python" and cat.lexer_for("notes.txt", "x") is None and cat.lexer_for("big.py", "x" * (cat.COLOUR_LIMIT + 1)) is None
    cat.console = Console(force_terminal=True, color_system="standard", width=80)
    with cat.console.capture() as shown:
        cat.show("a.py", "def f():\n    return 1\n")
    assert "\x1b[" in shown.get() and "def" in shown.get(), "a Python file must be coloured on a terminal"
    with cat.console.capture() as shown:
        cat.show("notes.txt", "plain [bold] text\n")
    assert shown.get() == "plain [bold] text\n", "an unknown type must print exactly as it is"

    # a real session, fed keys through a pipe (no terminal needed)
    try:
        from prompt_toolkit.input import create_pipe_input
        from prompt_toolkit.output import DummyOutput
    except ImportError:
        print("prompt: prompt_toolkit is not installed; session checks skipped")
        return 0
    complete = lambda line: [n for n in ("echo", "env", "exit") if n.startswith(line.split(" ")[-1])]       # noqa: E731
    with create_pipe_input() as pipe:
        session = prompt._build_session(complete, known, lambda w: False, input=pipe, output=DummyOutput())
        pipe.send_text("ls -l\r")
        assert session.prompt("$ ") == "ls -l"
        assert "ls -l" in prompt.read_history(), "an accepted line must reach the history file"
        pipe.send_text("\x04")                                                      # Ctrl+D on an empty line
        try:
            session.prompt("$ ")
            raise AssertionError("Ctrl+D must raise EOFError")
        except EOFError:
            pass
        pipe.send_text("\x03")                                                      # Ctrl+C
        try:
            session.prompt("$ ")
            raise AssertionError("Ctrl+C must raise KeyboardInterrupt")
        except KeyboardInterrupt:
            pass
    # not on a terminal (this test), the prompt is the plain input()
    assert not prompt.enabled()
    print("prompt: all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
