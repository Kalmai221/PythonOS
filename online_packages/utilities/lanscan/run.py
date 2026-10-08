#!/usr/bin/env python3
"""LAN scanner: finds the devices on your own local network (home or office) by trying to connect to common ports on every address, then lists
what answered with its name, hardware address and maker, how fast it replied, and what it seems to be. It only scans private network ranges
(192.168.x.x, 10.x.x.x, 172.16-31.x.x) - never the internet. Only scan networks you own or are allowed to examine.

    lanscan                          scan the network this computer is on
    lanscan 192.168.1.0/24           a particular private network (up to /22)
    lanscan --full                   try 40 common ports instead of 11 (slower, finds more)
    lanscan --ports 22,80,8000-8100  your own ports
    lanscan --save                   remember this scan, then later:
    lanscan --diff                   what is new on the network, and what is gone, since the last saved scan
    lanscan --name 192.168.1.20 "Living room TV"     give a device a name (kept by its hardware address)
    lanscan --sort ip|name|speed     order the table;   --up  only devices that answered a port
    lanscan --json   or   --csv      machine-readable output
"""
import csv
import io
import ipaddress
import json
import os
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from rich.console import Console
from rich.markup import escape
from rich.progress import BarColumn, Progress, TextColumn
from rich.table import Table

console = Console()
PORTS = [80, 443, 22, 445, 139, 135, 53, 8080, 62078, 5353, 1900]      # web, ssh, file sharing, dns, phones (62078), printers...
FULL_PORTS = PORTS + [21, 23, 25, 111, 119, 123, 137, 161, 389, 515, 548, 554, 631, 873, 1883, 3306, 3389, 5000, 5001, 5900, 8000, 8443, 8888, 9100, 32400]
TIMEOUT = 0.35
THREADS = 64
SERVICES = {21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns", 80: "http", 111: "rpc", 119: "nntp", 123: "ntp", 135: "rpc", 137: "netbios", 139: "netbios",
            161: "snmp", 389: "ldap", 443: "https", 445: "smb", 515: "lpd", 548: "afp", 554: "rtsp", 631: "ipp", 873: "rsync", 1883: "mqtt", 1900: "upnp",
            3306: "mysql", 3389: "rdp", 5000: "upnp/web", 5001: "web", 5353: "mdns", 5900: "vnc", 8000: "http", 8080: "http", 8443: "https", 8888: "http",
            9100: "printer", 32400: "plex", 62078: "iphone sync"}
