#!/usr/bin/env python3
"""Sending a problem report: GitHub through the GitHub CLI (`gh`, faked here), reading what became of an issue, the Discord way, and the
engine of the `gh` command that runs the real gh in the PythonOS terminal. All network traffic and every gh call is faked; nothing leaves
this computer."""
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO_ROOT)

from pyos import ghfetch, reportsend  # noqa: E402
reportsend.ghfetch = ghfetch


class Reply:
    def __init__(self, status, payload):
        self.status = status
        self._raw = payload if isinstance(payload, str) else json.dumps(payload)

    def read(self):
        return self._raw.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class FakeNet:
    """Answers by URL; records every request so the test can see what was sent."""

    def __init__(self):
        self.routes, self.sent = [], []

    def on(self, part, *replies):
        self.routes.append([part, list(replies)])

    def __call__(self, request, timeout=None):
        url = request.full_url
        self.sent.append((url, request.get_method(), dict(request.header_items()), request.data))
        for route in self.routes:
            if route[0] in url:
                reply = route[1].pop(0) if len(route[1]) > 1 else route[1][0]
                if isinstance(reply, Exception):
                    raise reply
                return reply
        raise AssertionError("unexpected request: " + url)


def main():
    net = FakeNet()
    reportsend._open = net
    real_gh_function = reportsend._gh
    tmp = tempfile.mkdtemp()
    here = os.getcwd()
    os.chdir(tmp)
    os.makedirs(".OSData")
    real_targets = reportsend.TARGETS
    reportsend.TARGETS = os.path.join(tmp, "targets.json")
    try:
        # nothing set up: Discord is not offered, and asking for it is a plain error
        assert not reportsend.can_discord()
        try:
            reportsend.send_discord("x", "y")
            raise AssertionError("must refuse when Discord is not set up")
        except reportsend.SendError:
            pass

        hook = "https://discord.com/api/webhooks/123/abc"
        assert reportsend.reveal(reportsend.disguise(hook)) == hook
        assert "discord" not in reportsend.disguise(hook), "the address must not appear in the file"
        with open(reportsend.TARGETS, "w", encoding="utf-8") as f:
            json.dump({"discord": reportsend.disguise("http://insecure.example/x")}, f)
        assert not reportsend.can_discord(), "only https addresses are used"
        with open(reportsend.TARGETS, "w", encoding="utf-8") as f:
            json.dump({"discord": reportsend.disguise(hook)}, f)
        assert reportsend.can_discord()

        # gh is the real GitHub CLI: without it nothing is offered and the hint says how to get it
        real_which = shutil.which
        shutil.which = lambda name, *a, **k: None if name == "gh" else real_which(name, *a, **k)
        try:
            assert reportsend.gh_path() is None
            assert reportsend.can_github() == reportsend.ghfetch.possible(), "without gh it can be downloaded, except on Android"
            try:
                reportsend.gh_login("sam")
                raise AssertionError("must say gh is missing")
            except reportsend.SendError as e:
                assert "not installed" in str(e)
            assert reportsend.install_hint()
        finally:
            shutil.which = real_which

        # with gh: it runs with a folder of its own for each account, and the sign-in is deleted on request
        ran = []
        reportsend.gh_path = lambda: "/usr/bin/gh"
        assert reportsend.can_github()
        env_sam, env_lee = reportsend.gh_env("sam"), reportsend.gh_env("lee")
        assert env_sam["GH_CONFIG_DIR"] != env_lee["GH_CONFIG_DIR"] and ".OSData" in env_sam["GH_CONFIG_DIR"], "accounts must not share a sign-in"
        assert "BROWSER" not in env_sam

        signed = {"in": False}

        def fake_gh(args, user, capture=None, timeout=None):
            ran.append((args, user, capture))
            if args[:2] == ["auth", "login"]:
                signed["in"] = True
                os.makedirs(os.path.join(reportsend.GH_HOME, user), exist_ok=True)
                open(os.path.join(reportsend.GH_HOME, user, "hosts.yml"), "w", encoding="utf-8").write("oauth_token: secret")
                return 0, ""
            if args[:2] == ["auth", "status"]:
                return (0, "Logged in") if signed["in"] else (1, "not logged in")
            if args[:2] == ["issue", "create"]:
                return 0, "https://github.com/Kalmai221/PythonOS/issues/91\n"
            raise AssertionError(args)

        reportsend._gh = fake_gh
        assert not reportsend.gh_signed_in("sam")
        reportsend.gh_login("sam")
        login_call = next(c for c in ran if c[0][:2] == ["auth", "login"])
        assert "--web" in login_call[0] and "public_repo" in login_call[0]
        assert reportsend.gh_signed_in("sam")
        issue = reportsend.gh_create_issue("sam", "It broke", "details")
        assert issue == {"number": 91, "url": "https://github.com/Kalmai221/PythonOS/issues/91"}, issue
        args, user, capture = ran[-1]
        assert args[args.index("--repo") + 1] == "Kalmai221/PythonOS" and capture == "details" and "-" in args and user == "sam"
        assert reportsend.recorded()[-1]["number"] == 91
        reportsend.gh_forget("sam")
        assert not os.path.exists(os.path.join(reportsend.GH_HOME, "sam")), "the sign-in must be deleted"

        reportsend._gh = lambda args, user, capture=None, timeout=None: (1, "HTTP 403: nope\n")
        try:
            reportsend.gh_create_issue("sam", "x", "y")
            raise AssertionError("must fail")
        except reportsend.SendError as e:
            assert "could not create" in str(e) and "403" in str(e), e
        reportsend._gh = lambda args, user, capture=None, timeout=None: (1, "")
        try:
            reportsend.gh_login("sam")
            raise AssertionError("must fail when the sign-in does not finish")
        except reportsend.SendError as e:
            assert "did not finish" in str(e)
        reportsend._gh = lambda args, user, capture=None, timeout=None: (0, "created\n")
        try:
            reportsend.gh_create_issue("sam", "x", "y")
            raise AssertionError("an answer without an issue address is a failure")
        except reportsend.SendError:
            pass

        # a gh that hangs is stopped with a plain message
        reportsend._gh = real_gh_function
        real_run = subprocess.run

        def hang(*_a, **_k):
            raise subprocess.TimeoutExpired("gh", 1)
        subprocess.run = hang
        try:
            reportsend._gh(["issue", "list"], "sam", capture="", timeout=1)
            raise AssertionError("must fail")
        except reportsend.SendError as e:
            assert "too long" in str(e)
        finally:
            subprocess.run = real_run

        # the gh command's engine: in a pipe the output is captured and written out
        calls = []
        reportsend._gh = lambda args, user, capture=None, timeout=None: (calls.append(args), (0, "#1 a bug\n"))[1]
        old_out = sys.stdout
        sys.stdout = io.StringIO()                          # not a terminal, so the output is captured
        try:
            code = reportsend.run_gh(["issue", "list"], "sam")
            printed = sys.stdout.getvalue()
        finally:
            sys.stdout = old_out
        assert code == 0 and printed == "#1 a bug\n" and calls == [["issue", "list"]], (code, printed, calls)

        # on a real terminal gh gets the terminal itself (its sign-in prompts and waits for a key)
        class Terminal(io.StringIO):
            def isatty(self):
                return True
        direct, old_in, old_call = [], sys.stdin, subprocess.call
        subprocess.call = lambda cmd, env=None: (direct.append((cmd, env["GH_CONFIG_DIR"])), 0)[1]
        sys.stdin, sys.stdout = Terminal(), Terminal()
        try:
            code = reportsend.run_gh(["auth", "login"], "sam")
        finally:
            sys.stdin, sys.stdout, subprocess.call = old_in, old_out, old_call
        assert code == 0 and direct and direct[0][0] == ["/usr/bin/gh", "auth", "login"] and ".OSData" in direct[0][1], direct
        assert calls == [["issue", "list"]], "on a terminal gh must not be captured"

        # what became of the report: state and replies, with no sign-in
        net.routes = [["/issues/77/comments", [Reply(200, [{"user": {"login": "Kalmai221"}, "body": "Fixed in 1.0.12"}])]],
                      ["/issues/77", [Reply(200, {"title": "It broke", "state": "closed", "state_reason": "completed", "comments": 1,
                                                  "html_url": "https://github.com/Kalmai221/PythonOS/issues/77"})]]]
        info = reportsend.status_of(77)
        assert info["state"].startswith("closed") and info["comments"] == [("Kalmai221", "Fixed in 1.0.12")], info
        assert all("Authorization" not in h for _u, _m, h, _d in net.sent)
        net.routes = [["/issues/5", [Reply(404, {"message": "Not Found"})]]]
        try:
            reportsend.status_of(5)
            raise AssertionError("must fail")
        except reportsend.SendError as e:
            assert "no issue number 5" in str(e)
        net.routes = [["/issues/6", [urllib.error.URLError("no route")]]]
        try:
            reportsend.status_of(6)
            raise AssertionError("must fail")
        except reportsend.SendError as e:
            assert "could not reach" in str(e), e

        # Discord: a message and the full text as a file, once per ten minutes
        net.sent.clear()
        net.routes = [["discord.com", [Reply(204, "")]]]
        reportsend.send_discord("Crash", "full text of the report")
        url, method, headers, data = net.sent[0]
        assert url == hook and "multipart/form-data" in headers["Content-type"], headers
        assert b"full text of the report" in data and b"report.txt" in data and b'"parse": []' in data, "no pings, the text is attached"
        try:
            reportsend.send_discord("Crash again", "x")
            raise AssertionError("a second report right away must wait")
        except reportsend.SendError as e:
            assert "try again in" in str(e), e
        assert len(net.sent) == 1, "the wait is enforced before anything is sent"
        os.remove(reportsend._stamp_file())
        net.routes = [["discord.com", [Reply(429, {"message": "slow"})]]]
        try:
            reportsend.send_discord("Crash", "x")
            raise AssertionError("must fail")
        except reportsend.SendError as e:
            assert "busy" in str(e)
        assert not os.path.exists(reportsend._stamp_file()), "a refused report must not start the wait"
    finally:
        reportsend.TARGETS = real_targets
        os.chdir(here)                                      # a Windows folder cannot be removed while it is the current one
        shutil.rmtree(tmp, ignore_errors=True)
    print("report sending: all checks passed")


if __name__ == "__main__":
    main()
