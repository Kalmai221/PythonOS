import datetime
from rich.console import Console

console = Console()
config = {"name": "date", "description": "Show the current date and time."}


def execute(args=None):
    console.print(datetime.datetime.now().strftime("%A %Y-%m-%d %H:%M:%S"))
