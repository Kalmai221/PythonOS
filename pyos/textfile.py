# pyos/textfile.py - read a text file whatever it was written in
#
# Commands used to read every file as UTF-8 and show anything else as question marks: a Notepad file in Windows-1252 ("café" as one byte), a
# UTF-16 file saved by PowerShell, a Latin-1 export from a spreadsheet. decode() works out the encoding: a byte-order mark, then UTF-8, then
# charset-normalizer when it is installed (requests brings it along, so it nearly always is), then Windows-1252 and finally Latin-1, which
# can read any byte. The result is always text; nothing is ever lost or raises.
import codecs

from . import fs, optional

SAMPLE = 512 * 1024            # how much of a big file the detection looks at (the whole file is then read in the encoding it found)
SHORTEST = 8                  # under this many bytes the detector only guesses (UTF-16 for "café"): Windows-1252, the usual answer, is used
BOMS = ((codecs.BOM_UTF8, "utf-8-sig"), (codecs.BOM_UTF32_LE, "utf-32"), (codecs.BOM_UTF32_BE, "utf-32"),
        (codecs.BOM_UTF16_LE, "utf-16"), (codecs.BOM_UTF16_BE, "utf-16"))


def _newlines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n")          # what a text-mode open() gives


def detect(data):
    """The name of the encoding of `data` (bytes)."""
    for bom, name in BOMS:
        if data.startswith(bom):
            return name
    try:
        data.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError as e:
        if e.start >= len(data) - 4 and len(data) > SAMPLE:      # only the end of a cut sample is broken: it is UTF-8
            return "utf-8"
    detector = optional.get("charset_normalizer")
    if detector is not None and len(data) >= SHORTEST:
        try:
            best = detector.from_bytes(data[:SAMPLE]).best()
            # a "UTF-16 or UTF-32 without a byte-order mark" answer is nearly always a mistaken guess about single-byte text
            if best is not None and best.encoding and not best.encoding.lower().replace("-", "_").startswith(("utf_16", "utf_32")):
                return best.encoding
        except Exception:                                     # noqa: BLE001 - a detection problem is never the person's problem
            pass
    try:
        data.decode("cp1252")
        return "cp1252"
    except UnicodeDecodeError:
        return "latin-1"


def decode(data):
    """(text, encoding name) for bytes. Line endings are made plain newlines."""
    name = detect(data[:SAMPLE] if len(data) > SAMPLE else data)
    try:
        text = data.decode(name)
    except (UnicodeDecodeError, LookupError):
        name, text = "utf-8", data.decode("utf-8", errors="replace")
    return _newlines(text), name


def read(name, limit=None):
    """(text, encoding) of a file inside the PythonOS filesystem rules. `limit` is the most bytes to read (None: all)."""
    with open(fs.resolve(name), "rb") as f:
        data = f.read(limit) if limit else f.read()
    return decode(data)


def is_plain(encoding):
    """True for the encodings that need no remark (UTF-8 and ASCII)."""
    return encoding.lower().replace("_", "-") in ("utf-8", "ascii", "us-ascii", "utf-8-sig")
