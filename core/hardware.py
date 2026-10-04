"""Hardware, audio and network setup (the PythonOS live ISO, or any Linux system as root).

* hardware_check()  - what hardware was found, which drivers are loaded, missing firmware
* audio_setup()     - pick the sound card/output, unmute, set the volume, play a test
* network_setup()   - choose an interface, connect (wired DHCP or Wi-Fi) and test the internet
* live_setup()      - the first-boot flow on the ISO that offers all of the above

Everything goes through run() so the parsing and flows can be tested without real hardware.
"""
import glob
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import time

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

console = Console()

ASOUND_CONF = "/etc/asound.conf"
WPA_DIR = "/etc/wpa_supplicant"
CTRL_DIR = "/var/run/wpa_supplicant"


# ------------------------------------------------------------------ helpers
def run(cmd, timeout=15, text_input=None):
    """Run a command. Returns (returncode, output); 127 = not installed, 124 = timed out."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, input=text_input)
    except FileNotFoundError:
        return 127, ""
    except subprocess.TimeoutExpired:
        return 124, ""
    except OSError as e:
        return 126, str(e)
    return p.returncode, (p.stdout or "") + ("" if p.stdout else (p.stderr or ""))


def have(tool):
    return shutil.which(tool) is not None


def unavailable_reason():
    """Why hardware setup cannot run here, or None if it can."""
    if not sys.platform.startswith("linux"):
        return "Hardware setup needs Linux (it is built for the PythonOS live ISO)."
    if not hasattr(os, "geteuid") or os.geteuid() != 0:
        return "Hardware setup needs root. On the PythonOS live ISO this is the default."
    return None


def read(path, default=""):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read().strip()
    except OSError:
        return default


# ------------------------------------------------------------ hardware check
CLASS_NAMES = {
    "0200": "Network", "0280": "Wi-Fi / wireless", "0300": "Graphics", "0302": "Graphics",
    "0380": "Graphics", "0403": "Audio", "0401": "Audio", "0402": "Audio",
    "0106": "Storage", "0108": "Storage", "0100": "Storage", "0101": "Storage", "0104": "Storage",
    "0c03": "USB controller", "0d11": "Bluetooth",
}
INTERESTING = {"Network", "Wi-Fi / wireless", "Graphics", "Audio", "Storage", "Bluetooth"}


def parse_lspci(text):
    """Parse `lspci -k -nn` into [{slot, cls, desc, driver, modules}]."""
    devices, current = [], None
    for line in text.splitlines():
        m = re.match(r"^(\S+)\s+(.+?)\s+\[([0-9a-f]{4})\]:\s+(.*)$", line)
        if m:
            current = {"slot": m.group(1), "cls": CLASS_NAMES.get(m.group(3), m.group(2)),
                       "code": m.group(3), "desc": re.sub(r"\s*\(rev [0-9a-f]+\)$", "", m.group(4)),
                       "driver": None, "modules": ""}
            devices.append(current)
        elif current is not None:
            if "Kernel driver in use:" in line:
                current["driver"] = line.split(":", 1)[1].strip()
            elif "Kernel modules:" in line:
                current["modules"] = line.split(":", 1)[1].strip()
    return devices


def pci_devices():
    """PCI devices with their driver status (lspci if present, /sys otherwise)."""
    rc, out = run(["lspci", "-k", "-nn"])
    if rc == 0 and out.strip():
        return parse_lspci(out)
    devices = []
    for path in sorted(glob.glob("/sys/bus/pci/devices/*")):
        code = read(os.path.join(path, "class"))[2:6]
        driver = os.path.basename(os.path.realpath(os.path.join(path, "driver"))) if os.path.exists(os.path.join(path, "driver")) else None
        devices.append({"slot": os.path.basename(path), "cls": CLASS_NAMES.get(code, "Other"), "code": code,
                        "desc": f"{read(os.path.join(path, 'vendor'))}:{read(os.path.join(path, 'device'))}",
                        "driver": driver, "modules": ""})
    return devices


FIRMWARE_PATTERNS = [
    re.compile(r"Direct firmware load for (\S+) failed with error (-?\d+)"),
    re.compile(r"firmware: failed to load (\S+) \(-?\d+\)"),
    re.compile(r"Failed to load firmware \"?([^\"\s]+)\"?"),
]


def parse_firmware_failures(dmesg_text):
    """Unique firmware file names the kernel could not load."""
    names = []
    for line in dmesg_text.splitlines():
        for pattern in FIRMWARE_PATTERNS:
            m = pattern.search(line)
            if m and m.group(1) not in names:
                names.append(m.group(1))
    return names


def firmware_status(name):
    """'present' if the file exists under /lib/firmware (also compressed), else 'missing'."""
    base = os.path.join("/lib/firmware", name)
    return "present" if any(os.path.exists(base + ext) for ext in ("", ".zst", ".xz", ".gz")) else "missing"


def system_summary():
    cpu = ""
    for line in read("/proc/cpuinfo").splitlines():
        if line.lower().startswith("model name"):
            cpu = line.split(":", 1)[1].strip()
            break
    try:
        import psutil
        ram = f"{psutil.virtual_memory().total / 1024 ** 3:.1f} GB"
    except Exception:
        ram = "unknown"
    vendor = read("/sys/class/dmi/id/sys_vendor")
    product = read("/sys/class/dmi/id/product_name")
    return {"machine": f"{vendor} {product}".strip() or "unknown", "cpu": cpu or platform.processor() or "unknown",
            "ram": ram, "kernel": platform.release()}


def load_missing_drivers():
    """Ask the kernel to load a driver for every PCI device that has none. Returns how many got one."""
    fixed = 0
    for path in sorted(glob.glob("/sys/bus/pci/devices/*")):
        if os.path.exists(os.path.join(path, "driver")):
            continue
        alias = read(os.path.join(path, "modalias"))
        if alias:
            run(["modprobe", "-b", "-q", alias], timeout=20)
            time.sleep(0.2)
            if os.path.exists(os.path.join(path, "driver")):
                fixed += 1
    return fixed


def hardware_check():
    console.print(Panel("[bold]Hardware and firmware check[/bold]", border_style="cyan", expand=False))
    s = system_summary()
    info = Table.grid(padding=(0, 2))
    info.add_column(style="bold magenta", justify="right")
    info.add_column()
    for label, key in (("Machine", "machine"), ("CPU", "cpu"), ("Memory", "ram"), ("Kernel", "kernel")):
        info.add_row(label, escape(str(s[key])))
    console.print(info)

    with console.status("Looking at the hardware..."):
        devices = [d for d in pci_devices() if d["cls"] in INTERESTING]
    table = Table(title="Devices", header_style="bold blue")
    table.add_column("Type", style="magenta")
    table.add_column("Device")
    table.add_column("Driver")
    missing = 0
    for d in sorted(devices, key=lambda d: (d["cls"], d["slot"])):
        if d["driver"]:
            driver = f"[green]{escape(d['driver'])}[/green]"
        else:
            driver = "[red]none loaded[/red]"
            missing += 1
        table.add_row(d["cls"], escape(d["desc"]), driver)
    console.print(table if devices else "[yellow]No PCI devices were listed (lspci is missing?).[/yellow]")

    _, dmesg = run(["dmesg"])
    failures = parse_firmware_failures(dmesg)
    if failures:
        ftable = Table(title="Firmware the kernel could not load", header_style="bold blue")
        ftable.add_column("File")
        ftable.add_column("This system")
        for name in failures:
            state = firmware_status(name)
            ftable.add_row(escape(name), "[yellow]file exists - try a reboot[/yellow]" if state == "present"
                           else "[red]not included (proprietary or too new)[/red]")
        console.print(ftable)
    else:
        console.print("[green]No missing firmware reported by the kernel.[/green]")

    if missing and Confirm.ask(f"{missing} device(s) have no driver. Try to load drivers now?", default=True):
        fixed = load_missing_drivers()
        console.print(f"[bold green]{fixed} device(s) now have a driver.[/bold green]" if fixed
                      else "[yellow]No additional drivers could be loaded.[/yellow]")
    return not missing and not failures


# --------------------------------------------------------------------- audio
def parse_sound_cards(text):
    """Parse /proc/asound/cards into [{index, id, name}]."""
    cards = []
    for m in re.finditer(r"^\s*(\d+)\s+\[(\S+)\s*\]:\s+(.*)$", text, re.M):
        cards.append({"index": int(m.group(1)), "id": m.group(2), "name": m.group(3).strip()})
    return cards


def parse_playback_devices(text):
    """Parse `aplay -l` into [{card, device, label}]."""
    out = []
    for m in re.finditer(r"^card (\d+): (\S+) \[(.*?)\], device (\d+): (.*?) \[(.*?)\]", text, re.M):
        out.append({"card": int(m.group(1)), "device": int(m.group(4)),
                    "label": f"{m.group(3)} - {m.group(6)}"})
    return out


def write_asound_conf(card, device, path=ASOUND_CONF):
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"defaults.pcm.card {card}\ndefaults.pcm.device {device}\ndefaults.ctl.card {card}\n")


def unmute_and_set_volume(card, percent):
    """Unmute the usual playback controls and set their volume. Returns the controls it touched."""
    rc, out = run(["amixer", "-c", str(card), "scontrols"])
    touched = []
    for control in re.findall(r"Simple mixer control '([^']+)'", out):
        if control in ("Master", "Speaker", "Headphone", "PCM", "Front", "Line Out", "Headphone+LO", "Speaker+LO"):
            rc, _ = run(["amixer", "-c", str(card), "-q", "sset", control, f"{percent}%", "unmute"])
            if rc == 0:
                touched.append(control)
    return touched


def audio_setup():
    console.print(Panel("[bold]Audio setup[/bold]", border_style="cyan", expand=False))
    if not have("aplay"):
        console.print("[red]The ALSA tools (alsa-utils) are not installed, so audio cannot be set up here.[/red]")
        return False

    cards = parse_sound_cards(read("/proc/asound/cards"))
    if not cards:
        console.print("[yellow]No sound card is active.[/yellow]")
        if Confirm.ask("Try loading the common audio drivers?", default=True):
            for module in ("snd_hda_intel", "snd_usb_audio", "snd_ac97_codec", "snd_intel8x0"):
                run(["modprobe", "-q", module], timeout=20)
            time.sleep(1)
            cards = parse_sound_cards(read("/proc/asound/cards"))
        if not cards:
            console.print("[red]Still no sound card. This machine's audio may need a driver or firmware that is not "
                          "available, or it has no audio hardware.[/red]")
            return False

    while True:
        _, listing = run(["aplay", "-l"])
        outputs = parse_playback_devices(listing)
        if not outputs:
            console.print("[red]Sound cards were found, but none has a playback output.[/red]")
            return False
        table = Table(title="Audio outputs", header_style="bold blue")
        table.add_column("#", justify="right")
        table.add_column("Card")
        table.add_column("Output")
        for i, o in enumerate(outputs, 1):
            table.add_row(str(i), str(o["card"]), escape(o["label"]))
        console.print(table)
        pick = IntPrompt.ask("Choose the output to use", choices=[str(i) for i in range(1, len(outputs) + 1)], default=1)
        chosen = outputs[pick - 1]
        volume = IntPrompt.ask("Volume (0-100)", default=80)
        volume = max(0, min(100, volume))

        try:
            write_asound_conf(chosen["card"], chosen["device"])
        except OSError as e:
            console.print(f"[red]Could not save the choice: {e}[/red]")
            return False
        touched = unmute_and_set_volume(chosen["card"], volume)
        console.print(f"[green]Using {escape(chosen['label'])}; unmuted: {', '.join(touched) or 'nothing to unmute'}.[/green]")

        if not have("speaker-test"):
            return True
        if Confirm.ask("Play a test sound now?", default=True):
            console.print("[dim]You should hear 'Front Left', 'Front Right'...[/dim]")
            run(["speaker-test", "-c", "2", "-t", "wav", "-l", "1"], timeout=25)
            if Confirm.ask("Did you hear it?", default=True):
                console.print("[bold green]Audio is set up.[/bold green]")
                return True
            if not Confirm.ask("Pick a different output?", default=True):
                return False
        else:
            return True


# ------------------------------------------------------------------- network
def interfaces():
    """Network interfaces (without loopback): [{name, wireless, state, ip, mac, driver}]."""
    result = []
    for path in sorted(glob.glob("/sys/class/net/*")):
        name = os.path.basename(path)
        if name == "lo":
            continue
        driver_link = os.path.join(path, "device", "driver")
        _, addr = run(["ip", "-4", "-o", "addr", "show", name])
        ip = re.search(r"inet (\S+?)/", addr)
        result.append({
            "name": name,
            "wireless": os.path.isdir(os.path.join(path, "wireless")) or os.path.isdir(os.path.join(path, "phy80211")),
            "state": read(os.path.join(path, "operstate"), "unknown"),
            "ip": ip.group(1) if ip else "",
            "mac": read(os.path.join(path, "address")),
            "driver": os.path.basename(os.path.realpath(driver_link)) if os.path.exists(driver_link) else "",
        })
    return result


def parse_iw_scan(text):
    """Parse `iw dev X scan` into [{ssid, signal, freq, secured}], strongest first, one per SSID."""
    best = {}
    for block in re.split(r"^BSS ", text, flags=re.M)[1:]:
        ssid_m = re.search(r"^\s*SSID: (.*)$", block, re.M)
        ssid = ssid_m.group(1).strip() if ssid_m else ""
        if not ssid or "\\x00" in ssid:
            continue  # hidden network
        signal_m = re.search(r"signal: (-?[\d.]+) dBm", block)
        freq_m = re.search(r"freq: (\d+)", block)
        entry = {
            "ssid": ssid,
            "signal": float(signal_m.group(1)) if signal_m else -100.0,
            "freq": int(freq_m.group(1)) if freq_m else 0,
            "secured": bool(re.search(r"^\s*(RSN|WPA):", block, re.M)) or "Privacy" in block,
        }
        if ssid not in best or entry["signal"] > best[ssid]["signal"]:
            best[ssid] = entry
    return sorted(best.values(), key=lambda e: -e["signal"])


def signal_bars(dbm):
    level = 4 if dbm >= -55 else 3 if dbm >= -65 else 2 if dbm >= -75 else 1
    return "[green]" + "#" * level + "[/green][dim]" + "." * (4 - level) + "[/dim]"


def wifi_scan(iface):
    run(["rfkill", "unblock", "wifi"])
    run(["ip", "link", "set", iface, "up"])
    for attempt in range(4):
        rc, out = run(["iw", "dev", iface, "scan"], timeout=25)
        if rc == 0:
            return parse_iw_scan(out)
        time.sleep(1.5)  # "Device or resource busy" while the card is still waking up
    return []


def build_wpa_conf(ssid, psk_hex=None):
    """wpa_supplicant config. The SSID is written as hex so no escaping is needed."""
    ssid_hex = ssid.encode("utf-8").hex()
    if psk_hex:
        auth = f"    psk={psk_hex}\n    key_mgmt=WPA-PSK\n"
    else:
        auth = "    key_mgmt=NONE\n"
    return f"ctrl_interface={CTRL_DIR}\nupdate_config=0\nnetwork={{\n    ssid={ssid_hex}\n{auth}}}\n"


def derive_psk(ssid, passphrase):
    """64-hex-digit WPA key from wpa_passphrase (so the plain password is never stored)."""
    rc, out = run(["wpa_passphrase", ssid, passphrase])
    m = re.search(r"^\s*psk=([0-9a-f]{64})\s*$", out, re.M)
    return m.group(1) if rc == 0 and m else None


def wifi_connect(iface, ssid, passphrase=None):
    """Connect to a Wi-Fi network. Returns (ok, message)."""
    if not have("wpa_supplicant"):
        return False, "wpa_supplicant is not installed."
    psk = None
    if passphrase is not None:
        if not 8 <= len(passphrase) <= 63:
            return False, "A WPA password must be 8 to 63 characters."
        psk = derive_psk(ssid, passphrase)
        if not psk:
            return False, "Could not process the password (wpa_passphrase failed)."
    os.makedirs(WPA_DIR, mode=0o755, exist_ok=True)
    conf = os.path.join(WPA_DIR, f"pyos-{iface}.conf")
    fd = os.open(conf, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(build_wpa_conf(ssid, psk))

    run(["pkill", "-f", f"wpa_supplicant.*-i {iface}"])
    time.sleep(0.5)
    run(["rfkill", "unblock", "wifi"])
    run(["ip", "link", "set", iface, "up"])
    rc, out = run(["wpa_supplicant", "-B", "-i", iface, "-c", conf, "-D", "nl80211,wext"], timeout=20)
    if rc != 0:
        return False, f"wpa_supplicant failed to start. {out.strip()[:200]}"
    for _ in range(25):
        time.sleep(1)
        _, status = run(["wpa_cli", "-i", iface, "status"])
        if "wpa_state=COMPLETED" in status:
            return True, "Connected."
        if "WRONG_KEY" in status or "reason=WRONG_KEY" in status:
            break
    return False, "Could not connect - check the password and signal strength."


def dhcp(iface):
    """Get an address on `iface`. Returns (ok, ip)."""
    run(["ip", "link", "set", iface, "up"])
    if have("udhcpc"):
        rc, _ = run(["udhcpc", "-i", iface, "-n", "-q", "-t", "6", "-T", "3"], timeout=40)
    elif have("dhcpcd"):
        rc, _ = run(["dhcpcd", "-w", "-4", iface], timeout=40)
    else:
        return False, ""
    _, addr = run(["ip", "-4", "-o", "addr", "show", iface])
    ip = re.search(r"inet (\S+?)/", addr)
    if rc == 0 and ip and "nameserver" not in read("/etc/resolv.conf"):
        try:
            with open("/etc/resolv.conf", "a", encoding="utf-8") as f:
                f.write("\nnameserver 1.1.1.1\nnameserver 8.8.8.8\n")
        except OSError:
            pass
    return bool(ip), ip.group(1) if ip else ""


def check_internet():
    """(reachable, dns_works)."""
    try:
        socket.create_connection(("1.1.1.1", 443), timeout=4).close()
        reachable = True
    except OSError:
        reachable = False
    try:
        socket.gethostbyname("github.com")
        dns = True
    except OSError:
        dns = False
    return reachable, dns


def report_internet():
    with console.status("Testing the internet connection..."):
        reachable, dns = check_internet()
    if reachable and dns:
        console.print("[bold green]Online - the internet is reachable.[/bold green]")
    elif reachable:
        console.print("[yellow]Connected, but names do not resolve (DNS problem).[/yellow]")
    else:
        console.print("[red]No internet access yet.[/red]")
    return reachable and dns


def connect_wifi_interactive(iface):
    with console.status(f"Scanning for networks on {iface}..."):
        networks = wifi_scan(iface)
    if not networks:
        console.print("[yellow]No networks found. Wi-Fi cards often need firmware - run the hardware check, "
                      "or try again nearer the router.[/yellow]")
        ssid = Prompt.ask("Type a network name to try anyway (blank to cancel)", default="").strip()
        if not ssid:
            return False
        secured = Confirm.ask("Does it have a password?", default=True)
    else:
        table = Table(title="Wi-Fi networks", header_style="bold blue")
        table.add_column("#", justify="right")
        table.add_column("Network")
        table.add_column("Signal")
        table.add_column("Security")
        for i, n in enumerate(networks, 1):
            table.add_row(str(i), escape(n["ssid"]), signal_bars(n["signal"]), "password" if n["secured"] else "open")
        console.print(table)
        pick = IntPrompt.ask("Choose a network (0 = enter a hidden network, blank = cancel)", default=-1)
        if pick == 0:
            ssid = Prompt.ask("Network name").strip()
            secured = Confirm.ask("Does it have a password?", default=True)
        elif 1 <= pick <= len(networks):
            ssid, secured = networks[pick - 1]["ssid"], networks[pick - 1]["secured"]
        else:
            return False
        if not ssid:
            return False

    password = Prompt.ask(f"Password for {escape(ssid)}", password=True) if secured else None
    with console.status("Connecting..."):
        ok, message = wifi_connect(iface, ssid, password)
    if not ok:
        console.print(f"[red]{escape(message)}[/red]")
        return False
    with console.status("Getting an address..."):
        got, ip = dhcp(iface)
    if not got:
        console.print("[red]Connected to the network but did not get an address.[/red]")
        return False
    console.print(f"[green]Connected to {escape(ssid)} - address {ip}[/green]")
    return True


def network_setup():
    console.print(Panel("[bold]Network setup[/bold]", border_style="cyan", expand=False))
    while True:
        nics = interfaces()
        if not nics:
            console.print("[red]No network interfaces were found.[/red] The card may need a driver or firmware: "
                          "run the hardware check.")
            return False
        table = Table(title="Network interfaces", header_style="bold blue")
        for col in ("#", "Name", "Type", "State", "Address", "Driver"):
            table.add_column(col)
        for i, n in enumerate(nics, 1):
            table.add_row(str(i), n["name"], "Wi-Fi" if n["wireless"] else "wired", n["state"],
                          n["ip"] or "-", n["driver"] or "-")
        console.print(table)
        pick = IntPrompt.ask("Choose an interface (0 to finish)", default=0)
        if not 1 <= pick <= len(nics):
            return report_internet()
        nic = nics[pick - 1]
        if nic["wireless"]:
            ok = connect_wifi_interactive(nic["name"])
        else:
            with console.status(f"Requesting an address on {nic['name']}..."):
                ok, ip = dhcp(nic["name"])
            console.print(f"[green]{nic['name']} has address {ip}[/green]" if ok else
                          f"[red]No address on {nic['name']}. Is the cable plugged in?[/red]")
        if ok and report_internet():
            return True
        if not Confirm.ask("Try another interface or network?", default=True):
            return False


# ---------------------------------------------------------------- the flows
def menu():
    while True:
        console.print("\n[bold cyan]Hardware setup[/bold cyan]")
        console.print("  [bold]1[/bold] Hardware and firmware check")
        console.print("  [bold]2[/bold] Audio")
        console.print("  [bold]3[/bold] Network and internet")
        console.print("  [bold]4[/bold] Done")
        choice = Prompt.ask("Choose", choices=["1", "2", "3", "4"], default="4")
        if choice == "1":
            hardware_check()
        elif choice == "2":
            audio_setup()
        elif choice == "3":
            network_setup()
        else:
            return


def live_setup():
    """First-boot offer on the live ISO. Never raises: the OS must still boot."""
    try:
        reason = unavailable_reason()
        if reason:
            return
        nics = [n for n in interfaces() if n["ip"]]
        status = (f"[green]Online via {nics[0]['name']} ({nics[0]['ip']})[/green]" if nics
                  else "[yellow]Not connected to a network yet[/yellow]")
        console.print(Panel(f"Welcome to the PythonOS live system.\n\nNetwork: {status}\n\n"
                            "Set up your hardware now? You can check drivers and firmware, choose the audio output "
                            "and connect to the internet. (Run [bold]hwsetup[/bold] any time to come back.)",
                            title="[bold cyan]Hardware setup[/bold cyan]", border_style="cyan", expand=False))
        if Confirm.ask("Set up hardware now?", default=True):
            menu()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]Skipped hardware setup.[/yellow]")
    except Exception as e:
        console.print(f"[yellow]Hardware setup could not run: {escape(str(e))}[/yellow]")
