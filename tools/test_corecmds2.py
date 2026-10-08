#!/usr/bin/env python3
"""The core commands added in 1.0.13: base64, md5sum, sha1sum, sha256sum, sha512sum, cmp, comm, paste, fold, column, shuf, sed, calc, uuidgen, gzip, gunzip,
zcat and strings. Each is run the way the shell runs it (execute(args)) on files in a scratch folder, with the screen and the pipe replaced."""
import base64
import gzip
import hashlib
import importlib.util
import io
import os
import random
import sys
import tempfile
import uuid

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO)


def command(name):
    spec = importlib.util.spec_from_file_location("cmd2_" + name, os.path.join(REPO, "commands", name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    os.chdir(tempfile.mkdtemp(prefix="pyos-core2-"))
    os.environ["PYOS_BUNDLED"] = "1"
    from rich.console import Console

    from pyos import calc, checksum, gzipfile, sedlite, stdio, textcmd, textfile
    import pyos.fs as fs
    fs.resolve = lambda path, write=False: os.path.abspath(path)             # the sandbox is not what is tested here
    out = io.StringIO()
    piped = {"text": None}
    stdio.read_stdin = lambda: piped["text"]

    def screen(*modules):
        for m in modules:
            m.console = Console(file=out, force_terminal=False, width=400)

    def run(name, args, stdin=None):
        module = command(name)
        screen(textcmd, module, checksum, gzipfile)
        out.seek(0)
        out.truncate(0)
        piped["text"] = stdin
        result = module.execute(args)
        piped["text"] = None
        return result, out.getvalue()

    def write(name, data):
        with open(name, "wb" if isinstance(data, bytes) else "w", **({} if isinstance(data, bytes) else {"encoding": "utf-8", "newline": "\n"})) as f:
            f.write(data)

    # ---- base64
    ok, text = run("base64", [], "hello world\n")
    assert ok and text.strip() == "aGVsbG8gd29ybGQK"
    write("plain.txt", "x" * 100)
    ok, text = run("base64", ["plain.txt"])
    assert len(text.splitlines()[0]) == 76 and len(text.splitlines()) == 2, "wrapped at 76"
    ok, text = run("base64", ["-w", "0", "plain.txt"])
    assert len(text.splitlines()) == 1
    ok, text = run("base64", ["-d"], "aGVsbG8gd29ybGQK\n")
    assert ok and text.strip() == "hello world"
    ok, text = run("base64", ["-d"], "aGVsbG8gd29ybGQ")                                     # missing padding is accepted
    assert ok and text.strip() == "hello world"
    assert run("base64", ["-d"], "not base64 !!!")[0] is False and run("base64", ["-w", "x", "plain.txt"])[0] is False and run("base64", [])[0] is False
    write("binary.b64", base64.b64encode(bytes([0xff, 0xfe, 0x00])).decode())
    ok, text = run("base64", ["-d", "binary.b64"])
    assert ok is False and "not text" in text

    # ---- checksums
    write("a.txt", "abc")
    write("b.txt", "abd")
    for name, algorithm in (("md5sum", "md5"), ("sha1sum", "sha1"), ("sha256sum", "sha256"), ("sha512sum", "sha512")):
        ok, text = run(name, ["a.txt"])
        assert ok and text.strip() == f"{hashlib.new(algorithm, b'abc').hexdigest()}  a.txt", name
    ok, text = run("sha256sum", [], "abc")
    assert text.strip().endswith("  -") and text.startswith("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
    ok, text = run("sha256sum", ["a.txt", "nosuch.txt"])
    assert ok is False and "nosuch.txt" in text and "a.txt" in text, "a missing file does not stop the others"
    write("sums.txt", f"{hashlib.sha256(b'abc').hexdigest()}  a.txt\n{hashlib.sha256(b'abc').hexdigest()}  b.txt\n")
    ok, text = run("sha256sum", ["-c", "sums.txt"])
    assert ok is False and "a.txt: OK" in text and "b.txt: FAILED" in text and "1 of 2" in text
    write("good.txt", f"{hashlib.md5(b'abc').hexdigest()} *a.txt\n\n")
    ok, text = run("md5sum", ["-c", "good.txt"])
    assert ok and "a.txt: OK" in text
    write("junk.txt", "not a checksum line\n")
    assert run("md5sum", ["-c", "junk.txt"])[0] is False and run("md5sum", [])[0] is False
    assert checksum.parse_line("ABCDEF12  file name.txt") == ("abcdef12", "file name.txt") and checksum.parse_line("zz  x") is None

    # ---- cmp
    write("c1.bin", b"hello\nworld\n")
    write("c2.bin", b"hello\nwerld\n")
    write("c3.bin", b"hello\n")
    assert run("cmp", ["c1.bin", "c1.bin"]) == (True, "")
    ok, text = run("cmp", ["c1.bin", "c2.bin"])
    assert ok is False and "differ: byte 8, line 2" in text, text
    ok, text = run("cmp", ["c3.bin", "c1.bin"])
    assert ok is False and "EOF on c3.bin after byte 6" in text, text
    ok, text = run("cmp", ["c1.bin", "c3.bin"])
    assert "EOF on c3.bin after byte 6" in text and run("cmp", ["c1.bin"])[0] is False and run("cmp", ["c1.bin", "missing"])[0] is False

    # ---- comm
    write("left.txt", "apple\nbanana\ncherry\n")
    write("right.txt", "banana\ncherry\ndate\n")
    ok, text = run("comm", ["left.txt", "right.txt"])
    assert text.splitlines() == [l.expandtabs(8) for l in ["apple", "\t\tbanana", "\t\tcherry", "\tdate"]], text            # (Rich shows tabs as spaces)
    assert run("comm", ["-12", "left.txt", "right.txt"])[1].splitlines() == ["banana", "cherry"]
    assert run("comm", ["-3", "left.txt", "right.txt"])[1].splitlines() == ["apple", "\tdate".expandtabs(8)]
    assert run("comm", ["left.txt"])[0] is False

    # ---- paste
    write("n.txt", "ann\nbob\n")
    write("p.txt", "111\n222\n333\n")
    assert run("paste", ["n.txt", "p.txt"])[1].splitlines() == [l.expandtabs(8) for l in ["ann\t111", "bob\t222", "\t333"]]
    assert run("paste", ["-d", ",", "n.txt", "p.txt"])[1].splitlines()[0] == "ann,111"
    assert run("paste", ["-s", "-d", ",", "p.txt"])[1].strip() == "111,222,333" and run("paste", [])[0] is False

    # ---- fold
    write("long.txt", "abcdefghij" * 3 + "\nshort\n")
    assert run("fold", ["-w", "10", "long.txt"])[1].splitlines() == ["abcdefghij"] * 3 + ["short"]
    write("words.txt", "the quick brown fox jumps over the lazy dog\n")
    folded = run("fold", ["-s", "-w", "16", "words.txt"])[1].splitlines()
    assert all(len(l) <= 16 for l in folded) and " ".join(l.strip() for l in folded) == "the quick brown fox jumps over the lazy dog", folded
    assert run("fold", ["-w", "0", "words.txt"])[0] is False

    # ---- column
    write("table.txt", "name qty\napple 3\nwatermelon 12\n")
    assert run("column", ["-t", "table.txt"])[1].splitlines() == ["name        qty", "apple       3", "watermelon  12"]
    write("table.csv", "a,bb\nccc,d\n")
    assert run("column", ["-t", "-s", ",", "-o", " | ", "table.csv"])[1].splitlines() == ["a   | bb", "ccc | d"]
    write("items.txt", "\n".join(f"item{i}" for i in range(10)) + "\n")
    arranged = run("column", ["items.txt"])[1].splitlines()
    assert arranged and "item0" in arranged[0] and sum(l.count("item") for l in arranged) == 10

    # ---- shuf
    write("lines.txt", "\n".join(str(i) for i in range(20)) + "\n")
    shuffled = run("shuf", ["lines.txt"])[1].splitlines()
    assert sorted(shuffled, key=int) == [str(i) for i in range(20)] and shuffled != [str(i) for i in range(20)]
    assert len(run("shuf", ["-n", "3", "lines.txt"])[1].splitlines()) == 3 and run("shuf", ["-n", "0", "lines.txt"])[1] == ""
    assert sorted(run("shuf", ["-i", "1-5"])[1].split()) == ["1", "2", "3", "4", "5"]
    assert sorted(run("shuf", ["-e", "x", "y", "z"])[1].split()) == ["x", "y", "z"]
    assert run("shuf", ["-i", "5-1"])[0] is False and run("shuf", ["-n", "-1", "lines.txt"])[0] is False

    # ---- sed (the language, then the command)
    lines = ["one cat", "two cats", "# comment", "three Cat", "four"]

    def apply(script, quiet=False, data=lines):
        return sedlite.run(sedlite.parse(script), list(data), quiet)
    assert apply("s/cat/dog/") == ["one dog", "two dogs", "# comment", "three Cat", "four"]
    assert apply("s/cat/dog/gi")[3] == "three dog" and apply("s/a/A/g")[1] == "two cAts"
    assert apply("s/\\(o\\)/[\\1]/", data=["foo"]) == ["foo"] and apply("s/(o)/[\\1]/", data=["foo"]) == ["f[o]o"], "Python regular expressions"
    assert apply("s/c.t/<&>/", data=["a cat"]) == ["a <cat>"] and apply("s|/|-|g", data=["a/b/c"]) == ["a-b-c"] and apply("s/a\\/b/X/", data=["a/b"]) == ["X"]
    assert apply("2d") == ["one cat", "# comment", "three Cat", "four"] and apply("$d")[-1] == "three Cat" and apply("/^#/d") == ["one cat", "two cats", "three Cat", "four"]
    assert apply("2,3d") == ["one cat", "three Cat", "four"] and apply("2,+1d") == ["one cat", "three Cat", "four"] and apply("/two/,/three/d") == ["one cat", "four"]
    assert apply("2!d") == ["two cats"] and apply("2,4!d") == ["two cats", "# comment", "three Cat"]
    assert apply("2,3p", quiet=True) == ["two cats", "# comment"] and apply("2p")[1:3] == ["two cats", "two cats"]
    assert apply("2q") == ["one cat", "two cats"] and apply("2q", quiet=True) == [] and apply("s/o/0/;s/e/3/", data=["one"]) == ["0n3"]
    assert apply("1,3d;s/f/F/") == ["three Cat", "Four"] and apply("/cat/s/^/> /")[:2] == ["> one cat", "> two cats"]
    for bad in ("", "s/a/b", "s/(/x/", "5", "x", "3,", "s/a/b/z", "/abc", "2,+x"):
        try:
            if bad:
                sedlite.parse(bad)
                raise AssertionError(f"{bad!r} must be refused")
            assert sedlite.parse(bad) == []
        except sedlite.SedError:
            pass
    ok, text = run("sed", ["s/cat/dog/g"], "a cat\nb cat\n")
    assert ok and text.splitlines() == ["a dog", "b dog"]
    write("sedfile.txt", "alpha\nbeta\ngamma\n")
    assert run("sed", ["-n", "2p", "sedfile.txt"])[1].splitlines() == ["beta"] and run("sed", ["-e", "1d", "-e", "s/a/A/g", "sedfile.txt"])[1].splitlines() == ["betA", "gAmmA"]
    assert run("sed", ["-i", "s/a/b/", "sedfile.txt"])[0] is False and run("sed", [])[0] is False and run("sed", ["s/a"], "x")[0] is False

    # ---- calc
    for expression, expected in (("2 + 3 * 4", "14"), ("2^10", "1024"), ("(1+2)*(3+4)", "21"), ("10/4", "2.5"), ("7//2", "3"), ("7%3", "1"), ("-3**2", "-9"),
                                 ("sqrt(144)", "12"), ("max(1, 5, 3)", "5"), ("0.1+0.2", "0.3"), ("fact(10)", "3628800"), ("pi", "3.14159265359"), ("abs(-4)", "4")):
        assert run("calc", [expression])[1].strip() == expected, expression
    assert run("calc", [], "1+1\n2*5\n")[1].split() == ["2", "10"]
    for bad in ("1/0", "9**9**9", "__import__('os')", "open('x')", "x + 1", "2 +", "lambda: 1", "[1,2]", "'a'*5", "True + 1", "(1).real", "sqrt(-1)", "1" * 600):
        ok, text = run("calc", [bad])
        assert ok is False and "calc:" in text, bad
    assert calc.show(10**20) == str(10**20) and calc.show(2.0) == "2" and calc.show(float("inf")) == "inf"

    # ---- uuidgen
    ok, text = run("uuidgen", [])
    assert ok and uuid.UUID(text.strip()).version == 4
    assert len(run("uuidgen", ["-n", "5"])[1].split()) == 5 and len(set(run("uuidgen", ["-n", "20"])[1].split())) == 20
    assert uuid.UUID(run("uuidgen", ["-t"])[1].strip()).version == 1 and run("uuidgen", ["--upper"])[1].strip().isupper()
    assert run("uuidgen", ["-n", "0"])[0] is False and run("uuidgen", ["-n", "x"])[0] is False

    # ---- gzip, gunzip, zcat
    payload = ("line of log text\n" * 200)
    write("big.log", payload)
    ok, text = run("gzip", ["-k", "big.log"])
    assert ok and os.path.exists("big.log") and os.path.exists("big.log.gz") and os.path.getsize("big.log.gz") < len(payload) / 5 and "big.log.gz" in text
    assert gzip.open("big.log.gz", "rt").read() == payload
    assert run("gzip", ["big.log"])[0] is False, "big.log.gz already exists"
    os.remove("big.log.gz")
    ok, text = run("gzip", ["big.log"])
    assert ok and not os.path.exists("big.log") and os.path.exists("big.log.gz")
    ok, text = run("zcat", ["big.log.gz"])
    assert ok and text.count("line of log text") == 200
    ok, text = run("gunzip", ["-k", "big.log.gz"])
    assert ok and open("big.log", encoding="utf-8").read() == payload and os.path.exists("big.log.gz")
    assert run("gunzip", ["big.log.gz"])[0] is False, "big.log already exists"
    os.remove("big.log")
    ok, _ = run("gunzip", ["big.log.gz"])
    assert ok and open("big.log", encoding="utf-8").read() == payload and not os.path.exists("big.log.gz")
    write("fake.gz", "this is not gzip")
    assert run("gunzip", ["fake.gz"])[0] is False and run("zcat", ["fake.gz"])[0] is False and run("gzip", ["nosuch"])[0] is False
    assert run("gzip", ["-d", "big.log"])[0] is False and run("gzip", [])[0] is False and run("zcat", [])[0] is False
    write("already.gz", b"")
    assert run("gzip", ["already.gz"])[0] is False
    real_limit = gzipfile.archive.MAX_TOTAL
    gzipfile.archive.MAX_TOTAL = 100
    try:
        with gzip.open("bomb.gz", "wb") as f:
            f.write(b"0" * 5000)
        ok, text = run("gunzip", ["bomb.gz"])
        assert ok is False and "too large" in text and not os.path.exists("bomb"), "a gzip bomb is stopped"
    finally:
        gzipfile.archive.MAX_TOTAL = real_limit

    # ---- strings
    write("prog.bin", b"\x00\x01Hello, world\x00\xff\xfeab\x00Another string here\x7f\x00xyz")
    assert run("strings", ["prog.bin"])[1].splitlines() == ["Hello, world", "Another string here"]
    assert "ab" in run("strings", ["-n", "2", "prog.bin"])[1].splitlines() and run("strings", ["-n", "0", "prog.bin"])[0] is False
    assert run("strings", [])[0] is False and run("strings", ["missing.bin"])[0] is False

    # a Windows-1252 text file goes through the text commands correctly (see test_newlibs for the others)
    assert textfile.decode("café".encode("cp1252"))[0] == "café"
    random.seed()
    print("core commands (1.0.13): all checks passed")


if __name__ == "__main__":
    main()
