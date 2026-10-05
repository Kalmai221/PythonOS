#!/usr/bin/env python3
"""Network tools: check your connection, look up names (A, AAAA, MX, TXT, NS, CNAME records), test a port, time a web page, trace the
path to a host, keep a list of saved hosts with a watchlist, and run an uptime monitor that notifies you when a host goes down or comes back.
Usage: nettools  (menu)  |  check  |  ip  |  lookup <name> [A|AAAA|MX|TXT|NS|CNAME]  |  port <host> <port>  |  web <address>  |  ping <host>
|  trace <host>  |  hosts  |  hosts add <host> [port]  |  hosts remove <host>  |  watch  |  monitor on|off|status|check"""
import random
import socket
import ssl
import statistics
import struct
import sys
import time

import requests
from rich.console import Console
from rich.markup import escape
from rich.prompt import Prompt
from rich.table import Table

try:
    from pyos import appdata, notify, scheduler
    import pyos
except ImportError:
    appdata = notify = scheduler = pyos = None

console = Console()
COMMON_PORTS = {22: "SSH", 25: "SMTP", 53: "DNS", 80: "HTTP", 110: "POP3", 143: "IMAP", 443: "HTTPS", 465: "SMTPS",
                587: "SMTP (submission)", 993: "IMAPS", 3306: "MySQL", 5432: "PostgreSQL", 8080: "HTTP (alt)"}
RECORD_TYPES = {"A": 1, "NS": 2, "CNAME": 5, "MX": 15, "TXT": 16, "AAAA": 28}
TYPE_NAMES = {v: k for k, v in RECORD_TYPES.items()}
MONITOR_COMMAND = "run nettools monitor check"


