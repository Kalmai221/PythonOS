"""PythonOS Flash: write a PythonOS ISO to a USB stick, safely. The parts both the window and the command line use.

What it does, in this order, and stops at the first problem:
  1. gets the ISO (the latest release, downloaded, or a file you pick) and checks it against the release's SHA256SUMS
  2. lists only removable / USB drives that are not the one the computer runs from
  3. shows what will be erased and makes you confirm
  4. unmounts the drive (Windows: cleans its partition table), writes the image in 4 MB steps
  5. reads the stick back and compares it with the ISO
It never touches a drive you did not confirm, and never lists the drive the computer runs from.
"""
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

CHUNK = 4 * 1024 * 1024
SECTOR = 512
MIN_STICK = 1024 ** 3
LATEST = "https://github.com/Kalmai221/PythonOS/releases/latest/download"
ISO_NAME = re.compile(r"^pythonos-(\d+(?:\.\d+)*)(-minimal)?-(x86_64|aarch64)\.iso$")


def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


# ----------------------------------------------------------------------------------------- checksums
def sha256_file(path, progress=None):
    digest = hashlib.sha256()
    total = os.path.getsize(path)
    done = 0
    with open(path, "rb") as f:
        while True:
            block = f.read(CHUNK)
            if not block:
                break
            digest.update(block)
            done += len(block)
            if progress:
                progress("check", done, total)
    return digest.hexdigest()


def parse_sums(text):
    """{file name: sha256} from the text of a SHA256SUMS file."""
    sums = {}
    for line in text.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            sums[parts[1].lstrip("*").strip()] = parts[0].lower()
    return sums


def expected_hash(iso, given=None):
    """The hash the ISO should have: the one given, or the line for it in SHA256SUMS next to it. None if neither exists."""
    if given:
        return given.strip().lower()
    try:
        with open(os.path.join(os.path.dirname(os.path.abspath(iso)), "SHA256SUMS"), encoding="utf-8") as f:
            return parse_sums(f.read()).get(os.path.basename(iso))
    except OSError:
        return None


# ----------------------------------------------------------------------------------------- the latest release
def _open(url, timeout=30):
    return urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "PythonOS-Flash"}), timeout=timeout)


def latest_sums():
    """{file name: sha256} for the latest PythonOS release."""
    with _open(f"{LATEST}/SHA256SUMS") as response:
        return parse_sums(response.read().decode("utf-8", "replace"))


def _archinfo():
    """pyos/archinfo.py, the one place the processor is detected (next to this file's repository folder, or bundled into the program)."""
    try:
        import archinfo
    except ImportError:
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, os.pardir, "pyos"))
        import archinfo
    return archinfo


def machine_arch():
    """This computer's processor as the release files name it (x86_64 or aarch64), the real one also when this program runs emulated."""
    return _archinfo().arch()


def describe_machine():
    return _archinfo().describe()


def pick_iso(sums, arch, minimal=False):
    """The name of the ISO for this processor and variant in a SHA256SUMS listing, or None."""
    for name in sorted(sums):
        m = ISO_NAME.match(name)
        if m and m.group(3) == arch and bool(m.group(2)) == bool(minimal):
            return name
    return None


def download_iso(name, expected, folder=None, progress=None):
    """Download a release file of the latest release into `folder`, checking it against `expected`. Returns the path."""
    folder = folder or tempfile.mkdtemp(prefix="pythonos-flash-")
    return download_file(f"{LATEST}/{name}", expected, os.path.join(folder, name), progress)


def download_file(url, expected, target, progress=None):
    """Download `url` to `target`, checking it against the SHA-256 `expected`. The partial file is deleted on any problem. Returns `target`."""
    digest = hashlib.sha256()
    try:
        with _open(url, timeout=60) as response, open(target, "wb") as out:
            total = int(response.headers.get("Content-Length") or 0)
            done = 0
            while True:
                block = response.read(1 << 20)
                if not block:
                    break
                out.write(block)
                digest.update(block)
                done += len(block)
                if progress:
                    progress("download", done, total)
    except BaseException:
        _remove(target)
        raise
    if digest.hexdigest() != expected:
        _remove(target)
        raise ValueError("the download does not match its checksum (damaged or changed), so it was deleted")
    return target