# the makers behind the first three bytes of a hardware address (a short list of the common ones; a missing one just shows nothing)
VENDORS = {
    "00:1A:11": "Google", "3C:5A:B4": "Google", "F4:F5:D8": "Google", "54:60:09": "Google", "A4:77:33": "Google",
    "00:03:93": "Apple", "00:0A:95": "Apple", "00:1C:B3": "Apple", "00:25:00": "Apple", "28:CF:E9": "Apple", "3C:07:54": "Apple", "A4:5E:60": "Apple",
    "F0:18:98": "Apple", "DC:A9:04": "Apple", "BC:92:6B": "Apple", "14:7D:DA": "Apple", "88:66:5A": "Apple",
    "00:12:FB": "Samsung", "00:16:32": "Samsung", "5C:0A:5B": "Samsung", "8C:77:12": "Samsung", "F8:04:2E": "Samsung", "CC:07:AB": "Samsung",
    "B8:27:EB": "Raspberry Pi", "DC:A6:32": "Raspberry Pi", "E4:5F:01": "Raspberry Pi", "28:CD:C1": "Raspberry Pi", "D8:3A:DD": "Raspberry Pi",
    "00:50:56": "VMware", "00:0C:29": "VMware", "08:00:27": "VirtualBox", "52:54:00": "QEMU/KVM", "00:15:5D": "Hyper-V",
    "00:1B:21": "Intel", "3C:97:0E": "Intel", "A4:34:D9": "Intel", "F8:B1:56": "Dell", "00:14:22": "Dell", "B8:AC:6F": "Dell",
    "00:1D:7E": "Cisco-Linksys", "00:18:F8": "Cisco-Linksys", "00:25:9C": "Cisco", "00:0B:46": "Cisco",
    "C0:25:E9": "TP-Link", "50:C7:BF": "TP-Link", "F4:F2:6D": "TP-Link", "98:DA:C4": "TP-Link", "14:CC:20": "TP-Link",
    "00:14:6C": "Netgear", "A0:63:91": "Netgear", "9C:3D:CF": "Netgear", "28:C6:8E": "Netgear",
    "FC:EC:DA": "Ubiquiti", "24:A4:3C": "Ubiquiti", "74:AC:B9": "Ubiquiti", "00:27:22": "Ubiquiti",
    "B0:BE:76": "TP-Link", "30:B5:C2": "TP-Link", "88:D7:F6": "ASUS", "04:92:26": "ASUS", "2C:56:DC": "ASUS", "00:1F:C6": "ASUS",
    "44:65:0D": "Amazon", "F0:D2:F1": "Amazon", "FC:A6:67": "Amazon", "68:54:FD": "Amazon", "74:C2:46": "Amazon",
    "00:0E:58": "Sonos", "5C:AA:FD": "Sonos", "B8:E9:37": "Sonos", "48:A6:B8": "Sonos",
    "24:0A:C4": "Espressif (IoT)", "30:AE:A4": "Espressif (IoT)", "84:0D:8E": "Espressif (IoT)", "A4:CF:12": "Espressif (IoT)", "EC:FA:BC": "Espressif (IoT)",
    "00:17:88": "Philips Hue", "EC:B5:FA": "Philips Hue", "00:04:20": "Slim Devices", "00:0D:4B": "Roku", "B0:A7:37": "Roku", "CC:6D:A0": "Roku",
    "00:1D:BA": "Sony", "FC:F1:52": "Sony", "78:C8:81": "Sony", "00:13:A9": "Sony", "00:24:BE": "Sony",
    "00:09:BF": "Nintendo", "98:B6:E9": "Nintendo", "7C:BB:8A": "Nintendo", "00:50:F2": "Microsoft", "7C:1E:52": "Microsoft", "28:18:78": "Microsoft",
    "00:1E:C2": "Apple", "18:65:90": "Apple", "00:23:12": "Apple", "00:26:BB": "Apple", "04:0C:CE": "Apple",
    "00:1C:62": "LG", "A8:16:B2": "LG", "00:E0:91": "LG", "C4:36:6C": "LG", "00:1E:75": "LG",
    "D8:0F:99": "HP", "00:1B:78": "HP", "3C:D9:2B": "HP", "9C:B6:54": "HP", "00:21:5A": "HP", "00:17:A4": "HP",
    "00:00:48": "Epson", "00:26:AB": "Epson", "00:80:77": "Brother", "00:1B:A9": "Brother", "00:00:85": "Canon", "00:1E:8F": "Canon",
    "00:18:E7": "Xiaomi", "64:09:80": "Xiaomi", "F8:A4:5F": "Xiaomi", "34:CE:00": "Xiaomi", "00:9E:C8": "Xiaomi",
    "00:1A:A0": "Dell", "18:03:73": "Dell", "00:11:32": "Synology", "00:50:43": "Marvell", "E8:48:B8": "TP-Link",
}
CHOICES = ("ip", "name", "speed")


# ---------------------------------------------------------------- where things are kept (per user, like the other apps)
def data_file(name):
    try:
        with open("current_user.json", encoding="utf-8") as f:
            user = json.load(f)["username"]
    except Exception:                                          # noqa: BLE001 - no user: the shared files folder
        user = None
    folder = os.path.join("files", "home", user) if user else "files"
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, name)


def load_json(name, default):
    try:
        with open(data_file(name), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, type(default)) else default
    except (OSError, ValueError):
        return default


def save_json(name, data):
    path = data_file(name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


# ---------------------------------------------------------------- the network
def local_address():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))
            return s.getsockname()[0]
    except OSError:
        return None


def default_network(address):
    return ipaddress.ip_network(f"{address}/24", strict=False)


def allowed(network):
    """Only private ranges, and nothing bigger than a /22 (1022 addresses)."""
    return network.version == 4 and network.is_private and not network.is_loopback and network.prefixlen >= 22


