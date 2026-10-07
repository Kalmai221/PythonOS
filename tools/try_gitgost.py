#!/usr/bin/env python3
"""Tries the GitGost anonymous issue service (https://gitgost.leapcell.app) once, to see whether it works from PythonOS.

    python tools/try_gitgost.py            show what would be sent (nothing is sent)
    python tools/try_gitgost.py --send     really create ONE issue on the repository (public; close it afterwards)

Not a CI test (its name does not start with test_): it needs the internet and creates a real issue.
Options: --repo owner/name (default Kalmai221/PythonOS), --url <service address>.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO_ROOT)

SERVICE = "https://gitgost.leapcell.app"


def option(name, default):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv and sys.argv.index(name) + 1 < len(sys.argv) else default


def main():
    repo = option("--repo", "Kalmai221/PythonOS")
    service = option("--url", SERVICE).rstrip("/")
    owner, _, name = repo.partition("/")
    endpoint = f"{service}/v1/gh/{owner}/{name}/issues/anonymous"
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    body = ("**This is a test of the automatic problem report from PythonOS (GitGost relay). Please ignore and close it.**\n\n"
            f"Sent: {stamp}\n\n"
            "```\nPythonOS test report\nnothing is wrong; this checks that an issue can be created without a GitHub login\n```\n")
    try:
        from pyos import report
        body = report.redact(body)                         # the same redaction a real report goes through
    except Exception:                                      # noqa: BLE001 - the test must also run from a bare checkout
        pass
    payload = {"title": f"[test] automatic report check {stamp}", "body": body}

    print(f"Endpoint: {endpoint}")
    print("Payload:")
    print(json.dumps(payload, indent=2))
    if "--send" not in sys.argv:
        print("\nNothing was sent. Add --send to create the issue.")
        return 0

    request = urllib.request.Request(endpoint, data=json.dumps(payload).encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/json", "User-Agent": "PythonOS-report-test"})
    started = time.time()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:                  # nosec - the address is fixed above
            status, text = response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        print(f"\nThe service answered with an error: HTTP {e.code}")
        print(e.read().decode("utf-8", "replace")[:1000])
        return 1
    except (urllib.error.URLError, OSError) as e:
        print(f"\nCould not reach the service: {e}")
        return 1
    print(f"\nHTTP {status} after {time.time() - started:.1f} s")
    try:
        data = json.loads(text)
    except ValueError:
        print(text[:1000])
        return 0 if 200 <= status < 300 else 1
    print(json.dumps(data, indent=2)[:2000])
    for key in ("issue_url", "html_url", "url"):
        if data.get(key):
            print(f"\nThe issue is at {data[key]} (plain text: type it into a browser on any device). Close it when you have looked.")
            break
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    sys.exit(main())
