"""PythonOS Setup Wizard: the decisions and the actions behind the window and the terminal version.

The wizard looks at the computer it runs on (system, processor, what is installed), asks what you want (install PythonOS here, put it on a
phone, make a bootable USB stick, run it in a virtual machine or in Docker), chooses the right file of the latest release for that, downloads
it, checks it against the release's SHA256SUMS, and does the next step or tells you exactly what it is.

Everything that decides something is a plain function (plan_* ...), so it is tested without a window or a network.
"""
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
for _path in (os.path.join(HERE, os.pardir), os.path.join(HERE, os.pardir, os.pardir, "pyos")):
    if os.path.isdir(_path) and os.path.abspath(_path) not in sys.path:
        sys.path.append(os.path.abspath(_path))
import archinfo  # noqa: E402
import catalog  # noqa: E402
import flashlib as flash  # noqa: E402

API = "https://api.github.com/repos/Kalmai221/PythonOS/releases/latest"
RELEASES_PAGE = "https://github.com/Kalmai221/PythonOS/releases/latest"
DOCKER_IMAGE = "ghcr.io/kalmai221/pythonos"
DOCKER_RUN = f"docker run -it --rm -v pythonos-data:/data {DOCKER_IMAGE}"

GOALS = [
    ("install", "Install PythonOS on this computer", "A normal app on this computer: it opens in its own window or from the terminal."),
    ("android", "Put PythonOS on an Android phone or tablet", "Downloads the app (APK); can install it on a phone connected with a cable."),
    ("usb", "Make a bootable USB stick", "A computer starts PythonOS from the stick without touching its disk (the live system)."),
    ("vm", "Run PythonOS in a virtual machine", "VirtualBox, VMware, QEMU, Proxmox, UTM, Hyper-V and others: you pick the program."),
    ("docker", "Run PythonOS in Docker", "One command; your accounts and files are kept in a Docker volume."),
    ("download", "Just let me pick a file to download", "Every file of the latest release, checked after the download."),
]

VM_SOFTWARE = [
    ("virtualbox", "VirtualBox", "Free, Windows / Linux / macOS (Intel and Apple silicon)"),
    ("vmware", "VMware Workstation, Player or Fusion", "Windows / Linux / macOS"),
    ("qemu", "QEMU / KVM (virt-manager, libvirt)", "Linux, also Windows and macOS"),
    ("proxmox", "Proxmox VE", "A server for virtual machines"),
    ("utm", "UTM", "macOS (Intel and Apple silicon)"),
    ("hyperv", "Hyper-V", "Windows Pro / Enterprise"),
    ("parallels", "Parallels Desktop", "macOS"),
    ("other", "Another program, or I do not know", "Uses the bootable ISO, which every virtual machine program can start"),
]


# ------------------------------------------------------------------------------------------ this computer
def parse_os_release(text):
    """{'id', 'like': [...], 'name'} from the text of /etc/os-release."""
    fields = {}
    for line in text.splitlines():
        if "=" in line and not line.startswith("#"):
            key, value = line.split("=", 1)
            fields[key.strip()] = value.strip().strip('"').strip("'")
    return {"id": fields.get("ID", "").lower(), "like": fields.get("ID_LIKE", "").lower().split(), "name": fields.get("PRETTY_NAME") or fields.get("NAME", "")}


def package_kind(distro):
    """Which package file a Linux distribution takes: 'deb', 'rpm', 'pacman', or None (use the tarball)."""
    names = {distro.get("id", "")} | set(distro.get("like", []))
    if names & {"debian", "ubuntu", "linuxmint", "raspbian", "pop", "elementary", "kali", "zorin", "mint"}:
        return "deb"
    if names & {"fedora", "rhel", "centos", "rocky", "almalinux", "ol", "suse", "opensuse", "opensuse-leap", "opensuse-tumbleweed", "sles", "mageia", "amzn"}:
        return "rpm"
    if names & {"arch", "manjaro", "endeavouros", "garuda", "artix", "cachyos"}:
        return "pacman"
    return None