def parse_ports(text):
    """[ports] from '22,80,8000-8100' (up to 200). Raises ValueError."""
    ports = []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        low, _dash, high = part.partition("-")
        try:
            first, last = int(low), int(high or low)
        except ValueError:
            raise ValueError(f"'{part}' is not a port or a range of ports") from None
        if not (1 <= first <= last <= 65535):
            raise ValueError(f"'{part}' is not a valid range of ports (1 to 65535)")
        ports.extend(range(first, last + 1))
    ports = sorted(set(ports))
    if not ports or len(ports) > 200:
        raise ValueError("give between 1 and 200 ports")
    return ports


def probe(address, ports=None, timeout=TIMEOUT):
    """(address, answered?, [open ports], seconds of the fastest answer or None) - a device answers if a port connects or actively refuses."""
    open_ports, answered, fastest = [], False, None
    for port in (ports or PORTS):
        started = time.perf_counter()
        try:
            with socket.create_connection((address, port), timeout=timeout):
                open_ports.append(port)
                answered = True
        except ConnectionRefusedError:
            answered = True                       # something is there; the port is just closed
        except OSError:
            continue
        took = time.perf_counter() - started
        fastest = took if fastest is None else min(fastest, took)
    return address, answered, open_ports, fastest


def read_arp():
    """{ip: mac} from the system's neighbour table (Linux)."""
    table = {}
    try:
        with open("/proc/net/arp", encoding="utf-8") as f:
            for line in f.read().splitlines()[1:]:
                parts = line.split()
                if len(parts) >= 4 and parts[3] != "00:00:00:00:00:00":
                    table[parts[0]] = parts[3].upper()
    except OSError:
        pass
    return table


def hostname(address):
    try:
        return socket.gethostbyaddr(address)[0]
    except OSError:
        return ""


def vendor(mac):
    """The maker behind a hardware address ('' if unknown). A randomised address (a phone hiding itself) is said so."""
    mac = (mac or "").upper().replace("-", ":")
    if len(mac) < 8:
        return ""
    try:
        if int(mac[:2], 16) & 2:                  # the 'locally administered' bit: made up by the device, not by a maker
            return "private address (a phone or computer hiding itself)"
    except ValueError:
        return ""
    return VENDORS.get(mac[:8], "")


def services(ports):
    """'22 ssh, 80 http' for a list of open ports."""
    return ", ".join(f"{p} {SERVICES[p]}" if p in SERVICES else str(p) for p in ports)


def guess_kind(ports, maker=""):
    if 62078 in ports or maker == "Apple":
        return "Apple device"
    if 9100 in ports or 631 in ports or 515 in ports:
        return "printer"
    if 554 in ports:
        return "camera or media device"
    if 3389 in ports:
        return "Windows computer (remote desktop)"
    if 445 in ports or 139 in ports or 135 in ports:
        return "computer (file sharing)"
    if 32400 in ports:
        return "media server"
    if 22 in ports:
        return "computer/server (SSH)"
    if maker.startswith("Raspberry"):
        return "Raspberry Pi"
    if maker.startswith("Espressif") or 1883 in ports:
        return "smart-home / IoT device"
    if 80 in ports or 443 in ports or 8080 in ports:
        return "has a web page (router, printer, camera...)"
    if 53 in ports:
        return "router/DNS"
    return ""


