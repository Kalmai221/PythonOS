import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import requests
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.progress import BarColumn, Progress, TextColumn
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

try:
    from pyos import lockdown
except ImportError:  # running outside PythonOS
    class lockdown:  # noqa: N801 - stand-in with the same interface
        enabled = staticmethod(lambda: False)
        record_package = staticmethod(lambda *a, **k: None)
        forget_package = staticmethod(lambda *a, **k: None)

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
INDEX_URL = f"{RAW_BASE}/index.json"
CACHE_FILE = Path(".OSData") / "market_index.json"
INSTALL_ROOT = Path("files")
TIMEOUT = 15

console = Console()


# ----------------------------------------------------------------- catalog
def http_get(url):
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()
    return response


def load_index():
    """Fetch the package catalog, falling back to the last copy we saw when offline."""
    try:
        with console.status("Contacting the marketplace..."):
            index = http_get(INDEX_URL).json()
        CACHE_FILE.parent.mkdir(exist_ok=True)
        CACHE_FILE.write_text(json.dumps(index), encoding="utf-8")
        return index["packages"], False
    except (requests.RequestException, ValueError, KeyError) as e:
        try:
            cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))["packages"]
            console.print("[yellow]Could not reach the marketplace; showing the last catalog we saw "
                          "(installing needs internet).[/yellow]")
            return cached, True
        except (OSError, ValueError, KeyError):
            console.print(f"[bold red]Could not load the marketplace catalog:[/bold red] {escape(str(e))}")
            console.print("[dim]Check your internet connection. If you maintain the repo, run "
                          "'python tools/build_index.py' and push online_packages/index.json.[/dim]")
            return None, True


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
    tags = [t.lower() for t in pkg.get("tags", [])] + [pkg["category"].lower()]
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
        table.add_row(str(i), escape(p["name"]), p["category"], escape(p.get("description", "")),
                      p["version"], "[dim]not available here[/dim]" if blocked
                      else status_label(status_of(p, installed), p, installed))
    console.print(table)


def show_details(pkg, installed):
    size = sum(f.get("size", 0) for f in pkg["files"])
    local = installed.get(pkg["id"])
    lines = [
        escape(pkg.get("description", "")),
        "",
        f"[bold]Version:[/bold]  {pkg['version']}",
        f"[bold]Category:[/bold] {pkg['category']}",
        f"[bold]Start with:[/bold] [cyan]run {pkg['command']}[/cyan]" if pkg.get("command") else "[bold]Start with:[/bold] run programs",
        f"[bold]Tags:[/bold]     {', '.join(pkg.get('tags', [])) or '-'}",
        f"[bold]Size:[/bold]     {size / 1024:.1f} KB in {len(pkg['files'])} file(s)",
        f"[bold]Status:[/bold]   {status_label(status_of(pkg, installed), pkg, installed) or 'not installed'}"
        + (f" [dim](installed {local['version']})[/dim]" if local and status_of(pkg, installed) == "installed" else ""),
    ]
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


def install_package(pkg, installed, quiet=False):
    """Download into a temporary folder, verify every file, then swap into place."""
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
                data = http_get(f"{RAW_BASE}/{pkg['id']}/{rel}").content
                if entry.get("sha256") and not hash_matches(data, entry["sha256"]):
                    raise ValueError(f"checksum mismatch for {rel}")
                target = tmp / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                progress.advance(task)
        if dest.exists():
            dest.rename(old)
        tmp.rename(dest)
        shutil.rmtree(old, ignore_errors=True)
    except Exception as e:
        console.print(f"[bold red]Could not install {escape(pkg['name'])}: {escape(str(e))}[/bold red]")
        shutil.rmtree(tmp, ignore_errors=True)
        if old.exists() and not dest.exists():
            old.rename(dest)  # put the previous version back
        return False

    lockdown.record_package(dest, pkg.get("lockdown_safe", False))   # remember its hashes (see pyos/lockdown.py)
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


def remove_package(pid, info, quiet=False):
    folder, meta = info["path"], info.get("meta", {})
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
    if not Confirm.ask(f"Update {len(pending)} package(s)?", default=True):
        return
    results = [install_package(p, installed, quiet=True) for p in pending]
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
        action = Prompt.ask("What now?", choices=actions, default=actions[0])
        if action == "back":
            return
        if action in ("install", "update"):
            install_package(pkg, installed)
        elif action == "remove":
            remove_package(pkg["id"], installed[pkg["id"]])
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
    cats = sorted({p["category"] for p in packages})
    table = Table(title="Categories", header_style="bold blue")
    table.add_column("#", justify="right")
    table.add_column("Category", style="magenta")
    table.add_column("Packages", justify="right")
    table.add_row("0", "[bold]All[/bold]", str(len(packages)))
    for i, c in enumerate(cats, 1):
        table.add_row(str(i), c, str(sum(1 for p in packages if p["category"] == c)))
    console.print(table)
    n = IntPrompt.ask("Choose a category (blank to go back)", default=-1)
    if n == 0:
        pick_from(sorted(packages, key=lambda p: p["name"].lower()), installed, "All packages")
    elif 1 <= n <= len(cats):
        pick_from([p for p in packages if p["category"] == cats[n - 1]], installed, f"{cats[n - 1].title()} packages")


def main_menu():
    packages, offline = load_index()
    if packages is None:
        return
    installed = installed_packages()
    updates = sum(1 for p in packages if status_of(p, installed) == "update")
    console.print(Panel(f"[bold]PyOS Marketplace[/bold]  -  {len(packages)} packages"
                        + (f", [yellow]{updates} update(s) available[/yellow]" if updates else ""),
                        border_style="magenta", expand=False))
    while True:
        installed = installed_packages()
        console.print("\n[bold magenta]b[/bold magenta]rowse  [bold magenta]s[/bold magenta]earch  "
                      "[bold magenta]i[/bold magenta]nstalled  [bold magenta]u[/bold magenta]pdates  "
                      "[bold magenta]q[/bold magenta]uit")
        choice = Prompt.ask("Choose", choices=["b", "s", "i", "u", "q"], default="s")
        if choice == "q":
            return
        if choice == "b":
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


# ------------------------------------------------------------ command line
HELP = """[bold]marketplace[/bold] (also: market, store, pkg)

  marketplace                    open the interactive store
  marketplace search <words>     find packages
  marketplace info <name>        show details
  marketplace install <name>     install a package
  marketplace remove <name>      remove a package
  marketplace update <name>      update one package (leave out the name to update everything)
  marketplace list               show installed packages"""


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
            install_package(pkg, installed)
    elif cmd in ("remove", "uninstall", "rm"):
        matches = [p for p in resolve(packages, query) if p["id"] in installed] if query else []
        pkg = choose(matches, installed)
        if pkg:
            remove_package(pkg["id"], installed[pkg["id"]])
        else:
            console.print("[yellow]That package is not installed. See: marketplace list[/yellow]")
    elif cmd in ("update", "upgrade"):
        if offline:
            console.print("[yellow]Updates need a connection to the marketplace.[/yellow]")
        elif query:
            pkg = choose([p for p in resolve(packages, query) if p["id"] in installed], installed)
            if pkg and status_of(pkg, installed) == "update":
                install_package(pkg, installed)
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
