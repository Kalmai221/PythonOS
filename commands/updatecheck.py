from rich.console import Console
from rich.prompt import Prompt
import core

# Command metadata
config = {
    "name": "sysupdate",
    "description": "Checks for updates and installs them if available."
}

console = Console()

def execute():
    from pyos import audit
    audit.record("checked for and applied a system update")
    core.update_system()