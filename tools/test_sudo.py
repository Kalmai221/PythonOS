#!/usr/bin/env python3
"""sudo: an administrator confirms with their password, a standard user needs an administrator's name and password, the command runs with
administrator rights only for that one command, and the person's own session is always put back. Passwords are faked."""
import json
import os
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["PYOS_USERS_FILE"] = os.path.join(tmp, "users.json")
        os.chdir(tmp)
        os.makedirs(".OSData")
        import pyos
        import users
        from pyos import audit, settings
        from commands import sudo
        import shell

        db = {"root": {"password": users.hash_password("rootpw"), "role": "admin"},
              "sam": {"password": users.hash_password("sampw"), "role": "user"}}
        with open(os.environ["PYOS_USERS_FILE"], "w", encoding="utf-8") as f:
            json.dump(db, f)
        sudo.console.quiet = True

        seen = []
        shell.run_line = lambda line: (seen.append((line, pyos.userinfo())), 0)[1]
        typed = []
        sudo.getpass.getpass = lambda prompt="": typed.pop(0)
        sudo.input = lambda prompt="": typed.pop(0)

        # a standard user: the administrator's password is needed, and it is only an administrator for that one command
        users.save_session("sam", "user")
        typed[:] = ["rootpw"]
        assert sudo.execute(["doctor", "--fix"]) is True
        assert seen == [("doctor --fix", ["root", "admin"])], seen
        assert pyos.userinfo() == ["sam", "user"], "the person's own session must be put back"

        typed[:] = ["wrong", "wrong", "wrong"]
        seen.clear()
        assert sudo.execute(["doctor"]) is False and not seen, "a wrong password must not run anything"
        assert pyos.userinfo() == ["sam", "user"]

        # the command failing or raising still restores the session
        typed[:] = ["rootpw"]
        shell.run_line = lambda line: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            sudo.execute(["doctor"])
        except RuntimeError:
            pass
        assert pyos.userinfo() == ["sam", "user"], "the session must come back even when the command fails"

        # an administrator is asked for their own password (unless the setting is off), then the command runs as them
        shell.run_line = lambda line: (seen.append((line, pyos.userinfo())), 0)[1]
        users.save_session("root", "admin")
        audit.forget()
        seen.clear()
        typed[:] = ["rootpw"]
        assert sudo.execute(["hostname", "x"]) is True and seen == [("hostname x", ["root", "admin"])], seen
        seen.clear()
        assert sudo.execute(["hostname", "y"]) is True, "the password is remembered for a few minutes"
        assert not typed
        assert sudo.execute(["-k"]) is True
        typed[:] = ["wrong", "wrong", "wrong"]
        assert sudo.execute(["hostname", "z"]) is False, "after -k the password is asked again"

        # no command is a usage error
        assert sudo.execute([]) is False
        del settings
        os.chdir(REPO)                                    # a Windows folder cannot be removed while it is the current one
    print("sudo: all checks passed")


if __name__ == "__main__":
    main()
