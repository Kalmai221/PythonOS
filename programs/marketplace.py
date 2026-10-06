import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import requests
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

try:
    from pyos import lockdown, sandbox
except ImportError:  # running outside PythonOS
    class lockdown:  # noqa: N801 - stand-in with the same interface
        enabled = staticmethod(lambda: False)
        record_package = staticmethod(lambda *a, **k: None)
        forget_package = staticmethod(lambda *a, **k: None)

    class sandbox:  # noqa: N801
        PERMISSIONS = {"network": "connect to the internet", "files": "read and change your files", "notifications": "show notifications",
                       "schedule": "schedule tasks", "system": "read system information", "exec": "start other programs"}
        describe = staticmethod(lambda perms: ", ".join(perms) or "nothing special")
        granted = staticmethod(lambda pid: None)
        set_granted = staticmethod(lambda pid, perms: None)
        forget = staticmethod(lambda pid: None)

try:
    from pyos import marketapi
except ImportError:  # running outside PythonOS: the API 1 rules
    class marketapi:  # noqa: N801
        CURRENT = OLDEST = 1
        index_names = staticmethod(lambda: ["index.json"])
        package_api = staticmethod(lambda meta: 1)
        index_api = staticmethod(lambda index: 1)
        compatibility = staticmethod(lambda meta: (True, ""))
        usable = staticmethod(lambda packages: (packages, 0))

config = {
    "name": "marketplace",
    "description": "Find, install, update and remove packages (marketplace search <term>).",
    "alias": ["market", "store"],
}

# === CONFIGURATION ===
REPO_OWNER = "Kalmai221"
REPO_NAME = "PythonOS"
BRANCH = "main"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO_OWNER}/{REPO_NAME}/{BRANCH}/online_packages"
INDEX_URL = f"{RAW_BASE}/index.json"                       # the API 1 catalog, readable by every PythonOS ever released
CACHE_FILE = Path(".OSData") / "market_index.json"
META_FILE = Path(".OSData") / "package_meta.json"          # why each package is installed (asked for, or needed by another)
BACKUP_DIR = Path(".OSData") / "package_backups"           # the version before the last update of each package (pkg rollback)
CHECK_STATE = Path(".OSData") / "market_check.json"        # quiet update checks
CHECK_INTERVAL = 24 * 3600
CATALOG = {"categories": []}                               # filled by load_index
FILE_CACHE = Path(".OSData") / "market_cache"          # downloaded package files by checksum: reinstalls work offline
CATEGORY_BLURBS = {
    "games": "Something to play",
    "utilities": "Everyday tools",
    "developer": "For people who write code",
    "system": "Look after the system itself",
    "network": "Online and network tools",
    "productivity": "Get things done",
}
INSTALL_ROOT = Path("files")
TIMEOUT = 15

console = Console()


# ----------------------------------------------------------------- catalog
def http_get(url):
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response


def fetch_index():
    """The catalog for this PythonOS's marketplace API: the file of its own version first (index-api<N>.json), then index.json
    (a server that does not publish the versioned files yet). Only a missing file moves on to the next one."""
    last = None
    for name in marketapi.index_names():
        try:
            return http_get(f"{RAW_BASE}/{name}").json()
        except requests.HTTPError as e:
            last = e
            if e.response is None or e.response.status_code != 404:
                raise
    raise last


def usable_packages(index):
    """The packages of a catalog this system can run. Says so when some were left out (they need a newer PythonOS)."""
    packages, left_out = marketapi.usable(index["packages"])
    if left_out or marketapi.index_api(index) > marketapi.CURRENT:
        console.print(f"[dim]{left_out} app(s) are not shown: they need a newer PythonOS (update it with: updatecheck).[/dim]")
    return packages


def load_index():
    """Fetch the package catalog, falling back to the last copy we saw when offline."""
    try:
        with console.status("Contacting the marketplace..."):
            index = fetch_index()
        CACHE_FILE.parent.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps(index), encoding="utf-8")
        CATALOG["categories"] = index.get("categories", [])
        return usable_packages(index), False
    except (requests.RequestException, ValueError, KeyError) as e:
        try:
            cached_index = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            CATALOG["categories"] = cached_index.get("categories", [])
            cached = marketapi.usable(cached_index["packages"])[0]
            console.print("[yellow]Could not reach the marketplace; showing the last catalog we saw "
                          "(installing needs internet).[/yellow]")
            return cached, True
        except (OSError, ValueError, KeyError):
            console.print(f"[bold red]Could not load the marketplace catalog:[/bold red] {escape(str(e))}")
            console.print("[dim]Check your internet connection. If you maintain the repo, run "
                          "'python tools/build_index.py' and push online_packages/index.json.[/dim]")
            return None, True


# ------------------------------------------------------------ Python libraries (marketplace API 2)
LIBS = ".libs"                                                  # inside the package folder; removed with it, and put on the app's search path


def pip_available():
    """(True, '') when this system can install Python libraries, else (False, why)."""
    if lockdown.enabled():
        return False, "this locked-down system does not install Python libraries"
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError):
        return False, "pip is not available on this system (the Android app and the live ISO cannot install Python libraries)"
    return True, ""


