# pyos/report.py - a problem report the user can read, then send in a way they choose
#
# Nothing here sends anything by itself. build() gathers: the version and package, the platform, the last log lines, what happened
# to the last session and the newest crash report. redact() removes things that identify the person (user names, home paths, email
# and IP addresses). The user sees the whole text first, then picks: open a prefilled GitHub issue (a link), save it to a file,
# or - only if a relay address is set - send it through a small relay service that files the issue (see OS_Export/relay/README.md).
# A GitHub token is never stored in PythonOS: anything inside an app can be taken out of it.
import json
import os
import platform
import re
import time
import urllib.parse

REPO = "Kalmai221/PythonOS"
ISSUE_URL = f"https://github.com/{REPO}/issues/new"
MAX_URL_BODY = 3500           # browsers and GitHub refuse very long links


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


def issue_link(title, body):
    """A link that opens GitHub's new-issue page with the title and text filled in (the text is cut to fit a link)."""
    note = ""
    if len(body) > MAX_URL_BODY:
        body = body[:MAX_URL_BODY]
        note = "\n\n(report cut to fit a link - the full text is in the file the app saved)"
    query = urllib.parse.urlencode({"title": title, "body": body + note}, quote_via=urllib.parse.quote)
    return f"{ISSUE_URL}?{query}"


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
