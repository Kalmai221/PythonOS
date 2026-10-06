# pyos/netprobe.py - the network probes the tracert command needs: one probe at a given TTL, three ways to make it.
#
#   windows   the IcmpSendEcho call of the system (iphlpapi), which needs no administrator rights
#   errqueue  Linux: a UDP probe whose "time exceeded" answers are read from the socket's error queue, which needs no root
#   raw       a raw ICMP socket (root on Linux and the ISO, administrator on Windows), the fallback
# probe(address, ttl, timeout) -> ("hop", address, ms) | ("done", address, ms) | ("timeout", None, None)
import os
import select
import socket
import struct
import sys
import time

IP_RECVERR = 11            # Linux
MSG_ERRQUEUE = 0x2000


def checksum(data):
    if len(data) % 2:
        data += b"\0"
    total = sum(struct.unpack("!%dH" % (len(data) // 2), data))
    total = (total >> 16) + (total & 0xFFFF)
    total += total >> 16
    return ~total & 0xFFFF


def echo_packet(ident, sequence):
    header = struct.pack("!BBHHH", 8, 0, 0, ident, sequence)
    payload = b"pythonos-tracert-probe-0123456789"
    return struct.pack("!BBHHH", 8, 0, checksum(header + payload), ident, sequence) + payload


# ----------------------------------------------------------------------------------------- Windows
def probe_windows(address, ttl, timeout):
    import ctypes
    from ctypes import wintypes
    iphlpapi = ctypes.WinDLL("iphlpapi")

    class Options(ctypes.Structure):
        _fields_ = [("Ttl", ctypes.c_ubyte), ("Tos", ctypes.c_ubyte), ("Flags", ctypes.c_ubyte), ("OptionsSize", ctypes.c_ubyte), ("OptionsData", ctypes.c_void_p)]

    class Reply(ctypes.Structure):
        _fields_ = [("Address", ctypes.c_uint32), ("Status", ctypes.c_uint32), ("RoundTripTime", ctypes.c_uint32), ("DataSize", ctypes.c_ushort),
                    ("Reserved", ctypes.c_ushort), ("Data", ctypes.c_void_p), ("Options", Options)]

    iphlpapi.IcmpCreateFile.restype = wintypes.HANDLE
    iphlpapi.IcmpSendEcho.argtypes = [wintypes.HANDLE, ctypes.c_uint32, ctypes.c_char_p, ctypes.c_ushort, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32]
    iphlpapi.IcmpSendEcho.restype = ctypes.c_uint32
    iphlpapi.IcmpCloseHandle.argtypes = [wintypes.HANDLE]
    handle = iphlpapi.IcmpCreateFile()
    if not handle or handle == ctypes.c_void_p(-1).value:
        raise OSError("the system could not open an ICMP handle")
    try:
        payload = b"pythonos-tracert"
        options = Options(ttl, 0, 0, 0, None)
        buffer = ctypes.create_string_buffer(ctypes.sizeof(Reply) + len(payload) + 8)
        destination = struct.unpack("<I", socket.inet_aton(address))[0]
        start = time.perf_counter()
        count = iphlpapi.IcmpSendEcho(handle, destination, payload, len(payload), ctypes.byref(options), buffer, len(buffer), int(timeout * 1000))
        took = (time.perf_counter() - start) * 1000
        if not count:
            return ("timeout", None, None)
        reply = Reply.from_buffer(buffer)
        who = socket.inet_ntoa(struct.pack("<I", reply.Address))
        if reply.Status == 0:
            return ("done", who, float(reply.RoundTripTime) or took)
        if reply.Status == 11013:                       # IP_TTL_EXPIRED_TRANSIT
            return ("hop", who, float(reply.RoundTripTime) or took)
        return ("timeout", None, None)
    finally:
        iphlpapi.IcmpCloseHandle(handle)


# ----------------------------------------------------------------------------------------- Linux, no root
def parse_errqueue(ancillary):
    """(icmp type, offender address) from the ancillary data of recvmsg(MSG_ERRQUEUE), or None."""
    for level, kind, data in ancillary:
        if level == socket.SOL_IP and kind == IP_RECVERR and len(data) >= 20:
            origin, icmp_type = data[4], data[5]
            if origin == 2:                             # SO_EE_ORIGIN_ICMP
                return icmp_type, socket.inet_ntoa(data[20:24])
    return None


def probe_errqueue(address, ttl, timeout):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.IPPROTO_IP, IP_RECVERR, 1)
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
        sock.setblocking(False)
        start = time.perf_counter()
        sock.sendto(b"pythonos", (address, 33434 + ttl))
        deadline = start + timeout
        while True:
            left = deadline - time.perf_counter()
            if left <= 0:
                return ("timeout", None, None)
            ready, _, errors = select.select([sock], [], [sock], left)
            if not ready and not errors:
                return ("timeout", None, None)
            try:
                _data, ancillary, _flags, _addr = sock.recvmsg(512, 512, MSG_ERRQUEUE)
            except BlockingIOError:
                continue
            found = parse_errqueue(ancillary)
            took = (time.perf_counter() - start) * 1000
            if found is None:
                continue
            icmp_type, who = found
            if icmp_type == 11:
                return ("hop", who, took)
            return ("done", who, took)                   # destination unreachable / port unreachable: the target answered
    finally:
        sock.close()


# ----------------------------------------------------------------------------------------- raw ICMP
def probe_raw(address, ttl, timeout, ident=None, sequence=1):
    ident = ident or (os.getpid() & 0xFFFF)
    sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
        start = time.perf_counter()
        sock.sendto(echo_packet(ident, sequence), (address, 0))
        deadline = start + timeout
        while True:
            left = deadline - time.perf_counter()
            if left <= 0:
                return ("timeout", None, None)
            ready, _, _ = select.select([sock], [], [], left)
            if not ready:
                return ("timeout", None, None)
            data, (who, _port) = sock.recvfrom(1024)
            took = (time.perf_counter() - start) * 1000
            header = (data[0] & 0x0F) * 4
            icmp = data[header:]
            if len(icmp) < 8:
                continue
            kind = icmp[0]
            if kind == 0 and struct.unpack("!H", icmp[4:6])[0] == ident:
                return ("done", who, took)
            if kind == 11 and len(icmp) >= 36:          # time exceeded: it holds the start of our packet
                inner = icmp[8:]
                inner_header = (inner[0] & 0x0F) * 4
                if struct.unpack("!H", inner[inner_header + 4:inner_header + 6])[0] == ident:
                    return ("hop", who, took)
    finally:
        sock.close()


# ----------------------------------------------------------------------------------------- Android and Linux "ping sockets"
def probe_pingsock(address, ttl, timeout, ident=None, sequence=1):
    """An ICMP echo sent from an unprivileged "ping socket" (SOCK_DGRAM + IPPROTO_ICMP), which Linux and Android let ordinary programs use. The
    router that drops the packet at its TTL answers "time exceeded", which comes back through the socket's error queue; the target answers with
    an echo reply. Needs no root."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)
        try:
            sock.setsockopt(socket.IPPROTO_IP, IP_RECVERR, 1)
        except OSError:
            pass                                                   # without it only the target's own answer can be seen
        sock.setblocking(False)
        start = time.perf_counter()
        sock.sendto(echo_packet(ident or (os.getpid() & 0xFFFF), sequence), (address, 0))
        deadline = start + timeout
        while True:
            left = deadline - time.perf_counter()
            if left <= 0:
                return ("timeout", None, None)
            ready, _, _ = select.select([sock], [], [sock], left)
            if not ready:
                return ("timeout", None, None)
            try:
                data, (who, _port) = sock.recvfrom(1024)
                took = (time.perf_counter() - start) * 1000
                if data and data[0] == 0:                          # echo reply: the target itself
                    return ("done", who, took)
                continue
            except BlockingIOError:
                pass
            except OSError:
                pass                                               # an error is waiting in the error queue
            try:
                _data, ancillary, _flags, _addr = sock.recvmsg(512, 512, MSG_ERRQUEUE)
            except (BlockingIOError, OSError):
                continue
            found = parse_errqueue(ancillary)
            took = (time.perf_counter() - start) * 1000
            if found is None:
                continue
            icmp_type, who = found
            return ("hop" if icmp_type == 11 else "done", who, took)
    finally:
        sock.close()


def methods():
    """The probe functions to try, best first, for this system."""
    if sys.platform == "win32":
        return [probe_windows, probe_raw]
    if sys.platform.startswith("linux"):
        return [probe_errqueue, probe_pingsock, probe_raw]
    return [probe_raw]
