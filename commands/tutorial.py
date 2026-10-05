import os

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm

import pyos
import pyos.fs as fs
from pyos import appdata, settings, stdio, trash

console = Console()
config = {
    "name": "tutorial",
    "description": "A guided tour that checks what you type: tutorial [list|<lesson number>|reset]. It remembers where you stopped.",
    "alias": ["tour"],
}

PRACTICE = "practice"


class State:
    """What the learner has done so far, for the lessons' checks."""

    def __init__(self):
        self.lines = []
        self.status = 0

    def ran(self, name):
        return any(line.split()[:1] == [name] for line in self.lines)

    @property
    def last(self):
        return self.lines[-1] if self.lines else ""

    def home(self):
        return fs.home_dir(pyos.userinfo()[0])

    def practice(self):
        return os.path.join(self.home(), PRACTICE)

    def file(self, name):
        return os.path.join(self.practice(), name)

    def read(self, name):
        try:
            with open(self.file(name), encoding="utf-8", errors="replace") as f:
                return f.read()
        except OSError:
            return ""


def _make(state, name, text):
    os.makedirs(state.practice(), exist_ok=True)
    if not os.path.exists(state.file(name)):
        with open(state.file(name), "w", encoding="utf-8") as f:
            f.write(text)


def _trashed(state, name):
    return any(i["name"] == name for i in trash.mine(pyos.userinfo()[0]))


def _trash_listing(state):
    """Before the undo lesson: listing.txt must be sitting in the trash."""
    _make(state, "listing.txt", "hello.txt\n")
    if os.path.exists(state.file("listing.txt")):
        trash.discard(state.file("listing.txt"), pyos.userinfo()[0])