# ---------------------------------------------------------------- the scan and what is done with it
def scan(network, ports, timeout):
    hosts = [str(h) for h in network.hosts()]
    found = []
    with Progress(TextColumn("Scanning {task.description}"), BarColumn(), TextColumn("{task.completed}/{task.total}"), console=console,
                  transient=True) as progress:
        task = progress.add_task(str(network), total=len(hosts))
        with ThreadPoolExecutor(THREADS) as pool:
            for address, answered, open_ports, seconds in pool.map(lambda h: probe(h, ports, timeout), hosts):
                progress.advance(task)
                if answered:
                    found.append({"ip": address, "ports": open_ports, "seconds": seconds})
    arp = read_arp()
    seen = {d["ip"] for d in found}
    for address in hosts:                           # devices that ignored every port may still be in the neighbour table
        if address in arp and address not in seen:
            found.append({"ip": address, "ports": [], "seconds": None})
    names = {}
    with ThreadPoolExecutor(16) as pool:            # names are asked of the network in parallel: one slow answer does not hold up the rest
        for device, name in zip(found, pool.map(lambda d: hostname(d["ip"]), found)):
            names[device["ip"]] = name
    labels = load_json(".lanscan-names.json", {})
    for device in found:
        device["mac"] = arp.get(device["ip"], "")
        device["name"] = names.get(device["ip"], "")
        device["vendor"] = vendor(device["mac"])
        device["kind"] = guess_kind(device["ports"], device["vendor"])
        device["label"] = labels.get(device["mac"], "") if device["mac"] else ""
    return sorted(found, key=lambda d: ipaddress.ip_address(d["ip"]))


def order(devices, how):
    if how == "name":
        return sorted(devices, key=lambda d: ((d["label"] or d["name"] or "~").lower(), ipaddress.ip_address(d["ip"])))
    if how == "speed":
        return sorted(devices, key=lambda d: (d["seconds"] is None, d["seconds"] or 0, ipaddress.ip_address(d["ip"])))
    return sorted(devices, key=lambda d: ipaddress.ip_address(d["ip"]))


def identity(device):
    """What identifies a device between scans: its hardware address when it has one, else its address."""
    return device.get("mac") or device["ip"]


def compare(before, now):
    """(new devices, gone devices, devices whose address changed) between two scans, by hardware address."""
    old = {identity(d): d for d in before}
    new = {identity(d): d for d in now}
    added = [new[k] for k in new if k not in old]
    gone = [old[k] for k in old if k not in new]
    moved = [(old[k], new[k]) for k in new if k in old and old[k]["ip"] != new[k]["ip"]]
    return added, gone, moved


def parse_args(argv):
    """The options as a dict. Raises ValueError with a sentence (empty for 'show the help')."""
    argv = list(argv)
    options = {"network": None, "ports": PORTS, "timeout": TIMEOUT, "save": False, "diff": False, "sort": "ip", "up": False, "json": False,
               "csv": False, "name": None}
    flags = {"--full": ("ports", FULL_PORTS), "--save": ("save", True), "--diff": ("diff", True), "--up": ("up", True), "--json": ("json", True),
             "--csv": ("csv", True)}
    rest = []
    i = 0
    while i < len(argv):
        word = argv[i]
        if word in flags:
            options[flags[word][0]] = flags[word][1]
        elif word in ("--ports", "--sort", "--timeout"):
            if i + 1 >= len(argv):
                raise ValueError(f"{word} needs a value")
            value = argv[i + 1]
            i += 1
            if word == "--ports":
                options["ports"] = parse_ports(value)
            elif word == "--sort":
                if value not in CHOICES:
                    raise ValueError("--sort is ip, name or speed")
                options["sort"] = value
            else:
                try:
                    options["timeout"] = max(0.05, min(float(value), 3.0))
                except ValueError:
                    raise ValueError("--timeout needs a number of seconds") from None
        elif word == "--name":
            if len(argv) < i + 3:
                raise ValueError("--name needs an address and a name")
            options["name"] = (argv[i + 1], " ".join(argv[i + 2:]))
            break
        elif word in ("-h", "--help"):
            raise ValueError("")
        elif word.startswith("-"):
            raise ValueError(f"I do not know the option {word}")
        else:
            rest.append(word)
        i += 1
    if len(rest) > 1:
        raise ValueError("Give one network, like 192.168.1.0/24.")
    if rest:
        try:
            options["network"] = ipaddress.ip_network(rest[0], strict=False)
        except ValueError:
            raise ValueError("Give a network like 192.168.1.0/24.") from None
    return options


