#!/usr/bin/env python3
"""Writes the "What's new" page of the Windows installer: the CHANGELOG section of this version, as RTF (Inno Setup shows an RTF file before
installing). The same Markdown subset the installers and the in-OS update screen understand: headings, bullets, numbered lists, **bold**,
`code`, quotes, code blocks and rules; links show their text.

    python OS_Export/whatsnew_rtf.py <out.rtf>
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_core  # noqa: E402
import stage  # noqa: E402

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET = re.compile(r"^[-*+]\s+(.*)$")
NUMBERED = re.compile(r"^(\d+)[.)]\s+(.*)$")
QUOTE = re.compile(r"^>\s?(.*)$")
RULE = re.compile(r"^(-{3,}|\*{3,}|_{3,})$")
LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")


def escape(text):
    out = []
    for ch in text:
        if ch in "\\{}":
            out.append("\\" + ch)
        elif ord(ch) > 126:
            code = ord(ch)
            out.append("\\u%d?" % (code - 65536 if code > 32767 else code))     # RTF wants a signed 16-bit number
        else:
            out.append(ch)
    return "".join(out)


def inline(text):
    text = LINK.sub(lambda m: m.group(1), text)
    out, bold, code, i = [], False, False, 0
    while i < len(text):
        if not code and text.startswith("**", i):
            bold = not bold
            out.append("\\b " if bold else "\\b0 ")
            i += 2
            continue
        if text[i] == "`":
            code = not code
            out.append("{\\f1\\fs18\\cf2 " if code else "}")
            i += 1
            continue
        out.append(escape(text[i]))
        i += 1
    if code:
        out.append("}")
    if bold:
        out.append("\\b0 ")
    return "".join(out)


def to_rtf(markdown):
    rtf = ["{\\rtf1\\ansi\\ansicpg1252\\deff0{\\fonttbl{\\f0\\fnil\\fcharset0 Segoe UI;}{\\f1\\fnil\\fcharset0 Consolas;}}",
           "{\\colortbl ;\\red22\\green27\\blue36;\\red47\\green91\\blue216;}", "\\viewkind4\\uc1 "]
    fence = False
    for raw in markdown.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        trimmed = line.lstrip()
        if trimmed.startswith("```"):
            fence = not fence
            continue
        if fence:
            rtf.append("\\pard\\li240\\sa0\\f1\\fs18\\cf2 " + escape(line) + "\\par")
            continue
        if not trimmed:
            rtf.append("\\pard\\sa0\\f0\\fs12\\cf1 \\par")
            continue
        indent = (len(line) - len(trimmed)) // 2 * 360
        heading, bullet, numbered, quote = HEADING.match(trimmed), BULLET.match(trimmed), NUMBERED.match(trimmed), QUOTE.match(trimmed)
        if heading:
            size = {1: 32, 2: 28, 3: 23}.get(len(heading.group(1)), 20)
            rtf.append("\\pard\\sb120\\sa60\\f0\\fs%d\\cf1\\b %s\\b0\\par" % (size, inline(heading.group(2))))
        elif bullet:
            rtf.append("\\pard\\tx%d\\li%d\\fi-300\\sa40\\f0\\fs20\\cf1 \\bullet\\tab %s\\par" % (indent + 300, indent + 300, inline(bullet.group(1))))
        elif numbered:
            rtf.append("\\pard\\tx%d\\li%d\\fi-340\\sa40\\f0\\fs20\\cf1 %s.\\tab %s\\par" % (indent + 340, indent + 340, numbered.group(1), inline(numbered.group(2))))
        elif quote:
            rtf.append("\\pard\\li240\\sa40\\f0\\fs20\\cf1\\i %s\\i0\\par" % inline(quote.group(1)))
        elif RULE.match(trimmed):
            rtf.append("\\pard\\sa40\\f0\\fs20\\cf1 " + "\\u9472?" * 24 + "\\par")
        else:
            rtf.append("\\pard\\sa60\\f0\\fs20\\cf1 " + inline(trimmed) + "\\par")
    rtf.append("}")
    return "".join(rtf)


def changelog_markdown(version):
    """What's new in `version`: the PythonOS and Exports parts of its CHANGELOG section. A version without a section gives a short note."""
    parts = make_core.changelog_parts(version)
    out = [f"## What's new in {version}", ""]
    titles = (("PythonOS", "PythonOS"), ("Exports", "The app and its packages"))
    wrote = False
    for key, title in titles:
        bullets = parts.get(key) or []
        if bullets:
            out += [f"### {title}", ""] + [f"- {b}" for b in bullets] + [""]
            wrote = True
    if not wrote:
        out += ["This release has no notes yet."]
    return "\n".join(out).rstrip() + "\n"


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    text = changelog_markdown(stage.version())
    with open(sys.argv[1], "w", encoding="ascii", newline="\r\n") as f:       # RTF is plain ASCII: everything else is escaped
        f.write(to_rtf(text))
    print(f"Wrote {sys.argv[1]}")


if __name__ == "__main__":
    main()