def install_pip(specs, target):
    """Install the libraries into `target` (wheels only: nothing is built or run from a downloaded source package). Raises RuntimeError."""
    if not specs:
        return
    ok, why = pip_available()
    if not ok:
        raise RuntimeError(f"it needs Python libraries ({', '.join(specs)}), but {why}")
    command = [sys.executable, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "--no-input", "--only-binary", ":all:",
               "--target", str(target), "--upgrade", *specs]
    extra = os.environ.get("PYOS_PIP_ARGS")                      # a test or an offline mirror: for example "--no-index --find-links DIR"
    if extra:
        import shlex
        command += shlex.split(extra)
    try:
        with console.status(f"Installing Python libraries: {', '.join(specs)}..."):
            done = subprocess.run(command, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        raise RuntimeError("installing the Python libraries took too long")
    if done.returncode != 0:
        lines = [l for l in (done.stderr or done.stdout).strip().splitlines() if l.strip()]
        raise RuntimeError("pip could not install the Python libraries: " + (lines[-1] if lines else "no reason given"))


def libs_ready(old_folder, specs):
    """The old version's .libs folder, when it holds exactly these libraries already (an update does not download them again)."""
    marker = old_folder / LIBS / ".specs"
    try:
        return json.loads(marker.read_text(encoding="utf-8")) == sorted(specs)
    except (OSError, ValueError):
        return False


def fetch_file(pkg, entry):
    """A package file's bytes: from the local cache when its checksum is known, else downloaded and cached."""
    sha = entry.get("sha256")
    cached = FILE_CACHE / sha[:2] / sha if sha else None
    if cached is not None and cached.is_file():
        data = cached.read_bytes()
        if hash_matches(data, sha):
            return data
    data = http_get(f"{RAW_BASE}/{pkg['id']}/{entry['path']}").content
    if sha and not hash_matches(data, sha):
        raise ValueError(f"checksum mismatch for {entry['path']}")
    if cached is not None:
        try:
            cached.parent.mkdir(parents=True, exist_ok=True)
            cached.write_bytes(data)
        except OSError:
            pass
    return data


def installed_packages():
    """{package id: {"path", "version", "name"}} for everything under files/installed_*/."""
    found = {}
    if not INSTALL_ROOT.exists():
        return found
    for cat_dir in sorted(INSTALL_ROOT.glob("installed_*")):
        category = cat_dir.name[len("installed_"):]
        for pkg_dir in sorted(p for p in cat_dir.iterdir() if p.is_dir() and not p.name.startswith(".")):
            meta = {}
            try:
                meta = json.loads((pkg_dir / "data.json").read_text(encoding="utf-8"))
            except (OSError, ValueError):
                pass
            found[f"{category}/{pkg_dir.name}"] = {
                "path": pkg_dir,
                "version": str(meta.get("version", "?")),
                "name": meta.get("name", pkg_dir.name),
                "meta": meta,
            }
    return found


def version_key(text):
    return tuple(int(n) for n in re.findall(r"\d+", str(text))) or (0,)


def parse_requirement(spec):
    """'utilities/notes>=1.1,<2' -> ('utilities/notes', [('>=', '1.1'), ('<', '2')]). A bare name has no constraints."""
    spec = str(spec).strip()
    m = re.match(r"^([^<>=!\s]+)\s*(.*)$", spec)
    if not m:
        return spec, []
    constraints = []
    for part in [c.strip() for c in m.group(2).split(",") if c.strip()]:
        cm = re.fullmatch(r"(>=|<=|==|!=|>|<)\s*([\d.]+)", part)
        if cm:
            constraints.append((cm.group(1), cm.group(2)))
    return m.group(1), constraints


def version_ok(version, constraints):
    """Does `version` satisfy every (operator, version) pair?"""
    have = version_key(version)
    ops = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, "==": lambda a, b: a == b, "!=": lambda a, b: a != b,
           ">": lambda a, b: a > b, "<": lambda a, b: a < b}
    for op, wanted in constraints:
        w = version_key(wanted)
        n = max(len(have), len(w))
        a, b = have + (0,) * (n - len(have)), w + (0,) * (n - len(w))
        if not ops[op](a, b):
            return False
    return True


def status_of(pkg, installed):
    local = installed.get(pkg["id"])
    if not local:
        return ""
    return "update" if version_key(pkg["version"]) > version_key(local["version"]) else "installed"


def status_label(status, pkg=None, installed=None):
    if status == "installed":
        return "[green]installed[/green]"
    if status == "update":
        return f"[yellow]update ({installed[pkg['id']]['version']} -> {pkg['version']})[/yellow]"
    return ""


# ------------------------------------------------------------------ search
def score(pkg, words):
    """Higher is a better match; 0 means no match. All words must match something."""
    name = pkg["name"].lower()
    ident = pkg["id"].lower()
    command = (pkg.get("command") or "").lower()
    aliases = [a.lower() for a in pkg.get("alias", [])]
    tags = [t.lower() for t in pkg.get("tags", [])] + [pkg["category"].lower()] + [c.lower() for c in pkg.get("categories", [])]
    desc = pkg.get("description", "").lower()
    total = 0
    for w in words:
        s = 0
        if w == command or w in aliases or w == ident.split("/")[-1]:
            s = 100
        elif name.startswith(w) or command.startswith(w):
            s = 60
        elif w in name or w in ident:
            s = 45
        elif w in tags:
            s = 30
        elif any(w in t for t in tags):
            s = 20
        elif w in desc:
            s = 10
        else:
            close = difflib.get_close_matches(w, [name, command, ident.split("/")[-1]] + tags, n=1, cutoff=0.75)
            s = 8 if close else 0
        if s == 0:
            return 0
        total += s
    return total


def search(packages, query):
    words = [w for w in re.split(r"\s+", query.lower().strip()) if w]
    if not words:
        return sorted(packages, key=lambda p: p["name"].lower())
    ranked = [(score(p, words), p) for p in packages]
    return [p for s, p in sorted(ranked, key=lambda x: (-x[0], x[1]["name"].lower())) if s > 0]


def resolve(packages, query):
    """Exact lookup by id, command, alias, folder name or display name."""
    q = query.lower().strip()
    exact = [p for p in packages
             if q in (p["id"].lower(), (p.get("command") or "").lower(), p["name"].lower(), p["id"].split("/")[-1].lower())
             or q in [a.lower() for a in p.get("alias", [])]]
    return exact or search(packages, query)


def choose(matches, installed, prompt="Which one?"):
    """Pick one package from several matches (or return the only one)."""
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    show_packages(matches, installed, "Several packages match")
    n = IntPrompt.ask(f"{prompt} (0 to cancel)", default=0)
    return matches[n - 1] if 1 <= n <= len(matches) else None