def give_name(address, label):
    """Remember a name for the device at `address` (needs its hardware address, found by looking at the neighbour table)."""
    try:
        ipaddress.ip_address(address)
    except ValueError:
        return "That is not an address."
    mac = read_arp().get(address)
    if not mac:
        return "I do not know that device's hardware address yet. Run a scan first, then try again."
    labels = load_json(".lanscan-names.json", {})
    if label.strip():
        labels[mac] = label.strip()[:60]
    else:
        labels.pop(mac, None)
    save_json(".lanscan-names.json", labels)
    return f"Saved: {mac} is now '{label.strip()}'." if label.strip() else f"Removed the name of {mac}."


def rows_for(devices, mine):
    return [{"ip": d["ip"], "this_device": d["ip"] == mine, "name": d["label"] or d["name"], "hardware_address": d["mac"], "maker": d["vendor"],
             "looks_like": d["kind"], "ms": round(d["seconds"] * 1000) if d["seconds"] is not None else None, "open_ports": d["ports"]} for d in devices]


def as_csv(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]) if rows else ["ip"])
    writer.writeheader()
    for row in rows:
        writer.writerow({**row, "open_ports": " ".join(map(str, row["open_ports"]))})
    return out.getvalue()


def show_table(devices, mine):
    table = Table(header_style="bold blue", title=f"{len(devices)} device(s) found")
    for col in ("Address", "Name", "Hardware address", "Maker", "Looks like", "Reply", "Open ports"):
        table.add_column(col)
    for d in devices:
        name = d["label"] or d["name"]
        table.add_row(d["ip"] + (" (this device)" if d["ip"] == mine else ""), (f"[bold]{escape(name)}[/bold]" if d["label"] else escape(name)), d["mac"],
                      escape(d["vendor"]), d["kind"], f"{d['seconds'] * 1000:.0f} ms" if d["seconds"] is not None else "", escape(services(d["ports"])))
    console.print(table)


def main(args):
    try:
        options = parse_args(args)
    except ValueError as e:
        console.print(__doc__)
        if str(e):
            console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    if options["name"]:
        console.print(escape(give_name(*options["name"])))
        return 0
    network = options["network"]
    mine = local_address()
    if network is None:
        if not mine:
            console.print("[yellow]You do not appear to be on a network.[/yellow]")
            return 1
        network = default_network(mine)
    if not allowed(network):
        console.print("[bold red]Only private local networks (up to /22) can be scanned here.[/bold red]")
        return 1
    quiet = options["json"] or options["csv"]
    if not quiet:
        console.print(f"Scanning {network} ({network.num_addresses - 2} addresses, {len(options['ports'])} ports each). Only devices on your own network will answer.")
    devices = scan(network, options["ports"], options["timeout"])
    if options["up"]:
        devices = [d for d in devices if d["ports"]]
    devices = order(devices, options["sort"])
    rows = rows_for(devices, mine)
    if options["json"]:
        print(json.dumps(rows, indent=2))
    elif options["csv"]:
        print(as_csv(rows), end="")
    else:
        show_table(devices, mine)
    if options["diff"]:
        previous = load_json(".lanscan-last.json", {})
        if not previous.get("devices"):
            console.print("[dim]No saved scan to compare with yet. Run: lanscan --save[/dim]")
        else:
            added, gone, moved = compare(previous["devices"], devices)
            console.print(f"\n[bold]Since {escape(str(previous.get('when', 'the last saved scan')))}[/bold]")
            for d in added:
                console.print(f"  [bold green]new[/bold green]   {d['ip']}  {escape(d['label'] or d['name'] or d['vendor'] or d['kind'])}  {d['mac']}")
            for d in gone:
                console.print(f"  [yellow]gone[/yellow]  {d['ip']}  {escape(d['label'] or d['name'] or d['vendor'])}  {d['mac']}")
            for old, now in moved:
                console.print(f"  [cyan]moved[/cyan] {old['ip']} -> {now['ip']}  {now['mac']}")
            if not (added or gone or moved):
                console.print("  [green]nothing changed[/green]")
    if options["save"]:
        save_json(".lanscan-last.json", {"when": time.strftime("%Y-%m-%d %H:%M"), "network": str(network), "devices": devices})
        if not quiet:
            console.print("[dim]Saved. Compare later with: lanscan --diff[/dim]")
    if not quiet:
        console.print("[dim]Phones and some devices hide from scans, so this list can miss some.[/dim]")
    return 0


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
