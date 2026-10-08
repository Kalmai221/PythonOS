#!/usr/bin/env python3
"""The Developer Console: its working parts (pyos/devtools.py) and the tools as the person uses them (programs/developer.py), started straight from
the shell with arguments, so no keyboard is needed. Files are made in a scratch folder."""
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time
import zipfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO)
os.chdir(REPO)
os.environ["PYOS_BUNDLED"] = "1"

from pyos import devtools  # noqa: E402


def raises(call, *errors):
    try:
        call()
    except errors:
        return True
    return False


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main():
    # ---- JSON
    text = '{"users": [{"name": "ada", "id": 1}, {"name": "bob", "id": 2}], "count": 2,\n "bad": }'
    try:
        json.loads(text)
        raise AssertionError("must not parse")
    except json.JSONDecodeError as e:
        message, line, column = devtools.json_error(text, e)
        assert message.startswith("line 2, column ") and line.strip().startswith('"bad"') and column >= 0
    data = json.loads('{"users": [{"name": "ada", "id": 1}, {"name": "bob", "id": 2}], "count": 2, "a b": {"x": [1, [2, 3]]}}')
    assert devtools.json_query(data, ".count") == [2] and devtools.json_query(data, ".users[0].name") == ["ada"] and devtools.json_query(data, ".users[*].id") == [1, 2]
    assert devtools.json_query(data, "users[1].name") == ["bob"] and devtools.json_query(data, ".") == [data] and devtools.json_query(data, '["a b"].x[1][0]') == [2]
    assert devtools.json_query(data, ".users[*].name") == ["ada", "bob"]
    assert raises(lambda: devtools.json_query(data, ".users.name"), ValueError), "a list needs [*] to look inside each item"
    for bad in (".nothing", ".users[9]", ".count[0]", ".users[x]", ".count.deeper"):
        assert raises(lambda b=bad: devtools.json_query(data, b), ValueError), bad
    stats = devtools.json_stats(data)
    assert stats["type"] == "dict" and stats["depth"] >= 4 and stats["items"] > 8 and "users" in stats["keys"]

    # ---- regular expressions
    found = devtools.regex_try(r"(\d+)-(?P<word>[a-z]+)", "12-ab and 7-xyz", "i")
    assert len(found["matches"]) == 2 and found["matches"][0]["groups"] == ["12", "ab"] and found["matches"][1]["named"] == {"word": "xyz"} and found["names"] == ["word"]
    assert devtools.regex_try(r"\d+", "a1b22", "", "#")["replaced"] == "a#b#" and devtools.regex_try("A", "a", "i")["matches"]
    assert not devtools.regex_try("A", "a", "")["matches"] and devtools.regex_try("a.b", "a\nb", "s")["matches"]
    assert raises(lambda: devtools.regex_try("(", "x"), ValueError) and raises(lambda: devtools.regex_try("a", "a", "q"), ValueError)
    assert raises(lambda: devtools.regex_try("a", "a", "", r"\1"), ValueError), "a replacement that names a group the pattern lacks"

    # ---- hashes and encodings
    digests = devtools.hash_all(b"abc")
    assert digests["sha256"] == hashlib.sha256(b"abc").hexdigest() and digests["crc32"] == "352441c2" and digests["md5"] == "900150983cd24fb0d6963f7d28e17f72"
    assert devtools.which_hash(digests["sha256"]) == ["sha256", "sha3_256"] and devtools.which_hash("zz") == [] and "md5" in devtools.which_hash(digests["md5"])
    for mode in devtools.ENCODINGS:
        for sample in ("hello world", "café 日本 ☃", "", "a&b <c> %20 \\n"):
            assert devtools.decode(mode, devtools.encode(mode, sample)) == sample, (mode, sample)
    assert devtools.encode("base64", "hi") == "aGk=" and devtools.encode("hex", "hi") == "6869" and devtools.encode("url", "a b&c") == "a%20b%26c"
    assert devtools.encode("html", "<a & b>") == "&lt;a &amp; b&gt;" and devtools.encode("rot13", "Hello") == "Uryyb"
    for mode, bad in (("base64", "!!!"), ("hex", "xyz"), ("gzip-base64", "aGk="), ("base32", "1!1")):
        assert raises(lambda m=mode, b=bad: devtools.decode(m, b), ValueError), mode
    assert raises(lambda: devtools.encode("nope", "x"), ValueError) and raises(lambda: devtools.decode("nope", "x"), ValueError)
    assert "base64" in devtools.guess_encoding("aGVsbG8gd29ybGQ=") and "url" in devtools.guess_encoding("a%20b") and "html" in devtools.guess_encoding("a &amp; b")
    assert "hex" in devtools.guess_encoding("68656c6c6f") and devtools.guess_encoding("plain words here") == []

    # ---- packages
    tmp = tempfile.mkdtemp(prefix="pyos-devtools-")
    try:
        for template in devtools.TEMPLATES:
            folder = os.path.join(tmp, "app_" + template)
            files = devtools.create_package(folder, "my-" + template, template)
            assert files == ["README.md", "data.json", "run.py", "test_run.py"], files
            findings, entry = devtools.check_package(folder)
            assert not [t for lvl, t in findings if lvl == "error"], (template, findings)
            assert entry["command"] == "my-" + template and entry["permissions"] == sorted(devtools.TEMPLATES[template][1])
            compile(open(os.path.join(folder, "run.py"), encoding="utf-8").read(), "run.py", "exec")
            namespace = {"__name__": "not_main"}
            exec(compile(open(os.path.join(folder, "run.py"), encoding="utf-8").read(), "run.py", "exec"), namespace)
            assert callable(namespace["main"]), template
        assert raises(lambda: devtools.create_package(os.path.join(tmp, "x"), "Bad Name"), ValueError) and raises(lambda: devtools.create_package(os.path.join(tmp, "x"), "ok", "nope"), ValueError)
        assert raises(lambda: devtools.create_package(os.path.join(tmp, "app_basic"), "my-basic"), FileExistsError)
        assert devtools.valid_name("ok-name_1") and not devtools.valid_name("a") and not devtools.valid_name("1abc") and not devtools.valid_name("Upper")

        def check(meta, code, extra=None):
            folder = os.path.join(tmp, "c%d" % check.n)
            check.n += 1
            write(os.path.join(folder, "data.json"), json.dumps(meta))
            for name, body in {"run.py": code, **(extra or {})}.items():
                write(os.path.join(folder, name), body)
            return devtools.check_package(folder)
        check.n = 0
        base = {"name": "T", "description": "A test package", "version": "1.0.0", "command": "tt", "scripts": {"run": "run.py"}, "permissions": [], "tags": ["t"], "changelog": "x"}

        def texts(findings, level=None):
            return " | ".join(t for lvl, t in findings if level is None or lvl == level)
        findings, entry = check(base, "print('hi')\n")
        assert not [1 for lvl, _t in findings if lvl in ("error", "warn")], findings
        findings, _e = check({k: v for k, v in base.items() if k not in ("description", "command")}, "print(1)\n")
        assert "no 'description'" in texts(findings, "error") and "no 'command'" in texts(findings, "error")
        findings, _e = check({k: v for k, v in base.items() if k != "permissions"}, "print(1)\n")
        assert "no 'permissions' list" in texts(findings, "warn")
        findings, _e = check(dict(base, permissions=["teleport"]), "print(1)\n")
        assert "teleport" in texts(findings, "error")
        findings, _e = check(base, "import requests\nrequests.get('x')\n")
        assert "the internet" in texts(findings, "warn") and "'network' permission" in texts(findings, "warn")
        findings, _e = check(dict(base, permissions=["network"]), "x = 1\n")
        assert "does not seem to use it" in texts(findings, "note")
        findings, _e = check(dict(base, lockdown_safe=True), "import subprocess\nsubprocess.run(['ls'])\neval('1')\n")
        assert texts(findings, "error").count("lockdown_safe") >= 2, findings
        findings, _e = check(dict(base, lockdown_safe=True), "import os\nos.system('ls')\n")
        assert "os.system()" in texts(findings, "error")
        findings, _e = check(base, "import numpy_zzz\n")
        assert "numpy_zzz" in texts(findings, "error") and "pip" in texts(findings, "error")
        findings, _e = check(dict(base, api=2, pip=["numpy_zzz"]), "import numpy_zzz\n")
        assert "numpy_zzz" not in texts(findings), "declared under pip"
        findings, _e = check(base, "try:\n    import numpy_zzz\nexcept ImportError:\n    numpy_zzz = None\n")
        assert "optional here" in texts(findings, "warn") and not texts(findings, "error")
        findings, _e = check(base, "import helpers\n", {"helpers.py": "x = 1\n"})
        assert "helpers" not in texts(findings), "the app's own file"
        findings, _e = check(base, "def broken(:\n")
        assert "syntax error on line 1" in texts(findings, "error")
        findings, _e = check(base, "api_key = 'abcdefgh12345678'\n")
        assert "password or key" in texts(findings, "warn")
        findings, _e = check(dict(base, scripts={"run": "nothere.py"}), "")
        assert "nothere.py" in texts(findings, "error")
        findings, _e = check(dict(base, version="one"), "print(1)\n")
        assert "version" in texts(findings, "warn")
        assert devtools.check_package(os.path.join(tmp, "nowhere"))[1] is None and "data.json" in texts(devtools.check_package(os.path.join(tmp, "nowhere"))[0], "error")

        # packing: caches and libraries stay out, the checksum is the zip's
        pack_src = os.path.join(tmp, "app_basic")
        write(os.path.join(pack_src, "__pycache__", "x.pyc"), "junk")
        write(os.path.join(pack_src, ".libs", "lib.py"), "junk")
        write(os.path.join(pack_src, "sub", "more.txt"), "kept")
        destination = os.path.join(tmp, "out.zip")
        count, size, digest = devtools.pack_package(pack_src, destination)
        with zipfile.ZipFile(destination) as z:
            names = sorted(z.namelist())
        assert names == ["README.md", "data.json", "run.py", "sub/more.txt", "test_run.py"] and count == 5, names
        assert size == os.path.getsize(destination) and digest == hashlib.sha256(open(destination, "rb").read()).hexdigest()
        count_again = devtools.pack_package(pack_src, os.path.join(pack_src, "inside.zip"))[0]
        assert count_again == 5, "the zip being written is not packed into itself"

        # ---- measuring and odd input and the map of PythonOS
        outcome = devtools.measure(lambda: sum(i * i for i in range(200_000)))
        assert outcome["seconds"] > 0 and outcome["peak_kb"] >= 0 and outcome["error"] is None and outcome["result"] == sum(i * i for i in range(200_000)) and "ncalls" in outcome["top"]
        failing = devtools.measure(lambda: 1 / 0)
        assert failing["error"] and "ZeroDivisionError" in failing["error"]
        assert tracemalloc_stopped()
        cases = devtools.fuzz_cases(["sort", "curl", "rev", "rm"])
        assert {c for c, _a, _t in cases} == {"sort", "rev"} and len(cases) > 20 and any(a == ["--bogus"] for _c, a, _t in cases) and any(t and len(t) > 50_000 for _c, _a, t in cases)
        assert len(devtools.fuzz_cases(["sort"], per_command=3)) == 3
        modules = dict(devtools.api_modules())
        assert "corecmd" in modules and "pull" not in modules and modules["corecmd"]
        members = {name: (kind, signature) for kind, name, signature, _doc in devtools.api_members("corecmd")}
        assert members["run"] == ("def", "(name, args, stdin)") and members["Result"][0] == "class" and members["ALLOWED"][0] == "value"
        assert raises(lambda: devtools.api_members("nosuchmodule_zzz"), ValueError)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- the console: the tools started with arguments
    from rich.console import Console
    from programs import developer
    import pyos
    import pyos.fs as fs
    out = io.StringIO()
    developer.console = Console(file=out, force_terminal=False, width=140)
    scratch = tempfile.mkdtemp(prefix="pyos-dev-ui-")
    real_resolve, real_userinfo = fs.resolve, pyos.userinfo
    fs.resolve = lambda path, write=False: os.path.abspath(os.path.join(scratch, path.replace("~/", "").lstrip("~"))) if not os.path.isabs(path) or path.startswith("~") else path
    pyos.userinfo = lambda: ("tester", "admin")

    def shown(*args):
        out.seek(0)
        out.truncate(0)
        developer.execute(list(args))
        return out.getvalue()
    try:
        assert "help" in developer.MENU and all(name in developer.MENU for name in developer.TOOLS)
        assert set(developer.TOOLS) == {name for name, _g, _s, _u in developer.REGISTRY}, "every tool is in the registry and the menu"
        assert all(group in developer.GROUPS for _n, group, _s, _u in developer.REGISTRY if group != "Other")
        text = shown("json", '{"a": {"b": [10, 20]}}', ".a.b[1]")
        assert "20" in text and "Valid JSON" in text
        text = shown("json", '{"a": }')
        assert "Invalid: line 1" in text and "^" in text
        assert "no 'not-there'" in shown("json", '{"a": 1}', ".not-there")
        text = shown("hash", "abc", "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        assert "Match" in text and "sha256" in text
        assert "No match" in shown("hash", "abc", "0" * 64) and "sha256 or sha3_256" in out.getvalue()
        assert "aGk=" in shown("encode", "base64", "hi") and "hi" in shown("encode", "base64", "aGk=", "-d")
        assert "not valid base64" in shown("encode", "base64", "!!!", "-d")
        text = shown("time", "1790000000")
        assert "2026-09-21" in text and "Unix seconds" in text and "1790000000" in text
        assert "ISO 8601" in shown("time", "2026-10-08T12:00:00Z") and "cannot read" in shown("time", "not a time")
        text = shown("api", "corecmd")
        assert "def" in text and "run" in text and "ALLOWED" in text
        assert "corecmd" in shown("api", "") and "there is no module" in shown("api", "nosuch_zzz")
        text = shown("scaffold", "demo-app", "network")
        assert "Created" in text and os.path.isfile(os.path.join(scratch, "demo-app", "data.json"))
        assert "already exists" in shown("scaffold", "demo-app", "basic")
        text = shown("check", "demo-app")
        assert "Package looks good" in text or "Fine to publish" in text
        assert "Catalog entry" in out.getvalue() and '"command": "demo-app"' in out.getvalue()
        text = shown("deps", "demo-app")
        assert "requests" in text and "PythonOS" in text and "curl, wget" in text
        text = shown("pack", "demo-app")
        assert "Packed 4 file(s)" in text and os.path.isfile(os.path.join(scratch, "demo-app-0.1.0.zip"))
        assert "Unknown tool" in shown("jsno") and "json" in out.getvalue(), "did you mean"
        text = shown("help", "json")
        assert "check, pretty-print" in text and "json [text or @file]" in text
        assert "Package folder" not in shown("check", "nowhere-zzz") and "not a folder" in out.getvalue()
        pyos.userinfo = lambda: ("guest", "user")
        assert "for administrators" in shown("json", "{}")
        pyos.userinfo = lambda: ("tester", "admin")
        started = time.time()
        text = shown("fuzz", "--quick")
        assert "odd cases" in text or "raised an error" in text, text
        assert time.time() - started < 120
    finally:
        fs.resolve, pyos.userinfo = real_resolve, real_userinfo
        shutil.rmtree(scratch, ignore_errors=True)
    print("developer console: all checks passed")


def tracemalloc_stopped():
    import tracemalloc
    return not tracemalloc.is_tracing()


if __name__ == "__main__":
    main()
