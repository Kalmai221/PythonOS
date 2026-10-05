"""Hardware, audio and network setup (the PythonOS live ISO, or any Linux system as root).

* hardware_check()  - what hardware was found, which drivers are loaded, missing firmware
* audio_setup()     - pick the sound card/output, unmute, set the volume, play a test
* network_setup()   - choose an interface, connect (wired DHCP or Wi-Fi) and test the internet
* keyboard_setup() / timezone_setup() - keyboard layout and time zone
* bluetooth_setup() / display_setup() / printer_setup() - pair devices, choose text size and resolution, add a printer
* live_setup()      - the first-boot flow on the ISO that offers all of the above
* apply_saved()     - every boot: put the saved keyboard, time zone, audio and Wi-Fi choices back (no questions)

Everything goes through run() so the parsing and flows can be tested without real hardware.
"""
import glob
import gzip
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
import time

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

console = Console()

PREFS_FILE = os.path.join(".OSData", "hardware.json")     # saved choices; on the ISO this lives on the data disk
BKEYMAPS = "/usr/share/bkeymaps"
ZONEINFO = "/usr/share/zoneinfo"
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
        out.append({"card": int(m.group(1)), "device": int(m.group(4)), "id": m.group(2),
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
        save_audio_choice(chosen, volume)
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


def wifi_connect(iface, ssid, passphrase=None, psk_hex=None):
    """Connect to a Wi-Fi network (with a password, or a key saved earlier). Returns (ok, message)."""
    if not have("wpa_supplicant"):
        return False, "wpa_supplicant is not installed."
    psk = psk_hex
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
    if Confirm.ask("Remember this network and reconnect automatically next time?", default=True):
        save_network(ssid, derive_psk(ssid, password) if password else None)
        console.print("[dim]Saved. (Only a derived key is kept, never the password itself.)[/dim]")
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


# ------------------------------------------------------------ saved choices
def save_audio_choice(chosen, volume):
    """Remember the output chosen for this sound card (by its id, which survives a changed card order) and make it the default."""
    prefs = load_prefs()
    devices = prefs.get("audio_devices", {})
    card_id = chosen.get("id") or str(chosen["card"])
    devices[card_id] = {"device": chosen["device"], "volume": volume, "label": chosen["label"]}
    save_pref("audio_devices", devices)
    save_pref("audio_default", card_id)


def restore_audio(prefs):
    """At boot: use the saved default output if that card is present, otherwise any saved card that is. Cards are found by
    id because their numbers can change between boots (a USB headset plugged in first becomes card 0)."""
    present = {c["id"]: c["index"] for c in parse_sound_cards(read("/proc/asound/cards"))}
    saved = prefs.get("audio_devices") or {}
    order = [prefs.get("audio_default")] + list(saved)
    for card_id in order:
        if card_id in saved and card_id in present:
            item = saved[card_id]
            write_asound_conf(present[card_id], item["device"])
            unmute_and_set_volume(present[card_id], item.get("volume", 80))
            return True
    old = prefs.get("audio")
    if old:                                      # a choice saved by an earlier version
        write_asound_conf(old["card"], old["device"])
        unmute_and_set_volume(old["card"], old.get("volume", 80))
        return True
    return False


def load_prefs():
    try:
        with open(PREFS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_pref(key, value):
    prefs = load_prefs()
    prefs[key] = value
    try:
        os.makedirs(os.path.dirname(PREFS_FILE), exist_ok=True)
        fd = os.open(PREFS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)     # holds Wi-Fi keys: owner only
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2)
    except OSError:
        pass


def save_network(ssid, psk_hex):
    nets = [n for n in load_prefs().get("wifi", []) if n.get("ssid") != ssid]
    nets.insert(0, {"ssid": ssid, "psk": psk_hex})
    save_pref("wifi", nets[:10])


# ------------------------------------------------------------------ keyboard
def keyboard_layouts():
    """[(label, bmap path)] for the keymaps installed (kbd-bkeymaps), the common ones first."""
    found = {}
    for path in glob.glob(os.path.join(BKEYMAPS, "*", "*.bmap.gz")):
        layout, variant = os.path.basename(os.path.dirname(path)), os.path.basename(path)[:-len(".bmap.gz")]
        found[layout if variant == layout else f"{layout}-{variant}"] = path
    common = ["us", "uk", "gb", "de", "fr", "es", "it", "pt", "br", "ie", "nl", "se", "no", "dk", "fi", "ca", "pl", "cz", "tr", "jp", "ru"]
    ordered = [n for n in common if n in found] + sorted(n for n in found if n not in common)
    return [(n, found[n]) for n in ordered]


def apply_keyboard(path):
    """Load a keymap into the console. Returns True on success."""
    try:
        with gzip.open(path, "rb") as f:
            data = f.read()
        p = subprocess.run(["loadkmap"], input=data, capture_output=True, timeout=10)
        return p.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def keyboard_setup():
    console.print(Panel("[bold]Keyboard layout[/bold]", border_style="cyan", expand=False))
    layouts = keyboard_layouts()
    if not layouts or not have("loadkmap"):
        console.print("[yellow]No keyboard layouts are installed on this system, so the default (US) stays.[/yellow]")
        return False
    names = [n for n, _ in layouts]
    console.print("Available: " + ", ".join(names[:40]) + (" ..." if len(names) > 40 else ""))
    current = load_prefs().get("keyboard", "us")
    while True:
        choice = Prompt.ask("Layout name (Enter keeps the current one)", default=current).strip().lower()
        if choice in names:
            break
        console.print(f"[yellow]'{escape(choice)}' is not available. Try one of the names above.[/yellow]")
    if not apply_keyboard(dict(layouts)[choice]):
        console.print("[red]Could not switch the layout.[/red]")
        return False
    save_pref("keyboard", choice)
    console.print(f"[green]Keyboard layout: {choice}.[/green] Type a few keys to check them.")
    return True


# ------------------------------------------------------------------ time zone
def timezone_names():
    try:
        from zoneinfo import available_timezones
        return sorted(z for z in available_timezones() if "/" in z and not z.startswith(("Etc/", "posix", "right", "SystemV")))
    except Exception:
        return []


def apply_timezone(zone):
    """Use this time zone for the rest of this run (and as /etc/localtime when we may). Returns True on success."""
    if zone not in timezone_names():
        return False
    os.environ["TZ"] = zone
    if hasattr(time, "tzset"):
        time.tzset()
    try:
        if os.path.isdir(ZONEINFO) and os.geteuid() == 0:
            if os.path.lexists("/etc/localtime"):
                os.remove("/etc/localtime")
            os.symlink(os.path.join(ZONEINFO, zone), "/etc/localtime")
    except (OSError, AttributeError):
        pass
    return True


def timezone_setup():
    console.print(Panel("[bold]Time zone[/bold]", border_style="cyan", expand=False))
    names = timezone_names()
    if not names:
        console.print("[yellow]No time zone data on this system, so the clock stays in UTC.[/yellow]")
        return False
    console.print(f"Now: {time.strftime('%H:%M')} ({time.tzname[0]})")
    while True:
        text = Prompt.ask("Part of your city or region (for example London, New_York, Tokyo; Enter to cancel)", default="").strip().lower().replace(" ", "_")
        if not text:
            return False
        matches = [n for n in names if text in n.lower()]
        if not matches:
            console.print("[yellow]Nothing matches. Try a nearby big city.[/yellow]")
            continue
        for i, n in enumerate(matches[:15], 1):
            console.print(f"  [bold]{i}[/bold] {n}")
        if len(matches) > 15:
            console.print(f"  [dim]... and {len(matches) - 15} more; type more letters to narrow it down[/dim]")
            continue
        pick = IntPrompt.ask("Number", default=1) if len(matches) > 1 else 1
        if 1 <= pick <= len(matches):
            zone = matches[pick - 1]
            apply_timezone(zone)
            save_pref("timezone", zone)
            console.print(f"[green]Time zone: {zone}. The time is now {time.strftime('%H:%M')}.[/green]")
            return True


# ------------------------------------------------------------------- bluetooth
MAC_RE = re.compile(r"^[0-9A-Fa-f]{2}(:[0-9A-Fa-f]{2}){5}$")


def parse_bt_devices(text):
    """`bluetoothctl devices` -> [{mac, name}]."""
    return [{"mac": m.group(1).upper(), "name": m.group(2).strip()}
            for m in re.finditer(r"^Device ([0-9A-Fa-f:]{17}) (.*)$", text, re.M)]


def bluetooth_setup():
    console.print(Panel("[bold]Bluetooth[/bold]", border_style="cyan", expand=False))
    if not have("bluetoothctl"):
        console.print("[yellow]The Bluetooth tools (bluez) are not installed on this system.[/yellow]")
        return False
    run(["rfkill", "unblock", "bluetooth"])
    code, out = run(["bluetoothctl", "power", "on"], timeout=15)
    if code != 0 and "succeeded" not in out.lower():
        console.print(f"[yellow]No Bluetooth adapter is ready ({escape(out.strip()[-120:]) or 'none found'}). Is the adapter plugged in, "
                      "and does it need firmware (run: hwsetup check)?[/yellow]")
        return False
    console.print("[dim]Put the device you want to pair in pairing mode. This works with devices that pair without typing a code "
                  "(most speakers, mice and many keyboards).[/dim]")
    while True:
        with console.status("Looking for devices (10 seconds)..."):
            run(["bluetoothctl", "--timeout", "10", "scan", "on"], timeout=25)
        _, listing = run(["bluetoothctl", "devices"])
        devices = parse_bt_devices(listing)
        _, paired_text = run(["bluetoothctl", "devices", "Paired"])
        paired = {d["mac"] for d in parse_bt_devices(paired_text)}
        if not devices:
            console.print("[yellow]No devices found.[/yellow]")
        else:
            table = Table(title="Bluetooth devices", header_style="bold blue")
            for col in ("#", "Name", "Address", "State"):
                table.add_column(col)
            for i, d in enumerate(devices, 1):
                table.add_row(str(i), escape(d["name"]), d["mac"], "[green]paired[/green]" if d["mac"] in paired else "")
            console.print(table)
        pick = IntPrompt.ask("Number to pair or connect (0 to scan again, blank to finish)", default=-1)
        if pick == -1:
            return True
        if not 1 <= pick <= len(devices):
            continue
        d = devices[pick - 1]
        if not MAC_RE.match(d["mac"]):
            continue
        with console.status(f"Pairing with {d['name']}..."):
            if d["mac"] not in paired:
                code, out = run(["bluetoothctl", "pair", d["mac"]], timeout=45)
                if code != 0 and "already" not in out.lower():
                    console.print(f"[red]Could not pair ({escape(out.strip()[-120:])}). Some devices need a code typed on them; "
                                  "those are not supported yet.[/red]")
                    continue
            run(["bluetoothctl", "trust", d["mac"]])
            code, out = run(["bluetoothctl", "connect", d["mac"]], timeout=30)
        if code == 0 or "successful" in out.lower():
            console.print(f"[green]Connected to {escape(d['name'])}. It will reconnect by itself next time.[/green]")
            macs = [m for m in load_prefs().get("bluetooth", []) if m != d["mac"]]
            save_pref("bluetooth", [d["mac"]] + macs[:9])
        else:
            console.print(f"[yellow]Paired, but could not connect ({escape(out.strip()[-120:])}).[/yellow]")


# --------------------------------------------------------------------- display
FONT_SIZES = [("Small", "ter-v16n"), ("Medium", "ter-v20n"), ("Large", "ter-v24n"), ("Extra large", "ter-v32n")]
FONT_DIR = "/usr/share/consolefonts"


def available_fonts():
    return [(label, name) for label, name in FONT_SIZES
            if os.path.exists(os.path.join(FONT_DIR, name + ".psf.gz")) or os.path.exists(os.path.join(FONT_DIR, name + ".psf"))]


def screen_size():
    """(width, height) of the console framebuffer, or None."""
    text = read("/sys/class/graphics/fb0/virtual_size")
    m = re.match(r"(\d+),(\d+)", text)
    return (int(m.group(1)), int(m.group(2))) if m else None


def display_modes():
    """Resolutions the connected screens report, largest first."""
    modes = set()
    for status in glob.glob("/sys/class/drm/card*-*/status"):
        if read(status) != "connected":
            continue
        for line in read(os.path.join(os.path.dirname(status), "modes")).splitlines():
            if re.fullmatch(r"\d+x\d+", line.strip()):
                modes.add(line.strip())
    return sorted(modes, key=lambda m: -int(m.split("x")[0]))


def apply_font(name):
    if not re.fullmatch(r"ter-v\d+n", name or ""):
        return False
    code, _ = run(["setfont", name], timeout=10)
    return code == 0


def display_setup():
    console.print(Panel("[bold]Display[/bold]", border_style="cyan", expand=False))
    size = screen_size()
    console.print("Screen: " + (f"{size[0]} x {size[1]}" if size else "unknown"))
    fonts = available_fonts()
    if fonts and have("setfont"):
        console.print("Text size makes everything bigger or smaller without changing the resolution:")
        for i, (label, name) in enumerate(fonts, 1):
            console.print(f"  [bold]{i}[/bold] {label}")
        pick = IntPrompt.ask("Choose a size (blank to keep it)", default=0)
        if 1 <= pick <= len(fonts):
            label, name = fonts[pick - 1]
            if apply_font(name):
                prefs = load_prefs().get("display", {})
                prefs["font"] = name
                save_pref("display", prefs)
                console.print(f"[green]Text size: {label}.[/green]")
            else:
                console.print("[yellow]Could not change the text size on this screen.[/yellow]")
    else:
        console.print("[dim]No console fonts are installed here, so the text size cannot be changed.[/dim]")
    modes = display_modes()
    if modes and have("fbset"):
        console.print("Resolutions this screen offers: " + ", ".join(modes[:10]))
        want = Prompt.ask("Resolution to try, like 1280x720 (blank to keep it)", default="").strip()
        if want:
            if want not in modes:
                console.print("[yellow]The screen does not list that resolution.[/yellow]")
            else:
                w, h = want.split("x")
                before = screen_size()
                run(["fbset", "-xres", w, "-yres", h, "-vxres", w, "-vyres", h], timeout=10)
                if screen_size() == (int(w), int(h)):
                    prefs = load_prefs().get("display", {})
                    prefs["mode"] = want
                    save_pref("display", prefs)
                    console.print(f"[green]Resolution: {want}.[/green]")
                else:
                    console.print("[yellow]This display only works at its native resolution (the graphics driver ignored the "
                                  f"request).[/yellow] Staying at {before[0]}x{before[1]}." if before else "[yellow]Not changed.[/yellow]")
    elif modes:
        console.print("[dim]The resolution can only be changed with the fbset tool, which is not installed.[/dim]")
    return True


# --------------------------------------------------------------------- printer
URI_RE = re.compile(r"^(ipp|ipps|http|https|socket|lpd|usb|dnssd)://[^\s'\"`;|&$<>]+$")
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,30}$")


def parse_lpinfo(text):
    """`lpinfo -v` -> [uri] for device types a person can use."""
    out = []
    for line in text.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2 and parts[0] in ("network", "direct") and URI_RE.match(parts[1].strip()) and not parts[1].startswith(("hp:", "hpfax")):
            out.append(parts[1].strip())
    return out


def printer_setup():
    console.print(Panel("[bold]Printer[/bold]", border_style="cyan", expand=False))
    if not have("lpadmin"):
        console.print("[yellow]The printing system (CUPS) is not installed on this system.[/yellow]")
        return False
    if have("rc-service"):
        run(["rc-service", "cupsd", "start"], timeout=20)
    code, out = run(["lpstat", "-p", "-d"], timeout=15)
    if "printer" in out:
        console.print(escape(out.strip()))
    with console.status("Looking for printers..."):
        _, found = run(["lpinfo", "-v"], timeout=30)
    uris = parse_lpinfo(found)
    for i, uri in enumerate(uris[:12], 1):
        console.print(f"  [bold]{i}[/bold] {escape(uri)}")
    answer = Prompt.ask("Number of a printer above, or type its address (like 192.168.1.20 or ipp://host/ipp/print); blank to finish",
                        default="").strip()
    if not answer:
        return True
    if answer.isdigit() and 1 <= int(answer) <= len(uris):
        uri = uris[int(answer) - 1]
    elif "://" in answer:
        uri = answer
    else:
        uri = f"ipp://{answer}/ipp/print"
    if not URI_RE.match(uri):
        console.print("[red]That is not a printer address I can use.[/red]")
        return False
    name = Prompt.ask("Name for this printer (letters and digits)", default="printer").strip()
    if not NAME_RE.match(name):
        console.print("[red]Use letters, digits, - and _ only (up to 30).[/red]")
        return False
    with console.status("Adding the printer..."):
        code, out = run(["lpadmin", "-p", name, "-E", "-v", uri, "-m", "everywhere"], timeout=60)
    if code != 0:
        console.print(f"[red]Could not add it ({escape(out.strip()[-150:])}). Only modern network printers that support "
                      "driverless printing (IPP Everywhere) are supported.[/red]")
        return False
    run(["lpadmin", "-d", name])
    console.print(f"[green]Added {escape(name)} and made it the default.[/green] Print a file with: [bold]print <file>[/bold]")
    if Confirm.ask("Print a test page now?", default=False):
        code, out = run(["lp", "-d", name, "/usr/share/cups/data/testprint"], timeout=30)
        console.print("[green]Sent.[/green]" if code == 0 else f"[red]Could not print ({escape(out.strip()[-120:])}).[/red]")
    return True


# ----------------------------------------------------- every boot, no questions
def pyos_notify(message):
    try:
        from pyos import notify
        notify.notify(message, title="Network")
    except Exception:
        pass


def _reconnect_wifi(prefs):
    """Background: join the strongest saved network that is in range."""
    try:
        saved = {n["ssid"]: n.get("psk") for n in prefs.get("wifi", []) if n.get("ssid")}
        for nic in interfaces():
            if not nic["wireless"] or nic["ip"]:
                continue
            seen = [n["ssid"] for n in wifi_scan(nic["name"])]
            for ssid in [s for s in seen if s in saved]:
                ok, _ = wifi_connect(nic["name"], ssid, psk_hex=saved[ssid])
                if ok and dhcp(nic["name"])[0]:
                    pyos_notify(f"Connected to {ssid}")
                    break
    except Exception:
        pass


def apply_saved():
    """Put the saved keyboard layout, time zone, audio output and Wi-Fi back at boot. Silent; never raises."""
    try:
        prefs = load_prefs()
        if not prefs:
            return
        if prefs.get("timezone"):
            apply_timezone(prefs["timezone"])
        if unavailable_reason():
            return
        layout = prefs.get("keyboard")
        if layout and layout != "us":
            path = dict(keyboard_layouts()).get(layout)
            if path:
                apply_keyboard(path)
        if have("amixer"):
            restore_audio(prefs)
        display = prefs.get("display") or {}
        if display.get("font"):
            apply_font(display["font"])
        for mac in prefs.get("bluetooth", []):
            if have("bluetoothctl") and MAC_RE.match(mac):
                threading.Thread(target=run, args=(["bluetoothctl", "connect", mac], 30), daemon=True).start()
        if prefs.get("wifi") and have("wpa_supplicant"):
            threading.Thread(target=_reconnect_wifi, args=(prefs,), daemon=True).start()
    except Exception:
        pass


# ---------------------------------------------------------------- the flows
def menu():
    from pyos import stdio
    stdio.fresh_screen()
    while True:
        console.print("\n[bold cyan]Hardware setup[/bold cyan]")
        console.print("  [bold]1[/bold] Hardware and firmware check")
        console.print("  [bold]2[/bold] Audio")
        console.print("  [bold]3[/bold] Network and internet")
        console.print("  [bold]4[/bold] Keyboard layout")
        console.print("  [bold]5[/bold] Time zone")
        console.print("  [bold]6[/bold] Bluetooth")
        console.print("  [bold]7[/bold] Display (text size, resolution)")
        console.print("  [bold]8[/bold] Printer")
        console.print("  [bold]9[/bold] Done")
        choice = Prompt.ask("Choose", choices=[str(i) for i in range(1, 10)], default="9")
        if choice == "1":
            hardware_check()
        elif choice == "2":
            audio_setup()
        elif choice == "3":
            network_setup()
        elif choice == "4":
            keyboard_setup()
        elif choice == "5":
            timezone_setup()
        elif choice == "6":
            bluetooth_setup()
        elif choice == "7":
            display_setup()
        elif choice == "8":
            printer_setup()
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
