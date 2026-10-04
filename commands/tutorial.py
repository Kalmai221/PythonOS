import os
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm
import pyos
import pyos.fs as fs
from pyos import appdata, jobs, settings

console = Console()
config = {
    "name": "tutorial",
    "description": "A short guided tour: try real commands and it checks them. Type tutorial to start.",
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


# (title, what to say, the task, a check, a hint)
LESSONS = [
    ("Where are you?",
     "PythonOS keeps everything in folders. You start in your home folder, which the prompt calls ~.",
     "Type  pwd  to see where you are.",
     lambda s: s.ran("pwd"), "Just type: pwd"),
    ("Look around",
     "ls lists what is in a folder. Folders are blue and end in /.",
     "Type  ls",
     lambda s: s.ran("ls"), "Just type: ls"),
    ("Make a folder",
     "mkdir creates a folder. We will use one called practice, so nothing else gets mixed up.",
     "Type  mkdir practice",
     lambda s: os.path.isdir(s.practice()), "Type exactly: mkdir practice"),
    ("Step inside",
     "cd moves into a folder (cd .. goes back up, cd on its own goes home). Tab completes names - try cd pra and press Tab.",
     "Type  cd practice",
     lambda s: os.path.normcase(fs.current_dir()) == os.path.normcase(s.practice()), "Type: cd practice"),
    ("Write a file",
     "echo prints text, and > sends the output into a file instead of the screen. That creates hello.txt.",
     "Type  echo hello world > hello.txt",
     lambda s: os.path.isfile(os.path.join(s.practice(), "hello.txt")), "Type: echo hello world > hello.txt"),
    ("Read it back",
     "cat shows what is inside a file.",
     "Type  cat hello.txt",
     lambda s: s.ran("cat") and "hello.txt" in s.last, "Type: cat hello.txt"),
    ("Pipes",
     "A pipe | feeds one command's output into the next. Here ls lists the files and grep keeps only the lines containing 'hello'.",
     "Type  ls | grep hello",
     lambda s: "|" in s.last and "grep" in s.last and s.status == 0, "Type: ls | grep hello"),
    ("Chaining with && and ||",
     "&& runs the next command only if the first worked; || only if it failed. Together they let a line make decisions.",
     "Type  mkdir two && echo made it",
     lambda s: "&&" in s.last and os.path.isdir(os.path.join(s.practice(), "two")), "Type: mkdir two && echo made it"),
    ("Background jobs",
     "Ending a line with & runs it in the background so you can keep working. jobs lists them and fg shows their output.",
     "Type  sleep 2 &  and then  jobs",
     lambda s: s.last.strip() == "jobs" and any("sleep" in line and line.rstrip().endswith("&") for line in s.lines),
     "First: sleep 2 &   then: jobs"),
    ("Editing",
     "edit opens PythonOS's own text editor. On a real terminal it is full screen (Ctrl+S saves, Ctrl+Q quits); in the phone app it is "
     "a line editor (type h for help, wq saves and quits).",
     "Type  edit hello.txt  and look around, then save or quit.",
     lambda s: s.ran("edit"), "Type: edit hello.txt"),
    ("The manual",
     "help lists every command. man shows a full page with examples, and man -k searches the manual.",
     "Type  man ls",
     lambda s: s.ran("man") and "ls" in s.last, "Type: man ls"),
    ("Make it yours",
     "settings changes colours and behaviour. Try a theme (default, ocean, forest, sunset, mono, contrast).",
     "Type  settings theme ocean",
     lambda s: settings.get("theme") != "default", "Type: settings theme ocean"),
    ("More software",
     "The marketplace has games and tools. pkg search finds them and pkg install adds one.",
     "Type  pkg search game",
     lambda s: s.ran("pkg") and "search" in s.last, "Type: pkg search game"),
]


class Tutorial:
    """The lesson logic. feed(line) -> list of messages to show; .finished when done."""

    def __init__(self, run_line):
        self.run_line = run_line
        self.state = State()
        self.index = 0
        self.finished = False
        self.quit = False

    def intro(self, number=None):
        number = self.index if number is None else number
        title, text, task, _check, _hint = LESSONS[number]
        return (f"Lesson {number + 1} of {len(LESSONS)}: {title}", text, task)

    def feed(self, line):
        line = line.strip()
        messages = []
        if not line:
            return messages
        word = line.lower()
        if word in ("quit", "q", "exit"):
            self.quit = self.finished = True
            return ["Leaving the tutorial. Type tutorial any time to continue."]
        if word == "hint":
            return ["Hint: " + LESSONS[self.index][4]]
        if word == "skip":
            return self._advance(["Skipped."])
        self.state.lines.append(line)
        self.state.status = self.run_line(line)
        if LESSONS[self.index][3](self.state):
            return self._advance(["Well done!"])
        messages.append("That ran - but this lesson wants:  " + LESSONS[self.index][2].replace("Type  ", "").replace("Type: ", "") +
                        "   (hint, skip or quit are always available)")
        return messages

    def _advance(self, messages):
        self.index += 1
        if self.index >= len(LESSONS):
            self.finished = True
            messages.append("That is the whole tour. You now know files, pipes, chaining, jobs, the editor, the manual, settings and packages.")
        return messages


def execute(args=None):
    import shell
    user = pyos.userinfo()[0]
    if not user:
        console.print("[bold red]tutorial: you are not logged in.[/bold red]")
        return False
    home = fs.home_dir(user)
    start_dir = fs.current_dir()
    fs.save_current_dir(home)
    console.print(Panel("This takes about five minutes. You type real commands; I check them and move on.\n"
                        "Type [bold]hint[/bold] for help, [bold]skip[/bold] to skip a lesson, [bold]quit[/bold] to leave.",
                        title="[bold cyan]PythonOS tutorial[/bold cyan]", border_style="blue", expand=False))
    tutorial = Tutorial(shell.run_line)
    shown = -1
    try:
        while not tutorial.finished:
            if shown != tutorial.index:
                title, text, task = tutorial.intro()
                console.print(f"\n[bold cyan]{escape(title)}[/bold cyan]")
                console.print(escape(text))
                console.print(f"[bold]{escape(task)}[/bold]")
                shown = tutorial.index
            try:
                line = input("tutorial> ")
            except (EOFError, KeyboardInterrupt):
                console.print()
                break
            for message in tutorial.feed(line):
                console.print(f"[green]{escape(message)}[/green]" if message.startswith(("Well", "That is")) else escape(message))
    finally:
        fs.save_current_dir(start_dir if os.path.isdir(start_dir) else home)

    practice = os.path.join(home, PRACTICE)
    if tutorial.finished and not tutorial.quit:
        appdata.save("tutorial", {"done": True})
    if os.path.isdir(practice):
        try:
            if Confirm.ask(f"Remove the practice folder ({fs.display(practice, tilde=True)})?", default=True):
                import shutil
                shutil.rmtree(practice, ignore_errors=True)
        except (EOFError, KeyboardInterrupt):
            pass
    return True