def _which(*names):
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


def find_tools():
    """What is installed that the wizard can use: {'virtualbox': path, 'docker': path, ...} (only those found)."""
    system = platform.system()
    candidates = {
        "virtualbox": (("VBoxManage",), [r"C:\Program Files\Oracle\VirtualBox\VBoxManage.exe", "/Applications/VirtualBox.app/Contents/MacOS/VBoxManage"]),
        "vmware": (("vmrun", "vmplayer", "vmware"), [r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
                                                      "/Applications/VMware Fusion.app/Contents/Library/vmrun"]),
        "qemu": (("qemu-system-x86_64", "qemu-system-aarch64", "virt-manager", "virsh"), [r"C:\Program Files\qemu\qemu-system-x86_64.exe"]),
        "proxmox": (("qm", "pvesh"), []),
        "utm": (("utmctl",), ["/Applications/UTM.app"]),
        "parallels": (("prlctl",), ["/Applications/Parallels Desktop.app"]),
        "docker": (("docker",), [r"C:\Program Files\Docker\Docker\resources\bin\docker.exe"]),
        "adb": (("adb",), []),
    }
    found = {}
    for key, (names, paths) in candidates.items():
        path = _which(*names) or next((p for p in paths if os.path.exists(p)), None)
        if path:
            found[key] = path
    if system == "Windows" and shutil.which("powershell"):
        try:
            out = subprocess.run(["powershell", "-NoProfile", "-Command", "if (Get-Command Get-VM -ErrorAction SilentlyContinue) { 'yes' }"],
                                 capture_output=True, text=True, timeout=8, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if "yes" in out.stdout:
                found["hyperv"] = "Get-VM"
        except (OSError, subprocess.SubprocessError):
            pass
    return found


def detect_environment():
    """{'os': windows|macos|linux, 'os_name', 'arch', 'arch_label', 'emulated', 'note', 'distro', 'package', 'tools'} for this computer."""
    system = platform.system()
    info = archinfo.detect()
    env = {"os": {"Windows": "windows", "Darwin": "macos", "Linux": "linux"}.get(system, system.lower()), "arch": info["arch"],
           "arch_label": info["label"], "emulated": info["emulated"], "note": info["note"], "distro": {}, "package": None, "tools": {}}
    if system == "Windows":
        env["os_name"] = f"Windows {platform.release()}"
    elif system == "Darwin":
        env["os_name"] = f"macOS {platform.mac_ver()[0]}"
    else:
        try:
            with open("/etc/os-release", encoding="utf-8") as f:
                env["distro"] = parse_os_release(f.read())
        except OSError:
            pass
        env["os_name"] = env["distro"].get("name") or "Linux"
        env["package"] = package_kind(env["distro"])
    env["tools"] = find_tools()
    return env


def describe_environment(env):
    tools = [name for name in env["tools"] if name != "adb"]
    text = f"{env['os_name']}, {env['arch_label']}"
    if env["emulated"]:
        text += " (this program runs emulated)"
    if tools:
        text += "; found: " + ", ".join(sorted(tools))
    return text


# ------------------------------------------------------------------------------------------ the release
class Release:
    """The latest release: its files (name -> {'url', 'size'}), their checksums and the catalog entries."""

    def __init__(self, tag, assets, sums=None, entries=None):
        self.tag = tag
        self.version = tag.lstrip("v")
        self.assets = assets
        self.sums = sums or {}
        self.entries = entries if entries is not None else catalog.build(assets)

    def entry(self, **wanted):
        return catalog.find(self.entries, **wanted)

    def size(self, name):
        return self.assets.get(name, {}).get("size", 0)


def _get_json(url):
    with flash._open(url) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def fetch_release():
    """The latest release from GitHub. Falls back to the SHA256SUMS listing when the API cannot be used (rate limit)."""
    try:
        data = _get_json(API)
        assets = {a["name"]: {"url": a["browser_download_url"], "size": int(a.get("size") or 0)} for a in data.get("assets", [])}
        sums = {}
        if "SHA256SUMS" in assets:
            with flash._open(assets["SHA256SUMS"]["url"]) as response:
                sums = flash.parse_sums(response.read().decode("utf-8", "replace"))
        entries = None
        if "release-catalog.json" in assets:
            try:
                entries = _get_json(assets["release-catalog.json"]["url"]).get("files")
            except (OSError, ValueError):
                entries = None
        return Release(data["tag_name"], assets, sums, entries)
    except (OSError, ValueError, KeyError):
        sums = flash.latest_sums()
        match = next((re.search(r"-(\d+(?:\.\d+)+)", n) for n in sums if n.startswith(("pythonos-", "PythonOS-"))), None)
        tag = "v" + match.group(1) if match else "latest"
        return Release(tag, {n: {"url": f"{flash.LATEST}/{n}", "size": 0} for n in sums}, sums)


# ------------------------------------------------------------------------------------------ plans (pure)
def _file(release, **wanted):
    entry = release.entry(**wanted)
    return entry["name"] if entry else None


def plan_install(env, release):
    """Install PythonOS on this computer. Returns a plan dict (see make_plan)."""
    if env["os"] == "windows":
        name = _file(release, os_name="windows", kind="installer-web")
        if name:
            return make_plan("install", [name], "run-installer", [
                "The installer is small; it fetches the right PythonOS package for this PC (" + env["arch_label"] + "), checks it, and offers shortcuts.",
                "It installs for your user: no administrator rights needed."])
        fallback = _file(release, os_name="windows", kind="installer", arch=env["arch"]) or _file(release, os_name="windows", kind="portable", arch=env["arch"])
        return make_plan("install", [fallback] if fallback else [], "run-installer" if fallback else "none",
                         ["This release has no web installer; using the full package."] if fallback else ["This release has no Windows package."])
    if env["os"] == "linux":
        kind = env.get("package")
        if kind:
            name = _file(release, os_name="linux", kind=kind)
            if name:
                return make_plan("install", [name], "install-package", [
                    f"Your system ({env['distro'].get('name') or 'Linux'}) takes {kind} packages. It is installed with your package tool; "
                    "you are asked for your password.", "Afterwards start it with: pythonos"], package=kind)
        name = _file(release, os_name="linux", kind="tarball")
        steps = ["Unpacked into your home folder (no administrator rights); start it with: pythonos",
                 "Needs Python 3.8 or newer with venv (Debian/Ubuntu: sudo apt install python3 python3-venv)."]
        return make_plan("install", [name] if name else [], "install-tarball" if name else "none", steps)
    if env["os"] == "macos":
        return make_plan("install", [], "none", ["macOS is not supported by this program. On a Mac, use Docker (choose it here) or a virtual machine: "
                                                 "the release page explains both."])
    return make_plan("install", [], "none", [f"{env['os']} is not supported by the wizard yet. See the releases page."])


def plan_android(release, arch="aarch64"):
    """The APK for a phone: the installer app for "not sure" (it picks the right app by itself), else the full app for arm64 (nearly every
    phone) or x86_64 (Chromebooks, emulators); the universal APK of older releases is the last resort."""
    installer = _file(release, os_name="android", kind="apk-installer")
    if arch == "universal" and installer:
        name = installer
    else:
        name = (_file(release, os_name="android", kind="apk", arch=arch) if arch != "universal" else None) or installer \
            or _file(release, os_name="android", kind="apk-universal")
    return make_plan("android", [name] if name else [], "android-apk", [
        "Copy the APK to the phone and open it, or connect the phone with a cable (USB debugging on) and the wizard installs it.",
        "Android asks you to allow installs from this source the first time. Updates later come from inside PythonOS."])


def plan_usb(arch="x86_64", minimal=False):
    """A bootable stick: the choice of image is made in the stick window (it can download the right one itself)."""
    return make_plan("usb", [], "flash", ["The next screen writes the image to the stick and checks it."], arch=arch, minimal=minimal)


def vm_steps(software, files):
    """What to do with the downloaded file(s), per virtual machine program."""
    ova = next((f for f in files if f.endswith(".ova")), "the .ova file")
    qcow = next((f for f in files if f.endswith(".qcow2") and "data" not in f), "the .qcow2 file")
    data = next((f for f in files if f.endswith("data.qcow2")), None)
    iso = next((f for f in files if f.endswith(".iso")), "the .iso file")
    steps = {
        "virtualbox": [f"File > Import Appliance... and choose {ova} (the wizard can do this for you).", "Start the machine \"PythonOS\". It has 1 GB, 2 CPUs and a data disk."],
        "vmware": [f"File > Open... (Workstation / Player) or File > Import (Fusion) and choose {ova}.", "Power it on. It has a data disk that keeps your files."],
        "qemu": [f"Attach {qcow} as a disk" + (f" and {data} as a second disk (it keeps your files)" if data else "") + ".",
                 "virt-manager: New VM > Import existing disk image, Linux, 1024 MB. Or on the command line: qemu-system-x86_64 -m 1024 -enable-kvm -drive file=" + qcow
                 + (f" -drive file={data}" if data else "")],
        "proxmox": [f"Upload {qcow} to the Proxmox host, create a VM (no disk, BIOS or UEFI), then: qm importdisk <vmid> {qcow} <storage>",
                    "Attach the imported disk as the boot disk" + (f"; do the same with {data} as a second disk" if data else "") + "."],
        "utm": [f"Create a new virtual machine in UTM: Virtualize (Apple silicon uses the ARM image), choose Other, Boot ISO Image: {iso}.",
                "Give it 1 GB of memory and a small disk; start it."],
        "hyperv": [f"New > Virtual Machine, Generation 2, 1024 MB memory, then Installation Options: Image file {iso}.",
                   "In the machine's Settings > Security, turn Secure Boot off (or choose the Microsoft UEFI Certificate Authority template)."],
        "parallels": [f"Create a new VM from an image file: {iso}. Choose Other Linux as the system, 1 GB of memory."],
        "other": [f"Create a new virtual machine, attach {iso} as its CD/DVD, 1 GB of memory (512 MB for the minimal image), and start it."],
    }
    return steps.get(software, steps["other"])


def plan_vm(software, host_arch, release):
    """Which file(s) a virtual machine program needs. The ready-made images are for Intel/AMD computers; an ARM computer uses the ARM ISO."""
    notes = []
    arch = "aarch64" if host_arch == "aarch64" else "x86_64"
    if arch == "aarch64":
        iso = _file(release, os_name="bootable", kind="iso", arch="aarch64", variant="full")
        files = [iso] if iso else []
        notes.append("This is an ARM computer. The ready-made virtual machine images are for Intel/AMD computers, so the ARM live image (ISO) is used: "
                     "every virtual machine program can start it.")
    elif software in ("virtualbox", "vmware"):
        ova = _file(release, os_name="vm", kind="ova")
        files = [ova] if ova else []
    elif software in ("qemu", "proxmox"):
        wanted = [_file(release, os_name="vm", kind="qcow2"), _file(release, os_name="vm", kind="qcow2-data")]
        if software == "qemu":
            wanted.append(_file(release, os_name="vm", kind="vm-kit"))
        files = [f for f in wanted if f]
    else:
        iso = _file(release, os_name="bootable", kind="iso", arch="x86_64", variant="full")
        files = [iso] if iso else []
    if not files:
        notes.append("This release has no file for that program.")
    return make_plan("vm", files, "vm", vm_steps(software, files), software=software, notes=notes)


def plan_docker():
    return make_plan("docker", [], "docker-run", [f"Run: {DOCKER_RUN}", "The volume (pythonos-data) keeps your accounts, files and updates between runs."])


def make_plan(goal, files, action, steps, **extra):
    plan = {"goal": goal, "files": [f for f in files if f], "action": action, "steps": list(steps), "notes": []}
    plan.update(extra)
    return plan


def plan_for(goal, env, release, **options):
    """The plan for a goal: options may hold 'software' (vm), 'arch' and 'minimal' (usb), 'abi' (android)."""
    if goal == "install":
        return plan_install(env, release)
    if goal == "android":
        return plan_android(release, options.get("abi") or "aarch64")
    if goal == "usb":
        return plan_usb(options.get("arch") or env["arch"], bool(options.get("minimal")))
    if goal == "vm":
        return plan_vm(options.get("software") or "other", env["arch"], release)
    if goal == "docker":
        return plan_docker()
    return make_plan("download", [], "none", [])


# ------------------------------------------------------------------------------------------ doing it
def download(release, name, folder, progress=None):
    """Download one release file into `folder` and check it against the release's SHA256SUMS. Returns the path."""
    expected = release.sums.get(name)
    if not expected:
        raise ValueError("this release has no checksum for the file, so it cannot be checked")
    os.makedirs(folder, exist_ok=True)
    return flash.download_file(release.assets[name]["url"], expected, os.path.join(folder, name), progress)


def default_folder():
    folder = os.path.join(os.path.expanduser("~"), "Downloads")
    return folder if os.path.isdir(folder) else tempfile.gettempdir()


def run_windows_installer(path):
    subprocess.Popen([path], close_fds=True)
    return "The installer is open: follow it, then start PythonOS from the Start menu."


def install_package(kind, path):
    """Install a downloaded .deb/.rpm/Arch package with the system's tool (it asks for the password). Returns (ok, message)."""
    command = {"deb": ["apt-get", "install", "-y", path], "rpm": ["dnf", "install", "-y", "--nogpgcheck", path],
               "pacman": ["pacman", "-U", "--noconfirm", path]}.get(kind)
    if kind == "deb" and not shutil.which("apt-get"):
        command = ["dpkg", "-i", path]
    if kind == "rpm" and not shutil.which("dnf"):
        command = ["zypper", "--non-interactive", "install", "--allow-unsigned-rpm", path] if shutil.which("zypper") else ["rpm", "-U", path]
    wrapped = flash.privileged_command(command)
    if not wrapped:
        return False, "No way to ask for administrator rights was found. Install it yourself with: sudo " + " ".join(command)
    code = subprocess.call(wrapped)
    return code == 0, "PythonOS is installed. Start it with: pythonos" if code == 0 else "The package tool did not finish. Nothing was changed by the wizard."


def install_tarball(path):
    """Unpack the portable launcher into ~/.local/share/pythonos-app and link it as ~/.local/bin/pythonos. Returns (ok, message)."""
    import tarfile
    target = os.path.join(os.path.expanduser("~"), ".local", "share", "pythonos-app")
    link = os.path.join(os.path.expanduser("~"), ".local", "bin", "pythonos")
    os.makedirs(target, exist_ok=True)
    os.makedirs(os.path.dirname(link), exist_ok=True)
    with tarfile.open(path, "r:gz") as tar:
        for member in tar.getmembers():
            parts = member.name.split("/")
            if not member.isfile() or len(parts) != 2 or ".." in parts:
                continue
            data = tar.extractfile(member).read()
            destination = os.path.join(target, parts[1])
            with open(destination, "wb") as f:
                f.write(data)
            os.chmod(destination, 0o755 if parts[1] == "pythonos" else 0o644)
    if os.path.lexists(link):
        os.remove(link)
    os.symlink(os.path.join(target, "pythonos"), link)
    on_path = os.path.dirname(link) in os.environ.get("PATH", "").split(os.pathsep)
    return True, f"Installed in {target}. Start it with: pythonos" + ("" if on_path else f"  (add {os.path.dirname(link)} to your PATH, or run {link})")


def adb_devices(adb):
    out = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=15)
    return [line.split()[0] for line in out.stdout.splitlines()[1:] if line.strip().endswith("device")]


