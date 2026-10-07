#!/usr/bin/env python3
"""The gh command (runs the real GitHub CLI in the PythonOS terminal) and the GitHub way of `report`. gh itself is faked."""
import json
import os
import shutil
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO_ROOT)


def main():
    tmp = tempfile.mkdtemp()
    try:
        os.environ["PYOS_USERS_FILE"] = os.path.join(tmp, "users.json")
        os.chdir(tmp)
        os.makedirs(".OSData")
        import users
        from commands import gh, report as report_command
        from pyos import reportsend

        with open(os.environ["PYOS_USERS_FILE"], "w", encoding="utf-8") as f:
            json.dump({"sam": {"password": users.hash_password("x"), "role": "user"}}, f)
        users.save_session("sam", "user")
        gh.console.quiet = True
        report_command.console.quiet = True

        # gh missing: a clear failure with how to install it, nothing run
        reportsend.gh_path = lambda: None
        assert gh.execute(["issue", "list"]) is False

        # gh present: the arguments go to the real gh untouched, as this account; its exit code is the command's
        reportsend.gh_path = lambda: "/usr/bin/gh"
        seen = []
        reportsend.run_gh = lambda args, user: (seen.append((args, user)), 0)[1]
        assert gh.execute(["issue", "list", "--state", "all", "-L", "5"]) is True
        assert seen == [(["issue", "list", "--state", "all", "-L", "5"], "sam")], seen
        reportsend.run_gh = lambda args, user: 1
        assert gh.execute(["issue", "view", "9999"]) is False
        reportsend.run_gh = lambda args, user: (_ for _ in ()).throw(reportsend.SendError("gh took too long"))
        assert gh.execute(["issue", "list"]) is False
        reportsend.run_gh = lambda args, user: (_ for _ in ()).throw(KeyboardInterrupt())
        assert gh.execute(["auth", "login"]) is False

        # report's GitHub way: signs in when needed, creates the issue, and deletes the sign-in unless the person chooses to stay in
        events = []
        state = {"in": False}
        reportsend.gh_signed_in = lambda user: state["in"]

        def login(user):
            events.append("login")
            state["in"] = True
        reportsend.gh_login = login
        reportsend.gh_create_issue = lambda user, title, body: (events.append(("create", title)), {"number": 9, "url": "https://github.com/x/9"})[1]
        reportsend.gh_forget = lambda user: (events.append("forget"), state.__setitem__("in", False))
        report_command.Confirm.ask = lambda *a, **k: False
        assert report_command._send_github("Crash", "text") is True
        assert events == ["login", ("create", "Crash"), "forget"], events

        events.clear()
        report_command.Confirm.ask = lambda *a, **k: True
        assert report_command._send_github("Crash", "text") is True
        assert events == ["login", ("create", "Crash")], "staying signed in keeps it"

        events.clear()
        assert report_command._send_github("Crash", "text") is True
        assert events == [("create", "Crash")], "already signed in: no sign-in, and it is not deleted"

        # a failed issue is a clean failure; a half-finished sign-in is not kept
        state["in"] = False
        events.clear()

        def refuse(user, title, body):
            raise reportsend.SendError("GitHub could not create the issue: nope")
        reportsend.gh_create_issue = refuse
        report_command.Confirm.ask = lambda *a, **k: False
        assert report_command._send_github("Crash", "text") is False
        assert events == ["login", "forget"], events
    finally:
        os.chdir(REPO_ROOT)                               # a Windows folder cannot be removed while it is the current one
        shutil.rmtree(tmp, ignore_errors=True)
    print("gh command: all checks passed")


if __name__ == "__main__":
    main()
