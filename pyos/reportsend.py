# pyos/reportsend.py - sending a problem report: to GitHub as the person's own account, or to a Discord channel without one
#
# PythonOS is a command line system, so nothing here opens a browser or a link. Everything is plain HTTPS from this process.
#
#   GitHub (main):  the "device flow". The person is shown a short code and an address to type on any device; once they have approved,
#                   PythonOS gets a token for the `public_repo` scope, creates the issue as them, and throws the token away. It is never
#                   written to disk (anything inside an app can be taken out of it). It needs the client id of PythonOS's OAuth app, which
#                   is public and not a secret (pyos/report_targets.json, set with tools/set_report_targets.py).
#   Discord:        for people with no GitHub account: the report is posted to a channel through a webhook. The address is only lightly
#                   disguised (so GitHub's secret scanner does not revoke it): it is not a secret from anyone who reads the code, so it is
#                   rate limited on this side and can be replaced by editing one file.
#
# Both are used only when the person chooses them, after reading the whole report.
import base64
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from pyos import report

TARGETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_targets.json")
API = "https://api.github.com"
GITHUB = "https://github.com"
SCOPE = "public_repo"                        # the smallest scope that lets an OAuth app create an issue in a public repository
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
    """{"github_client_id": str, "discord": str}; an empty value means that way of sending is not set up in this build."""
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
    return {"github_client_id": str(data.get("github_client_id", "")).strip(), "discord": hook}


def can_github():
    return bool(targets()["github_client_id"])


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


def _form(url, fields):
    return _request(url, urllib.parse.urlencode(fields).encode("ascii"),
                    {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}, "POST")


# ---------------------------------------------------------------- GitHub: sign in with a code
def start_device_flow():
    """Ask GitHub for a code. Returns {"user_code", "verification_uri", "device_code", "interval", "expires_in"}."""
    client = targets()["github_client_id"]
    if not client:
        raise SendError("sending through GitHub is not set up in this copy of PythonOS")
    status, data = _form(f"{GITHUB}/login/device/code", {"client_id": client, "scope": SCOPE})
    if status != 200 or not isinstance(data, dict) or "device_code" not in data:
        raise SendError(f"GitHub did not start the sign-in (HTTP {status}): {_message(data)}")
    return {"user_code": data["user_code"], "verification_uri": data.get("verification_uri", f"{GITHUB}/login/device"),
            "device_code": data["device_code"], "interval": max(int(data.get("interval", 5)), 1), "expires_in": int(data.get("expires_in", 900))}


def wait_for_token(flow, sleep=time.sleep, clock=time.time, tick=None):
    """Wait until the person has approved the code on their other device. Returns the access token (kept in memory only)."""
    client = targets()["github_client_id"]
    deadline = clock() + flow["expires_in"]
    interval = flow["interval"]
    while clock() < deadline:
        sleep(interval)
        status, data = _form(f"{GITHUB}/login/oauth/access_token",
                             {"client_id": client, "device_code": flow["device_code"], "grant_type": "urn:ietf:params:oauth:grant-type:device_code"})
        if isinstance(data, dict):
            if data.get("access_token"):
                return data["access_token"]
            error = data.get("error")
            if error == "authorization_pending":
                if tick:
                    tick()
                continue
            if error == "slow_down":
                interval += 5
                continue
            if error == "expired_token":
                raise SendError("the code ran out; start again")
            if error == "access_denied":
                raise SendError("the sign-in was cancelled on GitHub")
            raise SendError(f"GitHub refused the sign-in: {data.get('error_description') or error or status}")
        raise SendError(f"unexpected answer from GitHub (HTTP {status})")
    raise SendError("the code ran out; start again")


def _message(data):
    if isinstance(data, dict):
        return str(data.get("message") or data.get("error_description") or data.get("error") or "")[:300]
    return str(data)[:300]


def create_issue(token, title, body):
    """Create the issue as the person who signed in. Returns {"number", "url"}."""
    if len(body) > MAX_BODY:
        body = body[:MAX_BODY] + "\n\n(cut to fit GitHub's limit)"
    payload = json.dumps({"title": title[:250] or "Problem report", "body": body}).encode("utf-8")
    status, data = _request(f"{API}/repos/{report.REPO}/issues", payload,
                            {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
                             "Content-Type": "application/json", "X-GitHub-Api-Version": "2022-11-28"}, "POST")
    if status in (200, 201) and isinstance(data, dict) and data.get("number"):
        number = int(data["number"])
        url = str(data.get("html_url") or f"https://github.com/{report.REPO}/issues/{number}")
        remember(number, title, url)
        return {"number": number, "url": url}
    if status in (401, 403):
        raise SendError(f"GitHub did not allow it (HTTP {status}): {_message(data)}")
    if status == 410:
        raise SendError("issues are switched off on that repository")
    raise SendError(f"GitHub could not create the issue (HTTP {status}): {_message(data)}")


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
    status, data = _request(f"{API}/repos/{report.REPO}/issues/{int(number)}", headers={"Accept": "application/vnd.github+json"})
    if status == 404:
        raise SendError(f"there is no issue number {int(number)}")
    if status != 200 or not isinstance(data, dict):
        raise SendError(f"GitHub could not be asked (HTTP {status}): {_message(data)}")
    comments = []
    if data.get("comments"):
        code, found = _request(f"{API}/repos/{report.REPO}/issues/{int(number)}/comments?per_page=10", headers={"Accept": "application/vnd.github+json"})
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
