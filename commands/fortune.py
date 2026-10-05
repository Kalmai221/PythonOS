import random

from rich.console import Console

console = Console()
config = {"name": "fortune", "description": "Print a random saying. Try: fortune | cowsay, fortune > ~/today.txt"}

SAYINGS = [
    "A pipe | sends one command's output into the next. Try: fortune | cowsay",
    "Use > to save output in a file and >> to add to it. Try: fortune > ~/today.txt",
    "&& runs the next command only if the first worked; || only if it failed.",
    "Put & at the end of a command to run it in the background. See it with jobs.",
    "Tab completes commands and file names. Press it twice to see the choices.",
    "man <command> explains any command; man alone lists them all.",
    "history shows what you typed before. The up arrow brings it back.",
    "The best backup is the one you made before you needed it: backup create",
    "echo $? shows whether the last command worked (0 means yes).",
    "A good programmer looks both ways before crossing a one-way street.",
    "There are 10 kinds of people: those who understand binary and those who do not.",
    "It works on my machine - which is why we ship the machine.",
    "Debugging is twice as hard as writing the code. So if you write it as cleverly as you can, you are not clever enough to debug it.",
    "Simple is better than complex. Complex is better than complicated.",
    "Readability counts.",
    "In the face of ambiguity, refuse the temptation to guess.",
    "Errors should never pass silently.",
    "The first rule of optimisation: don't. The second: don't yet.",
    "Have you tried turning it off and on again? (restart)",
    "schedule add daily 08:00 echo good morning - and PythonOS will say it for you.",
]


def execute(args=None):
    console.print(random.choice(SAYINGS), markup=False, highlight=False)
    return True
