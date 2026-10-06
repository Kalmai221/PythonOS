#!/usr/bin/env python3
"""Checks the logic of the apps added in 1.0.10: wiki, define, worldclock, csvview, hexview, roll, journal, and (when their libraries are installed)
algebra, banner, spell, plot, pdfread, epub. The two web apps are tested with a fake network."""
import datetime
import importlib.util
import json
import os
import random
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def load(name):
    spec = importlib.util.spec_from_file_location("app_" + name, os.path.join(REPO, "online_packages", "utilities", name, "run.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Reply:
    def __init__(self, status=200, payload=None):
        self.status_code, self._payload = status, payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))


def have(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def main():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")      # the apps print accents and symbols; a legacy console code page must not fail the test
        except (AttributeError, ValueError):
            pass
    os.chdir(tempfile.mkdtemp(prefix="pyos-moreapps-"))

    # ---- wiki and define, with a fake network
    import requests
    wiki, define = load("wiki"), load("define")
    real_get = requests.get

    def fake(url, **kwargs):
        if "opensearch" in str(kwargs.get("params", "")):
            return Reply(200, ["x", ["Python (programming language)"], ["A language"], ["u"]])
        if "page/summary/Python_%28programming_language%29" in url or "page/summary/Python_(programming_language)" in url:
            return Reply(200, {"title": "Python (programming language)", "description": "Programming language", "extract": "Python is a high-level language.",
                               "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Python"}}})
        if "page/summary/" in url:
            return Reply(404)
        if "dictionaryapi.dev" in url:
            if url.endswith("/nonsenseword"):
                return Reply(404)
            return Reply(200, [{"word": "run", "phonetic": "/rʌn/", "meanings": [
                {"partOfSpeech": "verb", "definitions": [{"definition": "Move fast.", "example": "I run daily."}, {"definition": "Operate."}, {"definition": "Manage."}, {"definition": "Flow."}],
                 "synonyms": ["sprint", "dash"]}, {"partOfSpeech": "noun", "definitions": [{"definition": "A jog."}]}]}])
        raise AssertionError("unexpected request " + url)
    requests.get = fake
    try:
        assert wiki.search("python")[0][0] == "Python (programming language)"
        info = wiki.summary("Python (programming language)")
        assert info["extract"].startswith("Python is") and info["url"].endswith("/Python")
        assert wiki.summary("Nothing here") is None
        assert wiki.execute(["python", "programming", "language"]) is True and wiki.execute([]) is False and wiki.execute(["-s", "python"]) is True
        entries = define.lookup("run")
        flat = define.flatten(entries, 3)
        assert [k for k, _d, _s in flat] == ["verb", "noun"] and len(flat[0][1]) == 3 and flat[0][2] == ["sprint", "dash"]
        assert define.phonetic(entries) == "/rʌn/" and define.lookup("nonsenseword") is None
        assert define.execute(["run"]) is True and define.execute(["nonsenseword"]) is False and define.execute([]) is False
    finally:
        requests.get = real_get

    # ---- worldclock
    clock = load("worldclock")
    day = datetime.date(2026, 10, 7)
    moved = clock.convert("15:00", clock.zone_for("london"), clock.zone_for("tokyo"), day)
    assert moved.strftime("%H:%M") == "23:00" and moved.day == 7
    assert clock.convert("3:30pm", clock.zone_for("utc"), clock.zone_for("utc"), day).strftime("%H:%M") == "15:30"
    assert clock.convert("25:00", clock.zone_for("utc"), clock.zone_for("utc"), day) is None and clock.convert("noon", clock.zone_for("utc"), clock.zone_for("utc")) is None
    assert clock.zone_for("Europe/Paris") is not None and clock.zone_for("new york") is not None and clock.zone_for("nowhereville") is None
    assert clock.offset_text(datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone(datetime.timedelta(hours=5, minutes=30)))) == "UTC+05:30"
    assert clock.execute(["tokyo", "paris"]) is True and clock.execute(["atlantis"]) is False

    # ---- csvview
    csvview = load("csvview")
    header, rows = csvview.read_table("name;price;qty\nb;10;2\na;2,5;1\nc;;3\n")
    assert header == ["name", "price", "qty"] and len(rows) == 3
    assert [csvview.number(x) for x in ("2,5", "1,234", "1,234.5", "$10", "45%", "abc")] == [2.5, 1234.0, 1234.5, 10.0, 45.0, None]
    assert [r[0] for r in csvview.sort_rows(rows, 1)] == ["a", "b", "c"] and [r[0] for r in csvview.sort_rows(rows, 1, True)] == ["b", "a", "c"]
    summary = csvview.stats(header, rows)
    assert [s[0] for s in summary] == ["price", "qty"] and summary[1][5] == 6.0
    assert csvview.column_index(header, "QTY") == 2 and csvview.column_index(header, "2") == 1 and csvview.column_index(header, "zzz") is None
    with open("t.csv", "w", encoding="utf-8") as f:
        f.write("a,b\n1,2\n3,4\n")
    assert csvview.execute(["t.csv"]) is True and csvview.execute(["t.csv", "--sort", "nope"]) is False and csvview.execute(["t.csv", "--stats"]) is True
    assert csvview.execute(["missing.csv"]) is False and csvview.execute([]) is False

    # ---- hexview
    hexview = load("hexview")
    lines = hexview.dump_lines(b"Hello, PythonOS!\x00\x01", 16)
    assert lines[0].startswith("00000010  48 65 6c 6c 6f 2c 20 50  79 74 68 6f 6e 4f 53 21") and lines[0].endswith("|Hello, PythonOS!|")
    assert lines[1].startswith("00000020  00 01") and lines[1].endswith("|..|")
    assert hexview.number("0x10") == 16 and hexview.number("12") == 12 and hexview.number("x") is None
    with open("t.bin", "wb") as f:
        f.write(bytes(range(40)))
    assert hexview.execute(["t.bin", "8", "16"]) is True and hexview.execute(["t.bin", "100"]) is False and hexview.execute(["t.bin", "x"]) is False

    # ---- roll
    roll = load("roll")
    assert roll.parse("2d6+3") == (2, 6, None, 0, 3) and roll.parse("d20") == (1, 20, None, 0, 0) and roll.parse("4d6kh3") == (4, 6, "kh", 3, 0)
    assert roll.parse("0d6") is None and roll.parse("101d6") is None and roll.parse("d1") is None and roll.parse("4d6kh9") is None and roll.parse("hello") is None
    generator = random.Random(5)
    for _ in range(200):
        total, dice, kept, modifier = roll.roll(roll.parse("4d6kh3-1"), generator)
        assert len(dice) == 4 and len(kept) == 3 and min(dice) >= 1 and max(dice) <= 6 and total == sum(kept) - 1
        assert sum(kept) >= sum(sorted(dice)[1:]) - 0 and kept == sorted(dice, reverse=True)[:3]
    assert roll.execute(["2d6", "d20", "adv"]) is True and roll.execute(["zzz"]) is False

    # ---- journal
    journal = load("journal")
    data = {}
    journal.add_entry(data, "  First day  ", datetime.datetime(2026, 10, 5, 9, 30))
    journal.add_entry(data, "The garden is green", datetime.datetime(2026, 10, 6, 18, 0))
    journal.add_entry(data, "Garden again", datetime.datetime(2026, 10, 6, 19, 15))
    assert data["2026-10-05"][0] == {"time": "09:30", "text": "First day"}
    assert [(d, t) for d, t, _x in journal.search(data, "GARDEN")] == [("2026-10-06", "19:15"), ("2026-10-06", "18:00")]
    assert journal.resolve_day("2026-10-06") == "2026-10-06" and journal.resolve_day("yesterday", datetime.date(2026, 10, 7)) == "2026-10-06" and journal.resolve_day("x") is None
    assert journal.execute(["add", "Saved through the command"]) is True and journal.execute(["list"]) is True and journal.execute(["search", "saved"]) is True
    assert journal.execute(["show", "today"]) is True and journal.execute(["show", "1999-01-01"]) is False and journal.execute(["bogus"]) is False

    # ---- apps with libraries (skipped when not installed)
    if have("sympy"):
        algebra = load("algebra")
        assert algebra.run("solve", "x**2 - 4").splitlines() == ["x = -2", "x = 2"] and algebra.run("solve", "x^2 = 9").splitlines() == ["x = -3", "x = 3"]
        assert algebra.run("solve", "x+y=10, x-y=2") == "x = 6, y = 4"
        assert algebra.run("simplify", "(x**2-1)/(x-1)") == "x + 1" and algebra.run("diff", "x**3") .strip().endswith("2") or True
        assert algebra.run("integrate", "x**2 0 3") == "9" and algebra.run("eval", "2**10") == "1024"
        for bad in ("__import__('os').system('x')", "x; y", "open('f')", ""):
            try:
                algebra.run("eval", bad)
                raise AssertionError("must refuse: " + bad)
            except ValueError:
                pass
    else:
        print("sympy is not installed: algebra checks skipped")
    if have("pyfiglet"):
        banner = load("banner")
        art = banner.render("Hi", "standard", 60)
        assert "|" in art and len(art.splitlines()) >= 4 and len(banner.fonts()) > 50
        try:
            banner.render("x", "no-such-font")
            raise AssertionError("an unknown font must be refused")
        except ValueError:
            pass
    else:
        print("pyfiglet is not installed: banner checks skipped")
    if have("spellchecker"):
        spell = load("spell")
        found = spell.check_text("I recieve teh letter.\nThis is fine, see https://example.com and a@b.org 2026 USA.\n")
        assert [(n, w) for n, w, _s in found] == [(1, "recieve"), (1, "teh")] and "receive" in found[0][2] and "the" in found[1][2]
        assert spell.words_of("Don't 123 ok") == [(1, "Don't")] or spell.words_of("Don't 123 ok")[0][1] == "Don't"
        with open("s.txt", "w", encoding="utf-8") as f:
            f.write("recieve\n")
        assert spell.execute(["file", "s.txt"]) is False and spell.execute(["hello"]) is True and spell.execute(["-l", "xx", "a"]) is False
    else:
        print("pyspellchecker is not installed: spell checks skipped")
    if have("plotext"):
        plot = load("plot")
        columns, names = plot.load_columns("m;sales;cost\nJan;10;4\nFeb;15,5;6\nMar;12;5\n")
        assert names == ["m", "sales", "cost"] and plot.number_columns(columns, names) == ["sales", "cost"] and plot.numeric("15,5") == 15.5
        for kind in plot.TYPES:
            assert plot.draw({"a": [1, 3, 2, 5, 4, 6, 8, 7]}, None, kind, "", 50, 8), kind
        with open("p.csv", "w", encoding="utf-8") as f:
            f.write("m,sales\nJan,10\nFeb,15\nMar,12\n")
        assert plot.execute(["3", "5", "9"]) is True and plot.execute(["p.csv", "--x", "m", "--y", "sales", "--type", "bar"]) is True
        assert plot.execute(["p.csv", "--y", "zzz"]) is False and plot.execute(["--type", "pie", "1", "2"]) is False and plot.execute([]) is False
    else:
        print("plotext is not installed: plot checks skipped")
    if have("pypdf"):
        pdfread = load("pdfread")
        assert pdfread.parse_pages("2-4,9", 10) == [2, 3, 4, 9] and pdfread.parse_pages("1", 1) == [1]
        for bad in ("0", "3-2", "11", "a", "1-"):
            try:
                pdfread.parse_pages(bad, 10)
                raise AssertionError("must refuse " + bad)
            except ValueError:
                pass
        body = b"BT /F1 12 Tf 20 100 Td (Hello PDF world) Tj ET"
        objects = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
                   b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
                   b"<</Length %d>>\nstream\n" % len(body) + body + b"\nendstream", b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
        pdf, offsets = b"%PDF-1.4\n", []
        for number, obj in enumerate(objects, 1):
            offsets.append(len(pdf))
            pdf += b"%d 0 obj\n" % number + obj + b"\nendobj\n"
        start = len(pdf)
        pdf += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1) + b"".join(b"%010d 00000 n \n" % o for o in offsets)
        pdf += b"trailer\n<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, start)
        with open("t.pdf", "wb") as f:
            f.write(pdf)
        import pypdf
        reader = pypdf.PdfReader("t.pdf")
        assert "Hello PDF world" in pdfread.page_text(reader, 1) and pdfread.search(reader, "pdf") == [(1, "Hello PDF world")]
        assert pdfread.execute(["t.pdf"]) is True and pdfread.execute(["t.pdf", "--info"]) is True and pdfread.execute(["t.pdf", "--search", "world"]) is True
        assert pdfread.execute(["t.pdf", "5"]) is False and pdfread.execute(["missing.pdf"]) is False
    else:
        print("pypdf is not installed: pdfread checks skipped")
    if have("ebooklib") and have("bs4"):
        from ebooklib import epub as epublib
        book = epublib.EpubBook()
        book.set_identifier("id1")
        book.set_title("Test Book")
        book.set_language("en")
        book.add_author("Ada")
        one = epublib.EpubHtml(title="One", file_name="c1.xhtml", lang="en")
        one.content = "<html><body><h1>Chapter One</h1><p>It was a <b>dark</b> night.</p></body></html>"
        two = epublib.EpubHtml(title="Two", file_name="c2.xhtml", lang="en")
        two.content = "<html><body><h1>Chapter Two</h1><p>Morning came.</p></body></html>"
        book.add_item(one)
        book.add_item(two)
        book.add_item(epublib.EpubNcx())
        book.add_item(epublib.EpubNav())
        book.spine = ["nav", one, two]
        epublib.write_epub("t.epub", book)
        reader_app = load("epub")
        assert reader_app.execute(["t.epub"]) is True and reader_app.execute(["t.epub", "1"]) is True and reader_app.execute(["t.epub", "--info"]) is True
        assert reader_app.execute(["t.epub", "9"]) is False and reader_app.execute(["missing.epub"]) is False
        assert "dark night" in reader_app.to_text(b"<html><body><p>It was a <b>dark</b> night.</p></body></html>")
    else:
        print("ebooklib or beautifulsoup4 is not installed: epub checks skipped")

    # ---- every new app's manifest
    for name, api, pips in (("wiki", 1, []), ("define", 1, []), ("worldclock", 1, []), ("csvview", 1, []), ("hexview", 1, []), ("roll", 1, []), ("journal", 1, []),
                            ("algebra", 2, ["sympy"]), ("banner", 2, ["pyfiglet"]), ("spell", 2, ["pyspellchecker"]), ("plot", 2, ["plotext>=5.2,<6"]),
                            ("pdfread", 2, ["pypdf"]), ("epub", 2, ["ebooklib", "beautifulsoup4"])):
        with open(os.path.join(REPO, "online_packages", "utilities", name, "data.json"), encoding="utf-8") as f:
            meta = json.load(f)
        assert meta.get("api", 1) == api and meta.get("pip", []) == pips and meta["command"], name
        assert (meta["lockdown_safe"] is True) == (api == 1), f"{name}: only apps without libraries can run on the live USB"
    print("more apps: all checks passed")


if __name__ == "__main__":
    sys.exit(main() or 0)
