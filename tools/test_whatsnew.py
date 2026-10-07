#!/usr/bin/env python3
"""Markdown in "What's new": the RTF page of the Windows installer (whatsnew_rtf.py), and the in-OS update screen (Rich renders the notes
as Markdown). The Kotlin and C# renderers cannot run here; this checks that they exist next to each other and are wired in."""
import io
import json
import os
import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "OS_Export"))

import whatsnew_rtf  # noqa: E402


def main():
    # the RTF: structure and escaping
    rtf = whatsnew_rtf.to_rtf("## What's new in 1.2.3\n\n- `doctor` is **much** more thorough, see [the docs](https://example.com)\n  - nested\n"
                              "1. first\n\n> quoted\n\n```\nraw {x} \\ y\n```\n---\nCafé – {braces} \\ slash\n")
    assert rtf.startswith("{\\rtf1") and rtf.endswith("}")
    depth = 0
    for i, ch in enumerate(rtf):
        if ch == "{" and rtf[i - 1] != "\\":
            depth += 1
        elif ch == "}" and rtf[i - 1] != "\\":
            depth -= 1
        assert depth >= 0, "unbalanced braces in the RTF"
    assert depth == 0, "unbalanced braces in the RTF"
    assert rtf.isascii(), "RTF must be plain ASCII (everything else is escaped)"
    assert "\\b much\\b0 " in rtf.replace("\\b much", "\\b much") or "\\b much\\b0" in rtf
    assert "{\\f1\\fs18\\cf2 doctor}" in rtf, "`code` is set in the code font"
    assert "the docs" in rtf and "https://" not in rtf, "links show their text only"
    assert "\\bullet\\tab" in rtf and "1.\\tab first" in rtf and "\\i quoted\\i0" in rtf
    assert "raw \\{x\\} \\\\ y" in rtf, "code blocks are escaped and shown as written"
    assert "Caf\\u233?" in rtf and "\\u8211?" in rtf and "\\{braces\\}" in rtf and "\\\\ slash" in rtf
    assert rtf.count("\\u9472?") == 24, "a rule is drawn with box characters"

    # the changelog page: this version's parts, as Markdown
    markdown = whatsnew_rtf.changelog_markdown("1.0.12")
    assert markdown.startswith("## What's new in 1.0.12") and "### PythonOS" in markdown and "- " in markdown
    assert "### Apps" not in markdown and "### Website" not in markdown and "### Development" not in markdown, "only what the person gets"
    assert "no notes yet" in whatsnew_rtf.changelog_markdown("0.0.1")
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "w.rtf")
        old = sys.argv
        sys.argv = ["whatsnew_rtf.py", out]
        try:
            whatsnew_rtf.main()
        finally:
            sys.argv = old
        assert Path(out).read_text(encoding="ascii").startswith("{\\rtf1")

    # the in-OS screen: Rich renders the notes as Markdown (bullets, no raw ** or `)
    os.chdir(REPO_ROOT)
    from rich.console import Console
    from core import sysupdate
    with tempfile.TemporaryDirectory() as tmp:
        real_file, real_console = sysupdate.LAST_UPDATE, sysupdate.console
        sysupdate.LAST_UPDATE = Path(tmp) / "last_update.json"
        sysupdate.LAST_UPDATE.write_text(json.dumps({"from": "1.0.11", "to": "1.0.12", "notes": "- `doctor` is **much** more thorough\n- New `sudo`",
                                                      "changed": ["a.py"]}), encoding="utf-8")
        buffer = io.StringIO()
        sysupdate.console = Console(file=buffer, width=80, force_terminal=False)
        try:
            assert sysupdate.show_whats_new(force=True) is True
        finally:
            sysupdate.console, sysupdate.LAST_UPDATE = real_console, real_file
        shown = buffer.getvalue()
        assert "What's new in PythonOS" in shown and "doctor is much more thorough" in shown and "New sudo" in shown, shown
        assert "**" not in shown and "`" not in shown, "the Markdown marks are not shown"
        assert re.search(r"[•*-]\s+New sudo", shown) or "•" in shown

    # the three installers are wired to their renderer
    root = Path(REPO_ROOT, "OS_Export")
    installer = root / "Android" / "installer" / "src" / "main" / "java" / "com" / "pythonos" / "installer"
    app = root / "Android" / "app" / "src" / "main" / "java" / "com" / "pythonos" / "app"
    assert "Markdown.render" in (installer / "MainActivity.kt").read_text(encoding="utf-8")
    assert (installer / "Markdown.kt").is_file() and (app / "Markdown.kt").is_file()
    assert "Markdown.render" in (app / "Sheet.kt").read_text(encoding="utf-8") and "sheet.markdown(" in (app / "MainActivity.kt").read_text(encoding="utf-8")
    setup = root / "Windows" / "native" / "setup"
    assert "Markdown.ToRtf" in (setup / "Ui.cs").read_text(encoding="utf-8") and "Markdown.WhatsNew" in (setup / "Core.cs").read_text(encoding="utf-8")
    assert "InfoBeforeFile" in (root / "Windows" / "PythonOS.iss").read_text(encoding="utf-8")
    assert "whatsnew_rtf.py" in (root / "Windows" / "build.ps1").read_text(encoding="utf-8")
    print("what's new: all checks passed")


if __name__ == "__main__":
    main()
