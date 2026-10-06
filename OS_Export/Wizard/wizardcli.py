"""The terminal version of the PythonOS Setup Wizard: the same questions, asked as a numbered list (or answered with options)."""
import sys

import flashlib as flash
import wizardlib as wiz


def ask_choice(title, options, default=1):
    """Show a numbered list and return the key of the chosen option."""
    print(f"\n{title}")
    for number, (key, text, detail) in enumerate(options, 1):
        print(f"  {number}) {text}" + (f"\n       {detail}" if detail else ""))
    while True:
        answer = input(f"Number [{default}]: ").strip() or str(default)
        if answer.isdigit() and 1 <= int(answer) <= len(options):
            return options[int(answer) - 1][0]
        print("Type one of the numbers above.")


def ask_yes(text, default=True):
    answer = input(f"{text} [{'Y/n' if default else 'y/N'}] ").strip().lower()
    return default if not answer else answer in ("y", "yes")


def cli_progress(phase, done, total):
    flash.cli_progress(phase, done, total)


def run(args):
    """args: goal, vm, abi, arch, minimal, folder, yes, dry_run (any may be missing). Returns an exit code."""
    interactive = not getattr(args, "goal", None)
    print("PythonOS Setup\nLooking at this computer and the latest release...")
    env = wiz.detect_environment()
    print("This computer: " + wiz.describe_environment(env))
    if env["note"]:
        print("Note: " + env["note"])
    try:
        release = wiz.fetch_release()
    except (OSError, ValueError) as e:
        print(f"The latest release could not be loaded ({e}). Check your internet connection, or open {wiz.RELEASES_PAGE}")
        return 1
    print(f"Latest release: {release.version}")

    goal = getattr(args, "goal", None) or ask_choice("What do you want to do?", wiz.GOALS)
    options = {}
    if goal == "vm":
        software = getattr(args, "vm", None) or (None if interactive else "other")
        if not software:
            marked = [(k, t + ("   (found on this computer)" if k in env["tools"] else ""), d) for k, t, d in wiz.VM_SOFTWARE]
            software = ask_choice("Which virtual machine program?", marked)
        options["software"] = software
    elif goal == "android":
        options["abi"] = getattr(args, "abi", None) or ("aarch64" if not interactive else ask_choice("What kind of Android device?", [
            ("aarch64", "A phone or tablet (almost all of them)", ""), ("x86_64", "A Chromebook or an Android emulator on a PC", ""),
            ("universal", "I am not sure", "a tiny installer app that picks the right one")]))
    elif goal == "usb":
        arch = getattr(args, "arch", None) or (env["arch"] if not interactive else ask_choice("Which kind of computer will start from the stick?", [
            ("x86_64", "A PC (Intel / AMD)", "" if env["arch"] != "x86_64" else "this computer"),
            ("aarch64", "An ARM computer (UEFI)", "" if env["arch"] != "aarch64" else "this computer")], 2 if env["arch"] == "aarch64" else 1))
        minimal = bool(getattr(args, "minimal", False)) or (interactive and ask_yes("Use the minimal (smaller) image?", False))
        import types
        flash_args = types.SimpleNamespace(iso=None, list=False, device=None, sha256=None, yes=False, no_verify=False, download=True,
                                           arch=arch, minimal=minimal)
        return flash.run_cli(flash_args)
    elif goal == "download":
        names = sorted(e["name"] for e in release.entries if e["os"] != "system")
        if not interactive:
            print("Files in this release:\n  " + "\n  ".join(names))
            return 2
        picked = ask_choice("Which file?", [(n, n, flash.human(release.size(n)) if release.size(n) else "") for n in names])
        plan = wiz.make_plan("download", [picked], "none", [])
    if goal != "download":
        plan = wiz.plan_for(goal, env, release, **options)

    print("\nHere is what will happen:")
    for name in plan["files"]:
        size = release.size(name)
        print(f"  - download {name}" + (f" ({flash.human(size)})" if size else ""))
    if plan["files"]:
        print("  - check each download against the release's SHA256SUMS")
    for line in plan["steps"] + plan["notes"]:
        print(f"  - {line}")
    if not plan["files"] and plan["action"] != "docker-run":
        print("\nNothing can be downloaded for this choice in the latest release.")
        return 1
    if getattr(args, "dry_run", False):
        return 0
    if interactive and not ask_yes("\nGo ahead?"):
        print("Cancelled. Nothing was changed.")
        return 2
    folder = getattr(args, "folder", None) or wiz.default_folder()
    confirm = (lambda text: True) if getattr(args, "yes", False) else (ask_yes if interactive else (lambda text: False))
    ok, lines, _paths = wiz.execute(plan, release, env, folder, cli_progress, print, confirm)
    print()
    for line in lines:
        print(line)
    return 0 if ok else 1