def _remove(path):
    try:
        os.remove(path)
    except OSError:
        pass


# ----------------------------------------------------------------------------------------- finding drives
def parse_lsblk(text):
    """Drives from `lsblk -J -b -o NAME,PATH,SIZE,TYPE,RM,TRAN,MODEL,MOUNTPOINTS`: whole disks that are removable or on USB."""
    found = []
    for d in json.loads(text).get("blockdevices", []):
        if d.get("type") != "disk":
            continue
        removable = str(d.get("rm")) in ("1", "True", "true") or d.get("tran") == "usb"
        mounts = [m for c in d.get("children", []) or [] for m in (c.get("mountpoints") or []) if m]
        mounts += [m for m in (d.get("mountpoints") or []) if m]
        if removable and int(d.get("size") or 0) >= MIN_STICK and "/" not in mounts:
            found.append({"id": d.get("path") or "/dev/" + d["name"], "size": int(d["size"]), "name": (d.get("model") or "").strip() or "USB drive",
                          "mounts": mounts})
    return found


def parse_windows_disks(text):
    """Drives from PowerShell's Get-Disk as JSON: USB drives that are neither the system nor the boot disk."""
    data = json.loads(text) if text.strip() else []
    if isinstance(data, dict):
        data = [data]
    found = []
    for d in data:
        if str(d.get("BusType", "")).upper() != "USB" or d.get("IsSystem") or d.get("IsBoot") or int(d.get("Size") or 0) < MIN_STICK:
            continue
        found.append({"id": str(d["Number"]), "size": int(d["Size"]), "name": (d.get("FriendlyName") or "USB drive").strip(), "mounts": []})
    return found


def parse_diskutil(disks):
    """Drives from already-parsed `diskutil` data: [{'DeviceIdentifier', 'Size', 'Name'}]."""
    return [{"id": f"/dev/{d['DeviceIdentifier']}", "size": int(d.get("Size", 0)), "name": d.get("Name", "USB drive"), "mounts": []}
            for d in disks if int(d.get("Size", 0)) >= MIN_STICK]


def list_drives():
    system = platform.system()
    if system == "Linux":
        out = subprocess.run(["lsblk", "-J", "-b", "-o", "NAME,PATH,SIZE,TYPE,RM,TRAN,MODEL,MOUNTPOINTS"], capture_output=True, text=True)
        return parse_lsblk(out.stdout)
    if system == "Windows":
        command = "Get-Disk | Select-Object Number,FriendlyName,Size,BusType,IsSystem,IsBoot | ConvertTo-Json -Compress"
        out = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return parse_windows_disks(out.stdout)
    if system == "Darwin":
        import plistlib
        out = subprocess.run(["diskutil", "list", "-plist", "external", "physical"], capture_output=True)
        disks = []
        for entry in plistlib.loads(out.stdout).get("AllDisksAndPartitions", []):
            info = subprocess.run(["diskutil", "info", "-plist", entry["DeviceIdentifier"]], capture_output=True)
            detail = plistlib.loads(info.stdout)
            disks.append({"DeviceIdentifier": entry["DeviceIdentifier"], "Size": entry.get("Size", 0), "Name": detail.get("MediaName", "USB drive")})
        return parse_diskutil(disks)
    raise SystemExit(f"PythonOS Flash: {system} is not supported")


def device_path(drive_id):
    """The raw device to open for writing."""
    if platform.system() == "Windows":
        return rf"\\.\PhysicalDrive{drive_id}"
    if platform.system() == "Darwin":
        return drive_id.replace("/dev/disk", "/dev/rdisk")      # the raw device is much faster
    return drive_id


