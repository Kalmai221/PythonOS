#!/usr/bin/env python3
"""The GitHub CLI download: the right release for each system, a checksum that must match, only the gh program taken out of the archive,
nothing outside PythonOS's folder touched, and the question asked before anything is downloaded. The network is faked."""
import hashlib
import io
import os
import shutil
import sys
import tarfile
import tempfile
import zipfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO_ROOT)

from pyos import ghfetch, reportsend  # noqa: E402


class Reply:
    def __init__(self, data):
        self._data = data

    def read(self, n=-1):
        return self._data if n < 0 else self._data[:n]

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


def archive(name, program=b"GH PROGRAM"):
    """A fake release archive: the program in bin/, and other files that must not be taken out."""
    if name.endswith(".zip"):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("gh_x/bin/gh.exe" if "windows" in name else "gh_x/bin/gh", program)
            z.writestr("gh_x/LICENSE", "license")
            z.writestr("../evil.txt", "must not be extracted")
        return out.getvalue()
    out = io.BytesIO()
    with tarfile.open(fileobj=out, mode="w:gz") as t:
        for member_name, data in (("gh_x/bin/gh", program), ("gh_x/LICENSE", b"license"), ("../evil.txt", b"must not be extracted")):
            info = tarfile.TarInfo(member_name)
            info.size = len(data)
            t.addfile(info, io.BytesIO(data))
    return out.getvalue()


def main():
    # the right release for each system; none for Android or a processor GitHub has no build for
    for system, machine, want in (("Linux", "x86_64", "linux_amd64.tar.gz"), ("Linux", "aarch64", "linux_arm64.tar.gz"), ("Linux", "armv7l", "linux_armv6.tar.gz"),
                                  ("Windows", "AMD64", "windows_amd64.zip"), ("Windows", "ARM64", "windows_arm64.zip"),
                                  ("Darwin", "arm64", "macOS_arm64.zip")):
        assert ghfetch.asset(system, machine) == f"gh_{ghfetch.VERSION}_{want}", (system, machine)
    assert ghfetch.asset("Linux", "riscv64") is None and ghfetch.asset("Darwin", "i386") is None
    os.environ["ANDROID_DATA"] = "/data"
    real_which = shutil.which
    shutil.which = lambda n, *a, **k: None if n == "gh" else real_which(n, *a, **k)      # a gh on this test machine must not matter
    try:
        assert ghfetch.asset("Linux", "aarch64") is None and not ghfetch.possible()
        try:
            reportsend.ensure_gh(lambda q: True)
            raise AssertionError("Android must say it cannot")
        except reportsend.SendError as e:
            assert "Android" in str(e), e
    finally:
        del os.environ["ANDROID_DATA"]
        shutil.which = real_which

    tmp = tempfile.mkdtemp()
    here = os.getcwd()
    try:
        os.chdir(tmp)
        os.makedirs(".OSData")
        name = ghfetch.asset()
        assert name, "this test machine must be a system gh is built for"
        blob = archive(name)
        good_sums = f"{hashlib.sha256(blob).hexdigest()}  {name}\n{'0' * 64}  other_file.zip\n".encode()
        served = {"blob": blob, "sums": good_sums, "asked": []}

        def fake_open(request, timeout=None):
            url = request.full_url
            served["asked"].append(url)
            if url.endswith("checksums.txt"):
                return Reply(served["sums"])
            if url.endswith(name):
                return Reply(served["blob"])
            raise AssertionError("unexpected download: " + url)
        ghfetch._open = fake_open

        # a wrong checksum: refused, and nothing is left behind
        served["sums"] = f"{'1' * 64}  {name}\n".encode()
        try:
            ghfetch.fetch(lambda text: None)
            raise AssertionError("a checksum that does not match must be refused")
        except ghfetch.FetchError as e:
            assert "checksum" in str(e)
        assert ghfetch.fetched() is None
        served["sums"] = b"nothing useful\n"
        try:
            ghfetch.fetch(lambda text: None)
            raise AssertionError("no checksum for the file must be refused")
        except ghfetch.FetchError:
            pass

        # the right checksum: only the program is taken out, inside PythonOS's private data, and runnable
        served["sums"] = good_sums
        path = ghfetch.fetch(lambda text: None)
        assert path == ghfetch.fetched() and os.path.isfile(path) and open(path, "rb").read() == b"GH PROGRAM"
        assert os.path.commonpath([path, os.path.abspath(".OSData")]) == os.path.abspath(".OSData"), "only PythonOS's private folder is written"
        assert not os.path.exists(os.path.join(tmp, "evil.txt")) and not os.path.exists(os.path.join(os.path.dirname(tmp), "evil.txt"))
        if os.name != "nt":
            assert os.access(path, os.X_OK)
        assert [u for u in served["asked"] if "github.com/cli/cli/releases/download/v" in u], "only GitHub's own release is used"

        # gh_path finds it, and ensure_gh then asks nothing
        assert not os.path.exists(os.path.join(os.getcwd(), "gh"))
        assert reportsend.gh_path() == path
        assert reportsend.ensure_gh(lambda q: (_ for _ in ()).throw(AssertionError("must not ask"))) is True

        # not downloaded yet: it asks first, and a "no" downloads nothing
        shutil.rmtree(".OSData/tools")
        shutil.which = lambda n, *a, **k: None if n == "gh" else real_which(n, *a, **k)
        served["asked"].clear()
        questions = []
        try:
            assert reportsend.ensure_gh(lambda q: (questions.append(q), False)[1]) is False
            assert served["asked"] == [] and "anywhere else" in questions[0]
            assert reportsend.ensure_gh(lambda q: True, lambda text: None) is True and ghfetch.fetched()
            # a failed download is one sentence
            shutil.rmtree(".OSData/tools")
            ghfetch._open = lambda request, timeout=None: (_ for _ in ()).throw(OSError("offline"))
            try:
                reportsend.ensure_gh(lambda q: True, lambda text: None)
                raise AssertionError("must fail offline")
            except reportsend.SendError as e:
                assert "could not download" in str(e), e
        finally:
            shutil.which = real_which
    finally:
        os.chdir(here)                                      # a Windows folder cannot be removed while it is the current one
        shutil.rmtree(tmp, ignore_errors=True)
    # a locked-down system never starts gh (it can run aliases and extensions) and never downloads it
    real_lock = reportsend._lockdown
    reportsend._lockdown = lambda: True
    try:
        for call in (lambda: reportsend.ensure_gh(lambda q: True), lambda: reportsend.run_gh(["issue", "list"], "sam"),
                     lambda: reportsend._gh(["auth", "status"], "sam", capture="")):
            try:
                call()
                raise AssertionError("must refuse when locked down")
            except reportsend.SendError as e:
                assert "locked-down" in str(e), e
    finally:
        reportsend._lockdown = real_lock
    print("gh download: all checks passed")


if __name__ == "__main__":
    main()
