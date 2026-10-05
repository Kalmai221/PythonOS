#!/usr/bin/env python3
"""QR code generator, written in plain Python (no libraries). Turn text, a web address, Wi-Fi details or a contact into a QR code you can
scan with a phone. Usage: qr <text>  |  qr wifi <name> <password>  |  qr --svg file.svg <text>  (no arguments opens a menu).
Options: --level L|M|Q|H (error correction; default M). Handles up to about 200 characters."""
import sys

from rich.console import Console
from rich.prompt import Prompt
from rich.text import Text

try:
    from pyos import fs
except ImportError:
    fs = None

console = Console()

# ---------------------------------------------------------------- tables
# version -> level -> (ec codewords per block, [(block count, data codewords per block), ...])
BLOCKS = {
    1: {"L": (7, [(1, 19)]), "M": (10, [(1, 16)]), "Q": (13, [(1, 13)]), "H": (17, [(1, 9)])},
    2: {"L": (10, [(1, 34)]), "M": (16, [(1, 28)]), "Q": (22, [(1, 22)]), "H": (28, [(1, 16)])},
    3: {"L": (15, [(1, 55)]), "M": (26, [(1, 44)]), "Q": (18, [(2, 17)]), "H": (22, [(2, 13)])},
    4: {"L": (20, [(1, 80)]), "M": (18, [(2, 32)]), "Q": (26, [(2, 24)]), "H": (16, [(4, 9)])},
    5: {"L": (26, [(1, 108)]), "M": (24, [(2, 43)]), "Q": (18, [(2, 15), (2, 16)]), "H": (22, [(2, 11), (2, 12)])},
    6: {"L": (18, [(2, 68)]), "M": (16, [(4, 27)]), "Q": (24, [(4, 19)]), "H": (28, [(4, 15)])},
    7: {"L": (20, [(2, 78)]), "M": (18, [(4, 31)]), "Q": (18, [(2, 14), (4, 15)]), "H": (26, [(4, 13), (1, 14)])},
    8: {"L": (24, [(2, 97)]), "M": (22, [(2, 38), (2, 39)]), "Q": (22, [(4, 18), (2, 19)]), "H": (26, [(4, 14), (2, 15)])},
    9: {"L": (30, [(2, 116)]), "M": (22, [(3, 36), (2, 37)]), "Q": (20, [(4, 16), (4, 17)]), "H": (24, [(4, 12), (4, 13)])},
    10: {"L": (18, [(2, 68), (2, 69)]), "M": (26, [(4, 43), (1, 44)]), "Q": (24, [(6, 19), (2, 20)]), "H": (28, [(6, 15), (2, 16)])},
}
ALIGNMENT = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50]}
LEVEL_BITS = {"L": 1, "M": 0, "Q": 3, "H": 2}


class QRError(ValueError):
    pass


# ------------------------------------------------------- Reed-Solomon maths
EXP, LOG = [0] * 512, [0] * 256
_x = 1
for _i in range(255):
    EXP[_i] = _x
    LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    EXP[_i] = EXP[_i - 255]


def gf_mul(a, b):
    return 0 if a == 0 or b == 0 else EXP[LOG[a] + LOG[b]]


def rs_generator(degree):
    poly = [1]
    for i in range(degree):
        nxt = [0] * (len(poly) + 1)
        for j, coef in enumerate(poly):
            nxt[j] ^= coef
            nxt[j + 1] ^= gf_mul(coef, EXP[i])
        poly = nxt
    return poly


def rs_remainder(data, degree):
    gen = rs_generator(degree)
    rem = [0] * degree
    for byte in data:
        factor = byte ^ rem[0]
        rem = rem[1:] + [0]
        for i in range(degree):
            rem[i] ^= gf_mul(gen[i + 1], factor)
    return rem


# ------------------------------------------------------------- encoding
def data_capacity(version, level):
    ec, groups = BLOCKS[version][level]
    return sum(n * d for n, d in groups)


def choose_version(length, level):
    for version in range(1, 11):
        header = 4 + (8 if version < 10 else 16)
        if (header + 8 * length + 7) // 8 <= data_capacity(version, level):
            return version
    raise QRError("That is too long for this QR generator (about 200 characters at most; try a lower error-correction level).")


