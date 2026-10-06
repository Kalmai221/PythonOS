# pyos/filetypes.py - what a file is, from its first bytes (file, cat). Uses filetype when it is installed, else a small table.
import os

from pyos import optional

SIGNATURES = [(b"\x89PNG\r\n\x1a\n", "PNG image"), (b"\xff\xd8\xff", "JPEG image"), (b"GIF8", "GIF image"), (b"%PDF", "PDF document"),
              (b"PK\x03\x04", "ZIP archive (or a document made of one)"), (b"\x7fELF", "Linux program (ELF)"), (b"MZ", "Windows program (EXE or DLL)"),
              (b"\x1f\x8b", "gzip compressed data"), (b"7z\xbc\xaf\x27\x1c", "7-Zip archive"), (b"SQLite format 3", "SQLite database"),
              (b"RIFF", "RIFF media file (WAV, AVI or WebP)"), (b"ID3", "MP3 audio"), (b"OggS", "Ogg audio or video"), (b"BM", "BMP image")]


def describe(head, name=""):
    """What a file is, from its first bytes (and its name when the bytes are plain text). Uses filetype when it is installed."""
    if not head:
        return "empty"
    lib = optional.get("filetype")
    if lib is not None:
        try:
            kind = lib.guess(head)
            if kind is not None:
                return f"{kind.mime} ({kind.extension})"
        except Exception:                                  # noqa: BLE001
            pass
    for magic, label in SIGNATURES:
        if head.startswith(magic):
            return label
    if is_text(head):
        ext = os.path.splitext(name)[1].lower()
        names = {".py": "Python source", ".json": "JSON text", ".md": "Markdown text", ".html": "HTML text", ".js": "JavaScript source", ".csv": "CSV text",
                 ".txt": "plain text", ".sh": "shell script", ".yml": "YAML text", ".yaml": "YAML text", ".xml": "XML text"}
        if head.startswith(b"#!"):
            return "script (starts with #!)"
        return names.get(ext, "text")
    return "binary data"


def is_text(data):
    """True when the bytes look like text: no NUL bytes and mostly printable (or UTF-8)."""
    if b"\0" in data:
        return False
    try:
        data.decode("utf-8")
        return True
    except UnicodeDecodeError:
        printable = sum(1 for b in data if b in (9, 10, 13) or 32 <= b < 127)
        return printable / max(1, len(data)) > 0.85