# ----------------------------------------------------------------- display
def changelog_for(pkg):
    """What changed in this version (the catalog's changelog is a string, or {version: notes})."""
    log = pkg.get("changelog", "")
    if isinstance(log, dict):
        log = log.get(pkg["version"], "")
    return str(log).strip()


def changelog_history(pkg):
    """[(version, notes)] newest first, from a changelog string or {version: notes}."""
    log = pkg.get("changelog", "")
    if isinstance(log, dict):
        return sorted(((v, str(n).strip()) for v, n in log.items()), key=lambda kv: version_key(kv[0]), reverse=True)
    return [(pkg["version"], str(log).strip())] if str(log).strip() else []


def show_notes(pkg):
    """The release notes page: what changed in every version the catalog remembers."""
    history = changelog_history(pkg)
    if not history:
        console.print("[dim]This package has no release notes.[/dim]")
        return
    lines = []
    for version, notes in history:
        lines.append(f"[bold cyan]{escape(version)}[/bold cyan]")
        lines += [f"  {escape(line)}" for line in notes.splitlines() or [""]]
        lines.append("")
    console.print(Panel("\n".join(lines).rstrip(), title=f"[bold]{escape(pkg['name'])} - release notes[/bold]", border_style="blue", expand=False))


def category_title(category_id):
    for c in CATALOG.get("categories", []):
        if c["id"] == category_id:
            return c["title"]
    return category_id.title()


def show_packages(packages, installed, title):
    table = Table(title=title, header_style="bold blue", expand=True)
    table.add_column("#", justify="right")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Category", style="magenta")
    table.add_column("Description")
    table.add_column("Version", style="yellow")
    table.add_column("Status")
    for i, p in enumerate(packages, 1):
        blocked = lockdown.enabled() and not p.get("lockdown_safe")
        table.add_row(str(i), escape(p["name"]), category_title(p.get("categories", [p["category"]])[0]), escape(p.get("description", "")),
                      p["version"], "[dim]not available here[/dim]" if blocked
                      else status_label(status_of(p, installed), p, installed))
    console.print(table)


def show_details(pkg, installed):
    size = sum(f.get("size", 0) for f in pkg["files"])
    local = installed.get(pkg["id"])
    lines = [
        escape(pkg.get("description", "")),
        "",
        *([f"[bold]Libraries:[/bold] {escape(', '.join(pkg['pip']))} [dim](Python libraries from PyPI, kept inside the app)[/dim]"] if pkg.get("pip") else []),
        f"[bold]Version:[/bold]  {pkg['version']}" + (f"  [dim](marketplace API {marketapi.package_api(pkg)})[/dim]" if marketapi.package_api(pkg) > 1 else ""),
        f"[bold]Category:[/bold] {', '.join(category_title(c) for c in pkg.get('categories', [pkg['category']]))}",
        f"[bold]Start with:[/bold] [cyan]run {pkg['command']}[/cyan]" if pkg.get("command") else "[bold]Start with:[/bold] run programs",
        f"[bold]Tags:[/bold]     {', '.join(pkg.get('tags', [])) or '-'}",
        *([f"[bold]Needs:[/bold]    {escape(', '.join(pkg['requires']))}"] if pkg.get("requires") else []),
        *([f"[bold]Works with:[/bold] {escape(', '.join(o if isinstance(o, str) else o.get('ref', '') for o in pkg['optional']))}"] if pkg.get("optional") else []),
        f"[bold]Can:[/bold]      {sandbox.describe(pkg['permissions']) if pkg.get('permissions') is not None else '[yellow]not stated (older package)[/yellow]'}",
        *([f"[bold]What's new:[/bold] {escape(changelog_for(pkg))}"] if changelog_for(pkg) else []),
        f"[bold]Size:[/bold]     {size / 1024:.1f} KB in {len(pkg['files'])} file(s)",
        f"[bold]Status:[/bold]   {status_label(status_of(pkg, installed), pkg, installed) or 'not installed'}"
        + (f" [dim](installed {local['version']})[/dim]" if local and status_of(pkg, installed) == "installed" else ""),
    ]
    if local:
        reason = _meta().get(pkg["id"], {}).get("reason")
        if reason:
            lines.append(f"[bold]Installed because:[/bold] {escape(reason)}")
    console.print(Panel("\n".join(lines), title=f"[bold cyan]{escape(pkg['name'])}[/bold cyan] [dim]{pkg['id']}[/dim]",
                        border_style="blue", expand=False))


# ----------------------------------------------------------------- install
def safe_relative(path):
    p = Path(path)
    return not p.is_absolute() and ".." not in p.parts and path.strip() != ""


def hash_matches(data, expected):
    if hashlib.sha256(data).hexdigest() == expected:
        return True
    # The index hashes text files with LF line endings
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() == expected


def refresh_shell():
    """Make new commands usable immediately instead of requiring a restart."""
    try:
        import shell
        shell.reload_all()
    except Exception:
        console.print("[yellow]Type 'reload' to start using the new package.[/yellow]")


def run_script(folder, meta, key, label):
    if lockdown.enabled():
        return True           # installer/uninstaller scripts run arbitrary code - never on a locked-down system
    script = meta.get("scripts", {}).get(key)
    if not script or not (folder / script).exists():
        return True
    console.print(f"[bold green]Running {label}...[/bold green]")
    code = subprocess.call([sys.executable, str(folder / script)])
    if code != 0:
        console.print(f"[bold yellow]The {label} exited with code {code}.[/bold yellow]")
    return code == 0


