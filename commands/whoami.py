from rich.console import Console
import pyos

console = Console()
config = {"name": "whoami", "description": "Show the logged-in user and role."}


def execute(args=None):
    name, role = pyos.userinfo()
    console.print(f"{name} ({role})" if name else "Not logged in", markup=False)
