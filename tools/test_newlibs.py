#!/usr/bin/env python3
"""The optional libraries added in 1.0.13, each with and without the library: charset-normalizer (text files in other encodings), py7zr (.7z in zip and
unzip), distro and py-cpuinfo (sysinfo, lscpu), watchfiles (watch -f) and dnspython (nslookup record types). Libraries that are not installed here are
replaced by small stand-ins that behave the way the real ones are documented to; nothing is downloaded and no network is used."""
import importlib.util
import io
import os
import sys
import tempfile
import types

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO)


def command(name):
    spec = importlib.util.spec_from_file_location("cmd_" + name, os.path.join(REPO, "commands", name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def capture(module, run):
    from rich.console import Console
    out = io.StringIO()
    module.console = Console(file=out, force_terminal=False, width=140)
    return run(), out.getvalue()


def with_library(name, stand_in, run):
    """Run with `name` replaced by a stand-in (None: as if it were not installed)."""
    from pyos import optional
    saved = dict(optional._cache)
    optional._cache[name] = stand_in
    try:
        return run()
    finally:
        optional._cache.clear()
        optional._cache.update(saved)


def main():
    os.chdir(tempfile.mkdtemp(prefix="pyos-newlibs-"))
    os.environ["PYOS_BUNDLED"] = "1"
    from pyos import archive, filewatch, fs, lockdown, optional, osinfo, textfile
    fs.resolve = lambda path, write=False: os.path.abspath(path)          # the sandbox is not what is tested here

    # ---- text files in other encodings
    samples = {"utf-8": "héllo wörld, ça va?", "cp1252": "café – “quoted” € 5", "utf-16": "line one\r\nline two", "utf-8-sig": "with a mark"}
    for encoding, text in samples.items():
        data = text.encode(encoding)
        got, name = textfile.decode(data)
        assert got == text.replace("\r\n", "\n"), (encoding, got)
    assert textfile.decode("Привет мир, как дела?".encode("cp1251"))[0] == "Привет мир, как дела?" or not optional.have("charset_normalizer")
    assert textfile.decode(b"")[0] == "" and textfile.decode(bytes(range(128, 256)))[0], "any bytes decode"
    assert textfile.decode(b"a\rb\r\nc")[0] == "a\nb\nc", "plain newlines"
    # without the library: UTF-8, then Windows-1252, then Latin-1
    for data, expected in (("café".encode("cp1252"), "café"), (bytes([0x81, 0x8d, 0xe9]), "\x81\x8d\xe9")):
        assert with_library("charset_normalizer", None, lambda d=data: textfile.decode(d))[0] == expected
    # a detector that fails or answers with a wide guess is not trusted
    boom = types.SimpleNamespace(from_bytes=lambda data: (_ for _ in ()).throw(RuntimeError("detector broke")))
    assert with_library("charset_normalizer", boom, lambda: textfile.decode("naïve café".encode("cp1252") * 3))[0].startswith("naïve café")
    wide = types.SimpleNamespace(from_bytes=lambda data: types.SimpleNamespace(best=lambda: types.SimpleNamespace(encoding="utf_16_be")))
    assert with_library("charset_normalizer", wide, lambda: textfile.decode("café au lait".encode("cp1252")))[0] == "café au lait"
    assert textfile.is_plain("UTF-8") and textfile.is_plain("ascii") and not textfile.is_plain("cp1252")
    with open("latin.txt", "wb") as f:
        f.write("Größe: 5 – schön\nzweite Zeile\n".encode("cp1252"))
    cat, head, tail, wc, diff = (command(n) for n in ("cat", "head", "tail", "wc", "diff"))
    ok, shown = capture(cat, lambda: cat.execute(["--plain", "latin.txt"]))
    assert ok and "Größe: 5 – schön" in shown and "�" not in shown, shown
    ok, shown = capture(head, lambda: head.execute(["-n", "1", "latin.txt"]))
    assert "Größe" in shown
    ok, shown = capture(tail, lambda: tail.execute(["-n", "1", "latin.txt"]))
    assert "zweite Zeile" in shown
    ok, shown = capture(wc, lambda: wc.execute(["latin.txt"]))
    assert shown.split()[0] == "2"
    with open("latin2.txt", "wb") as f:
        f.write("Größe: 6 – schön\nzweite Zeile\n".encode("cp1252"))
    ok, shown = capture(diff, lambda: diff.execute(["latin.txt", "latin2.txt"]))
    assert "Größe" in shown and "�" not in shown, shown

    # ---- 7z (a stand-in for py7zr that keeps its archives in memory)
    store = {}

    class Info:
        def __init__(self, filename, size, directory=False, symlink=False):
            self.filename, self.uncompressed, self.is_directory, self.is_symlink = filename, size, directory, symlink

    class SevenZipFile:
        def __init__(self, path, mode):
            self.path, self.mode = path, mode
            if mode == "w":
                store[path] = []
            elif path not in store:
                raise OSError("not there")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def write(self, path, arcname):
            store[self.path].append(Info(arcname, os.path.getsize(path), os.path.isdir(path)))
            with open(self.path, "wb") as f:
                f.write(b"7z")

        def list(self):
            return list(store[self.path])

        def reset(self):
            pass

        def extractall(self, path):
            for info in store[self.path]:
                target = os.path.join(path, info.filename)
                if info.is_directory:
                    os.makedirs(target, exist_ok=True)
                else:
                    os.makedirs(os.path.dirname(target), exist_ok=True)
                    with open(target, "wb") as f:
                        f.write(b"x" * info.uncompressed)
    fake7z = types.SimpleNamespace(SevenZipFile=SevenZipFile)
    os.makedirs("docs")
    with open("docs/a.txt", "w") as f:
        f.write("hello")
    zipc, unzipc = command("zip"), command("unzip")
    assert archive.is_7z("X.7Z") and not archive.is_7z("x.zip")
    ok, text = capture(zipc, lambda: with_library("py7zr", None, lambda: zipc.execute(["pack.7z", "docs"])))
    assert not ok and "py7zr" in text, "without the library the message says what to install"
    ok, text = capture(zipc, lambda: with_library("py7zr", fake7z, lambda: zipc.execute(["pack.7z", "docs"])))
    assert ok and "Added" in text and os.path.isfile("pack.7z"), text
    ok, text = capture(unzipc, lambda: with_library("py7zr", fake7z, lambda: unzipc.execute(["-l", "pack.7z"])))
    assert ok and "docs/a.txt" in text, text
    ok, text = capture(unzipc, lambda: with_library("py7zr", fake7z, lambda: unzipc.execute(["pack.7z", "-d", "out"])))
    assert ok and os.path.isfile("out/docs/a.txt"), text
    ok, text = capture(unzipc, lambda: with_library("py7zr", fake7z, lambda: unzipc.execute(["pack.7z", "-d", "out"])))
    assert not ok and "already exists" in text, "nothing is replaced without -o"
    # unsafe archives are refused before anything is written
    for bad in (Info("../evil.txt", 1), Info("/abs.txt", 1), Info("link", 1, symlink=True), Info("big", archive.MAX_TOTAL + 1)):
        store[os.path.abspath("bad.7z")] = [bad]
        try:
            with_library("py7zr", fake7z, lambda: archive.extract_7z("bad.7z", "out2"))
            raise AssertionError(f"{bad.filename} must be refused")
        except archive.ArchiveError:
            pass
    assert not os.path.exists("evil.txt") and not os.path.exists("out2/link")
    # a library error becomes a message, not a crash
    broken = types.SimpleNamespace(SevenZipFile=lambda path, mode: (_ for _ in ()).throw(ValueError("Bad7zFile")))
    try:
        with_library("py7zr", broken, lambda: archive.list_7z("pack.7z"))
        raise AssertionError("a damaged archive is an ArchiveError")
    except archive.ArchiveError as e:
        assert "cannot use this 7z archive" in str(e)

    # ---- distro and py-cpuinfo
    osinfo._cache.clear()
    pretty = types.SimpleNamespace(name=lambda pretty=False: "Alpine Linux v3.19" if pretty else "Alpine")
    real_system = osinfo.platform.system
    osinfo.platform.system = lambda: "Linux"
    try:
        assert with_library("distro", pretty, lambda: (osinfo._cache.clear(), osinfo.distribution())[1]) == "Alpine Linux v3.19"
        real_enabled = lockdown.enabled
        lockdown.enabled = lambda: True
        try:
            got = with_library("distro", pretty, lambda: (osinfo._cache.clear(), osinfo.distribution())[1])
            assert got != "Alpine Linux v3.19" or os.path.exists("/etc/os-release"), "no library while lockdown is on"
        finally:
            lockdown.enabled = real_enabled
        broke = types.SimpleNamespace(name=lambda pretty=False: (_ for _ in ()).throw(RuntimeError("no")))
        assert with_library("distro", broke, lambda: (osinfo._cache.clear(), osinfo.distribution())[1])
    finally:
        osinfo.platform.system = real_system
    osinfo._cache.clear()
    osinfo.platform.system = lambda: "Windows"
    try:
        info = types.SimpleNamespace(get_cpu_info=lambda: {"brand_raw": "Fancy CPU @ 3.00GHz", "vendor_id_raw": "AuthenticAMD", "l3_cache_size": "32 MiB"})
        found = with_library("cpuinfo", info, lambda: (osinfo._cache.clear(), osinfo.cpu())[1])
        assert found == {"model": "Fancy CPU @ 3.00GHz", "vendor": "AuthenticAMD", "cache": "32 MiB"}, found
        assert with_library("cpuinfo", None, lambda: (osinfo._cache.clear(), osinfo.cpu())[1])["vendor"] == ""
        slow_failing = types.SimpleNamespace(get_cpu_info=lambda: (_ for _ in ()).throw(OSError("registry")))
        assert with_library("cpuinfo", slow_failing, lambda: (osinfo._cache.clear(), osinfo.cpu())[1])["vendor"] == ""
    finally:
        osinfo.platform.system = real_system
        osinfo._cache.clear()
    lscpu, sysinfo = command("lscpu"), command("sysinfo")
    ok, text = capture(lscpu, lambda: lscpu.execute([]))
    assert ok and "Model" in text and "Vendor" in text
    from rich.console import Console as RichConsole
    out = io.StringIO()
    sysinfo.console = RichConsole(file=out, width=140)
    sysinfo.get_system_info()
    assert "Distribution" in out.getvalue()

    # ---- watching a folder
    os.makedirs("watched")
    before = filewatch.snapshot("watched")
    assert before == {}
    with open("watched/a.txt", "w") as f:
        f.write("1")
    after = filewatch.snapshot("watched")
    assert list(after) == [os.path.join("watched", "a.txt")] and filewatch.snapshot("watched/a.txt") != {}
    assert filewatch.snapshot("nothing-here") == {}
    ticks = []

    def sleeper(seconds):
        ticks.append(seconds)
        if len(ticks) == 2:
            with open("watched/b.txt", "w") as f:
                f.write("2")                                   # the change happens while the watcher waits
        if len(ticks) > 10:
            raise AssertionError("the change was not noticed")
    assert with_library("watchfiles", None, lambda: next(filewatch.changes("watched", 0.01, sleeper))) is True and len(ticks) == 2, "polling notices a new file, and only then yields"
    # with watchfiles, the library's events are used; an empty timeout tick does not count
    seen = {}

    def fake_watch(path, **kwargs):
        seen.update(kwargs)
        yield set()
        yield {("added", "x")}
    library = types.SimpleNamespace(watch=fake_watch)
    assert with_library("watchfiles", library, lambda: next(filewatch.changes("watched"))) is True
    assert seen["yield_on_timeout"] is True and seen["rust_timeout"] == 1000
    # a library that cannot start (no room for watches) falls back to polling
    ticks.clear()
    bad = types.SimpleNamespace(watch=lambda *a, **k: (_ for _ in ()).throw(OSError("inotify limit")))

    def sleeper_two(seconds):
        ticks.append(seconds)
        if len(ticks) == 2:
            with open("watched/d.txt", "w") as f:
                f.write("4")
        if len(ticks) > 10:
            raise AssertionError("the change was not noticed")
    assert with_library("watchfiles", bad, lambda: next(filewatch.changes("watched", 0.01, sleeper_two))) is True and len(ticks) == 2

    # ---- nslookup record types that need dnspython
    ns = command("nslookup")
    assert ns.parse(["example.com", "CAA"]) == ("example.com", "CAA", None) and ns.parse(["example.com", "mx"])[1] == "MX"
    assert ns.parse(["example.com", "BOGUS"]) is None

    class Rdata:
        def __init__(self, text):
            self.text = text

        def to_text(self):
            return self.text

    class Answer(list):
        rrset = types.SimpleNamespace(name="example.com.", ttl=300)

    class Resolver:
        def __init__(self, configure=True):
            pass

        def resolve(self, name, qtype):
            if name == "gone.example":
                raise type("NXDOMAIN", (Exception,), {})()
            if name == "empty.example":
                raise type("NoAnswer", (Exception,), {})()
            return Answer([Rdata('0 issue "letsencrypt.org"')])
    resolver_module = types.SimpleNamespace(Resolver=Resolver)
    ok, text = capture(ns, lambda: with_library("dns.resolver", resolver_module, lambda: ns.execute(["example.com", "CAA", "9.9.9.9"])))
    assert ok and 'letsencrypt.org' in text and "CAA" in text and "300" in text, text
    ok, text = capture(ns, lambda: with_library("dns.resolver", resolver_module, lambda: ns.execute(["gone.example", "SRV", "9.9.9.9"])))
    assert not ok and "no such name" in text
    ok, text = capture(ns, lambda: with_library("dns.resolver", resolver_module, lambda: ns.execute(["empty.example", "SRV", "9.9.9.9"])))
    assert ok and "no SRV records" in text
    ok, text = capture(ns, lambda: with_library("dns.resolver", None, lambda: ns.execute(["example.com", "CAA", "9.9.9.9"])))
    assert not ok and "dnspython" in text
    print("optional libraries (1.0.13): all checks passed")


if __name__ == "__main__":
    main()
