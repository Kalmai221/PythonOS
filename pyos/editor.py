# pyos/editor.py - PythonOS's own text editor (no external programs, so it also works when locked down)
#
# Two front ends over the same Document:
#   * full screen (like nano): used on a real terminal - Ctrl+S saves, Ctrl+Q quits
#   * line editor (like ed): used everywhere else - the Android app, pipes, minimal terminals
import os
import re

HELP = """Line editor commands (line numbers start at 1):
  p [N|N-M]        show lines (all by default)        a [N]    add lines after line N (end by default)
  i N              insert lines before line N         d N[-M]  delete lines
  r N [text]       replace line N                     s [N] /old/new/[g]   replace text (all lines if no N)
  f text           find lines containing text         u        undo the last change
  w                save           q   quit (asks if unsaved)   wq   save and quit      q!   quit without saving
While adding lines, type a single . on its own line to stop.   h   this help"""


class Document:
    """The text being edited, with undo."""

    def __init__(self, path, text=""):
        self.path = path
        self.name = os.path.basename(path)
        self.lines = text.split("\n")
        if self.lines and self.lines[-1] == "" and len(self.lines) > 1:
            self.lines.pop()                       # a trailing newline is not an extra empty line
        if self.lines == [""] and text == "":
            self.lines = []
        self.saved_lines = list(self.lines)
        self._undo = []

    @classmethod
    def open(cls, path):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                return cls(path, f.read())
        except FileNotFoundError:
            return cls(path, "")

    @property
    def modified(self):
        return self.lines != self.saved_lines

    def text(self):
        return "\n".join(self.lines) + ("\n" if self.lines else "")

    def set_text(self, text):
        self.remember()
        self.lines = text.split("\n")
        if len(self.lines) > 1 and self.lines[-1] == "":
            self.lines.pop()

    def remember(self):
        self._undo.append(list(self.lines))
        del self._undo[:-50]

    def undo(self):
        if not self._undo:
            return False
        self.lines = self._undo.pop()
        return True

    def save(self):
        folder = os.path.dirname(self.path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(self.text())
        os.replace(tmp, self.path)
        self.saved_lines = list(self.lines)


def _range(spec, count):
    """'3' -> (3, 3), '2-5' -> (2, 5), '' -> (1, count). Raises ValueError with a readable message."""
    spec = spec.strip()
    if not spec:
        return 1, count
    m = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", spec)
    if not m:
        raise ValueError(f"'{spec}' is not a line number or range like 3-5")
    start = int(m.group(1))
    end = int(m.group(2) or start)
    if start < 1 or end < start or end > count:
        raise ValueError(f"there are only {count} line(s)")
    return start, end


class LineEditor:
    """ed-style editor. Feed it one line at a time with feed(); it returns (text to show, finished)."""

    def __init__(self, doc):
        self.doc = doc
        self.adding_at = None      # while adding lines: where the next one goes
        self.confirm_quit = False

    def prompt(self):
        return "add> " if self.adding_at is not None else "edit> "

    def banner(self):
        n = len(self.doc.lines)
        return f"Editing {self.doc.name} ({n} line{'s' if n != 1 else ''}). Type h for help, a to add lines, w to save, q to quit."

    def feed(self, line):
        if self.adding_at is not None:
            if line == ".":
                self.adding_at = None
                return "", False
            self.doc.lines.insert(self.adding_at, line)
            self.adding_at += 1
            return "", False
        try:
            return self._command(line.strip())
        except ValueError as e:
            return f"? {e}", False

    def _show(self, start, end):
        width = len(str(len(self.doc.lines)))
        return "\n".join(f"{i:>{width}}  {self.doc.lines[i - 1]}" for i in range(start, end + 1))

    def _command(self, cmd):
        if not cmd:
            return "", False
        word, _, rest = cmd.partition(" ")
        rest = rest.strip()
        d = self.doc
        n = len(d.lines)
        if word not in ("q", "quit"):
            self.confirm_quit = False

        if word in ("h", "?", "help"):
            return HELP, False
        if word in ("p", "l", "list", "print"):
            if n == 0:
                return "(the file is empty - type a to add lines)", False
            return self._show(*_range(rest, n)), False
        if word in ("a", "append"):
            at = n if not rest else _range(rest, n)[0]
            d.remember()
            self.adding_at = at
            return "Adding lines - type a single . to finish.", False
        if word in ("i", "insert"):
            if not rest:
                raise ValueError("insert before which line?  (i 3)")
            at = _range(rest, n)[0] - 1
            d.remember()
            self.adding_at = at
            return "Adding lines - type a single . to finish.", False
        if word in ("d", "delete"):
            start, end = _range(rest, n) if rest else (_ for _ in ()).throw(ValueError("delete which line?  (d 3 or d 2-5)"))
            d.remember()
            del d.lines[start - 1:end]
            return f"Deleted {end - start + 1} line(s).", False
        if word in ("r", "replace"):
            num, _, text = rest.partition(" ")
            start, _end = _range(num, n) if num else (_ for _ in ()).throw(ValueError("replace which line?  (r 3 new text)"))
            if not text:
                return f"Line {start} is: {d.lines[start - 1]}\nUse  r {start} <new text>  to replace it.", False
            d.remember()
            d.lines[start - 1] = text
            return "", False
        if word in ("s", "sub", "substitute"):
            return self._substitute(rest), False
        if word in ("f", "find"):
            if not rest:
                raise ValueError("find what?  (f text)")
            hits = [i for i, text in enumerate(d.lines, 1) if rest.lower() in text.lower()]
            if not hits:
                return "No lines contain that.", False
            width = len(str(n))
            return "\n".join(f"{i:>{width}}  {d.lines[i - 1]}" for i in hits), False
        if word in ("u", "undo"):
            return ("Undone." if d.undo() else "Nothing to undo."), False
        if word == "w":
            d.save()
            return f"Saved {d.name} ({len(d.lines)} lines).", False
        if word in ("wq", "x"):
            d.save()
            return f"Saved {d.name}.", True
        if word == "q!":
            return "Discarded changes." if d.modified else "", True
        if word in ("q", "quit"):
            if d.modified and not self.confirm_quit:
                self.confirm_quit = True
                return "Unsaved changes! Type  wq  to save and quit, or  q!  to quit without saving.", False
            return "", True
        raise ValueError(f"unknown command '{word}' (h for help)")

    def _substitute(self, rest):
        d = self.doc
        n = len(d.lines)
        m = re.fullmatch(r"(?:(\d+(?:-\d+)?)\s+)?/(.*?)(?<!\\)/(.*?)(?<!\\)/(g?)", rest)
        if not m:
            raise ValueError("usage:  s [N] /old/new/   (add g after the last / to replace every match in a line)")
        spec, old, new, flag = m.groups()
        if not old:
            raise ValueError("what should be replaced?")
        start, end = _range(spec or "", n) if n else (1, 0)
        d.remember()
        changed = 0
        for i in range(start - 1, end):
            updated = d.lines[i].replace(old, new) if flag == "g" else d.lines[i].replace(old, new, 1)
            if updated != d.lines[i]:
                d.lines[i] = updated
                changed += 1
        if not changed:
            d._undo.pop()
            return "No match."
        return f"Changed {changed} line(s)."


# ----------------------------------------------------------------------------- front ends
def run_line_editor(doc, ask, say):
    """ask(prompt) -> a line of input (raises EOFError/KeyboardInterrupt to give up); say(text) shows text."""
    editor = LineEditor(doc)
    say(editor.banner())
    while True:
        try:
            line = ask(editor.prompt())
        except (EOFError, KeyboardInterrupt):
            say("")
            return doc.modified is False
        out, done = editor.feed(line)
        if out:
            say(out)
        if done:
            return True


def build_fullscreen(doc, input=None, output=None):
    """The nano-like editor as a prompt_toolkit Application (not started). Returns (app, area, state)."""
    from prompt_toolkit import Application
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style
    from prompt_toolkit.widgets import TextArea

    area = TextArea(text=doc.text(), scrollbar=True, line_numbers=True, wrap_lines=False, focus_on_click=True)
    state = {"message": "", "armed": False, "saved": False}

    def changed():
        return area.text != "\n".join(doc.saved_lines) + ("\n" if doc.saved_lines else "")

    def status():
        pos = area.document
        flag = " [modified]" if changed() else ""
        left = f" {doc.name}{flag}   Ln {pos.cursor_position_row + 1}, Col {pos.cursor_position_col + 1}   "
        return [("class:status", left + "Ctrl+S save   Ctrl+Q quit   "), ("class:message", state["message"])]

    keys = KeyBindings()

    @keys.add("c-s")
    def _save(event):
        doc.set_text(area.text)
        doc.save()
        state.update(message="Saved.", armed=False, saved=True)

    @keys.add("c-q")
    def _quit(event):
        if changed() and not state["armed"]:
            state.update(message="Unsaved changes - press Ctrl+Q again to quit without saving.", armed=True)
        else:
            event.app.exit()

    area.buffer.on_text_changed += lambda _buffer: state.update(armed=False, message="")

    app = Application(
        layout=Layout(HSplit([area, Window(height=1, content=FormattedTextControl(status), style="class:status")]), focused_element=area),
        key_bindings=keys,
        full_screen=True,
        mouse_support=True,
        style=Style.from_dict({"status": "reverse", "message": "reverse bold"}),
        input=input,
        output=output,
    )
    return app, area, state


def run_fullscreen(doc, input=None, output=None):
    """Run the full-screen editor. Returns True if the file was saved."""
    app, _area, state = build_fullscreen(doc, input, output)
    app.run()
    return state["saved"]


def can_use_fullscreen():
    import sys
    if os.environ.get("PYOS_LINE_EDITOR"):
        return False
    try:
        import prompt_toolkit  # noqa: F401
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False