def is_admin():
    if platform.system() == "Windows":
        try:
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


# ----------------------------------------------------------------------------------------- preparing and writing
def prepare(drive):
    """Unmount (or, on Windows, clean) the drive so nothing else uses it while it is written."""
    system = platform.system()
    if system == "Linux":
        for mount in drive.get("mounts", []):
            subprocess.run(["umount", mount], check=False)
    elif system == "Darwin":
        subprocess.run(["diskutil", "unmountDisk", drive["id"]], check=True)
    elif system == "Windows":
        script = f"select disk {drive['id']}\nclean\n"
        subprocess.run(["diskpart"], input=script, text=True, check=True, capture_output=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def _whole_sectors(block, raw):
    """Raw drives on Windows only accept whole sectors."""
    if not raw:
        return block
    remainder = len(block) % SECTOR
    return block + b"\0" * (SECTOR - remainder) if remainder else block


def is_raw_windows_drive(target):
    return str(target).startswith("\\\\.\\")


def write_image(iso, target, progress=None):
    """Copy the ISO onto the device (or file) `target`. progress(phase, done, total) is called as it goes. Returns the bytes written."""
    total = os.path.getsize(iso)
    raw = is_raw_windows_drive(target)
    with open(iso, "rb") as src, open(target, "r+b", buffering=0) as dst:
        done = 0
        while True:
            block = src.read(CHUNK)
            if not block:
                break
            dst.write(_whole_sectors(block, raw))
            done += len(block)
            if progress:
                progress("write", done, total)
        try:
            os.fsync(dst.fileno())
        except OSError:
            pass
    return total


def verify_image(iso, target, progress=None):
    """Read the device back and compare it with the ISO. True when every byte matches."""
    total = os.path.getsize(iso)
    raw = is_raw_windows_drive(target)
    want, got = hashlib.sha256(), hashlib.sha256()
    with open(iso, "rb") as src, open(target, "rb", buffering=0) as dst:
        done = 0
        while done < total:
            a = src.read(min(CHUNK, total - done))
            b = b""
            while len(b) < len(a):
                part = dst.read((len(_whole_sectors(a, raw)) if raw else len(a)) - len(b))
                if not part:
                    break
                b += part
            want.update(a)
            got.update(b[:len(a)])
            done += len(a)
            if progress:
                progress("verify", done, total)
    return want.hexdigest() == got.hexdigest()


def flash(iso, drive, verify=True, progress=None):
    """Prepare the drive, write the ISO and (unless verify is False) check it. Returns (ok, message). Needs administrator rights."""
    if not is_admin():
        return False, "writing a drive needs administrator rights"
    if os.path.getsize(iso) > drive["size"]:
        return False, "the stick is smaller than the ISO"
    try:
        prepare(drive)
        target = device_path(drive["id"])
        write_image(iso, target, progress)
        if verify and not verify_image(iso, target, progress):
            return False, "the stick does not match the ISO after writing: try again or use another stick"
    except (OSError, subprocess.CalledProcessError) as e:
        return False, f"the write failed: {e}"
    return True, "Done. Safely remove the stick, then start the computer from it (boot menu key, often F12 or Esc)."


# ----------------------------------------------------------------------------------------- running with privileges
def self_command():
    """The command that runs this program again: the packaged executable, or Python and the entry script."""
    if getattr(sys, "frozen", False):
        return [sys.executable]
    return [sys.executable, os.path.abspath(sys.argv[0])]


def quote(parts):
    import shlex
    return " ".join(shlex.quote(p) for p in parts)


def privileged_command(command):
    """`command` wrapped so it runs as an administrator, asking the user in the way this system does. None when there is no way."""
    system = platform.system()
    import shutil
    if system == "Linux":
        if shutil.which("pkexec"):
            return ["pkexec"] + command
        if shutil.which("sudo"):
            return ["sudo"] + command
        return None
    if system == "Darwin":
        script = f'do shell script {json.dumps(quote(command))} with administrator privileges'
        return ["osascript", "-e", script]
    return None


def run_privileged(command, hidden=False):
    """Run `command` as an administrator, asking the user the way this system does (UAC on Windows, polkit or sudo on Linux, a password
    prompt on macOS), wait for it and return its exit code. Only the part that needs the rights is run this way; the wizard itself never is.
    126 means there was no way to ask."""
    if platform.system() == "Windows":
        return _run_elevated_windows(command, hidden)
    wrapped = privileged_command(command)
    return subprocess.call(wrapped) if wrapped else 126


def _run_elevated_windows(command, hidden):
    import ctypes
    from ctypes import wintypes

    class ExecuteInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", ctypes.c_ulong), ("hwnd", wintypes.HWND), ("lpVerb", wintypes.LPCWSTR),
                    ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR), ("lpDirectory", wintypes.LPCWSTR),
                    ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE), ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR),
                    ("hkeyClass", wintypes.HKEY), ("dwHotKey", wintypes.DWORD), ("hIconOrMonitor", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]

    info = ExecuteInfo()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x40                                   # SEE_MASK_NOCLOSEPROCESS: keep the process handle so it can be waited for
    info.lpVerb = "runas"                               # the UAC prompt
    info.lpFile = command[0]
    info.lpParameters = subprocess.list2cmdline(command[1:])
    info.nShow = 0 if hidden else 1
    shell, kernel = ctypes.windll.shell32, ctypes.windll.kernel32
    shell.ShellExecuteExW.argtypes = [ctypes.POINTER(ExecuteInfo)]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    if not shell.ShellExecuteExW(ctypes.byref(info)):
        return 1223                                     # ERROR_CANCELLED: the user said no at the UAC prompt (or it could not be shown)
    kernel.WaitForSingleObject(info.hProcess, 0xFFFFFFFF)
    code = wintypes.DWORD()
    kernel.GetExitCodeProcess(info.hProcess, ctypes.byref(code))
    kernel.CloseHandle(info.hProcess)
    return int(code.value)