def install_package(pkg, installed, quiet=False, reason="you asked for it", grant=None):
    """Download into a temporary folder, verify every file, then swap into place. grant: the permissions to record."""
    fits, why = marketapi.compatibility(pkg)
    if not fits:
        console.print(f"[yellow]{escape(pkg['name'])} cannot be installed: {escape(why)}[/yellow]")
        return False
    if lockdown.enabled() and not pkg.get("lockdown_safe"):
        console.print(f"[yellow]{escape(pkg['name'])} cannot be installed on this locked-down system "
                      "(it is not marked as safe for it).[/yellow]")
        return False
    dest = INSTALL_ROOT / f"installed_{pkg['category']}" / pkg["id"].split("/", 1)[1]
    tmp = dest.parent / f".tmp_{dest.name}"
    old = dest.parent / f".old_{dest.name}"
    was_installed = pkg["id"] in installed
    for leftover in (tmp, old):
        shutil.rmtree(leftover, ignore_errors=True)

    try:
        tmp.mkdir(parents=True)
        with Progress(TextColumn("[cyan]{task.description}"), BarColumn(), TextColumn("{task.completed}/{task.total}"),
                      console=console, transient=True) as progress:
            task = progress.add_task(f"Downloading {pkg['name']}", total=len(pkg["files"]))
            for entry in pkg["files"]:
                rel = entry["path"]
                if not safe_relative(rel):
                    raise ValueError(f"unsafe file path in catalog: {rel}")
                data = fetch_file(pkg, entry)
                target = tmp / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                progress.advance(task)
        specs = marketapi.pip_specs(pkg)                       # API 2: Python libraries, installed into the package's own .libs folder
        if specs:
            if dest.exists() and libs_ready(dest, specs):
                shutil.copytree(dest / LIBS, tmp / LIBS)
            else:
                install_pip(specs, tmp / LIBS)
                (tmp / LIBS).mkdir(exist_ok=True)
                (tmp / LIBS / ".specs").write_text(json.dumps(sorted(specs)), encoding="utf-8")
        if dest.exists():
            dest.rename(old)
        tmp.rename(dest)
        keep_previous(pkg["id"], old, installed.get(pkg["id"], {}).get("version"))
    except Exception as e:
        console.print(f"[bold red]Could not install {escape(pkg['name'])}: {escape(str(e))}[/bold red]")
        shutil.rmtree(tmp, ignore_errors=True)
        if old.exists() and not dest.exists():
            old.rename(dest)  # put the previous version back
        return False

    lockdown.record_package(dest, pkg.get("lockdown_safe", False))   # remember its hashes (see pyos/lockdown.py)
    if grant is not None:
        sandbox.set_granted(pkg["id"], grant)
    elif sandbox.granted(pkg["id"]) is None and pkg.get("permissions") is not None:
        sandbox.set_granted(pkg["id"], pkg["permissions"])
    if not was_installed:
        note_reason(pkg["id"], reason)
    if was_installed and pkg.get("permissions") is not None:
        extra = [p for p in pkg["permissions"] if p not in (sandbox.granted(pkg["id"]) or [])]
        if extra:
            console.print(f"[yellow]{escape(pkg['name'])} {pkg['version']} wants new permission(s): {escape(sandbox.describe(extra))}. "
                          f"It keeps running without them until you allow them: pkg permissions {escape(pkg['id'])}[/yellow]")
    verb = "Updated" if was_installed else "Installed"
    console.print(f"[bold green]{verb} {escape(pkg['name'])} {pkg['version']}.[/bold green]")
    meta = {}
    try:
        meta = json.loads((dest / "data.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    if not was_installed and meta.get("scripts", {}).get("installer") and not quiet and not lockdown.enabled():
        if Confirm.ask("This package has a setup step. Run it now?", default=True):
            run_script(dest, meta, "installer", "installer")
    if not quiet:
        refresh_shell()
        if meta.get("command"):
            console.print(f"Start it with: [bold cyan]run {meta['command']}[/bold cyan]")
    return True


def find_required(packages, ref):
    """The catalog entry a `requires` reference points at (an id like utilities/notes, a command or a name). Version
    constraints in the reference ("notes>=1.1") are ignored here; see install_plan."""
    ref = parse_requirement(ref)[0].strip().lower()
    for p in packages:
        if ref in (p["id"].lower(), p.get("command", "").lower(), p["name"].lower()):
            return p
    return None


def install_plan(pkg, packages, installed, seen=None):
    """Packages to install, dependencies first. Returns (ordered list, missing requirements). A requirement with a version
    range ("notes>=1.1") is satisfied by the installed copy if it is new enough, else the newer one is installed."""
    seen = seen if seen is not None else set()
    order, missing = [], []
    if pkg["id"] in seen:
        return order, missing                       # already planned (also stops dependency cycles)
    seen.add(pkg["id"])
    for spec in pkg.get("requires", []):
        ref, constraints = parse_requirement(spec)
        dep = find_required(packages, ref)
        if dep is None:
            missing.append(spec)
            continue
        if not version_ok(dep["version"], constraints):
            missing.append(f"{spec} (the marketplace has {dep['version']})")
            continue
        local = installed.get(dep["id"])
        if local is None or not version_ok(local["version"], constraints):
            sub, sub_missing = install_plan(dep, packages, installed, seen)
            order += sub
            missing += sub_missing
    order.append(pkg)
    return order, missing


def optional_for(pkg, packages, installed):
    """[(catalog entry, why)] for the nice-to-have packages of pkg that are not installed yet."""
    found = []
    for item in pkg.get("optional", []):
        ref, why = (item.get("ref", ""), item.get("why", "")) if isinstance(item, dict) else (item, "")
        dep = find_required(packages, ref)
        if dep and dep["id"] not in installed and dep["id"] != pkg["id"]:
            found.append((dep, why))
    return found


def size_of(pkg):
    return sum(f.get("size", 0) for f in pkg.get("files", []))


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def show_install_plan(order, installed):
    """What is about to be installed: size and what each package may do."""
    table = Table(title="About to install", header_style="bold blue", expand=True)
    for col in ("Package", "Version", "Size", "It will be able to"):
        table.add_column(col)
    for p in order:
        if p.get("pip"):
            console.print(f"[bold]{escape(p['name'])}[/bold] also downloads these Python libraries from PyPI (the standard Python library index): "
                          f"[cyan]{escape(', '.join(p['pip']))}[/cyan]. They are kept inside the app's own folder and removed with it.")
        perms = p.get("permissions")
        what = sandbox.describe(perms) if perms is not None else "[yellow]not stated (an older package)[/yellow]"
        table.add_row(escape(p["name"]) + (" [dim](update)[/dim]" if p["id"] in installed else ""), p["version"], human(size_of(p)), what)
    console.print(table)
    console.print(f"[dim]Total download: {human(sum(size_of(p) for p in order))}. Permissions are enforced while the app runs "
                  "and can be changed any time with: pkg permissions <name>[/dim]")


def _is_admin():
    from pyos import userinfo
    return userinfo()[1] == "admin"


def install_with_dependencies(pkg, installed, packages, quiet=False, reason=None):
    """Install pkg after anything it requires that is not installed yet. Not quiet: shows the size and what each package may
    do, and asks first. Quiet (updates, starter apps): installs without asking, keeping what was allowed before."""
    order, missing = install_plan(pkg, packages, installed)
    if not quiet and _is_admin():
        from pyos import audit
        audit.record("installed an app", pkg["name"])
    if missing:
        console.print(f"[bold red]{escape(pkg['name'])} needs {', '.join(escape(m) for m in missing)}, "
                      "which the marketplace does not have.[/bold red]")
        return False
    needed = order[:-1]
    if not quiet:
        show_install_plan(order, installed)
        if needed:
            console.print(f"[bold]{escape(pkg['name'])}[/bold] also needs: " + ", ".join(f"[cyan]{escape(p['name'])}[/cyan]" for p in needed))
        if not Confirm.ask("Install?", default=True):
            console.print("[yellow]Cancelled.[/yellow]")
            return False
    for dep in needed:
        if not install_package(dep, installed, quiet=True, reason=f"needed by {pkg['name']}", grant=_grant_for(dep, quiet)):
            console.print(f"[bold red]Could not install {escape(dep['name'])}, so {escape(pkg['name'])} was not installed.[/bold red]")
            return False
        installed[dep["id"]] = {"version": dep["version"], "name": dep["name"], "path": None, "meta": {}}
    ok = install_package(pkg, installed, quiet=quiet, reason=reason or "you asked for it", grant=_grant_for(pkg, quiet))
    if ok and not quiet:
        for dep, why in optional_for(pkg, packages, installed):
            if Confirm.ask(f"{escape(pkg['name'])} works better with {escape(dep['name'])}" + (f" ({escape(why)})" if why else "") + ". Install it too?",
                           default=False):
                install_package(dep, installed, quiet=True, reason=f"suggested by {pkg['name']}", grant=_grant_for(dep, True))
    return ok


def _grant_for(pkg, quiet):
    """The permissions to record for an install. Interactive: what was shown and agreed to. Quiet: a first install gets what
    the package declares (the user chose the app); an update keeps what was allowed before, so it can never gain power silently."""
    declared = pkg.get("permissions")
    previous = sandbox.granted(pkg["id"])
    if quiet and previous is not None and declared is not None:
        return [p for p in previous if p in declared]
    return list(declared) if declared is not None else None


def dependents(pid, installed, packages):
    """Installed packages that list pid as a requirement."""
    by_id = {p["id"]: p for p in packages}
    target = by_id.get(pid)
    found = []
    for other, info in installed.items():
        pkg = by_id.get(other)
        if not pkg or other == pid:
            continue
        for ref in pkg.get("requires", []):
            if target is not None and find_required([target], ref):
                found.append(info["name"])
    return found


def keep_previous(pid, old_folder, version):
    """After an update, keep the folder of the version it replaced (one step back) for `pkg rollback`."""
    target = BACKUP_DIR / pid.replace("/", "__")
    shutil.rmtree(target, ignore_errors=True)
    if old_folder.exists():
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_folder), str(target))
            (target / ".previous_version").write_text(str(version or "?"), encoding="utf-8")
        except OSError:
            shutil.rmtree(old_folder, ignore_errors=True)


