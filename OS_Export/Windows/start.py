"""start.py - what the PythonOS window runs (the same job as launcher.py, without a console launcher around it).

Downloads the OS on the first start, refreshes it when the installer is newer than the files on disk, then runs main.py.
Lives next to PythonOS.exe in the install folder; run by the bundled Python.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PYTHON = os.path.join(HERE, "python", "python.exe")


def numbers(text):
    return tuple(int(p) for p in re.findall(r"\d+", str(text).split("-")[0])[:4])


def core_is_older():
    """True when the installer is newer than the OS files on disk (re-installing over an old version keeps the old files)."""
    try:
        with open(os.path.join(HERE, "export.json"), encoding="utf-8") as f:
            packaged = json.load(f)["version"]
        with open(os.path.join(HERE, "VERSION"), encoding="utf-8") as f:
            installed = f.read().strip()
        return numbers(installed) < numbers(packaged)
    except (OSError, ValueError, KeyError):
        return False


def libraries_ok(env):
    """True if the bundled Python can import everything PythonOS needs at start-up."""
    import bootstrap
    return subprocess.call([PYTHON, "-c", "import " + ", ".join(bootstrap.REQUIRED_MODULES.split())], env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def install_extras(env):
    """The optional libraries (requirements-extra.txt): installed once per version of that list, and never a reason to stop PythonOS starting."""
    extras = os.path.join(HERE, "requirements-extra.txt")
    marker = os.path.join(HERE, "python", ".extras-installed")   # lives with the libraries: a replaced python folder reinstalls them
    try:
        import hashlib
        with open(extras, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        if os.path.isfile(marker) and open(marker, encoding="utf-8").read().strip() == digest:
            return
        subprocess.call([PYTHON, "-m", "pip", "install", "--quiet", "--no-warn-script-location", "-r", extras], env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600)
        with open(marker, "w", encoding="utf-8") as f:
            f.write(digest)
    except Exception:                                      # noqa: BLE001 - optional: PythonOS starts without them
        pass


def main():
    os.chdir(HERE)
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYOS_EXPORT_INFO=os.path.join(HERE, "export.json"),
               COLORTERM="truecolor")
    env["PATH"] = os.path.join(HERE, "gh") + os.pathsep + env.get("PATH", "")      # the bundled GitHub CLI, run by the gh command
    env.pop("NO_COLOR", None)         # the PythonOS window always shows colour (the mono theme is a PythonOS setting)
    sys.path.insert(0, HERE)
    import bootstrap
    gone = bootstrap.missing(HERE)
    if gone or core_is_older():
        print("Downloading PythonOS..." if gone else "Updating PythonOS to the version you just installed...")
        if gone:
            print("Missing: " + ", ".join(gone))
        if subprocess.call([PYTHON, "bootstrap.py", "--dest", HERE], env=env) != 0:
            print("\nCould not download PythonOS. Check your internet connection and start it again.")
            return 1
    if not libraries_ok(env):
        print("Installing the Python libraries PythonOS needs...")
        packages = [x for pair in (("-r", n) for n in ("requirements.txt", "boot-requirements.txt") if os.path.isfile(os.path.join(HERE, n))) for x in pair]
        if not packages or subprocess.call([PYTHON, "-m", "pip", "install", "--quiet", "--no-warn-script-location", *packages], env=env) != 0 \
                or not libraries_ok(env):
            print("\nCould not install the libraries. Check your internet connection and start it again.")
            return 1
    install_extras(env)
    try:
        return subprocess.call([PYTHON, "main.py", *sys.argv[1:]], env=env)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
