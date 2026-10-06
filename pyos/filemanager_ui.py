"""The file manager's full-screen program (prompt_toolkit). Everything it does is the Manager's (pyos/filemanager.py); this draws it and reads keys."""
import os

from . import editor, fs, filemanager
from .filemanager import FileManagerError, human, when

HELP = [
    ("Move", "Up/Down or j/k, PageUp/PageDown, Home/End"),
    ("Open", "Enter or Right or l: open a folder, edit a file     Left, h or Backspace: up     ~ home    g go to a path"),
    ("Select", "Space marks (and moves down)     a all / none"),
    ("Copy, cut, paste", "c copy     x cut     p paste (a name that is taken gets (2); nothing is overwritten)"),
    ("Delete", "d or Delete: to the trash     D: delete for good     u: undo (bring back the last thing from the trash)"),
    ("Create, rename", "n new file     N new folder     r rename"),
    ("Look", "/ filter by name     s sort (name, size, time, type)     S reverse     . hidden files     i details     ? this help"),
    ("Leave", "q or Esc"),
]


def build(manager, input=None, output=None):
    """The file manager as a prompt_toolkit Application (not started)."""
    from prompt_toolkit import Application
    from prompt_toolkit.application import run_in_terminal
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout, VSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style
    from prompt_toolkit.widgets import TextArea

    state = {"mode": None, "action": None, "prompt": "", "message": "", "top": 0, "confirm": None, "help": False, "info": False}

    def rows():
        try:
            return max(5, (output or app.output).get_size().rows - 5)
        except Exception:
            return 20

    def say(text):
        state["message"] = text

    def failing(call, *args):
        """Run something that may raise FileManagerError and put its message on the status line."""
        try:
            return call(*args)
        except FileManagerError as e:
            say(str(e))
            return None

    # ------------------------------------------------------------------------------------------ drawing
    def header():
        shown = fs.display(manager.cwd, tilde=True)
        flags = []
        if manager.filter:
            flags.append(f"filter: {manager.filter}")
        if manager.show_hidden:
            flags.append("hidden shown")
        flags.append(f"sort: {manager.sort}{' (reversed)' if manager.reverse else ''}")
        op, paths = manager.clipboard
        if paths:
            flags.append(f"{op} {len(paths)}")
        if manager.selected:
            flags.append(f"{len(manager.selected)} marked")
        return [("class:header", f" {shown} "), ("class:headerdim", "  " + "  ".join(flags))]

    def listing():
        try:
            items = manager.entries()
        except FileManagerError as e:
            return [("class:error", f" {e}")]
        manager.current(items)
        height = rows()
        if manager.cursor < state["top"]:
            state["top"] = manager.cursor
        if manager.cursor >= state["top"] + height:
            state["top"] = manager.cursor - height + 1
        out = []
        if not items:
            return [("class:dim", "  (nothing here)" if not manager.filter else "  (nothing matches the filter)")]
        for index in range(state["top"], min(len(items), state["top"] + height)):
            e = items[index]
            marked = e.path in manager.selected
            under = index == manager.cursor
            name = e.name + ("/" if e.is_dir else "@" if e.is_link else "")
            width = 34
            label = (name[:width - 1] + "~") if len(name) > width else name.ljust(width)
            size = "" if e.is_dir else human(e.size)
            style = "class:cursor" if under else "class:marked" if marked else "class:dir" if e.is_dir else ""
            out.append((style, f" {'*' if marked else ' '} {label} {size:>9}  {when(e.mtime)} "))
            out.append(("", "\n"))
        return out[:-1] if out else out

    def preview():
        entry = manager.current(manager.entries())
        lines = manager.info(entry) + [""] if state["info"] else []
        lines += manager.preview(entry, lines=max(5, rows()))
        return [("class:preview", "\n".join(l[:200] for l in lines))]

    def status():
        if state["mode"] == "confirm":
            return [("class:prompt", f" {state['prompt']} (y/n) ")]
        if state["mode"] == "input":
            return [("class:prompt", f" {state['prompt']} ")]
        text = state["message"] or "? help   Enter open   Space mark   c/x/p copy-cut-paste   d trash   r rename   n/N new   / filter   q quit"
        return [("class:status", f" {text} ")]

    # ------------------------------------------------------------------------------------------ prompts
    box = TextArea(height=1, multiline=False, prompt="", style="class:input")

    def ask(prompt, action, initial=""):
        state.update(mode="input", prompt=prompt, action=action)
        box.text = initial
        box.buffer.cursor_position = len(initial)
        app.layout.focus(box)

    def accept(_buffer):
        action, text = state["action"], box.text
        state.update(mode=None, action=None)
        app.layout.focus(list_window)
        if action:
            action(text)
        return True

    box.accept_handler = accept

    def confirm(prompt, action):
        state.update(mode="confirm", prompt=prompt, confirm=action)

    # ------------------------------------------------------------------------------------------ keys
    normal = Condition(lambda: state["mode"] is None and not state["help"])
    confirming = Condition(lambda: state["mode"] == "confirm")
    inputting = Condition(lambda: state["mode"] == "input")
    helping = Condition(lambda: state["help"])
    keys = KeyBindings()

    def refresh_message(done, problems, verb):
        if problems:
            say(f"{verb} {done}; {len(problems)} problem(s): {problems[0]}")
        else:
            say(f"{verb} {done} item(s).")

    @keys.add("q", filter=normal)
    @keys.add("escape", filter=normal, eager=True)
    def _quit(event):
        event.app.exit()

    @keys.add("up", filter=normal)
    @keys.add("k", filter=normal)
    def _up(event):
        manager.move(-1)

    @keys.add("down", filter=normal)
    @keys.add("j", filter=normal)
    def _down(event):
        manager.move(1)

    @keys.add("pageup", filter=normal)
    def _pgup(event):
        manager.move(-rows())

    @keys.add("pagedown", filter=normal)
    def _pgdn(event):
        manager.move(rows())

    @keys.add("home", filter=normal)
    def _home(event):
        manager.cursor = 0

    @keys.add("end", filter=normal)
    def _end(event):
        manager.cursor = 10 ** 9

    def open_it(event):
        say("")
        entry = failing(manager.open_current)
        if entry is not None:
            def run():
                doc = editor.Document.open(entry.path)
                try:
                    if editor.can_use_fullscreen():
                        editor.run_fullscreen(doc)
                except OSError as e:
                    print(f"Could not edit it: {fs.errtext(e)}")
            try:
                fs._check_permission(entry.path, True)
            except PermissionError:
                say("you can look at that file but not change it (read-only for you)")
                return
            run_in_terminal(run)

    keys.add("enter", filter=normal)(open_it)
    keys.add("right", filter=normal)(open_it)
    keys.add("l", filter=normal)(open_it)

    @keys.add("left", filter=normal)
    @keys.add("h", filter=normal)
    @keys.add("backspace", filter=normal)
    def _parent(event):
        say("")
        failing(manager.up)

    @keys.add("~", filter=normal)
    def _tilde(event):
        failing(manager.home)

    @keys.add("g", filter=normal)
    def _goto(event):
        ask("Go to:", lambda text: failing(manager.goto_text, text))

    @keys.add("space", filter=normal)
    def _mark(event):
        manager.toggle()
        manager.move(1)

    @keys.add("a", filter=normal)
    def _all(event):
        manager.select_all()

    @keys.add("c", filter=normal)
    def _copy(event):
        n = failing(manager.copy)
        if n:
            say(f"copied {n} item(s): go to a folder and press p")

    @keys.add("x", filter=normal)
    def _cut(event):
        n = failing(manager.cut)
        if n:
            say(f"cut {n} item(s): go to a folder and press p")

    @keys.add("p", filter=normal)
    def _paste(event):
        result = failing(manager.paste)
        if result:
            refresh_message(result[0], result[1], "pasted")

    @keys.add("d", filter=normal)
    @keys.add("delete", filter=normal)
    def _trash(event):
        targets = manager.targets()
        if not targets:
            return
        confirm(f"Move {len(targets)} item(s) to the trash?", lambda: refresh_message(*manager.delete(False), "removed"))

    @keys.add("D", filter=normal)
    def _purge(event):
        targets = manager.targets()
        if not targets:
            return
        confirm(f"DELETE {len(targets)} item(s) FOR GOOD? This cannot be undone.", lambda: refresh_message(*manager.delete(True), "deleted"))

    @keys.add("u", filter=normal)
    def _undo(event):
        name = failing(manager.undo)
        if name:
            say(f"brought back {name}")

    @keys.add("r", filter=normal)
    def _rename(event):
        entry = manager.current()
        if entry:
            ask("New name:", lambda text: failing(manager.rename, text), entry.name)

    @keys.add("n", filter=normal)
    def _newfile(event):
        ask("New file:", lambda text: failing(manager.make_file, text))

    @keys.add("N", filter=normal)
    def _newfolder(event):
        ask("New folder:", lambda text: failing(manager.make_folder, text))

    @keys.add("/", filter=normal)
    def _filter(event):
        ask("Filter by name (empty to clear):", lambda text: (setattr(manager, "filter", text.strip()), setattr(manager, "cursor", 0)), manager.filter)

    @keys.add("s", filter=normal)
    def _sort(event):
        say(f"sorted by {manager.cycle_sort()}")

    @keys.add("S", filter=normal)
    def _reverse(event):
        manager.reverse = not manager.reverse

    @keys.add(".", filter=normal)
    def _hidden(event):
        manager.show_hidden = not manager.show_hidden
        manager.cursor = 0

    @keys.add("i", filter=normal)
    def _info(event):
        state["info"] = not state["info"]

    @keys.add("?", filter=normal)
    def _help(event):
        state["help"] = True

    @keys.add("y", filter=confirming)
    @keys.add("enter", filter=confirming)
    def _yes(event):
        action, state["confirm"] = state["confirm"], None
        state["mode"] = None
        if action:
            action()

    @keys.add("n", filter=confirming)
    @keys.add("escape", filter=confirming, eager=True)
    def _no(event):
        state.update(mode=None, confirm=None)
        say("cancelled")

    @keys.add("escape", filter=inputting, eager=True)
    def _cancel(event):
        state.update(mode=None, action=None)
        app.layout.focus(list_window)

    @keys.add("<any>", filter=helping)
    def _close_help(event):
        state["help"] = False

    # ------------------------------------------------------------------------------------------ layout
    list_window = Window(FormattedTextControl(listing, focusable=True), wrap_lines=False)
    help_text = "\n".join(f" {title:<18}{text}" for title, text in HELP)
    body = VSplit([list_window, Window(width=1, char="|", style="class:dim"),
                   Window(FormattedTextControl(preview), wrap_lines=False, width=lambda: max(20, ((output or app.output).get_size().columns - 3) // 2 - 2))])
    help_window = ConditionalContainer(Window(FormattedTextControl([("class:help", "\n Keys\n\n" + help_text + "\n\n Press any key to go back.")]), style="class:help"),
                                       filter=helping)
    app = Application(
        layout=Layout(HSplit([Window(FormattedTextControl(header), height=1, style="class:header"), ConditionalContainer(body, filter=~helping), help_window,
                              ConditionalContainer(box, filter=inputting),
                              Window(FormattedTextControl(status), height=1, style="class:status")]), focused_element=list_window),
        key_bindings=keys, full_screen=True, mouse_support=False, input=input, output=output,
        style=Style.from_dict({"header": "reverse bold", "headerdim": "reverse", "cursor": "reverse", "marked": "bold fg:ansiyellow", "dir": "bold fg:ansicyan",
                               "status": "reverse", "prompt": "reverse bold", "error": "fg:ansired", "dim": "fg:ansibrightblack", "preview": "fg:ansibrightblack",
                               "help": "", "input": "bold"}))
    return app


def can_use():
    return editor.can_use_fullscreen()


def run(start=None, user=None):
    manager = filemanager.Manager(start, user)
    build(manager).run()
    return manager