def make_codewords(data, version, level):
    """Byte-mode bit stream, padded, split into blocks with error correction, interleaved."""
    capacity = data_capacity(version, level)
    bits = "0100" + format(len(data), "08b" if version < 10 else "016b") + "".join(format(b, "08b") for b in data)
    bits += "0" * min(4, capacity * 8 - len(bits))
    bits += "0" * (-len(bits) % 8)
    words = [int(bits[i:i + 8], 2) for i in range(0, len(bits), 8)]
    pad = [0xEC, 0x11]
    while len(words) < capacity:
        words.append(pad[(len(words) - len(bits) // 8) % 2])
    ec_len, groups = BLOCKS[version][level]
    blocks, pos = [], 0
    for count, size in groups:
        for _ in range(count):
            blocks.append(words[pos:pos + size])
            pos += size
    ecs = [rs_remainder(b, ec_len) for b in blocks]
    out = []
    for i in range(max(len(b) for b in blocks)):
        out += [b[i] for b in blocks if i < len(b)]
    for i in range(ec_len):
        out += [e[i] for e in ecs]
    return out


# ------------------------------------------------------------- the matrix
def bch(value, poly, bits):
    """Remainder-style BCH encoding used for the format and version information."""
    shift = poly.bit_length() - 1
    v = value << shift
    for i in range(v.bit_length() - 1, shift - 1, -1):
        if v >> i & 1:
            v ^= poly << (i - shift)
    return (value << shift) | v


def build(version, level, codewords, mask):
    size = 17 + 4 * version
    m = [[None] * size for _ in range(size)]          # None = not yet set; True/False once set
    reserved = [[False] * size for _ in range(size)]

    def put(r, c, dark, reserve=True):
        if 0 <= r < size and 0 <= c < size:
            m[r][c] = dark
            if reserve:
                reserved[r][c] = True

    def finder(r0, c0):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                r, c = r0 + dr, c0 + dc
                if not (0 <= r < size and 0 <= c < size):
                    continue
                dark = 0 <= dr <= 6 and 0 <= dc <= 6 and (dr in (0, 6) or dc in (0, 6) or (2 <= dr <= 4 and 2 <= dc <= 4))
                put(r, c, dark)

    finder(0, 0)
    finder(0, size - 7)
    finder(size - 7, 0)
    pos = ALIGNMENT[version]
    for r in pos:
        for c in pos:
            if (r, c) in ((6, 6), (6, pos[-1]), (pos[-1], 6)):
                continue                                      # those would sit on top of a finder pattern
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    put(r + dr, c + dc, max(abs(dr), abs(dc)) != 1)
    for i in range(8, size - 8):                       # timing patterns
        put(6, i, i % 2 == 0)
        put(i, 6, i % 2 == 0)
    put(size - 8, 8, True)                             # the always-dark module
    for i in range(9):                                 # reserve the format information areas
        reserved[8][i] = reserved[i][8] = True
    for i in range(8):
        reserved[8][size - 1 - i] = reserved[size - 1 - i][8] = True
    if version >= 7:
        info = bch(version, 0x1F25, 18)
        for i in range(18):
            dark = bool(info >> i & 1)
            put(i // 3, size - 11 + i % 3, dark)
            put(size - 11 + i % 3, i // 3, dark)

    # place the data bits in the zig-zag order, skipping the vertical timing column
    bits = [b for cw in codewords for b in format(cw, "08b")]
    index, upward, c = 0, True, size - 1
    while c > 0:
        if c == 6:
            c -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for r in rows:
            for cc in (c, c - 1):
                if not reserved[r][cc]:
                    bit = bits[index] == "1" if index < len(bits) else False
                    index += 1
                    m[r][cc] = bit ^ mask_bit(mask, r, cc)
        upward = not upward
        c -= 2

    # format information: two copies of the 15 bits (level + mask, protected by a BCH code)
    fmt = bch(LEVEL_BITS[level] << 3 | mask, 0x537, 15) ^ 0x5412
    for i in range(15):
        dark = bool(fmt >> i & 1)
        if i < 6:
            m[i][8] = dark
        elif i == 6:
            m[7][8] = dark
        elif i == 7:
            m[8][8] = dark
        elif i == 8:
            m[8][7] = dark
        else:
            m[8][14 - i] = dark
        if i < 8:
            m[8][size - 1 - i] = dark
        else:
            m[size - 15 + i][8] = dark
    m[size - 8][8] = True
    return [[bool(v) for v in row] for row in m]


def mask_bit(mask, r, c):
    return [(r + c) % 2 == 0, r % 2 == 0, c % 3 == 0, (r + c) % 3 == 0, (r // 2 + c // 3) % 2 == 0,
            (r * c) % 2 + (r * c) % 3 == 0, ((r * c) % 2 + (r * c) % 3) % 2 == 0, ((r + c) % 2 + (r * c) % 3) % 2 == 0][mask]


def penalty(m):
    size = len(m)
    score = 0
    for grid in (m, [list(col) for col in zip(*m)]):
        for row in grid:
            run, prev = 1, row[0]
            for v in row[1:]:
                if v == prev:
                    run += 1
                else:
                    score += run - 2 if run >= 5 else 0
                    run, prev = 1, v
            score += run - 2 if run >= 5 else 0
            s = "".join("1" if v else "0" for v in row)
            score += 40 * (s.count("10111010000") + s.count("00001011101"))
    for r in range(size - 1):
        for c in range(size - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    dark = sum(v for row in m for v in row)
    score += 10 * (abs(dark * 20 - size * size * 10) // (size * size))
    return score


def make_qr(text, level="M", version=None, mask=None):
    """The QR code for `text` as a square list of lists of booleans (True = dark module)."""
    data = text.encode("utf-8")
    if level not in LEVEL_BITS:
        raise QRError("Error-correction level must be L, M, Q or H.")
    version = version or choose_version(len(data), level)
    codewords = make_codewords(data, version, level)
    if mask is not None:
        return build(version, level, codewords, mask)
    best = min((build(version, level, codewords, k) for k in range(8)), key=penalty)
    return best


# ----------------------------------------------------------------- output
def render(matrix, border=2):
    size = len(matrix) + 2 * border
    out = Text()
    for r in range(size):
        for c in range(size):
            rr, cc = r - border, c - border
            dark = 0 <= rr < len(matrix) and 0 <= cc < len(matrix) and matrix[rr][cc]
            out.append("  ", style="on black" if dark else "on white")
        out.append("\n")
    return out


def to_svg(matrix, border=4, scale=8):
    size = len(matrix) + 2 * border
    rects = "".join(f'<rect x="{(c + border) * scale}" y="{(r + border) * scale}" width="{scale}" height="{scale}"/>'
                    for r, row in enumerate(matrix) for c, v in enumerate(row) if v)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size * scale}" height="{size * scale}" viewBox="0 0 {size * scale} {size * scale}">'
            f'<rect width="100%" height="100%" fill="white"/><g fill="black">{rects}</g></svg>\n')


def escape_wifi(value):
    for ch in "\\;,:\"":
        value = value.replace(ch, "\\" + ch)
    return value


def wifi_text(ssid, password, security="WPA"):
    return f"WIFI:T:{security if password else 'nopass'};S:{escape_wifi(ssid)};" + (f"P:{escape_wifi(password)};" if password else "") + ";"


def show(text, level="M", svg=None):
    try:
        matrix = make_qr(text, level)
    except QRError as e:
        console.print(f"[red]{e}[/red]")
        return False
    console.print(render(matrix), end="")
    console.print(f"[dim]{len(matrix)}x{len(matrix)} modules, error correction {level}. Scan it with your phone's camera.[/dim]")
    if svg:
        try:
            path = fs.resolve(svg, write=True) if fs else svg
            with open(path, "w", encoding="utf-8") as f:
                f.write(to_svg(matrix))
            console.print(f"[green]Saved {svg}[/green]")
        except (OSError, PermissionError) as e:
            console.print(f"[red]Could not save: {e}[/red]")
    return True


def main(args):
    level, svg = "M", None
    for flag in ("--level", "--svg"):
        if flag in args:
            i = args.index(flag)
            if i + 1 >= len(args):
                console.print(f"[red]{flag} needs a value[/red]")
                return
            value = args[i + 1]
            del args[i:i + 2]
            if flag == "--level":
                level = value.upper()
            else:
                svg = value
    if args and args[0] == "wifi" and len(args) >= 2:
        show(wifi_text(args[1], args[2] if len(args) > 2 else ""), level, svg)
        return
    if args:
        show(" ".join(args), level, svg)
        return
    while True:
        kind = Prompt.ask("QR for: (t)ext or web address, (w)i-fi, (p)hone number, (e)mail, (q)uit", choices=["t", "w", "p", "e", "q"], default="t")
        if kind == "q":
            return
        if kind == "t":
            text = Prompt.ask("Text or address")
        elif kind == "w":
            text = wifi_text(Prompt.ask("Network name"), Prompt.ask("Password (blank for an open network)", password=True, default=""))
        elif kind == "p":
            text = "tel:" + Prompt.ask("Phone number").replace(" ", "")
        else:
            text = "mailto:" + Prompt.ask("Email address").strip()
        show(text, level, svg)


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
