# pyos/paging.py - show long output one screen at a time (the Linux console on the ISO and VMs has no scrollback to scroll)
import os
import re
import shutil

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
# commands that only print (no prompts, no questions): safe to collect their output and page it
PAGED = {"ls", "cat", "man", "history", "logs", "ps", "tree", "find", "grep", "tail", "head", "diff", "whatsnew", "sysinfo", "doctor", "df",
         "free", "help", "tar", "whathappened", "last", "jobs", "wc", "date", "uname", "version", "report"}


def screen_size():
    size = shutil.get_terminal_size((80, 24))
    return size.columns, size.lines


class Pager:
    """Sits between a command and the screen: passes output through (colours and all) and, each time a screen is full, waits to be told
    to go on. Enter shows one more line, a space (then Enter) the next page, q stops (the rest of the output is dropped)."""

    def __init__(self, real_write, ask, width=None, height=None):
        cols, lines = screen_size()
        self.width, self.page = max(1, width or cols), max(3, (height or lines) - 1)
        self.real_write, self.ask = real_write, ask
        self.shown = 0          # screen rows used since the last pause
        self.column = 0         # visible characters of the line being written
        self.stopped = False

    def write(self, text):
        if self.stopped:
            return
        start = 0
        while True:
            end = text.find("\n", start)
            if end < 0:
                self.column += len(ANSI.sub("", text[start:]))
                self.real_write(text[start:])
                return
            self.column += len(ANSI.sub("", text[start:end]))
            self.real_write(text[start:end + 1])
            start = end + 1
            self.shown += max(1, -(-self.column // self.width))
            self.column = 0
            if self.shown >= self.page and not self._more():
                return

    def _more(self):
        """Wait for the user. False when they asked to stop."""
        try:
            answer = self.ask("\x1b[7m-- more: Enter = next line, space = next page, q = stop --\x1b[0m").lower()
        except (EOFError, KeyboardInterrupt):
            answer = "q"
        if os.environ.get("TERM") != "dumb":
            self.real_write("\x1b[1A\x1b[2K\r")
        if answer.strip().startswith("q"):
            self.stopped = True
            return False
        self.shown = self.page - 1 if answer == "" else 0
        return True
