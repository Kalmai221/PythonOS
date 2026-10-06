# pyos/dnsquery.py - a small DNS client (A, AAAA, MX, NS, TXT, CNAME, PTR, SOA) for the nslookup command, standard library only.
import random
import re
import socket
import struct

TYPES = {"A": 1, "NS": 2, "CNAME": 5, "SOA": 6, "PTR": 12, "MX": 15, "TXT": 16, "AAAA": 28}
NAMES = {v: k for k, v in TYPES.items()}
RCODES = {0: "ok", 1: "malformed query", 2: "server failure", 3: "no such name", 4: "not implemented", 5: "refused"}


def default_server():
    """The first nameserver of the system, else a public one."""
    try:
        with open("/etc/resolv.conf", encoding="utf-8") as f:
            for line in f:
                match = re.match(r"\s*nameserver\s+(\S+)", line)
                if match and ":" not in match.group(1):
                    return match.group(1)
    except OSError:
        pass
    return "1.1.1.1"


def build_query(name, qtype, ident=None):
    ident = random.randrange(65536) if ident is None else ident
    packet = struct.pack("!HHHHHH", ident, 0x0100, 1, 0, 0, 0)
    for label in name.rstrip(".").split("."):
        raw = label.encode("idna")
        if not 0 < len(raw) < 64:
            raise ValueError("a name part must be 1 to 63 characters")
        packet += bytes([len(raw)]) + raw
    return packet + b"\0" + struct.pack("!HH", qtype, 1), ident


def read_name(data, offset):
    """(name, offset after it) with compression pointers followed."""
    labels, jumped, end, guard = [], False, offset, 0
    while True:
        guard += 1
        if guard > 100 or offset >= len(data):
            raise ValueError("bad name in the answer")
        length = data[offset]
        if length == 0:
            offset += 1
            break
        if length & 0xC0 == 0xC0:
            if not jumped:
                end = offset + 2
            offset = ((length & 0x3F) << 8) | data[offset + 1]
            jumped = True
            continue
        labels.append(data[offset + 1:offset + 1 + length].decode("ascii", "replace"))
        offset += 1 + length
    return ".".join(labels), (end if jumped else offset)


def parse_response(data, ident=None):
    """{'rcode', 'answers': [(name, type name, ttl, text)]} from a DNS reply."""
    if len(data) < 12:
        raise ValueError("the answer is too short")
    got, flags, questions, answers = struct.unpack("!HHHH", data[:8])
    if ident is not None and got != ident:
        raise ValueError("the answer is for another question")
    offset = 12
    for _ in range(questions):
        _name, offset = read_name(data, offset)
        offset += 4
    found = []
    for _ in range(answers):
        name, offset = read_name(data, offset)
        rtype, _cls, ttl, length = struct.unpack("!HHIH", data[offset:offset + 10])
        offset += 10
        rdata, text = data[offset:offset + length], ""
        if rtype == 1 and length == 4:
            text = socket.inet_ntoa(rdata)
        elif rtype == 28 and length == 16:
            text = socket.inet_ntop(socket.AF_INET6, rdata)
        elif rtype in (2, 5, 12):
            text = read_name(data, offset)[0]
        elif rtype == 15:
            text = f"{struct.unpack('!H', rdata[:2])[0]} {read_name(data, offset + 2)[0]}"
        elif rtype == 16:
            parts, i = [], 0
            while i < len(rdata):
                parts.append(rdata[i + 1:i + 1 + rdata[i]].decode("utf-8", "replace"))
                i += 1 + rdata[i]
            text = " ".join(parts)
        elif rtype == 6:
            primary, after = read_name(data, offset)
            admin, after = read_name(data, after)
            serial = struct.unpack("!I", data[after:after + 4])[0]
            text = f"{primary} {admin} serial {serial}"
        else:
            text = f"({len(rdata)} bytes)"
        found.append((name, NAMES.get(rtype, str(rtype)), ttl, text))
        offset += length
    return {"rcode": flags & 0x0F, "answers": found}


def reverse_name(address):
    return ".".join(reversed(address.split("."))) + ".in-addr.arpa"


def query(name, qtype="A", server=None, timeout=4):
    """Ask `server` (UDP, port 53) and return parse_response(). Raises OSError when nothing answers."""
    packet, ident = build_query(name, TYPES[qtype])
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(packet, (server or default_server(), 53))
        data, _ = sock.recvfrom(4096)
    return parse_response(data, ident)
