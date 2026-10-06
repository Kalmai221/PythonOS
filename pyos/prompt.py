# pyos/prompt.py - the main prompt. With prompt_toolkit (already a dependency) the prompt gets history search (Ctrl+R), greyed-out
# suggestions from your history, a completion menu on Tab and coloured commands. Where that is not possible (no real terminal, the
# library missing, the setting fancy_prompt off, or PYOS_PLAIN_PROMPT=1) it is the plain input() with readline, as before.
#
# History is one plain text file (a command per line, .OSData/history), shared by both prompts, the history command and !! recall.
import os
import re
import sys

HISTORY_FILE = os.path.join(".OSData", "history")
MAX_HISTORY = 1000
_state = {"session": None, "used": False, "key": None}


def enabled():
    if os.environ.get("PYOS_PLAIN_PROMPT") == "1":
        return False
    try:
        from pyos import settings
        if not settings.get("fancy_prompt"):
            return False
    except Exception:                                  # noqa: BLE001
        pass
    try:
        import prompt_toolkit  # noqa: F401
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:                                  # noqa: BLE001
        return False


def used():
    """True once the enhanced prompt has been used in this session (then it, not readline, owns the history file)."""
    return _state["used"]


def clean(message):
    """A readline-style prompt (colour codes wrapped in \\001 ... \\002) as plain colour codes for prompt_toolkit."""
    return re.sub(r"[\x01\x02]", "", message)


# ---------------------------------------------------------------- history
def read_history(path=HISTORY_FILE, limit=MAX_HISTORY):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return [l.rstrip("\n") for l in f if l.strip()][-limit:]
    except OSError:
        return []


def append_history(line, path=HISTORY_FILE):
    line = line.strip()
    if not line or "\n" in line:
        return
    previous = read_history(path, 1)
    if previous and previous[-1] == line:
        return
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def history_lines():
    """The commands typed so far, oldest first (from the file when the enhanced prompt is in use, else from readline)."""
    if _state["used"] or not _readline_available():
        return read_history()
    try:
        import readline
        return [readline.get_history_item(i) for i in range(1, readline.get_current_history_length() + 1)]
    except Exception:                                  # noqa: BLE001
        return read_history()


def _readline_available():
    try:
        import readline  # noqa: F401
        return True
    except ImportError:
        return False


def search_history(items, word):
    """[(number, line)] of the history lines containing `word` (case does not matter), newest last."""
    word = word.lower()
    return [(i, line) for i, line in enumerate(items, 1) if word in line.lower()]


def expand_bang(line, items):
    """Recall from history: '!!' the last command, '!n' command number n, '!-n' the n-th from last, '!word' the last command that starts
    with word. Returns the command, or None when there is no such command (or the line is not a recall)."""
    line = line.strip()
    if not line.startswith("!") or len(line) < 2 or line[1] == " ":
        return None
    past = list(items)
    if past and past[-1].strip() == line:             # the recall itself was just added to the history
        past.pop()
    key = line[1:]
    if key == "!":
        return past[-1] if past else None
    if re.fullmatch(r"-\d+", key):
        n = int(key[1:])
        return past[-n] if 0 < n <= len(past) else None
    if key.isdigit():
        n = int(key)
        return past[n - 1] if 1 <= n <= len(past) else None
    for candidate in reversed(past):
        if candidate.startswith(key):
            return candidate
    return None


# ---------------------------------------------------------------- the prompt_toolkit session
def command_spans(text, is_known, is_prefix):
    """[(style, text)] for a command line: the first word of each command (after | ; && || &) is green when it is a command, red when no
    command starts with it, and plain while it could still become one. Everything else is plain."""
    out = []
    at_start = True
    for token in re.findall(r"\s+|\|\||&&|[|;&]|[^\s|;&]+", text):
        if token.isspace():
            out.append(("", token))
        elif token in ("|", "||", "&&", ";", "&"):
            out.append(("ansibrightblack", token))
            at_start = True
        elif at_start:
            at_start = False
            if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", token) or is_known(token):
                out.append(("ansigreen", token))
            elif is_prefix(token):
                out.append(("", token))
            else:
                out.append(("ansired", token))
        else:
            out.append(("", token))
    return out


def _build_session(complete, is_known, is_prefix, input=None, output=None):
    from prompt_toolkit import PromptSession
    from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
    from prompt_toolkit.completion import Completer, Completion
    from prompt_toolkit.enums import EditingMode
    from prompt_toolkit.history import History
    from prompt_toolkit.lexers import Lexer

    class PlainHistory(History):
        """History kept in the same plain file readline used (one command per line)."""

        def load_history_strings(self):
            return reversed(read_history())

        def store_string(self, string):
            append_history(string)

    class ShellCompleter(Completer):
        def get_completions(self, document, complete_event):
            text = document.text_before_cursor
            word = text.split(" ")[-1]
            for match in complete(text):
                yield Completion(match, start_position=-len(word))

    class CommandLexer(Lexer):
        def lex_document(self, document):
            lines = document.lines

            def line(number):
                return command_spans(lines[number], is_known, is_prefix)
            return line

    mode = EditingMode.VI
    try:
        from pyos import settings
        mode = EditingMode.VI if settings.get("prompt_keys") == "vi" else EditingMode.EMACS
    except Exception:                                  # noqa: BLE001
        mode = EditingMode.EMACS
    return PromptSession(history=PlainHistory(), completer=ShellCompleter(), complete_while_typing=False, auto_suggest=AutoSuggestFromHistory(),
                         lexer=CommandLexer(), editing_mode=mode, enable_history_search=False, mouse_support=False,
                         input=input, output=output)


def read_line(message, complete, is_known, is_prefix):
    """One line from the person at the prompt. Raises EOFError (Ctrl+D) and KeyboardInterrupt (Ctrl+C), like input()."""
    if enabled():
        try:
            from prompt_toolkit.formatted_text import ANSI
            if _state["session"] is None:
                _state["session"] = _build_session(complete, is_known, is_prefix)
            _state["used"] = True
            return _state["session"].prompt(ANSI(clean(message)))
        except (EOFError, KeyboardInterrupt):
            raise
        except Exception:                              # noqa: BLE001 - never lose the prompt: fall back to the plain one for good
            os.environ["PYOS_PLAIN_PROMPT"] = "1"
            _state["session"] = None
    return input(message)