def read_progress(path, offset=0):
    """New progress lines a worker wrote to `path` since `offset`: ([(phase, done, total, message)], new offset)."""
    events = []
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            data = f.read()
    except OSError:
        return events, offset
    consumed = data.rfind(b"\n") + 1
    for line in data[:consumed].decode("utf-8", "replace").splitlines():
        try:
            item = json.loads(line)
            events.append((item.get("phase"), int(item.get("done", 0)), int(item.get("total", 0)), item.get("message", "")))
        except ValueError:
            continue
    return events, offset + consumed


def worker(iso, drive_id, verify, progress_file):
    """The privileged part, run as `--worker`: finds the drive again among the usable ones, writes it, and reports through a file."""
    last = {"phase": None, "at": 0.0}

    def report(phase, done=0, total=0, message=""):
        now = time.time()
        if phase == last["phase"] and phase not in ("done", "error") and now - last["at"] < 0.25 and done != total:
            return
        last.update(phase=phase, at=now)
        with open(progress_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({"phase": phase, "done": done, "total": total, "message": message}) + "\n")

    drive = next((d for d in list_drives() if d["id"] == drive_id), None)
    if drive is None:
        report("error", message=f"{drive_id} is not one of the usable drives (internal and system drives are never offered)")
        return 1
    ok, message = flash(iso, drive, verify, report)
    report("done" if ok else "error", message=message)
    return 0 if ok else 1


# ----------------------------------------------------------------------------------------- the command line
def bar(label, done, total):
    width = 30
    filled = int(width * done / total) if total else width
    sys.stdout.write(f"\r{label:<10}[{'#' * filled}{'-' * (width - filled)}] {done * 100 // max(1, total):>3}%  {human(done)} / {human(total)}")
    sys.stdout.flush()


