#!/usr/bin/env python3
"""The optional libraries (requirements-extra.txt) as a list for the Windows installers, made at build time so the lists never go stale.

    python make_extras_list.py <requirements-extra.txt> --txt extras.txt     for Inno Setup: one "name|what it adds" line each
    python make_extras_list.py <requirements-extra.txt> --cs ExtrasList.g.cs for the web installer: a C# class with the same list
A library whose marker says it is not for the Python in the Windows package (3.12) is left out (python_version < "3.14" stays, > "3.12" goes).
"""
import re
import sys

PYTHON = (3, 12)
MARKER = re.compile(r'\s*python_version\s*(<=|>=|<|>|==|!=)\s*["\']([\d.]+)["\']\s*')


def applies(marker, python=PYTHON):
    if not marker:
        return True
    found = MARKER.fullmatch(marker)
    if not found:
        return True
    parts = [int(x) for x in found.group(2).split(".")][:2]
    there = tuple(parts + [0] * (2 - len(parts)))
    return {"<": python < there, "<=": python <= there, ">": python > there, ">=": python >= there, "==": python == there, "!=": python != there}[found.group(1)]


def items(text, python=PYTHON):
    """[(name, description)] for the libraries that apply."""
    found = []
    for line in text.splitlines():
        body, _hash, comment = line.partition("#")
        body = body.strip()
        if not body:
            continue
        requirement, _semi, marker = body.partition(";")
        name = re.split(r"[<>=!~\[ ]", requirement.strip(), maxsplit=1)[0]
        if name and applies(marker.strip(), python):
            found.append((name, " ".join(comment.split())))
    return found


def as_text(entries):
    return "".join(f"{name}|{description}\n" for name, description in entries)


def as_csharp(entries):
    def quote(text):
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'
    rows = ",\n".join(f"            new string[] {{ {quote(name)}, {quote(description)} }}" for name, description in entries)
    return ("// Made by make_extras_list.py at build time from requirements-extra.txt. Do not edit.\n"
            "namespace PythonOS.Setup\n{\n    internal static class ExtrasList\n    {\n"
            "        public static readonly string[][] Items = new string[][]\n        {\n" + rows + "\n        };\n    }\n}\n")


def main(argv):
    if len(argv) != 4 or argv[2] not in ("--txt", "--cs"):
        print(__doc__)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        entries = items(f.read())
    with open(argv[3], "w", encoding="utf-8", newline="\n") as f:
        f.write(as_text(entries) if argv[2] == "--txt" else as_csharp(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
