#!/usr/bin/env python3
"""Sending a problem report: GitHub's device flow (code, wait, create the issue, forget the token), reading what became of an issue,
and the Discord way. All network traffic is faked; nothing leaves this computer."""
import json
import os
import sys
import tempfile
import urllib.error

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO_ROOT)

from pyos import reportsend  # noqa: E402


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
    with tempfile.TemporaryDirectory() as tmp:
        here = os.getcwd()
        os.chdir(tmp)
        os.makedirs(".OSData")
        real_targets = reportsend.TARGETS
        reportsend.TARGETS = os.path.join(tmp, "targets.json")
        try:
            # nothing is set up: neither way is offered, and asking for one is a plain error
            assert not reportsend.can_github() and not reportsend.can_discord()
            try:
                reportsend.start_device_flow()
                raise AssertionError("must refuse without a client id")
            except reportsend.SendError:
                pass

            hook = "https://discord.com/api/webhooks/123/abc"
            assert reportsend.reveal(reportsend.disguise(hook)) == hook
            assert hook not in reportsend.disguise(hook) and "discord" not in reportsend.disguise(hook), "the address must not appear in the file"
            with open(reportsend.TARGETS, "w", encoding="utf-8") as f:
                json.dump({"github_client_id": "Iv1.test", "discord": reportsend.disguise(hook)}, f)
            assert reportsend.can_github() and reportsend.can_discord()
            with open(reportsend.TARGETS, "w", encoding="utf-8") as f:
                json.dump({"github_client_id": "Iv1.test", "discord": reportsend.disguise("http://insecure.example/x")}, f)
            assert not reportsend.can_discord(), "only https addresses are used"
            with open(reportsend.TARGETS, "w", encoding="utf-8") as f:
                json.dump({"github_client_id": "Iv1.test", "discord": reportsend.disguise(hook)}, f)

            # the device flow: a code, GitHub says "pending", then "slow down", then the token
            net.on("/login/device/code", Reply(200, {"device_code": "dc", "user_code": "ABCD-1234", "verification_uri": "https://github.com/login/device",
                                                    "interval": 5, "expires_in": 900}))
            net.on("/login/oauth/access_token", Reply(200, {"error": "authorization_pending"}), Reply(200, {"error": "slow_down"}),
                   Reply(200, {"access_token": "gho_secret", "token_type": "bearer"}))
            flow = reportsend.start_device_flow()
            assert flow["user_code"] == "ABCD-1234"
            first = net.sent[0]
            assert b"client_id=Iv1.test" in first[3] and b"scope=public_repo" in first[3], first
            naps, ticks = [], []
            now = [0.0]
            token = reportsend.wait_for_token(flow, sleep=lambda s: (naps.append(s), now.__setitem__(0, now[0] + s)), clock=lambda: now[0],
                                              tick=lambda: ticks.append(1))
            assert token == "gho_secret"
            assert naps == [5, 5, 10], f"slow_down must make it wait longer: {naps}"
            assert ticks == [1]

            # a refusal and an expiry are plain errors
            for answer, words in (({"error": "access_denied"}, "cancelled"), ({"error": "expired_token"}, "ran out")):
                net.routes = [["/login/oauth/access_token", [Reply(200, answer)]]]
                try:
                    reportsend.wait_for_token(flow, sleep=lambda s: None, clock=lambda: 0.0)
                    raise AssertionError("must fail")
                except reportsend.SendError as e:
                    assert words in str(e), e
            # never waits longer than the code lives
            net.routes = [["/login/oauth/access_token", [Reply(200, {"error": "authorization_pending"})]]]
            now = [0.0]
            try:
                reportsend.wait_for_token(flow, sleep=lambda s: now.__setitem__(0, now[0] + 400), clock=lambda: now[0])
                raise AssertionError("must give up")
            except reportsend.SendError as e:
                assert "ran out" in str(e)

            # the issue is created as the person (their token), with the title and text; the token is never written to disk
            net.sent.clear()
            net.routes = [["/issues", [Reply(201, {"number": 77, "html_url": "https://github.com/Kalmai221/PythonOS/issues/77"})]]]
            issue = reportsend.create_issue("gho_secret", "It broke", "details here")
            assert issue == {"number": 77, "url": "https://github.com/Kalmai221/PythonOS/issues/77"}, issue
            url, method, headers, data = net.sent[0]
            assert url == "https://api.github.com/repos/Kalmai221/PythonOS/issues" and method == "POST"
            assert headers["Authorization"] == "Bearer gho_secret"
            assert json.loads(data) == {"title": "It broke", "body": "details here"}
            for base, _d, names in os.walk(tmp):
                for name in names:
                    assert "gho_secret" not in open(os.path.join(base, name), encoding="utf-8", errors="replace").read(), "the token must never be stored"
            assert reportsend.recorded()[-1]["number"] == 77

            # a long report is cut to GitHub's limit; errors are explained
            net.routes = [["/issues", [Reply(201, {"number": 78})]]]
            reportsend.create_issue("t", "x", "y" * 100000)
            assert len(json.loads(net.sent[-1][3])["body"]) < 65536
            for status, words in ((403, "did not allow"), (410, "switched off"), (500, "could not create")):
                net.routes = [["/issues", [Reply(status, {"message": "nope"})]]]
                try:
                    reportsend.create_issue("t", "x", "y")
                    raise AssertionError("must fail")
                except reportsend.SendError as e:
                    assert words in str(e), e

            # no network at all is a one-sentence error, not a traceback
            net.routes = [["/issues", [urllib.error.URLError("no route")]]]
            try:
                reportsend.create_issue("t", "x", "y")
                raise AssertionError("must fail")
            except reportsend.SendError as e:
                assert "could not reach" in str(e), e

            # what became of the report: state and replies, with no sign-in
            net.sent.clear()
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
            os.chdir(here)
    print("report sending: all checks passed")


if __name__ == "__main__":
    main()