# ------------------------------------------------------------- basics
def local_address():
    """The address this device uses on its network (no traffic is sent)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            return s.getsockname()[0]
    except OSError:
        return "unknown"


def connect_time(host, port, timeout=3.0):
    """Milliseconds to open a TCP connection, or None."""
    start = time.perf_counter()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return (time.perf_counter() - start) * 1000
    except OSError:
        return None


def check_connection():
    table = Table(title="Connection check", header_style="bold blue")
    table.add_column("Check")
    table.add_column("Result")
    table.add_row("Local address", local_address())
    for label, host, port in (("Internet (1.1.1.1:53)", "1.1.1.1", 53), ("Internet (8.8.8.8:53)", "8.8.8.8", 53)):
        ms = connect_time(host, port)
        table.add_row(label, f"[green]reachable, {ms:.0f} ms[/green]" if ms is not None else "[red]unreachable[/red]")
    try:
        ip = socket.gethostbyname("example.com")
        table.add_row("DNS (example.com)", f"[green]works ({ip})[/green]")
    except OSError:
        table.add_row("DNS (example.com)", "[red]failed - names do not resolve[/red]")
    console.print(table)


def port_check(host, port):
    ms = connect_time(host, port)
    service = COMMON_PORTS.get(port, "")
    console.print(f"{escape(host)}:{port} {f'({service}) ' if service else ''}-> "
                  + (f"[bold green]open[/bold green] ({ms:.0f} ms)" if ms is not None else "[bold red]closed or filtered[/bold red]"))


def tcp_ping(host, port=443, count=4):
    times = []
    for i in range(count):
        ms = connect_time(host, port)
        console.print(f"  {i + 1}: " + (f"{ms:.0f} ms" if ms is not None else "[red]no reply[/red]"))
        if ms is not None:
            times.append(ms)
        time.sleep(0.4)
    if times:
        console.print(f"[bold]{len(times)}/{count} replies[/bold], min {min(times):.0f} / avg {statistics.mean(times):.0f} / max {max(times):.0f} ms")
    else:
        console.print("[red]No replies.[/red]")


def web_check(url):
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    start = time.perf_counter()
    try:
        response = requests.get(url, timeout=10, headers={"User-Agent": "PythonOS-nettools/2.0"}, allow_redirects=True)
    except requests.RequestException as e:
        console.print(f"[red]Could not reach {escape(url)}: {escape(str(e)[:100])}[/red]")
        return
    elapsed = (time.perf_counter() - start) * 1000
    colour = "green" if response.ok else "red"
    console.print(f"[{colour}]{response.status_code} {escape(response.reason or '')}[/{colour}] in {elapsed:.0f} ms, "
                  f"{len(response.content) / 1024:.1f} KB" + (f", redirected to {escape(response.url)}" if response.history else ""))
    for header in ("server", "content-type", "last-modified"):
        if header in response.headers:
            console.print(f"  [dim]{header}:[/dim] {escape(response.headers[header])}")


def public_address():
    for url in ("https://api.ipify.org", "https://ifconfig.me/ip"):
        try:
            text = requests.get(url, timeout=6).text.strip()
            if text and len(text) < 50:
                console.print(f"Public address: [bold]{escape(text)}[/bold]   [dim](local: {local_address()})[/dim]")
                return
        except requests.RequestException:
            continue
    console.print("[red]Could not find the public address (are you online?).[/red]")


# ------------------------------------------------------------ DNS records
def resolvers():
    found = []
    try:
        with open("/etc/resolv.conf", encoding="utf-8") as f:
            found = [line.split()[1] for line in f if line.startswith("nameserver") and len(line.split()) > 1]
    except OSError:
        pass
    return [r for r in found if ":" not in r][:2] + ["1.1.1.1", "8.8.8.8"]


def build_query(name, rtype, query_id=None):
    query_id = query_id if query_id is not None else random.randrange(65536)
    header = struct.pack(">HHHHHH", query_id, 0x0100, 1, 0, 0, 0)
    question = b"".join(struct.pack("B", len(p)) + p.encode("idna") for p in name.strip(".").split(".")) + b"\x00"
    return query_id, header + question + struct.pack(">HH", RECORD_TYPES[rtype], 1)


def read_name(data, pos):
    """DNS name at pos (following compression pointers). Returns (name, position after it)."""
    labels, jumped, end = [], False, pos
    for _ in range(128):
        length = data[pos]
        if length == 0:
            pos += 1
            break
        if length & 0xC0 == 0xC0:
            pointer = ((length & 0x3F) << 8) | data[pos + 1]
            if not jumped:
                end = pos + 2
            pos, jumped = pointer, True
            continue
        labels.append(data[pos + 1:pos + 1 + length].decode("ascii", "replace"))
        pos += 1 + length
    return ".".join(labels), (end if jumped else pos)


def parse_response(data, query_id):
    """[(type name, ttl, text)] from a DNS answer; raises ValueError on a malformed or mismatched reply."""
    if len(data) < 12 or struct.unpack(">H", data[:2])[0] != query_id:
        raise ValueError("the reply did not match the question")
    flags, qd, an = struct.unpack(">HHH", data[2:8])
    if flags & 0xF == 3:
        return []                                       # NXDOMAIN: the name does not exist
    pos = 12
    for _ in range(qd):
        _, pos = read_name(data, pos)
        pos += 4
    answers = []
    for _ in range(an):
        _, pos = read_name(data, pos)
        rtype, _cls, ttl, rdlen = struct.unpack(">HHIH", data[pos:pos + 10])
        pos += 10
        rdata = data[pos:pos + rdlen]
        if rtype == 1 and rdlen == 4:
            text = socket.inet_ntoa(rdata)
        elif rtype == 28 and rdlen == 16:
            text = socket.inet_ntop(socket.AF_INET6, rdata)
        elif rtype in (2, 5):
            text = read_name(data, pos)[0]
        elif rtype == 15:
            text = f"{struct.unpack('>H', rdata[:2])[0]} {read_name(data, pos + 2)[0]}"
        elif rtype == 16:
            parts, i = [], 0
            while i < len(rdata):
                n = rdata[i]
                parts.append(rdata[i + 1:i + 1 + n].decode("utf-8", "replace"))
                i += 1 + n
            text = "".join(parts)
        else:
            text = ""
        pos += rdlen
        if rtype in TYPE_NAMES:
            answers.append((TYPE_NAMES[rtype], ttl, text))
    return answers


def dns_query(name, rtype="A", server=None, timeout=3.0):
    """Ask a resolver for records. Returns (answers, server used)."""
    query_id, packet = build_query(name, rtype)
    last = None
    for host in ([server] if server else resolvers()):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(timeout)
                s.sendto(packet, (host, 53))
                return parse_response(s.recv(4096), query_id), host
        except (OSError, ValueError) as e:
            last = e
    raise OSError(f"no DNS server answered ({last})")


def lookup(name, types=None):
    types = types or ["A", "AAAA", "MX", "TXT", "NS", "CNAME"]
    console.print(f"[bold]{escape(name)}[/bold]")
    found_any = False
    for rtype in types:
        try:
            answers, server = dns_query(name, rtype)
        except OSError as e:
            console.print(f"[red]{escape(str(e))}[/red]")
            return
        for kind, ttl, text in answers:
            if kind == rtype:
                found_any = True
                console.print(f"  [cyan]{kind:<6}[/cyan] {escape(text)}  [dim]ttl {ttl}s[/dim]")
    if not found_any:
        console.print("  [yellow]No records found (the name may not exist).[/yellow]")


# ---------------------------------------------------------- path / trace
def trace(host, max_hops=20):
    """Hop-by-hop path (needs permission to read ICMP replies, usually root); otherwise a timing breakdown of connecting to the host."""
    try:
        target = socket.gethostbyname(host)
    except OSError:
        console.print("[red]Unknown host.[/red]")
        return
    console.print(f"Path to {escape(host)} ({target})")
    try:
        recv = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
    except (PermissionError, OSError, AttributeError):
        recv = None
    if recv is None:
        console.print("[dim]Showing every hop needs administrator rights on this system, so here is a timing breakdown instead.[/dim]")
        timing_breakdown(host, target)
        return
    recv.settimeout(1.5)
    port = 33434
    for ttl in range(1, max_hops + 1):
        send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        send.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl)
        start = time.perf_counter()
        send.sendto(b"", (target, port))
        try:
            _, addr = recv.recvfrom(512)
            ms = (time.perf_counter() - start) * 1000
            name = ""
            try:
                name = socket.gethostbyaddr(addr[0])[0]
            except OSError:
                pass
            console.print(f"  {ttl:>2}  {addr[0]:<16} {ms:6.1f} ms  [dim]{escape(name)}[/dim]")
            if addr[0] == target:
                send.close()
                break
        except socket.timeout:
            console.print(f"  {ttl:>2}  [dim]*  no reply[/dim]")
        send.close()
    recv.close()


def timing_breakdown(host, target):
    """Where the time goes when connecting to a host: finding its address, opening the connection, the secure handshake, the first answer."""
    table = Table(header_style="bold blue", title="Connection timing")
    table.add_column("Step")
    table.add_column("Time", justify="right")
    start = time.perf_counter()
    try:
        socket.getaddrinfo(host, 443)
        dns = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        sock = socket.create_connection((target, 443), timeout=5)
        tcp = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        wrapped = ssl.create_default_context().wrap_socket(sock, server_hostname=host)
        tls = (time.perf_counter() - start) * 1000
        start = time.perf_counter()
        wrapped.sendall(f"HEAD / HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n".encode())
        wrapped.recv(1)
        first = (time.perf_counter() - start) * 1000
        wrapped.close()
    except (OSError, ssl.SSLError) as e:
        console.print(f"[red]Could not complete: {escape(str(e)[:80])}[/red]")
        return
    for label, ms in (("Look up the address (DNS)", dns), ("Open the connection (TCP)", tcp), ("Secure handshake (TLS)", tls), ("First byte of the answer", first)):
        table.add_row(label, f"{ms:.0f} ms")
    table.add_row("[bold]Total[/bold]", f"[bold]{dns + tcp + tls + first:.0f} ms[/bold]")
    console.print(table)


# ------------------------------------------------- saved hosts and monitor
def saved_hosts():
    return appdata.load("nettools_hosts", []) if appdata else []


def save_hosts(hosts):
    if appdata:
        appdata.save("nettools_hosts", hosts[:30])


def add_host(host, port=443):
    hosts = [h for h in saved_hosts() if h["host"] != host]
    hosts.append({"host": host, "port": int(port)})
    save_hosts(hosts)
    console.print(f"[green]Saved {escape(host)}:{port}.[/green]")


def watch_once():
    hosts = saved_hosts()
    if not hosts:
        console.print("[dim]No saved hosts. Add one: nettools hosts add example.com 443[/dim]")
        return {}
    table = Table(header_style="bold blue", title="Watchlist")
    for col in ("Host", "Port", "State", "Time"):
        table.add_column(col)
    state = {}
    for h in hosts:
        ms = connect_time(h["host"], h["port"])
        state[f"{h['host']}:{h['port']}"] = ms is not None
        table.add_row(escape(h["host"]), str(h["port"]), "[green]up[/green]" if ms is not None else "[red]DOWN[/red]", f"{ms:.0f} ms" if ms is not None else "-")
    console.print(table)
    return state


def monitor_check():
    """Silent unless something changed: compare with the last check and send a notification for every host that went down or came back."""
    previous = appdata.load("nettools_state", {}) if appdata else {}
    current = {}
    for h in saved_hosts():
        key = f"{h['host']}:{h['port']}"
        current[key] = connect_time(h["host"], h["port"], 4.0) is not None
        if key in previous and previous[key] != current[key] and notify and pyos:
            notify.notify(f"{key} is {'back UP' if current[key] else 'DOWN'}", title="Network monitor", level="info" if current[key] else "warn",
                          user=pyos.userinfo()[0])
    if appdata:
        appdata.save("nettools_state", current)


def monitor_command(sub):
    if not scheduler or not pyos:
        console.print("[yellow]The monitor needs PythonOS.[/yellow]")
        return
    user = pyos.userinfo()[0]
    existing = [t for t in scheduler.tasks_for(user) if t["command"] == MONITOR_COMMAND]
    if sub == "on":
        if existing:
            console.print("[green]The monitor is already on.[/green]")
        else:
            scheduler.add(user, ["every", "5m"] + MONITOR_COMMAND.split())
            console.print("[green]Monitor on: your saved hosts are checked every 5 minutes while you are logged in; you get a notification when one goes down or comes back.[/green]")
    elif sub == "off":
        for t in existing:
            scheduler.remove(user, t["id"])
        console.print("[green]Monitor off.[/green]")
    elif sub == "check":
        monitor_check()
    else:
        console.print("The monitor is [bold]on[/bold] (every 5 minutes)." if existing else "The monitor is [bold]off[/bold]. Turn it on: nettools monitor on")


# --------------------------------------------------------------------- UI
MENU = """(c)onnection check   (l)ookup name   (p)ort test   (t)cp ping   (w)eb page check   (i)p address
(r)ecords (DNS)   (h)ops / path   (s)aved hosts   (m)onitor   (q)uit"""


def main(args):
    if not args:
        while True:
            console.print(MENU)
            choice = Prompt.ask("Choose", choices=list("clptwirhsmq"), default="c")
            if choice == "q":
                return
            if choice == "c":
                check_connection()
            elif choice == "i":
                public_address()
            elif choice in ("l", "r"):
                lookup(Prompt.ask("Name").strip())
            elif choice == "p":
                host, port = Prompt.ask("Host").strip(), Prompt.ask("Port", default="443").strip()
                if port.isdigit() and 0 < int(port) < 65536:
                    port_check(host, int(port))
                else:
                    console.print("[red]A port is a number from 1 to 65535.[/red]")
            elif choice == "t":
                tcp_ping(Prompt.ask("Host").strip())
            elif choice == "w":
                web_check(Prompt.ask("Address").strip())
            elif choice == "h":
                trace(Prompt.ask("Host").strip())
            elif choice == "s":
                watch_once()
                action = Prompt.ask("(a)dd a host, (r)emove one, (b)ack", choices=["a", "r", "b"], default="b")
                if action == "a":
                    add_host(Prompt.ask("Host").strip(), Prompt.ask("Port", default="443"))
                elif action == "r":
                    gone = Prompt.ask("Host to remove").strip()
                    save_hosts([h for h in saved_hosts() if h["host"] != gone])
            else:
                monitor_command(Prompt.ask("on, off, status", choices=["on", "off", "status"], default="status"))
        return
    cmd = args[0].lower()
    if cmd == "check":
        check_connection()
    elif cmd == "ip":
        public_address()
    elif cmd == "lookup" and len(args) > 1:
        lookup(args[1], [args[2].upper()] if len(args) > 2 and args[2].upper() in RECORD_TYPES else None)
    elif cmd == "port" and len(args) > 2 and args[2].isdigit():
        port_check(args[1], int(args[2]))
    elif cmd == "web" and len(args) > 1:
        web_check(args[1])
    elif cmd == "ping" and len(args) > 1:
        tcp_ping(args[1])
    elif cmd in ("trace", "hops", "path") and len(args) > 1:
        trace(args[1])
    elif cmd == "hosts":
        if len(args) > 2 and args[1] == "add":
            add_host(args[2], args[3] if len(args) > 3 and args[3].isdigit() else 443)
        elif len(args) > 2 and args[1] == "remove":
            save_hosts([h for h in saved_hosts() if h["host"] != args[2]])
            console.print("[green]Removed.[/green]")
        else:
            for h in saved_hosts():
                console.print(f"{escape(h['host'])}:{h['port']}")
            if not saved_hosts():
                console.print("[dim]No saved hosts.[/dim]")
    elif cmd == "watch":
        watch_once()
    elif cmd == "monitor":
        monitor_command(args[1].lower() if len(args) > 1 else "status")
    else:
        console.print("nettools [check | ip | lookup <name> [type] | port <host> <port> | web <address> | ping <host> | trace <host> | hosts | watch | monitor on|off|status]")


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
