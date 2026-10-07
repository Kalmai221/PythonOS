# pyos/reportsend.py - sending a problem report: to GitHub as the person's own account, or to a Discord channel without one
#
# PythonOS is a command line system, so nothing here opens a browser or a link. Everything is plain HTTPS from this process.
#
#   GitHub (main):  the real GitHub CLI, `gh` (the `gh` command of PythonOS just runs it in this terminal). The ISO and the virtual
#                   machines install it (their own system), and every other export downloads it once, after asking, into PythonOS's
#                   private data (pyos/ghfetch.py): it is never installed on the computer itself.
#                   `gh` signs the person in (it shows a one-time code to approve on another device) and creates the issue. Its sign-in
#                   is kept in a private folder of PythonOS's data, per account, and `report` deletes it afterwards unless the person
#                   chooses to stay signed in. No app of ours is involved.
#   Discord:        for people with no GitHub account: the report is posted to a channel through a webhook. The address is only lightly
#                   disguised (so GitHub's secret scanner does not revoke it): it is not a secret from anyone who reads the code, so it is
#                   rate limited on this side and can be replaced by editing one file.
#
# Each is used only when the person chooses it, after reading the whole report.
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from pyos import report

TARGETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_targets.json")
API = "https://api.github.com"
DISCORD_EVERY = 10 * 60                      # seconds between two reports sent to Discord from one installation
MAX_BODY = 60000                             # GitHub accepts 65536 characters in an issue body
RECORDS = os.path.join(".OSData", "reports.json")
KEY = b"pythonos-report-targets"
_open = urllib.request.urlopen               # replaced by tests


class SendError(Exception):
    """Something the person can be told in one sentence."""


# ---------------------------------------------------------------- the targets
def disguise(text):
    raw = text.encode("utf-8")
    return base64.urlsafe_b64encode(bytes(b ^ KEY[i % len(KEY)] for i, b in enumerate(raw))).decode("ascii")


def reveal(text):
    try:
        raw = base64.urlsafe_b64decode(text.encode("ascii"))
        return bytes(b ^ KEY[i % len(KEY)] for i, b in enumerate(raw)).decode("utf-8")
    except (ValueError, UnicodeError):
        return ""


