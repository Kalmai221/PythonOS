#!/usr/bin/env python3
"""installos must make sure the base system (linux-lts, acct) can be fetched BEFORE erasing a disk. The live ISO's repository list can hold
only the disc, where `apk update` works but those packages do not exist (the failure seen in a VM). Tested with a fake `apk`."""
import os
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO)
os.chdir(REPO)

from core import hardware, installer  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as tmp:
        repos = os.path.join(tmp, "repositories")
        release = os.path.join(tmp, "alpine-release")
        installer.REPOSITORIES = repos
        real_open, real_run = open, hardware.run

        with real_open(release, "w", encoding="utf-8") as f:
            f.write("3.19.4\n")

        def fake_open(path, *a, **k):
            return real_open(release if path == "/etc/alpine-release" else path, *a, **k)

        def world(online, network=True):
            """A fake apk: the packages exist only when the online repository is listed; `update` fails without a network."""
            def run(cmd, timeout=15, text_input=None, env=None, merge=False):
                text = real_open(repos, encoding="utf-8").read()
                if cmd[:2] == ["apk", "update"]:
                    return (0, "ok") if (network or "dl-cdn" not in text) else (1, "network unreachable")
                if cmd[:3] == ["apk", "search", "-e"]:
                    return (0, cmd[3] + "-1.0\n" if False else cmd[3] + "\n") if online and "dl-cdn" in text else (0, "")
                raise AssertionError(cmd)
            return run

        import builtins
        builtins.open = fake_open
        try:
            # 1. the disc-only list: the online repositories for the running Alpine branch are added, and the packages are then found
            with real_open(repos, "w", encoding="utf-8") as f:
                f.write("/media/cdrom/apks\n")
            hardware.run = world(online=True)
            said = []
            installer.check_repositories(said.append)
            text = real_open(repos, encoding="utf-8").read()
            assert "https://dl-cdn.alpinelinux.org/alpine/v3.19/main" in text and "/community" in text and "/media/cdrom/apks" in text, text
            assert said, "the person is told the online repositories are being used"

            # 2. already fine (the packages exist): nothing is changed
            with real_open(repos, "w", encoding="utf-8") as f:
                f.write("https://dl-cdn.alpinelinux.org/alpine/v3.19/main\nhttps://dl-cdn.alpinelinux.org/alpine/v3.19/community\n")
            before = real_open(repos, encoding="utf-8").read()
            installer.check_repositories()
            assert real_open(repos, encoding="utf-8").read() == before

            # 3. no network: a clear error, and the repository list is put back
            with real_open(repos, "w", encoding="utf-8") as f:
                f.write("/media/cdrom/apks\n")
            hardware.run = world(online=True, network=False)
            try:
                installer.check_repositories()
                raise AssertionError("must fail without a network")
            except installer.InstallError as e:
                assert "cannot be reached" in str(e), e
            assert real_open(repos, encoding="utf-8").read() == "/media/cdrom/apks\n"

            # 4. the packages are in no repository: refuses, restores the list, says what is missing
            hardware.run = world(online=False)
            try:
                installer.check_repositories()
                raise AssertionError("must fail when the packages do not exist")
            except installer.InstallError as e:
                assert "linux-lts" in str(e) and "nothing was erased" in str(e), e
            assert real_open(repos, encoding="utf-8").read() == "/media/cdrom/apks\n"
        finally:
            builtins.open = real_open
            hardware.run = real_run
    print("installos repositories: all checks passed")


if __name__ == "__main__":
    main()
