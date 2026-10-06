from rich.console import Console

import pyos

console = Console()
config = {"name": "id", "description": "Show your user name and role (id).", "alias": ["groups"]}


def execute(args=None):
    user, role = pyos.userinfo()
    console.print(f"user={user} role={role}", markup=False, highlight=False)
    return True