# (section, title, what to say, the task, a check, a hint, setup: what must exist if you jump here)
LESSONS = [
    ("Basics", "Where are you?",
     "PythonOS keeps everything in folders. You start in your home folder, which the prompt calls ~.",
     "Type  pwd  to see where you are.",
     lambda s: s.ran("pwd"), "Just type: pwd", None),
    ("Basics", "Look around",
     "ls lists what is in a folder. Folders are blue and end in /.",
     "Type  ls",
     lambda s: s.ran("ls"), "Just type: ls", None),
    ("Basics", "Make a folder",
     "mkdir creates a folder. We will use one called practice, so nothing else gets mixed up.",
     "Type  mkdir practice",
     lambda s: os.path.isdir(s.practice()), "Type exactly: mkdir practice", None),
    ("Basics", "Step inside",
     "cd moves into a folder (cd .. goes back up, cd on its own goes home). Tab completes names - try cd pra and press Tab.",
     "Type  cd practice",
     lambda s: os.path.normcase(fs.current_dir()) == os.path.normcase(s.practice()), "Type: cd practice",
     lambda s: os.makedirs(s.practice(), exist_ok=True)),
    ("Files", "Write a file",
     "echo prints text, and > sends the output into a file instead of the screen. That creates hello.txt.",
     "Type  echo hello world > hello.txt",
     lambda s: os.path.isfile(s.file("hello.txt")), "Type: echo hello world > hello.txt",
     lambda s: (os.makedirs(s.practice(), exist_ok=True), fs.save_current_dir(s.practice()))),
    ("Files", "Read it back",
     "cat shows what is inside a file.",
     "Type  cat hello.txt",
     lambda s: s.ran("cat") and "hello.txt" in s.last, "Type: cat hello.txt",
     lambda s: _make(s, "hello.txt", "hello world\n")),
    ("Files", "Add to a file",
     "> replaces a file's contents, but >> adds to the end. Add a second line.",
     "Type  echo second line >> hello.txt",
     lambda s: len(s.read("hello.txt").splitlines()) >= 2, "Type: echo second line >> hello.txt", None),
    ("Files", "Copy a file",
     "cp makes a copy. We will use it in a moment to see how two files differ.",
     "Type  cp hello.txt copy.txt",
     lambda s: os.path.isfile(s.file("copy.txt")), "Type: cp hello.txt copy.txt",
     lambda s: _make(s, "hello.txt", "hello world\nsecond line\n")),
    ("Files", "Compare files",
     "diff shows what is different between two files. First change the copy, then compare: echo extra >> copy.txt  and then  diff hello.txt copy.txt",
     "Type  echo extra >> copy.txt  and then  diff hello.txt copy.txt",
     lambda s: s.ran("diff") and "copy.txt" in s.last and s.read("copy.txt") != s.read("hello.txt"),
     "First: echo extra >> copy.txt   then: diff hello.txt copy.txt",
     lambda s: (_make(s, "hello.txt", "hello world\nsecond line\n"), _make(s, "copy.txt", "hello world\nsecond line\n"))),
    ("Finding things", "Find files by name",
     "find looks through a folder and everything inside it. Give it a name pattern with -name; * matches anything.",
     "Type  find -name \"*.txt\"",
     lambda s: s.ran("find") and "-name" in s.last and s.status == 0, "Type: find -name \"*.txt\"", None),
    ("Finding things", "Search inside files",
     "grep looks for text inside files. -n adds the line numbers, -r searches a whole folder.",
     "Type  grep -n hello hello.txt",
     lambda s: s.ran("grep") and "hello" in s.last and "|" not in s.last and s.status == 0, "Type: grep -n hello hello.txt", None),
    ("Pipes and chains", "Pipes",
     "A pipe | feeds one command's output into the next. Here ls lists the files and grep keeps only the lines containing 'hello'.",
     "Type  ls | grep hello",
     lambda s: "|" in s.last and "grep" in s.last and s.status == 0, "Type: ls | grep hello", None),
    ("Pipes and chains", "Redirect a result",
     "Pipes and > work together: send a command's answer into a file. This saves the list of files.",
     "Type  ls > listing.txt",
     lambda s: os.path.isfile(s.file("listing.txt")), "Type: ls > listing.txt", None),
    ("Pipes and chains", "Chaining with && and ||",
     "&& runs the next command only if the first worked; || only if it failed. Together they let a line make decisions.",
     "Type  mkdir two && echo made it",
     lambda s: "&&" in s.last and os.path.isdir(s.file("two")), "Type: mkdir two && echo made it", None),
    ("Pipes and chains", "Pipes for fun",
     "Anything that prints can be piped. fortune prints a saying and cowsay lets a cow say whatever it is given.",
     "Type  fortune | cowsay",
     lambda s: "|" in s.last and "cowsay" in s.last and s.status == 0, "Type: fortune | cowsay", None),
    ("Safety nets", "Delete safely",
     "rm does not destroy anything at once: it moves the file to the trash. Remove the listing you made.",
     "Type  rm listing.txt",
     lambda s: not os.path.exists(s.file("listing.txt")) and _trashed(s, "listing.txt"), "Type: rm listing.txt",
     lambda s: _make(s, "listing.txt", "hello.txt\n")),
    ("Safety nets", "Undo",
     "Oops - changed your mind? undo brings back the last thing rm removed. (trash lists everything, trash empty clears it for good.)",
     "Type  undo",
     lambda s: s.ran("undo") and os.path.isfile(s.file("listing.txt")), "Just type: undo", lambda s: _trash_listing(s)),
    ("Safety nets", "Save a backup copy",
     "zip packs files into one archive you can keep or send. unzip opens one.",
     "Type  zip backup.zip hello.txt copy.txt",
     lambda s: os.path.isfile(s.file("backup.zip")), "Type: zip backup.zip hello.txt copy.txt", None),
    ("Everyday", "Background jobs",
     "Ending a line with & runs it in the background so you can keep working. jobs lists them and fg shows their output.",
     "Type  sleep 2 &  and then  jobs",
     lambda s: s.last.strip() == "jobs" and any("sleep" in line and line.rstrip().endswith("&") for line in s.lines),
     "First: sleep 2 &   then: jobs", None),
    ("Everyday", "Editing",
     "edit opens PythonOS's own text editor. On a real terminal it is full screen (Ctrl+S saves, Ctrl+Q quits); in the phone app it is "
     "a line editor (type h for help, wq saves and quits).",
     "Type  edit hello.txt  and look around, then save or quit.",
     lambda s: s.ran("edit"), "Type: edit hello.txt", None),
    ("Everyday", "Tidy the screen",
     "Output piles up. clear wipes the screen (and its scrollback). The prompt also tidies itself if you set auto_clear_lines.",
     "Type  clear",
     lambda s: s.ran("clear"), "Just type: clear", None),
    ("Everyday", "What did I type?",
     "history lists your earlier commands. The Up arrow brings the last one back.",
     "Type  history",
     lambda s: s.ran("history"), "Just type: history", None),
    ("Learn more", "Help by topic",
     "help groups the commands into categories. help files shows just the file commands; help search <word> finds one.",
     "Type  help files",
     lambda s: s.ran("help") and len(s.last.split()) > 1, "Type: help files", None),
    ("Learn more", "The manual",
     "man shows a full page with examples, and man -k searches the manual.",
     "Type  man ls",
     lambda s: s.ran("man") and "ls" in s.last, "Type: man ls", None),
    ("Make it yours", "Change the look",
     "settings changes colours and behaviour. Try a theme (default, ocean, forest, sunset, mono, contrast).",
     "Type  settings theme ocean",
     lambda s: settings.get("theme") != "default", "Type: settings theme ocean", None),
    ("Make it yours", "Check on the system",
     "doctor looks for problems (disk space, damaged files, odd settings) and can fix them. logs shows what happened recently.",
     "Type  doctor",
     lambda s: s.ran("doctor"), "Just type: doctor", None),
    ("Make it yours", "More software",
     "The marketplace has games and tools. pkg search finds them and pkg install adds one.",
     "Type  pkg search game",
     lambda s: s.ran("pkg") and "search" in s.last, "Type: pkg search game", None),
]

