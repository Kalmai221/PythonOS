#!/usr/bin/env python3
"""IP calculator: work out a network from an address and a mask (IPv4 and IPv6).

    ipcalc 192.168.1.10/24                  network, broadcast, mask, usable range, how many hosts
    ipcalc 10.0.0.5 255.255.255.0           a dotted mask works too
    ipcalc 192.168.1.0/24 --split 4         cut the network into 4 equal smaller ones
    ipcalc 192.168.1.0/24 --prefix 26       cut it into /26 networks
    ipcalc 2001:db8::/32                    IPv6
"""
import ipaddress
import sys

from rich.console import Console
from rich.markup import escape
from rich.table import Table

console = Console()


def parse(args):
    """(interface, split count or None, new prefix or None) from the arguments. Raises ValueError with a sentence."""
    args = list(args)
    split = prefix = None
    for flag in ("--split", "--prefix"):
        if flag in args:
            i = args.index(flag)
            try:
                value = int(args[i + 1])
            except (IndexError, ValueError):
                raise ValueError(f"{flag} needs a number") from None
            del args[i:i + 2]
            if flag == "--split":
                split = value
            else:
                prefix = value
    if not args or len(args) > 2:
        raise ValueError("")
    text = "/".join(args) if len(args) == 2 else args[0]
    try:
        return ipaddress.ip_interface(text), split, prefix
    except ValueError:
        raise ValueError(f"'{' '.join(args)}' is not an address with a mask, for example 192.168.1.10/24") from None


def kind(address):
    """What kind of address this is, in words."""
    for test, label in ((address.is_loopback, "loopback"), (address.is_link_local, "link-local (self-assigned)"), (address.is_multicast, "multicast"),
                        (address.is_private, "private (not on the internet)"), (address.is_reserved, "reserved"), (address.is_unspecified, "unspecified")):
        if test:
            return label
    return "public (reachable on the internet)"


def describe(interface):
    """{label: value} rows about the network of an interface."""
    network, address = interface.network, interface.ip
    rows = {"Address": str(address), "Network": str(network), "Mask": str(network.netmask), "Prefix length": f"/{network.prefixlen}",
            "Type": kind(address)}
    if network.version == 4:
        rows["Wildcard"] = str(network.hostmask)
        rows["Broadcast"] = str(network.broadcast_address)
        usable = network.num_addresses - 2 if network.prefixlen < 31 else network.num_addresses
        first = network.network_address + 1 if network.prefixlen < 31 else network.network_address
        last = network.broadcast_address - 1 if network.prefixlen < 31 else network.broadcast_address
        rows["Usable range"] = f"{first} - {last}" if usable > 0 else "none"
        rows["Usable hosts"] = f"{max(usable, 0):,}"
        rows["Binary address"] = ".".join(f"{int(part):08b}" for part in str(address).split("."))
        rows["Binary mask"] = ".".join(f"{int(part):08b}" for part in str(network.netmask).split("."))
    else:
        rows["First address"] = str(network.network_address)
        rows["Last address"] = str(network.broadcast_address)
        rows["Addresses"] = f"{network.num_addresses:,}"
    return rows


def split_network(network, count=None, prefix=None):
    """The smaller networks: `count` equal ones (a power of two) or all those of length `prefix`. Raises ValueError."""
    if count is not None:
        if count < 2 or count & (count - 1):
            raise ValueError("--split needs a power of two (2, 4, 8, 16, ...)")
        prefix = network.prefixlen + count.bit_length() - 1
    if prefix is None or prefix <= network.prefixlen or prefix > network.max_prefixlen:
        raise ValueError(f"the new prefix must be longer than /{network.prefixlen} and at most /{network.max_prefixlen}")
    if prefix - network.prefixlen > 12:
        raise ValueError("that would make more than 4096 networks")
    return list(network.subnets(new_prefix=prefix))


def main(argv):
    try:
        interface, count, prefix = parse(argv)
        rows = describe(interface)
        subnets = split_network(interface.network, count, prefix) if (count is not None or prefix is not None) else []
    except ValueError as e:
        console.print(__doc__)
        if str(e):
            console.print(f"[red]{escape(str(e))}[/red]")
        return 1
    table = Table(show_header=False, box=None)
    table.add_column(style="dim")
    table.add_column()
    for label, value in rows.items():
        table.add_row(label, escape(value))
    console.print(table)
    if subnets:
        console.print(f"\n[bold]{len(subnets)} networks of /{subnets[0].prefixlen}[/bold]")
        for net in subnets[:64]:
            if net.version == 4 and net.prefixlen < 31:
                console.print(f"  {net}   [dim]{net.network_address + 1} - {net.broadcast_address - 1}[/dim]")
            else:
                console.print(f"  {net}")
        if len(subnets) > 64:
            console.print(f"[dim]  ... and {len(subnets) - 64} more[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
