import importlib.util
import os
from rich.console import Console

console = Console()
config = {
    "name": "pkg",
    "description": "Package manager: pkg search|install|remove|update|list|info <name>",
}


def execute(args=None):
    path = os.path.join("programs", "marketplace.py")
    spec = importlib.util.spec_from_file_location("marketplace", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.execute(args or ["help"])
