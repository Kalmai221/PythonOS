import json
import os

from rich.console import Console

import pyos.fs as fs
from pyos import optional

console = Console()
config = {"name": "convert", "description": "Convert a data file between JSON and YAML (convert <file> [--to json|yaml] [-o output]).", "alias": ["yaml"]}


def load(text, name):
    ext = os.path.splitext(name)[1].lower()
    if ext in (".yml", ".yaml"):
        yaml = optional.get("yaml")
        if yaml is None:
            raise RuntimeError("reading YAML needs the PyYAML library, which is not installed here")
        return yaml.safe_load(text)
    return json.loads(text)


def dump(data, target):
    if target == "yaml":
        yaml = optional.get("yaml")
        if yaml is None:
            raise RuntimeError("writing YAML needs the PyYAML library, which is not installed here")
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def execute(args=None):
    args = list(args or [])
    target, output = None, None
    if "--to" in args:
        i = args.index("--to")
        target = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    if "-o" in args:
        i = args.index("-o")
        output = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
    if len(args) != 1 or target not in (None, "json", "yaml"):
        console.print("[bold red]Usage:[/bold red] convert <file> [--to json|yaml] [-o output]   (the target is the other format by default)")
        return False
    name = args[0]
    try:
        with open(fs.resolve(name), encoding="utf-8") as f:
            data = load(f.read(), name)
        target = target or ("json" if os.path.splitext(name)[1].lower() in (".yml", ".yaml") else "yaml")
        text = dump(data, target)
        if output:
            with open(fs.resolve(output, write=True), "w", encoding="utf-8") as f:
                f.write(text)
            console.print(f"Wrote {output} ({target}).")
        else:
            console.print(text, markup=False, highlight=False, end="")
    except Exception as e:                                 # noqa: BLE001
        console.print(f"[bold red]convert: {name}: {fs.errtext(e) if isinstance(e, OSError) else e}[/bold red]")
        return False
    return True