def targets():
    """{"discord": str}; an empty value means that way of sending is not set up in this build."""
    try:
        with open(TARGETS, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    if not isinstance(data, dict):
        data = {}
    hook = reveal(str(data.get("discord", ""))) if data.get("discord") else ""
    if hook and not hook.startswith("https://"):
        hook = ""
    return {"discord": hook}


def gh_path():
    """The GitHub CLI: the one named by PYOS_GH, the one PythonOS downloaded, or one on the system (ISO, VM)."""
    from pyos import ghfetch
    named = os.environ.get("PYOS_GH")
    if named and os.path.isfile(named):
        return named
    return ghfetch.fetched() or shutil.which("gh")


def can_github():
    """True if gh is here or can be downloaded (everywhere but Android)."""
    from pyos import ghfetch
    return bool(gh_path()) or ghfetch.possible()


def ensure_gh(ask, say=print):
    """Make sure gh is available, downloading it (into PythonOS's private data only) if the person agrees. `ask(question)` returns True or False.
    Returns True when gh can be run. Raises SendError when it cannot be had."""
    from pyos import ghfetch
    if gh_path():
        return True
    if not ghfetch.possible():
        raise SendError(install_hint())
    if not ask(f"The GitHub CLI is not in this PythonOS yet. Download GitHub's official release (version {ghfetch.VERSION}, about 15 MB) into "
               "PythonOS's own folder? It is not installed anywhere else and its checksum is verified"):
        return False
    try:
        ghfetch.fetch(say)
    except ghfetch.FetchError as e:
        raise SendError(str(e)) from e
    return True


def can_discord():
    return bool(targets()["discord"])


def _lockdown():
    try:
        from pyos import lockdown
        return lockdown.enabled()
    except Exception:                                      # noqa: BLE001
        return False


# ---------------------------------------------------------------- http
def _request(url, data=None, headers=None, method=None, timeout=15):
    """(status, parsed JSON or text). HTTP errors are returned, not raised, so GitHub's own message can be read."""
    if not url.startswith("https://"):
        raise SendError("only https:// addresses are used")
    request = urllib.request.Request(url, data=data, method=method, headers={"User-Agent": "PythonOS-report", **(headers or {})})
    try:
        with _open(request, timeout=timeout) as response:               # nosec - fixed https addresses
            status, text = response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as e:
        raise SendError(f"could not reach {urllib.parse.urlsplit(url).netloc}: {getattr(e, 'reason', e)}") from e
    try:
        return status, json.loads(text)
    except ValueError:
        return status, text


def _message(data):
    if isinstance(data, dict):
        return str(data.get("message") or data.get("error_description") or data.get("error") or "")[:300]
    return str(data)[:300]


# ---------------------------------------------------------------- GitHub with the GitHub CLI
GH_HOME = os.path.join(".OSData", "gh")      # one folder of gh's own config (and so its sign-in) for each account, inside PythonOS's private data


def gh_env(user):
    """The environment gh runs in: its config is in PythonOS's private data for this account, so accounts do not share a sign-in and apps cannot read it."""
    env = dict(os.environ, GH_CONFIG_DIR=os.path.abspath(os.path.join(GH_HOME, user or "default")), GH_NO_UPDATE_NOTIFIER="1")
    env.pop("GH_BROWSER", None)
    env.pop("BROWSER", None)
    return env


def gh_signed_in(user):
    """True if gh has a working sign-in for this account."""
    code, _out = _gh(["auth", "status", "--hostname", "github.com"], user, capture="")
    return code == 0


def _gh(args, user, capture=None, timeout=None):
    """Run gh. capture=None: it uses the terminal (the sign-in prints a code and waits for a key). Otherwise its output is captured
    and `capture` is what it is given as input. Returns (exit code, output)."""
    exe = gh_path()
    if not exe:
        raise SendError("the GitHub CLI (gh) is not installed in this copy of PythonOS")
    os.makedirs(os.path.join(GH_HOME, user or "default"), exist_ok=True)
    try:
        if capture is None:
            return subprocess.call([exe] + args, env=gh_env(user)), ""
        done = subprocess.run([exe] + args, input=capture, capture_output=True, text=True, env=gh_env(user), timeout=timeout or 60, check=False)
        return done.returncode, (done.stdout or "") + (done.stderr or "")
    except subprocess.TimeoutExpired as e:
        raise SendError("gh took too long") from e
    except OSError as e:
        raise SendError(f"could not run gh: {e}") from e


def gh_login(user):
    """Let gh sign the person in: it shows a one-time code to approve on another device. The token stays in this account's gh folder."""
    code, _out = _gh(["auth", "login", "--hostname", "github.com", "--web", "--scopes", "public_repo", "--git-protocol", "https", "--insecure-storage"], user)
    if code != 0 or not gh_signed_in(user):
        raise SendError("the GitHub sign-in did not finish")


def gh_create_issue(user, title, body):
    """Create the issue with gh. Returns {"number", "url"}."""
    if len(body) > MAX_BODY:
        body = body[:MAX_BODY] + "\n\n(cut to fit GitHub's limit)"
    code, out = _gh(["issue", "create", "--repo", report.REPO, "--title", title[:250] or "Problem report", "--body-file", "-"], user, capture=body, timeout=90)
    match = re.search(r"https://github\.com/[^\s]+/issues/(\d+)", out)
    if code != 0 or not match:
        raise SendError("GitHub could not create the issue: " + (out.strip().splitlines() or ["no answer"])[-1][:300])
    number = int(match.group(1))
    remember(number, title, match.group(0))
    return {"number": number, "url": match.group(0)}


def gh_forget(user):
    """Delete this account's gh sign-in."""
    shutil.rmtree(os.path.join(GH_HOME, user or "default"), ignore_errors=True)


def run_gh(args, user):
    """The `gh` command: run the real gh and show it in this terminal. Returns its exit code.

    On a real terminal gh gets the terminal itself (so its prompts and sign-in work). Inside a pipe or a redirect its output is
    captured and written to PythonOS's output, so `gh issue list | grep bug` works."""
    exe = gh_path()
    if not exe:
        raise SendError("the GitHub CLI (gh) is not installed in this copy of PythonOS")
    # PythonOS's stdout is a router that says it is not a terminal while the output is captured (a pipe, a redirect, `$(...)`)
    if sys.stdout.isatty() and sys.stdin.isatty():
        os.makedirs(os.path.join(GH_HOME, user or "default"), exist_ok=True)
        try:
            sys.stdout.flush()
        except (OSError, ValueError):
            pass
        return subprocess.call([exe] + args, env=gh_env(user))
    code, out = _gh(args, user, capture="", timeout=300)
    sys.stdout.write(out)
    return code


def install_hint():
    """Why gh is not here and what to do, in one line."""
    from pyos import ghfetch
    if ghfetch.on_android():
        return "the GitHub CLI cannot run on Android yet; use report with Discord or a file"
    if not ghfetch.possible():
        return "GitHub's CLI has no download for this kind of computer; use report with Discord or a file"
    return "the GitHub CLI is not here yet; run gh again and say yes to download it"


# ---------------------------------------------------------------- reports already sent, and what became of them
def remember(number, title, url):
    records = recorded()
    records.append({"number": number, "title": title[:120], "url": url, "time": int(time.time())})
    try:
        os.makedirs(os.path.dirname(RECORDS), exist_ok=True)
        with open(RECORDS, "w", encoding="utf-8") as f:
            json.dump(records[-30:], f)
    except OSError:
        pass


def recorded():
    try:
        with open(RECORDS, encoding="utf-8") as f:
            data = json.load(f)
        return [r for r in data if isinstance(r, dict) and "number" in r] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def status_of(number):
    """What is public about issue `number`: {"title", "state", "comments": [(who, text)], "url"}. Needs no sign-in (the repository is public)."""
    repo = report.REPO
    status, data = _request(f"{API}/repos/{repo}/issues/{int(number)}", headers={"Accept": "application/vnd.github+json"})
    if status == 404:
        raise SendError(f"there is no issue number {int(number)}")
    if status != 200 or not isinstance(data, dict):
        raise SendError(f"GitHub could not be asked (HTTP {status}): {_message(data)}")
    comments = []
    if data.get("comments"):
        code, found = _request(f"{API}/repos/{repo}/issues/{int(number)}/comments?per_page=10", headers={"Accept": "application/vnd.github+json"})
        if code == 200 and isinstance(found, list):
            comments = [(str((c.get("user") or {}).get("login", "?")), str(c.get("body", ""))) for c in found if isinstance(c, dict)]
    return {"title": str(data.get("title", "")), "state": str(data.get("state", "?")) + (" (resolved)" if data.get("state_reason") == "completed" else ""),
            "comments": comments, "url": str(data.get("html_url", ""))}


# ---------------------------------------------------------------- Discord: no account needed
def _stamp_file():
    return os.path.join(".OSData", "report_discord.txt")


def discord_wait():
    """Seconds until another report may be sent to Discord (0 if now)."""
    try:
        with open(_stamp_file(), encoding="utf-8") as f:
            return max(0, int(DISCORD_EVERY - (time.time() - float(f.read().strip()))))
    except (OSError, ValueError):
        return 0


def send_discord(title, body):
    """Post the report to the Discord channel: a short message and the full text as a file. Returns None when it was accepted."""
    hook = targets()["discord"]
    if not hook:
        raise SendError("sending through Discord is not set up in this copy of PythonOS")
    wait = discord_wait()
    if wait:
        raise SendError(f"a report was sent a moment ago; try again in {wait // 60 + 1} minute(s)")
    boundary = "----pythonos" + str(int(time.time() * 1000))
    summary = {"content": f"**{title[:200]}**\nPythonOS {report._version()} - full text attached", "allowed_mentions": {"parse": []}}
    parts = [f"--{boundary}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\nContent-Type: application/json\r\n\r\n{json.dumps(summary)}\r\n",
             f"--{boundary}\r\nContent-Disposition: form-data; name=\"files[0]\"; filename=\"report.txt\"\r\nContent-Type: text/plain\r\n\r\n"]
    data = parts[0].encode("utf-8") + parts[1].encode("utf-8") + body[:200000].encode("utf-8") + f"\r\n--{boundary}--\r\n".encode("ascii")
    status, answer = _request(hook, data, {"Content-Type": f"multipart/form-data; boundary={boundary}"}, "POST")
    if status == 429:
        raise SendError("Discord is busy; try again in a little while")
    if status not in (200, 204):
        raise SendError(f"Discord did not accept the report (HTTP {status}): {_message(answer)}")
    try:
        os.makedirs(".OSData", exist_ok=True)
        with open(_stamp_file(), "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    except OSError:
        pass