SECTION_ORDER = []
for _entry in LESSONS:
    if _entry[0] not in SECTION_ORDER:
        SECTION_ORDER.append(_entry[0])


def progress_bar(done, total, width=24):
    filled = int(width * done / total) if total else 0
    return "#" * filled + "-" * (width - filled)


class Tutorial:
    """The lesson logic. feed(line) -> list of messages to show; .finished when done."""

    def __init__(self, run_line, start=0):
        self.run_line = run_line
        self.state = State()
        self.index = start
        self.finished = False
        self.quit = False

    def intro(self, number=None):
        number = self.index if number is None else number
        _section, title, text, task, _check, _hint, _setup = LESSONS[number]
        return (f"Lesson {number + 1} of {len(LESSONS)}: {title}", text, task)

    def section(self):
        return LESSONS[self.index][0]

    def prepare(self):
        """Make sure what this lesson builds on exists (when you jump or resume), by running the setup of every earlier lesson."""
        for number in range(self.index + 1):
            setup = LESSONS[number][6]
            if setup is not None:
                try:
                    setup(self.state)
                except Exception:
                    pass

    def feed(self, line):
        line = line.strip()
        messages = []
        if not line:
            return messages
        word = line.lower()
        if word in ("quit", "q", "exit"):
            self.quit = self.finished = True
            return ["Leaving the tutorial. Type tutorial to carry on where you stopped."]
        if word == "hint":
            return ["Hint: " + LESSONS[self.index][5]]
        if word == "skip":
            return self._advance(["Skipped."])
        self.state.lines.append(line)
        self.state.status = self.run_line(line)
        if LESSONS[self.index][4](self.state):
            return self._advance(["Well done!"])
        messages.append("That ran - but this lesson wants:  " + LESSONS[self.index][3].replace("Type  ", "").replace("Type: ", "") +
                        "   (hint, skip or quit are always available)")
        return messages

    def _advance(self, messages):
        self.index += 1
        if self.index >= len(LESSONS):
            self.finished = True
            messages.append("That is the whole tour: files, searching, pipes, undo, jobs, the manual, settings and packages. "
                            "Everything here is also in man.")
        return messages