LABELS = {"download": "Download", "check": "Checking", "write": "Writing", "verify": "Verifying"}


def cli_progress(phase, done, total):
    bar(LABELS.get(phase, phase), done, total)
    if done >= total:
        print()


def run_cli(args):
    """The terminal version. args: iso, list, device, sha256, yes, no_verify, download, arch, minimal."""
    drives = list_drives()
    if args.list:
        if not drives:
            print("No USB stick found. Plug one in (at least 1 GB); the drive the computer runs from is never listed.")
        for d in drives:
            print(f"  {d['id']:<18} {human(d['size']):>9}  {d['name']}")
        return 0

    if not is_admin():                         # ask for rights first, so a download is not done twice
        print("Writing a drive needs administrator rights; asking for them...")
        code = run_privileged(self_command() + sys.argv[1:])
        if code == 126:
            print("No way to ask for administrator rights was found (needs sudo or pkexec). Run this as root.")
        elif code == 1223:
            print("Administrator rights were not given. Nothing was changed.")
        return code

    iso, want = args.iso, None
    if args.download or not iso:
        if not args.download:
            print("Give an ISO file, or use --download to fetch the latest release. (--list shows the usable drives, --gui opens the window.)")
            return 2
        arch = args.arch or machine_arch()
        if arch not in ("x86_64", "aarch64"):
            print(f"This computer's processor ({describe_machine()}) has no PythonOS image. Choose one with --arch x86_64 or --arch aarch64 "
                  "if the stick is for another computer.")
            return 2
        print(f"Looking up the latest release for {arch} ({'chosen' if args.arch else 'detected: ' + describe_machine()})...")
        try:
            sums = latest_sums()
            name = pick_iso(sums, arch, args.minimal)
            if not name:
                print(f"The latest release has no {'minimal ' if args.minimal else ''}ISO for {arch}.")
                return 2
            print(f"Downloading {name}...")
            iso = download_iso(name, sums[name], progress=cli_progress)
            want = sums[name]
        except (OSError, ValueError) as e:
            print(f"Could not get the ISO: {e}")
            return 1
    if not os.path.isfile(iso):
        print(f"{iso}: no such file")
        return 2
    want = want or expected_hash(iso, args.sha256)
    if want is None:
        print("Warning: no SHA256SUMS next to the ISO and no --sha256 given, so the download cannot be checked.")
        if input("Continue anyway? (yes/no) ").strip().lower() != "yes":
            return 2
    else:
        print("Checking the ISO...")
        if sha256_file(iso, cli_progress) != want:
            print("The ISO does not match its checksum. The download is damaged or has been changed. Nothing was written.")
            return 1
        print("The ISO matches its checksum.")

    if not drives:
        print("No USB stick found. Plug one in (at least 1 GB).")
        return 2
    if args.device:
        drive = next((d for d in drives if d["id"] == args.device), None)
        if drive is None:
            print(f"{args.device} is not one of the usable drives (see --list). Internal and system drives are never offered.")
            return 2
    else:
        for number, d in enumerate(drives, 1):
            print(f"  {number}  {d['id']:<18} {human(d['size']):>9}  {d['name']}")
        pick = input("Number of the stick to erase (blank to cancel): ").strip()
        if not pick.isdigit() or not 1 <= int(pick) <= len(drives):
            print("Cancelled. Nothing was changed.")
            return 2
        drive = drives[int(pick) - 1]
    print(f"\nEverything on {drive['id']} ({human(drive['size'])}, {drive['name']}) will be erased.")
    if not (args.yes and args.device):
        if input(f"Type {drive['id']} to continue: ").strip() != drive["id"]:
            print("Cancelled. Nothing was changed.")
            return 2
    ok, message = flash(iso, drive, not args.no_verify, cli_progress)
    print(message)
    return 0 if ok else 1