def install_apk(adb, path):
    """Install an APK on a phone connected with a cable. Returns (ok, message)."""
    devices = adb_devices(adb)
    if not devices:
        return False, "No phone found. Turn on USB debugging, connect it with a cable and allow this computer, or copy the APK to the phone and open it."
    out = subprocess.run([adb, "install", "-r", path], capture_output=True, text=True, timeout=300)
    return out.returncode == 0, "Installed on the phone." if out.returncode == 0 else (out.stdout + out.stderr).strip()[-300:]


def import_virtualbox(vboxmanage, path):
    out = subprocess.run([vboxmanage, "import", path, "--vsys", "0", "--vmname", "PythonOS"], capture_output=True, text=True, timeout=900)
    return out.returncode == 0, "Imported as the machine \"PythonOS\" in VirtualBox." if out.returncode == 0 else (out.stdout + out.stderr).strip()[-300:]


def open_folder(path):
    """Show a file in the file manager (best effort)."""
    try:
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", "/select,", os.path.normpath(path)])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", "-R", path])
        else:
            subprocess.Popen(["xdg-open", os.path.dirname(path)])
    except OSError:
        pass


def run_docker():
    """Start PythonOS in Docker in a terminal window of its own (best effort). Returns (ok, message)."""
    system = platform.system()
    try:
        if system == "Windows":
            subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", DOCKER_RUN])
        elif system == "Darwin":
            script = f'tell application "Terminal" to do script "{DOCKER_RUN}"'
            subprocess.Popen(["osascript", "-e", script])
        else:
            for term, flag in (("x-terminal-emulator", "-e"), ("gnome-terminal", "--"), ("konsole", "-e"), ("xterm", "-e")):
                if shutil.which(term):
                    subprocess.Popen([term, flag, "sh", "-c", DOCKER_RUN + "; read -p 'Press Enter to close'"])
                    break
            else:
                return False, "No terminal program was found. Run this yourself: " + DOCKER_RUN
        return True, "PythonOS is starting in a new terminal window."
    except OSError as e:
        return False, f"Could not start it: {e}. Run this yourself: {DOCKER_RUN}"