def _saved():
    data = appdata.load("tutorial", {}) or {}
    return data if isinstance(data, dict) else {}


def _show_list(done):
    section = None
    for number, entry in enumerate(LESSONS, 1):
        if entry[0] != section:
            section = entry[0]
            console.print(f"\n[bold cyan]{escape(section)}[/bold cyan]")
        mark = "[green]x[/green]" if number <= done else " "
        console.print(f"  [{mark}] {number:>2}  {escape(entry[1])}")
    console.print("\n[dim]Start at a lesson with: tutorial <number>[/dim]")


def _lesson_screen(tutorial):
    title, text, task = tutorial.intro()
    stdio.clear_screen(scrollback=False)
    total = len(LESSONS)
    console.print(f"[bold cyan]PythonOS tutorial[/bold cyan]  [dim]{escape(tutorial.section())}[/dim]  "
                  f"[green]{progress_bar(tutorial.index, total)}[/green] {tutorial.index}/{total}")
    console.print(f"\n[bold cyan]{escape(title)}[/bold cyan]")
    console.print(escape(text))
    console.print(f"\n[bold]{escape(task)}[/bold]")


def execute(args=None):
    import shell
    args = list(args or [])
    user = pyos.userinfo()[0]
    if not user:
        console.print("[bold red]tutorial: you are not logged in.[/bold red]")
        return False
    saved = _saved()
    done = int(saved.get("lesson", 0)) if not saved.get("done") else len(LESSONS)
    if args and args[0] == "list":
        _show_list(done)
        return True
    if args and args[0] == "reset":
        appdata.save("tutorial", {})
        console.print("[green]Tutorial progress cleared.[/green]")
        return True
    start = 0
    if args and args[0].isdigit():
        number = int(args[0])
        if not 1 <= number <= len(LESSONS):
            console.print(f"[bold red]tutorial: lessons are numbered 1 to {len(LESSONS)} (tutorial list shows them)[/bold red]")
            return False
        start = number - 1
    elif 0 < done < len(LESSONS):
        try:
            if Confirm.ask(f"Carry on at lesson {done + 1} ({LESSONS[done][1]})?", default=True):
                start = done
        except (EOFError, KeyboardInterrupt):
            return False

    home = fs.home_dir(user)
    start_dir = fs.current_dir()
    fs.save_current_dir(home)
    console.print(Panel("This takes about ten minutes. You type real commands; I check them and move on.\n"
                        "Type [bold]hint[/bold] for help, [bold]skip[/bold] to skip a lesson, [bold]quit[/bold] to leave (your place is saved).",
                        title="[bold cyan]PythonOS tutorial[/bold cyan]", border_style="blue", expand=False))
    tutorial = Tutorial(shell.run_line, start)
    tutorial.prepare()
    shown = -1
    try:
        while not tutorial.finished:
            if shown != tutorial.index:
                _lesson_screen(tutorial)
                shown = tutorial.index
            try:
                line = input("tutorial> ")
            except (EOFError, KeyboardInterrupt):
                console.print()
                break
            for message in tutorial.feed(line):
                console.print(f"[green]{escape(message)}[/green]" if message.startswith(("Well", "That is")) else escape(message))
            appdata.save("tutorial", {"lesson": min(tutorial.index, len(LESSONS)), "done": tutorial.index >= len(LESSONS)})
    finally:
        fs.save_current_dir(start_dir if os.path.isdir(start_dir) else home)

    practice = os.path.join(home, PRACTICE)
    if tutorial.finished and not tutorial.quit and os.path.isdir(practice):
        try:
            if Confirm.ask(f"Remove the practice folder ({fs.display(practice, tilde=True)})?", default=True):
                import shutil
                shutil.rmtree(practice, ignore_errors=True)
        except (EOFError, KeyboardInterrupt):
            pass
    return True
