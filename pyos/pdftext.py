# pyos/pdftext.py - plain text to a small PDF, so text files can be printed on printers that only accept PDF/PWG
# (driverless IPP printers). Courier 10 pt, A4, 60 lines of up to 90 characters per page.
LINES_PER_PAGE = 60
WIDTH = 90
FONT = 10
LEADING = 12
LEFT, TOP = 50, 800


def _escape(text):
    bs = chr(92)
    return text.replace(bs, bs + bs).replace("(", bs + "(").replace(")", bs + ")")


def wrap(text):
    """Split text into display lines (tabs to spaces, long lines wrapped, non-Latin-1 characters replaced)."""
    lines = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").expandtabs(4).split("\n"):
        raw = raw.encode("latin-1", "replace").decode("latin-1")
        while len(raw) > WIDTH:
            lines.append(raw[:WIDTH])
            raw = raw[WIDTH:]
        lines.append(raw)
    return lines


def make_pdf(text):
    """Returns the bytes of a PDF containing the text."""
    lines = wrap(text) or [""]
    pages = [lines[i:i + LINES_PER_PAGE] for i in range(0, len(lines), LINES_PER_PAGE)]
    objects = []                                   # object bodies, numbered from 1

    def add(body):
        objects.append(body)
        return len(objects)

    catalog = add(b"")                             # placeholders filled in below
    pages_obj = add(b"")
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")
    kids = []
    for page in pages:
        stream = [f"BT /F1 {FONT} Tf {LEADING} TL {LEFT} {TOP} Td"]
        for line in page:
            stream.append(f"({_escape(line)}) '")
        stream.append("ET")
        data = "\n".join(stream).encode("latin-1", "replace")
        content = add(b"<< /Length " + str(len(data)).encode() + b" >>\nstream\n" + data + b"\nendstream")
        kids.append(add(f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 595 842] /Contents {content} 0 R "
                        f"/Resources << /Font << /F1 {font} 0 R >> >> >>".encode()))
    objects[catalog - 1] = f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode()
    objects[pages_obj - 1] = (f"<< /Type /Pages /Count {len(kids)} /Kids [" + " ".join(f"{k} 0 R" for k in kids) + "] >>").encode()

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode() + b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)