def execute(plan, release, env, folder=None, progress=None, say=print, confirm=lambda text: True):
    """Download the plan's files and do its action. Returns (ok, [message lines], [downloaded paths]). `say` prints progress lines."""
    folder = folder or default_folder()
    paths = []
    for name in plan["files"]:
        say(f"Downloading {name} ({flash.human(release.size(name)) if release.size(name) else 'size unknown'})...")
        paths.append(download(release, name, folder, progress))
        say("The download matches its checksum.")
    action, lines = plan["action"], []
    path = paths[0] if paths else None
    if action == "run-installer":
        lines.append(run_windows_installer(path))
    elif action == "install-package":
        ok, message = install_package(plan["package"], path)
        return ok, [message], paths
    elif action == "install-tarball":
        ok, message = install_tarball(path)
        return ok, [message], paths
    elif action == "android-apk":
        adb = env["tools"].get("adb")
        if adb and confirm("A phone may be connected. Install the app on it now?"):
            ok, message = install_apk(adb, path)
            return ok, [message + (f"  The file is also at {path}" if not ok else "")], paths
        lines.append(f"The app is saved at {path}. Copy it to the phone and open it.")
    elif action == "docker-run":
        if env["tools"].get("docker") and confirm("Start PythonOS in Docker now?"):
            ok, message = run_docker()
            return ok, [message], paths
        lines.append("Docker was not found: install Docker, then run: " + DOCKER_RUN)
    elif action == "none":
        lines.append(f"Saved: {path}" if path else "Nothing to do.")
    elif action == "vm":
        software = plan.get("software")
        tool = env["tools"].get("virtualbox")
        if software == "virtualbox" and tool and path and path.endswith(".ova") and confirm("Import it into VirtualBox now?"):
            ok, message = import_virtualbox(tool, path)
            return ok, [message], paths
        lines.append(f"The file(s) are in {folder}.")
    return True, lines, paths