def can_rollback(pid):
    return (BACKUP_DIR / pid.replace("/", "__") / "data.json").is_file()


def rollback_package(pid, info):
    """Put the version from before the last update back."""
    backup = BACKUP_DIR / pid.replace("/", "__")
    if not can_rollback(pid):
        console.print("[yellow]There is no earlier version of this package to go back to (rollback works once, right after an update).[/yellow]")
        return False
    previous = (backup / ".previous_version").read_text(encoding="utf-8").strip() if (backup / ".previous_version").exists() else "?"
    if not Confirm.ask(f"Go back to {escape(info['name'])} {previous} (from {info['version']})?", default=False):
        return False
    folder = info["path"]
    swap = BACKUP_DIR / (pid.replace("/", "__") + ".swap")
    shutil.rmtree(swap, ignore_errors=True)
    try:
        shutil.move(str(folder), str(swap))
        shutil.move(str(backup), str(folder))
        (folder / ".previous_version").unlink(missing_ok=True)
    except OSError as e:
        console.print(f"[bold red]Could not roll back: {escape(str(e))}[/bold red]")
        if swap.exists() and not folder.exists():
            shutil.move(str(swap), str(folder))
        return False
    shutil.rmtree(swap, ignore_errors=True)
    lockdown.record_package(folder, bool(info.get("meta", {}).get("lockdown_safe")))
    console.print(f"[bold green]{escape(info['name'])} is back at {previous}.[/bold green] Updating again brings the newer one back.")
    refresh_shell()
    return True


