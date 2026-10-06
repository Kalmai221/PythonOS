#!/usr/bin/env python3
"""Offline checks of the network commands: the DNS packet code, argument parsing and the error-queue reader (no network needed)."""
import importlib.util
import os
import socket
import struct
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, ROOT)


def command(name):
    spec = importlib.util.spec_from_file_location("cmd_" + name, os.path.join(ROOT, "commands", name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    from pyos import dnsquery, netprobe

    packet, ident = dnsquery.build_query("example.com", dnsquery.TYPES["A"], ident=7)
    assert packet[:2] == struct.pack("!H", 7) and packet.endswith(struct.pack("!HH", 1, 1)) and b"\x07example\x03com\x00" in packet

    question = b"\x07example\x03com\x00" + struct.pack("!HH", 1, 1)

    def record(rtype, rdata, name=b"\xc0\x0c", ttl=60):
        return name + struct.pack("!HHIH", rtype, 1, ttl, len(rdata)) + rdata

    mx = struct.pack("!H", 10) + b"\x04mail\xc0\x0c"                              # mail.example.com through a pointer
    txt = bytes([5]) + b"hello" + bytes([3]) + b"you"
    reply = (struct.pack("!HHHHHH", 7, 0x8180, 1, 4, 0, 0) + question + record(1, socket.inet_aton("93.184.216.34")) +
             record(28, socket.inet_pton(socket.AF_INET6, "2606:2800::1")) + record(15, mx) + record(16, txt))
    parsed = dnsquery.parse_response(reply, 7)
    assert parsed["rcode"] == 0
    assert [a[1] for a in parsed["answers"]] == ["A", "AAAA", "MX", "TXT"]
    assert parsed["answers"][0][3] == "93.184.216.34" and parsed["answers"][0][0] == "example.com" and parsed["answers"][0][2] == 60
    assert parsed["answers"][2][3] == "10 mail.example.com" and parsed["answers"][3][3] == "hello you"
    assert dnsquery.parse_response(struct.pack("!HHHHHH", 7, 0x8183, 1, 0, 0, 0) + question, 7)["rcode"] == 3
    for bad in (b"", b"\x00" * 5):
        try:
            dnsquery.parse_response(bad)
            raise AssertionError("a short answer must be refused")
        except ValueError:
            pass
    assert dnsquery.reverse_name("1.2.3.4") == "4.3.2.1.in-addr.arpa"

    nslookup = command("nslookup")
    assert nslookup.parse(["example.com"]) == ("example.com", "A", None)
    assert nslookup.parse(["example.com", "mx", "8.8.8.8"]) == ("example.com", "MX", "8.8.8.8")
    assert nslookup.parse(["1.2.3.4"]) == ("4.3.2.1.in-addr.arpa", "PTR", None)
    assert nslookup.parse([]) is None and nslookup.parse(["a", "nonsense"]) is None

    tracert = command("tracert")
    assert tracert.parse(["example.com"]) == ("example.com", 30) and tracert.parse(["-m", "5", "x.org"]) == ("x.org", 5)
    assert tracert.parse([]) is None and tracert.parse(["-q", "x"]) is None and tracert.parse(["a", "b"]) is None

    ping = command("ping")
    assert ping.parse(["example.com"]) == ("example.com", None, 4, 3.0)
    assert ping.parse(["-c", "9", "-p", "22", "host"]) == ("host", 22, 9, 3.0)
    assert ping.parse(["host:8080"]) == ("host", 8080, 4, 3.0) and ping.parse(["https://example.com/x"]) == ("example.com", 443, 4, 3.0)
    assert ping.parse([]) is None and ping.parse(["a", "b"]) is None and ping.parse(["host:abc"]) is None
    assert ping.summary([10.0, 20.0], 4)[0] == "4 sent, 2 answered, 50% lost" and ping.summary([], 3)[0].endswith("100% lost")

    # the Linux error-queue reader: a "time exceeded" (type 11) from 10.0.0.1, and a "port unreachable" (type 3) from the target
    def extended(icmp_type, who):
        return struct.pack("=IBBBBII", 113, 2, icmp_type, 0, 0, 0, 0) + struct.pack("=H", socket.AF_INET) + struct.pack("!H", 0) + socket.inet_aton(who)
    assert netprobe.parse_errqueue([(socket.SOL_IP, netprobe.IP_RECVERR, extended(11, "10.0.0.1"))]) == (11, "10.0.0.1")
    assert netprobe.parse_errqueue([(socket.SOL_IP, netprobe.IP_RECVERR, extended(3, "1.1.1.1"))]) == (3, "1.1.1.1")
    assert netprobe.parse_errqueue([]) is None
    assert netprobe.checksum(netprobe.echo_packet(1, 1)) == 0

    from unittest import mock
    with mock.patch.object(sys, "platform", "linux"):
        assert [m.__name__ for m in netprobe.methods()] == ["probe_errqueue", "probe_pingsock", "probe_raw"], "Linux and Android try the no-root ways first"
    with mock.patch.object(sys, "platform", "win32"):
        assert [m.__name__ for m in netprobe.methods()] == ["probe_windows", "probe_raw"]

    curl = command("curl")
    assert curl.parse(["example.com"]) == ("https://example.com", False, None) and curl.parse(["-I", "http://x.org"]) == ("http://x.org", True, None)
    assert curl.parse(["-o", "a.html", "x.org"]) == ("https://x.org", False, "a.html") and curl.parse(["ftp://x"]) is None and curl.parse([]) is None
    assert command("wget").file_name("https://x.org/files/a.zip?d=1") == "a.zip" and command("wget").file_name("https://x.org/") == "index.html"
    assert command("whois").valid("example.com") and not command("whois").valid("a;b.com") and not command("whois").valid("nodots")
    assert command("whois").referral("refer:        whois.verisign-grs.com\n") == "whois.verisign-grs.com"
    print("network commands: all checks passed")


if __name__ == "__main__":
    sys.exit(main() or 0)
