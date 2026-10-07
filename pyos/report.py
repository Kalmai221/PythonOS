# pyos/report.py - a problem report the user can read, then send in a way they choose
#
# Nothing here sends anything by itself. build() gathers: the version and package, the platform, the last log lines, what happened
# to the last session and the newest crash report. redact() removes things that identify the person (user names, home paths, email
# and IP addresses). The user sees the whole text first, then picks: post it as a GitHub issue under their own account (a sign-in with
# a short code), send it to the developer's Discord channel (no account needed), or - only if a relay address is
# set - send it through a small relay service that files the issue (see OS_Export/relay/README.md). The sending is in reportsend.py.
# PythonOS is a command line system and cannot open links. A GitHub token is never stored: anything inside an app can be taken out of it.
import json
import os
import platform
import re
import time

REPO = "Kalmai221/PythonOS"
ISSUE_URL = f"https://github.com/{REPO}/issues/new"


def _version():
    try:
        with open("VERSION", encoding="utf-8") as f:
            return f.read().strip()
    except OSError:
        try:
            with open("config.json", encoding="utf-8") as f:
                return str(json.load(f).get("version", "?")) + " (source)"
        except (OSError, ValueError):
            return "?"


def _package():
    try:
        from pyos import export
        info = export.info()
        return f"{export.title(info['platform'])} {info['version']}" if info else "none (source)"
    except Exception:
        return "unknown"


def _tail(path, lines):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()[-lines:]
    except OSError:
        return []


def newest_crash_report():
    import pyos
    folder = os.path.join(pyos.fs.BASE_DIR, "var", "log")
    try:
        names = sorted(n for n in os.listdir(folder) if n.startswith("crash-") and n.endswith(".log"))
    except OSError:
        return None, []
    if not names:
        return None, []
    return names[-1], _tail(os.path.join(folder, names[-1]), 40)


def build(description="", include_log=True):
    """The report text (not redacted yet)."""
    import pyos
    parts = []
    if description.strip():
        parts.append("## What happened\n" + description.strip())
    parts.append("## Versions\n" + "\n".join([
        f"- PythonOS: {_version()}", f"- Package: {_package()}", f"- Python: {platform.python_version()}",
        f"- System: {platform.system()} {platform.release()}", f"- Time: {time.strftime('%Y-%m-%d %H:%M:%S')}"]))
    try:
        from core import whathappened
        headline, _details = whathappened.describe()
        if headline:
            parts.append("## Last session\n" + headline)
    except Exception:
        pass
    name, crash = newest_crash_report()
    if crash:
        parts.append(f"## Newest crash report ({name})\n```\n" + "\n".join(crash) + "\n```")
    if include_log:
        lines = _tail(pyos.log.LOG_FILE, 25)
        if lines:
            parts.append("## Last system log lines\n```\n" + "\n".join(lines) + "\n```")
    return "\n\n".join(parts) + "\n"


def pending_folder():
    import pyos
    return os.path.join(pyos.fs.BASE_DIR, "var", "reports")


def save_pending(summary):
    """After a crash: write a redacted, ready-to-send report to files/var/reports (it needs no network). Returns the path, or None."""
    try:
        folder = pending_folder()
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, f"pending-{time.strftime('%Y%m%d-%H%M%S')}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(summary.strip().splitlines()[0][:100] + "\n\n" + redact(build(summary)))
        return path
    except Exception:                                  # noqa: BLE001 - a crash must never fail while reporting itself
        return None


def pending():
    """[(name, path)] of the reports waiting to be sent, oldest first."""
    try:
        folder = pending_folder()
        return [(n, os.path.join(folder, n)) for n in sorted(os.listdir(folder)) if n.startswith("pending-") and n.endswith(".txt")]
    except OSError:
        return []


def read_pending(path):
    """(title, body) of a pending report file."""
    with open(path, encoding="utf-8") as f:
        first, _, rest = f.read().partition("\n\n")
    return first.strip() or "Crash report", rest


def finish_pending(path):
    """Move a handled report out of the waiting list (into var/reports/done)."""
    try:
        done = os.path.join(os.path.dirname(path), "done")
        os.makedirs(done, exist_ok=True)
        os.replace(path, os.path.join(done, os.path.basename(path)))
    except OSError:
        pass


def redact(text):
    """Remove what identifies the person: account names, home folders, email addresses, IP addresses, host name."""
    try:
        import users
        names = [n for n in users.get_users() if len(n) > 2]
    except Exception:
        names = []
    for name in sorted(names, key=len, reverse=True):
        text = re.sub(rf"(?<![\w-]){re.escape(name)}(?![\w-])", "<user>", text)
    try:
        import pyos.fs as fs
        host = fs.hostname()
        if host and len(host) > 2:
            text = re.sub(rf"(?<![\w-]){re.escape(host)}(?![\w-])", "<host>", text)
    except Exception:
        pass
    text = re.sub(r"[\w.+-]+@[\w-]+(\.[\w-]+)+", "<email>", text)
    text = re.sub(r"\b\d{1,3}(\.\d{1,3}){3}\b", "<ip>", text)
    text = re.sub(r"[A-Za-z]:\\Users\\[^\\\s]+", lambda m: "C:\\Users\\<user>", text)
    text = re.sub(r"/(home|Users)/[^/\s]+", r"/\1/<user>", text)
    return text


def send_via_relay(url, title, body, timeout=15):
    """POST the report to a relay that files the GitHub issue. Returns the issue address the relay gives back. Raises on failure."""
    import requests
    if not url.lower().startswith("https://"):
        raise ValueError("the relay address must start with https://")
    response = requests.post(url, json={"title": title, "body": body, "source": "pythonos", "version": _version()}, timeout=timeout)
    response.raise_for_status()
    try:
        return str(response.json().get("url", "")) or "sent"
    except ValueError:
        return "sent"
