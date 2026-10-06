#!/usr/bin/env python3
"""Checks the features built on optional libraries (requirements-extra.txt), both with the library and without it."""
import datetime
import importlib.util
import os
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def command(name):
    spec = importlib.util.spec_from_file_location("cmd_" + name, os.path.join(REPO, "commands", name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def without(name, run):
    """Run run() as if the optional library `name` were not installed."""
    from pyos import optional
    saved = dict(optional._cache)
    for key in list(saved) + [name]:
        if key == name or key.startswith(name + "."):
            optional._cache[key] = None
    try:
        return run()
    finally:
        optional._cache.clear()
        optional._cache.update(saved)


def main():
    os.chdir(tempfile.mkdtemp(prefix="pyos-libs-"))
    sys.path.insert(0, REPO)
    os.environ["PYOS_BUNDLED"] = "1"
    from pyos import filetypes, fuzzy, optional, passwords

    # date -d: the built-in parser (no library needed)
    date = command("date")
    now = datetime.datetime(2026, 10, 7, 12, 0)                                  # a Wednesday
    def check(text, expected):
        got = date.parse(text, now)
        assert got == expected, f"date -d {text!r}: {got} (wanted {expected})"
    check("tomorrow", datetime.datetime(2026, 10, 8)); check("yesterday", datetime.datetime(2026, 10, 6)); check("today", datetime.datetime(2026, 10, 7))
    check("next friday", datetime.datetime(2026, 10, 9)); check("last monday", datetime.datetime(2026, 10, 5)); check("next wednesday", datetime.datetime(2026, 10, 14))
    check("3 days ago", datetime.datetime(2026, 10, 4, 12)); check("+2 weeks", datetime.datetime(2026, 10, 21, 12)); check("in 5 hours", datetime.datetime(2026, 10, 7, 17))
    check("2026-12-25", datetime.datetime(2026, 12, 25)); check("2026-12-25 18:30", datetime.datetime(2026, 12, 25, 18, 30))
    check("1 month ago", datetime.datetime(2026, 9, 7, 12)); check("in 2 months", datetime.datetime(2026, 12, 7, 12))
    assert without("dateutil", lambda: date.parse("1 month ago", now)) == datetime.datetime(2026, 9, 7, 12), "month arithmetic needs no library"
    assert without("dateutil", lambda: date.parse("gibberish words", now)) is None
    jan31 = datetime.datetime(2026, 1, 31, 9, 0)
    assert without("dateutil", lambda: date.parse("+1 month", jan31)) == datetime.datetime(2026, 2, 28, 9, 0), "the 31st plus a month is the end of February"
    if optional.have("dateutil"):
        assert date.parse("March 3rd 2027", now) is not None, "dateutil understands more phrases"

    # password advice: works with and without zxcvbn
    assert passwords.advice("password1", "bob") is not None and passwords.advice("aaaaaaaaaaaa", "bob") is not None
    assert passwords.advice("tiger-Mountain-violet-5921!x", "bob") is None
    assert without("zxcvbn", lambda: passwords.advice("short1", "bob")) is not None
    assert without("zxcvbn", lambda: passwords.advice("a-Much-longer-passphrase-9!", "bob")) is None
    assert passwords.score("")[0] == 0

    # did you mean: with rapidfuzz and with difflib only
    for run in (lambda f: f(), lambda f: without("rapidfuzz", f)):
        found = run(lambda: fuzzy.close_matches("lss", ["ls", "less", "cat", "pwd"], n=2))
        assert "ls" in found and "pwd" not in found, found
        assert run(lambda: fuzzy.close_matches("zzzzzz", ["ls", "cat"])) == []

    # file types: signatures with and without the filetype library
    png = b"\x89PNG\r\n\x1a\n" + b"\0" * 20
    assert "png" in filetypes.describe(png, "a.png").lower()
    assert "PNG" in without("filetype", lambda: filetypes.describe(png, "a.png"))
    assert without("filetype", lambda: filetypes.describe(b"hello world\n", "a.txt")) == "plain text"
    assert filetypes.describe(b"\x00\x01\x02\x03", "x") == "binary data" and filetypes.describe(b"", "x") == "empty"
    assert filetypes.is_text("héllo".encode("utf-8")) and not filetypes.is_text(b"ab\0cd")

    # web: page text and links, with beautifulsoup4 and with the standard library reader
    web = command("web")
    page = "<html><head><title>T</title><style>p{}</style></head><body><nav>menu</nav><h1>Head</h1><p>Hello <a href='/x'>link</a></p><script>bad()</script></body></html>"
    for run in (lambda f: f(), lambda f: without("bs4", f)):
        title, text, links = run(lambda: web.extract(page))
        assert title == "T" and "Hello" in text and "bad()" not in text and "p{}" not in text, (title, text)
        assert links == [("link", "/x")], links
    assert web.absolute("https://a.org/dir/", "../x") == "https://a.org/x"

    # convert: JSON <-> YAML
    convert = command("convert")
    assert convert.dump({"a": [1, 2]}, "json").strip().startswith("{")
    if optional.have("yaml"):
        text = convert.dump({"a": [1, 2], "b": {"c": "d"}}, "yaml")
        assert "a:" in text and "- 1" in text
        import yaml
        assert yaml.safe_load(text) == {"a": [1, 2], "b": {"c": "d"}}
    try:
        without("yaml", lambda: convert.dump({"a": 1}, "yaml"))
        raise AssertionError("writing YAML without PyYAML must say so")
    except RuntimeError as e:
        assert "PyYAML" in str(e)
    print("optional libraries: all checks passed")


if __name__ == "__main__":
    sys.exit(main() or 0)