def _meta():
    try:
        return json.loads(META_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def note_reason(pid, reason):
    data = _meta()
    data[pid] = {"reason": reason, "time": time.time()}
    try:
        META_FILE.parent.mkdir(exist_ok=True)
        META_FILE.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass


def forget_reason(pid):
    data = _meta()
    if data.pop(pid, None) is not None:
        try:
            META_FILE.write_text(json.dumps(data), encoding="utf-8")
        except OSError:
            pass


def explain_why(pkg, installed, packages):
    """pkg why <name>: why it is installed and what depends on it."""
    local = installed.get(pkg["id"])
    if not local:
        console.print(f"[yellow]{escape(pkg['name'])} is not installed.[/yellow]")
        users = [p["name"] for p in packages if any(find_required([pkg], r) for r in p.get("requires", [])) and p["id"] in installed]
        if users:
            console.print(f"Installed packages that would need it: {escape(', '.join(users))}")
        return
    info = _meta().get(pkg["id"], {})
    reason = info.get("reason", "it was installed before the store kept track")
    console.print(f"[bold]{escape(pkg['name'])}[/bold] is installed because {escape(reason)}"
                  + (f" ({time.strftime('%Y-%m-%d', time.localtime(info['time']))})." if info.get("time") else "."))
    users = dependents(pkg["id"], installed, packages)
    if users:
        console.print(f"These installed packages need it: [cyan]{escape(', '.join(users))}[/cyan] - removing it may stop them working.")
    else:
        console.print("[dim]Nothing else installed needs it, so it can be removed safely.[/dim]")
    needs = [find_required(packages, r) for r in pkg.get("requires", [])]
    if pkg.get("requires"):
        console.print("It needs: " + ", ".join(escape(str(r)) for r in pkg["requires"]))


def permissions_command(pkg, installed, args):
    """pkg permissions <name> [grant|revoke <permission>]"""
    local = installed.get(pkg["id"])
    if not local:
        console.print(f"[yellow]{escape(pkg['name'])} is not installed.[/yellow]")
        return False
    declared = pkg.get("permissions") if pkg.get("permissions") is not None else (local.get("meta", {}).get("permissions"))
    declared = declared if declared is not None else list(getattr(sandbox, "LEGACY_DEFAULT", []))
    allowed = sandbox.granted(pkg["id"])
    if allowed is None:
        allowed = [p for p in declared]
    if args and args[0] in ("grant", "revoke") and len(args) > 1:
        perm = args[1].lower()
        if perm not in sandbox.PERMISSIONS:
            console.print(f"[red]Unknown permission '{escape(perm)}'. Known: {', '.join(sandbox.PERMISSIONS)}[/red]")
            return False
        if args[0] == "grant":
            if perm not in declared:
                console.print(f"[yellow]{escape(pkg['name'])} does not ask for '{perm}', so there is nothing to allow.[/yellow]")
                return False
            allowed = sorted(set(allowed) | {perm})
        else:
            allowed = [p for p in allowed if p != perm]
        sandbox.set_granted(pkg["id"], allowed)
        console.print(f"[green]{escape(pkg['name'])}: {'allowed' if args[0] == 'grant' else 'blocked'} {perm}.[/green]")
    table = Table(title=f"{pkg['name']} - permissions", header_style="bold blue")
    for col in ("Permission", "What it allows", "Asked for", "Allowed"):
        table.add_column(col)
    for perm, text in sandbox.PERMISSIONS.items():
        table.add_row(perm, text, "yes" if perm in declared else "", "[green]yes[/green]" if perm in allowed else "[red]no[/red]" if perm in declared else "")
    console.print(table)
    return True


def remove_package(pid, info, quiet=False, packages=None, installed=None):
    folder, meta = info["path"], info.get("meta", {})
    if not quiet and _is_admin():
        from pyos import audit
        audit.record("removed an app", info.get("name", pid))
    users = dependents(pid, installed, packages) if packages and installed else []
    if users:
        console.print(f"[yellow]{escape(', '.join(users))} needs {escape(info['name'])} and may stop working without it.[/yellow]")
        if not Confirm.ask("Remove it anyway?", default=False):
            console.print("[yellow]Cancelled.[/yellow]")
            return False
        quiet = True            # already asked
    if not quiet and not Confirm.ask(f"Remove {info['name']}?", default=False):
        console.print("[yellow]Cancelled.[/yellow]")
        return False
    if not run_script(folder, meta, "uninstaller", "uninstaller"):
        if not Confirm.ask("The uninstaller reported a problem. Remove the package files anyway?", default=False):
            return False
    try:
        shutil.rmtree(folder)
    except OSError as e:
        console.print(f"[bold red]Could not delete {folder}: {e}[/bold red]")
        return False
    lockdown.forget_package(folder)
    sandbox.forget(pid)
    forget_reason(pid)
    shutil.rmtree(BACKUP_DIR / pid.replace("/", "__"), ignore_errors=True)
    console.print(f"[bold green]Removed {escape(info['name'])}.[/bold green]")
    if not quiet:
        refresh_shell()
    return True


def update_all(packages, installed):
    pending = [p for p in packages if status_of(p, installed) == "update"]
    if not pending:
        console.print("[green]Everything is up to date.[/green]")
        return
    show_packages(pending, installed, "Updates available")
    for p in pending:
        notes = changelog_for(p)
        if notes:
            console.print(f"[bold cyan]{escape(p['name'])} {p['version']}[/bold cyan]: {escape(notes)}")
    if not Confirm.ask(f"Update {len(pending)} package(s)?", default=True):
        return
    results = [install_with_dependencies(p, installed, packages, quiet=True) for p in pending]
    console.print(f"[bold green]{sum(results)} updated[/bold green]" + (f", [bold red]{len(results) - sum(results)} failed[/bold red]" if not all(results) else ""))
    refresh_shell()


# ----------------------------------------------------------- interactive UI
def manage(pkg, installed, packages):
    """Details + actions for one package."""
    while True:
        show_details(pkg, installed)
        status = status_of(pkg, installed)
        actions = ["back"]
        blocked = lockdown.enabled() and not pkg.get("lockdown_safe")
        if not status and not blocked:
            actions.insert(0, "install")
        if status == "update" and not blocked:
            actions.insert(0, "update")
        if status:
            actions.insert(len(actions) - 1, "remove")
            actions.insert(len(actions) - 1, "permissions")
            actions.insert(len(actions) - 1, "why")
            if can_rollback(pkg["id"]):
                actions.insert(len(actions) - 1, "rollback")
        if changelog_history(pkg) and len(changelog_history(pkg)) > 1:
            actions.insert(len(actions) - 1, "notes")
        action = Prompt.ask("What now?", choices=actions, default=actions[0])
        if action == "back":
            return
        if action in ("install", "update"):
            install_with_dependencies(pkg, installed, packages)
        elif action == "remove":
            remove_package(pkg["id"], installed[pkg["id"]], packages=packages, installed=installed)
        elif action == "permissions":
            permissions_command(pkg, installed, [])
            if Confirm.ask("Change a permission?", default=False):
                which = Prompt.ask("Permission", choices=list(sandbox.PERMISSIONS))
                what = Prompt.ask("Allow or block", choices=["grant", "revoke"], default="revoke")
                permissions_command(pkg, installed, [what, which])
            continue
        elif action == "why":
            explain_why(pkg, installed, packages)
            continue
        elif action == "rollback":
            rollback_package(pkg["id"], installed[pkg["id"]])
        elif action == "notes":
            show_notes(pkg)
            continue
        installed.clear()
        installed.update(installed_packages())
        return


def pick_from(packages, installed, title):
    """Show a numbered list and let the user open entries until they go back."""
    while True:
        if not packages:
            console.print("[yellow]Nothing to show.[/yellow]")
            return
        show_packages(packages, installed, title)
        n = IntPrompt.ask("Open a package by number (0 to go back)", default=0)
        if not 1 <= n <= len(packages):
            return
        manage(packages[n - 1], installed, packages)


def browse(packages, installed):
    """Categories come from the catalog (online_packages/categories.json); a package can be in several."""
    known = CATALOG.get("categories") or []
    titles = {c["id"]: c for c in known}
    members = {}
    for p in packages:
        for c in p.get("categories", [p["category"]]):
            members.setdefault(c, []).append(p)
    order = [c["id"] for c in known if c["id"] in members] + sorted(c for c in members if c not in titles)
    table = Table(title="Categories", header_style="bold blue")
    table.add_column("#", justify="right")
    table.add_column("Category", style="magenta")
    table.add_column("Apps", justify="right")
    table.add_column("About")
    table.add_row("0", "[bold]All[/bold]", str(len(packages)), "Everything, A to Z")
    for i, c in enumerate(order, 1):
        info = titles.get(c, {"title": c.title(), "blurb": CATEGORY_BLURBS.get(c, "")})
        table.add_row(str(i), info["title"], str(len(members[c])), info.get("blurb", ""))
    console.print(table)
    n = IntPrompt.ask("Choose a category (blank to go back)", default=-1)
    if n == 0:
        pick_from(sorted(packages, key=lambda p: p["name"].lower()), installed, "All packages")
    elif 1 <= n <= len(order):
        c = order[n - 1]
        pick_from(sorted(members[c], key=lambda p: p["name"].lower()), installed, f"{titles.get(c, {'title': c.title()})['title']}")


def main_menu():
    packages, offline = load_index()
    if packages is None:
        return
    installed = installed_packages()
    updates = sum(1 for p in packages if status_of(p, installed) == "update")
    featured = [p for p in packages if p.get("featured") and p["id"] not in installed
                and not (lockdown.enabled() and not p.get("lockdown_safe"))]
    console.print(Panel(f"[bold]PyOS Marketplace[/bold]  -  {len(packages)} packages"
                        + (f", [yellow]{updates} update(s) available[/yellow]" if updates else ""),
                        border_style="magenta", expand=False))
    if featured:
        console.print("[bold]Featured:[/bold] " + ", ".join(f"[cyan]{escape(p['name'])}[/cyan]" for p in featured[:6])
                      + "  [dim](press f)[/dim]")
    while True:
        installed = installed_packages()
        console.print("\n[bold magenta]b[/bold magenta]rowse  [bold magenta]s[/bold magenta]earch  "
                      "[bold magenta]f[/bold magenta]eatured  "
                      "[bold magenta]i[/bold magenta]nstalled  [bold magenta]u[/bold magenta]pdates  "
                      "[bold magenta]q[/bold magenta]uit")
        choice = Prompt.ask("Choose", choices=["b", "s", "f", "i", "u", "q"], default="s")
        if choice == "q":
            return
        if choice == "f":
            pick_from([p for p in packages if p.get("featured")], installed, "Featured packages")
        elif choice == "b":
            browse(packages, installed)
        elif choice == "s":
            query = Prompt.ask("Search for").strip()
            results = search(packages, query)
            if results:
                pick_from(results, installed, f"Results for '{query}'")
            else:
                console.print(f"[yellow]Nothing matches '{escape(query)}'. Try a different word or browse by category.[/yellow]")
        elif choice == "i":
            show_installed(packages, installed)
        elif choice == "u":
            if offline:
                console.print("[yellow]Updates need a connection to the marketplace.[/yellow]")
            else:
                update_all(packages, installed)


def show_installed(packages, installed):
    if not installed:
        console.print("[yellow]No packages installed yet. Use 'search' or 'browse' to find some.[/yellow]")
        return
    by_id = {p["id"]: p for p in packages}
    table = Table(title="Installed packages", header_style="bold blue")
    table.add_column("Name", style="cyan")
    table.add_column("Category", style="magenta")
    table.add_column("Version", style="yellow")
    table.add_column("Status")
    for pid, info in installed.items():
        pkg = by_id.get(pid)
        table.add_row(escape(info["name"]), pid.split("/")[0], info["version"],
                      status_label(status_of(pkg, installed), pkg, installed) if pkg else "[dim]not in catalog[/dim]")
    console.print(table)


# ------------------------------------------------------------ quiet checks
def check_updates_quietly(user=None, force=False):
    """At most once a day (and only when the market_update_check setting is on): compare installed packages with the
    catalog and post one notification when updates are waiting. No output, never raises. Returns the number waiting."""
    try:
        try:
            from pyos import notify, settings
            if not force and not settings.get("market_update_check"):
                return 0
        except ImportError:
            notify = None
        try:
            state = json.loads(CHECK_STATE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            state = {}
        if not force and time.time() - state.get("last", 0) < CHECK_INTERVAL:
            return 0
        installed = installed_packages()
        if not installed:
            return 0
        index = fetch_index()
        index["packages"] = marketapi.usable(index["packages"])[0]
        CATALOG["categories"] = index.get("categories", [])
        waiting = sorted(p["id"] for p in index["packages"] if status_of(p, installed) == "update")
        state["last"] = time.time()
        if waiting and state.get("notified") != waiting and notify:
            names = ", ".join(p["name"] for p in index["packages"] if p["id"] in waiting[:3])
            more = f" and {len(waiting) - 3} more" if len(waiting) > 3 else ""
            notify.notify(f"{len(waiting)} app update(s) available: {names}{more}. Install them with: pkg update all",
                          title="Marketplace", user=user)
            state["notified"] = waiting
        CHECK_STATE.parent.mkdir(exist_ok=True)
        CHECK_STATE.write_text(json.dumps(state), encoding="utf-8")
        return len(waiting)
    except Exception:
        return 0


# ------------------------------------------------------------ command line
HELP = """[bold]marketplace[/bold] (also: market, store, pkg)

  marketplace                    open the interactive store
  marketplace search <words>     find packages
  marketplace info <name>        show details
  marketplace install <name>     install a package
  marketplace remove <name>      remove a package
  marketplace update <name>      update one package (leave out the name to update everything)
  marketplace update all         update every package that has a newer version
  marketplace featured           hand-picked packages
  marketplace list               show installed packages
  marketplace why <name>         why a package is installed, and what needs it
  marketplace permissions <name> [grant|revoke <permission>]   what an app may do (enforced while it runs)
  marketplace notes <name>       the release notes of every version
  marketplace rollback <name>    go back to the version before the last update

Some packages need others; they are installed together (and you are asked first)."""


def cli(args):
    cmd, rest = args[0].lower(), args[1:]
    if cmd in ("help", "-h", "--help"):
        console.print(HELP)
        return
    packages, offline = load_index()
    if cmd in ("list", "installed", "ls"):
        show_installed(packages or [], installed_packages())
        return
    if packages is None:
        return
    installed = installed_packages()
    query = " ".join(rest)

    if cmd in ("search", "find"):
        results = search(packages, query)
        if results:
            show_packages(results, installed, f"Results for '{query}'" if query else "All packages")
        else:
            console.print(f"[yellow]Nothing matches '{escape(query)}'.[/yellow]")
    elif cmd in ("why", "permissions", "perms", "notes", "changelog", "rollback"):
        pkg = choose(resolve(packages, rest[0]), installed) if rest else None
        if not pkg:
            console.print(f"[yellow]Usage: marketplace {cmd} <name>[/yellow]")
        elif cmd == "why":
            explain_why(pkg, installed, packages)
        elif cmd in ("permissions", "perms"):
            permissions_command(pkg, installed, rest[1:])
        elif cmd in ("notes", "changelog"):
            show_notes(pkg)
        elif pkg["id"] in installed:
            rollback_package(pkg["id"], installed[pkg["id"]])
        else:
            console.print("[yellow]That package is not installed.[/yellow]")
    elif cmd in ("featured", "popular"):
        show_packages([p for p in packages if p.get("featured")] or packages[:8], installed, "Featured packages")
    elif cmd in ("info", "show"):
        pkg = choose(resolve(packages, query), installed) if query else None
        if pkg:
            show_details(pkg, installed)
        else:
            console.print("[yellow]Usage: marketplace info <name>[/yellow]")
    elif cmd in ("install", "add"):
        if not query:
            console.print("[yellow]Usage: marketplace install <name>[/yellow]")
            return
        pkg = choose(resolve(packages, query), installed)
        if not pkg:
            console.print(f"[yellow]No package matches '{escape(query)}'. Try: marketplace search {escape(query)}[/yellow]")
        elif status_of(pkg, installed) == "installed":
            console.print(f"[green]{escape(pkg['name'])} is already installed.[/green]")
        else:
            install_with_dependencies(pkg, installed, packages)
    elif cmd in ("remove", "uninstall", "rm"):
        matches = [p for p in resolve(packages, query) if p["id"] in installed] if query else []
        pkg = choose(matches, installed)
        if pkg:
            remove_package(pkg["id"], installed[pkg["id"]], packages=packages, installed=installed)
        else:
            console.print("[yellow]That package is not installed. See: marketplace list[/yellow]")
    elif cmd in ("update", "upgrade"):
        if offline:
            console.print("[yellow]Updates need a connection to the marketplace.[/yellow]")
        elif query and query.lower() not in ("all", "--all", "-a"):
            pkg = choose([p for p in resolve(packages, query) if p["id"] in installed], installed)
            if pkg and status_of(pkg, installed) == "update":
                install_with_dependencies(pkg, installed, packages)
            elif pkg:
                console.print(f"[green]{escape(pkg['name'])} is up to date.[/green]")
            else:
                console.print("[yellow]That package is not installed.[/yellow]")
        else:
            update_all(packages, installed)
    else:
        console.print(f"[red]Unknown subcommand '{escape(cmd)}'.[/red]")
        console.print(HELP)


def execute(args=None):
    try:
        if args:
            cli(args)
        else:
            main_menu()
    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")


if __name__ == "__main__":
    execute(sys.argv[1:])
