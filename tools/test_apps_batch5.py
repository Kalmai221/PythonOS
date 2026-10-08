#!/usr/bin/env python3
"""Checks the apps added in the second batch of 1.0.13 (ipcalc, tipsplit, jwt, hn, xkcd, synonyms, countries, rates, emoji, higherlower, simon, snakes) and
the new features of the LAN scanner. Nothing is downloaded and no network is used: web services answer from canned data, the emoji library is a
stand-in, and the scanner's probe talks to a socket opened on this computer."""
import base64
import hashlib
import hmac
import importlib.util
import io
import ipaddress
import json
import os
import random
import socket
import sys
import tempfile
import types
from decimal import Decimal

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def load(kind, name):
    spec = importlib.util.spec_from_file_location("app5_" + name, os.path.join(REPO, "online_packages", kind, name, "run.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Reply:
    def __init__(self, data, status=200):
        self.data, self.status_code, self.content = data, status, b"PNG"

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))


def run_main(module, argv, replies=None):
    import requests
    from rich.console import Console
    out = io.StringIO()
    module.console = Console(file=out, force_terminal=False, width=140)
    real_get, real_stdout = requests.get, sys.stdout
    if replies is not None:
        requests.get = lambda url, **kw: replies(url, kw)
    sys.stdout = out
    try:
        code = module.main(argv)
    finally:
        requests.get, sys.stdout = real_get, real_stdout
    return code, out.getvalue()


def raises(call, *errors):
    try:
        call()
    except errors:
        return True
    return False


def main():
    os.chdir(tempfile.mkdtemp(prefix="pyos-apps5-"))

    # ---- ipcalc
    ipcalc = load("utilities", "ipcalc")
    interface, split, prefix = ipcalc.parse(["192.168.1.10/24"])
    rows = ipcalc.describe(interface)
    assert rows["Network"] == "192.168.1.0/24" and rows["Broadcast"] == "192.168.1.255" and rows["Usable range"] == "192.168.1.1 - 192.168.1.254"
    assert rows["Usable hosts"] == "254" and rows["Wildcard"] == "0.0.0.255" and rows["Type"].startswith("private") and rows["Mask"] == "255.255.255.0"
    assert ipcalc.parse(["10.0.0.5", "255.255.255.0"])[0].network == ipaddress.ip_network("10.0.0.0/24")
    assert ipcalc.describe(ipaddress.ip_interface("10.0.0.1/31"))["Usable hosts"] == "2", "a /31 has two usable addresses"
    assert ipcalc.describe(ipaddress.ip_interface("8.8.8.8/32"))["Usable hosts"] == "1"
    assert ipcalc.describe(ipaddress.ip_interface("8.8.8.8/24"))["Type"].startswith("public")
    assert ipcalc.describe(ipaddress.ip_interface("2001:db8::1/64"))["Addresses"] == f"{2 ** 64:,}"
    nets = ipcalc.split_network(ipaddress.ip_network("192.168.1.0/24"), count=4)
    assert [str(n) for n in nets] == ["192.168.1.0/26", "192.168.1.64/26", "192.168.1.128/26", "192.168.1.192/26"]
    assert len(ipcalc.split_network(ipaddress.ip_network("10.0.0.0/24"), prefix=26)) == 4
    for bad in ({"count": 3}, {"prefix": 24}, {"prefix": 33}, {"count": 1}):
        assert raises(lambda b=bad: ipcalc.split_network(ipaddress.ip_network("10.0.0.0/24"), **b), ValueError), bad
    assert raises(lambda: ipcalc.parse(["not-an-ip"]), ValueError) and raises(lambda: ipcalc.parse([]), ValueError) and raises(lambda: ipcalc.parse(["1.2.3.4/24", "--split"]), ValueError)
    code, text = run_main(ipcalc, ["192.168.1.0/24", "--split", "4"])
    assert code == 0 and "192.168.1.64/26" in text and "4 networks of /26" in text
    assert run_main(ipcalc, ["bogus"])[0] == 1

    # ---- tipsplit
    tip = load("utilities", "tipsplit")
    result = tip.calculate(Decimal("84.50"), Decimal(20), 4)
    assert result["tip_plain"] == Decimal("16.90") and result["total"] == Decimal("101.40") and result["each"] == Decimal("25.35") and result["paid"] == Decimal("101.40")
    third = tip.calculate(Decimal("100"), Decimal(15), 3)
    assert third["each"] == Decimal("38.34") and third["paid"] >= third["total"] and third["extra"] == third["paid"] - third["total"], "shares never add up to less than the total"
    rounded = tip.calculate(Decimal("84.50"), Decimal(18), 3, round_up=True)
    assert rounded["each"] == rounded["each"].to_integral_value() and rounded["paid"] >= rounded["total"]
    taxed = tip.calculate(Decimal("100"), Decimal(10), 1, Decimal("5"))
    assert taxed["tax"] == Decimal("5.00") and taxed["tip_plain"] == Decimal("10.00") and taxed["total"] == Decimal("115.00"), "the tip is on the bill before tax"
    assert tip.calculate(Decimal("10"), Decimal(0), 1)["total"] == Decimal("10")
    assert tip.parse(["84,50", "18", "3", "--tax", "6.5", "--round"]) == (Decimal("84.50"), Decimal(18), 3, Decimal("6.5"), True)
    assert tip.parse(["50"]) == (Decimal(50), Decimal(15), 1, Decimal(0), False)
    for bad in (["abc"], ["-5"], ["50", "150"], ["50", "10", "0"], ["50", "10", "1", "extra"], ["50", "--tax"], []):
        assert raises(lambda b=bad: tip.parse(b), ValueError), bad
    code, text = run_main(tip, ["84.50", "20", "4"])
    assert code == 0 and "25.35" in text and "101.40" in text

    # ---- jwt
    jwt = load("utilities", "jwt")

    def make(header, claims, secret=None, algorithm="HS256"):
        def part(obj):
            return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()
        signing = part(header) + "." + part(claims)
        digest = {"HS256": hashlib.sha256, "HS384": hashlib.sha384, "HS512": hashlib.sha512}[algorithm]
        signature = hmac.new(secret.encode(), signing.encode(), digest).digest() if secret is not None else b""
        return signing + "." + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    now = 1_790_000_000
    token = make({"alg": "HS256", "typ": "JWT"}, {"sub": "ada", "iat": now - 100, "exp": now + 7200}, "s3cret")
    header, claims, signing, signature = jwt.decode(token)
    assert header["alg"] == "HS256" and claims["sub"] == "ada"
    assert jwt.check_signature(header, signing, signature, "s3cret") == "valid" and jwt.check_signature(header, signing, signature, "wrong") == "invalid"
    assert "cannot check" in jwt.check_signature({"alg": "RS256"}, signing, signature, "x") and "cannot check" in jwt.check_signature({"alg": "none"}, signing, b"", "x")
    for algorithm in ("HS384", "HS512"):
        t = make({"alg": algorithm}, {"a": 1}, "k", algorithm)
        h, c, s, sig = jwt.decode(t)
        assert jwt.check_signature(h, s, sig, "k") == "valid"
    assert "in 2 hour(s)" in jwt.when(now + 7200, now) and "ago" in jwt.when(now - 90, now) and jwt.when("soon", now) == "soon"
    assert "expired" in jwt.status({"exp": now - 5}, now)[0] and "not valid yet" in jwt.status({"nbf": now + 5, "exp": now + 9}, now)[0]
    assert "within" in jwt.status({"exp": now + 5}, now)[0] and "no expiry" in jwt.status({}, now)[0]
    for bad in ("only.two", "a.b.c", "!!!.???.***", make({"alg": "x"}, {"a": 1}).rsplit(".", 1)[0]):
        assert raises(lambda b=bad: jwt.decode(b), ValueError), bad
    assert raises(lambda: jwt.decode(base64.urlsafe_b64encode(b"[1]").decode() + ".e30." + "x"), ValueError), "the header must be an object"
    code, text = run_main(jwt, [token, "--secret", "s3cret"])
    assert code == 0 and "ada" in text and "valid" in text and "Expires" in text
    code, text = run_main(jwt, [make({"alg": "none"}, {"a": 1}, None)])
    assert code == 0 and "no signature" in text
    assert run_main(jwt, ["x.y"])[0] == 1

    # ---- hn
    hn = load("utilities", "hn")
    assert hn.site("https://www.example.com/a/b") == "example.com" and hn.site("") == "" and hn.site(None) == ""
    assert hn.parse_args(["new", "-n", "5"]) == ("new", 5, None) and hn.parse_args(["ask", "3"]) == ("ask", 15, 3) and hn.parse_args(["-n", "999"])[1] == 50
    assert raises(lambda: hn.parse_args(["bogus"]), ValueError) and raises(lambda: hn.parse_args(["-n"]), ValueError)
    items = {1: {"id": 1, "title": "One", "score": 120, "descendants": 45, "by": "ada", "url": "https://www.one.example/x"},
             2: {"id": 2, "title": "Ask HN: two?", "score": 5, "by": "bob"}, 3: {"id": 3, "deleted": True}, 4: None}
    assert hn.story(items[1])["site"] == "one.example" and hn.story(items[2])["comments"] == 0 and hn.story(items[3]) == {} and hn.story(None) == {}

    def hnapi(url, kw):
        if url.endswith("topstories.json"):
            return Reply([1, 2, 3, 4])
        return Reply(items.get(int(url.rsplit("/", 1)[1].split(".")[0])))
    code, text = run_main(hn, ["-n", "4"], hnapi)
    assert code == 0 and "One" in text and "one.example" in text and "120" in text and "deleted" not in text
    code, text = run_main(hn, ["1"], hnapi)
    assert code == 0 and "120 points by ada" in text and "item 1" in text
    assert run_main(hn, ["9"], hnapi)[0] == 1

    # ---- xkcd
    xkcd = load("utilities", "xkcd")
    comic = {"num": 353, "title": "Python", "safe_title": "Python", "alt": "I wrote 20 short programs.  It was great.", "year": "2007", "month": "12", "day": "5",
             "img": "https://imgs.xkcd.com/comics/python.png", "transcript": "A\nB\n"}
    lines = xkcd.describe(comic)
    assert lines[0] == "xkcd 353: Python" and lines[1] == "Published 2007-12-05" and any("20 short programs. It was great." in l for l in lines)
    assert xkcd.parse(["353", "--save"]) == (353, False, True) and xkcd.parse(["random"]) == (None, True, False) and raises(lambda: xkcd.parse(["x"]), ValueError)

    def xkcdapi(url, kw):
        if url.endswith("info.0.json"):
            number = url.split("/")[-2]
            if number == "9999":
                return Reply({}, 404)
            return Reply(dict(comic, num=int(number)) if number.isdigit() else dict(comic, num=2000))
        return Reply({})
    code, text = run_main(xkcd, ["353"], xkcdapi)
    assert code == 0 and "xkcd 353: Python" in text and "xkcd.com/353" in text and "http" not in text
    code, text = run_main(xkcd, ["9999"], xkcdapi)
    assert code == 1 and "no xkcd number" in text
    code, text = run_main(xkcd, ["random"], xkcdapi)
    assert code == 0 and "xkcd " in text
    code, text = run_main(xkcd, ["353", "--save"], xkcdapi)
    assert code == 0 and os.path.exists("xkcd-353.png")

    # ---- synonyms
    syn = load("utilities", "synonyms")
    assert syn.parse(["happy"]) == ("rel_syn", "Words that mean the same as", "happy", 25)
    assert syn.parse(["orange", "--rhyme", "-n", "500"]) == ("rel_rhy", "Words that rhyme with", "orange", 100) and syn.parse(["te*r", "--spelled"])[0] == "sp"
    assert raises(lambda: syn.parse([]), ValueError) and raises(lambda: syn.parse(["x" * 100]), ValueError) and raises(lambda: syn.parse(["a", "-n", "x"]), ValueError)
    assert syn.words([{"word": "glad"}, {"word": "glad"}, {"nothing": 1}, "x", {"word": "joyful"}]) == ["glad", "joyful"] and syn.words({"error": 1}) == []
    seen = {}

    def datamuse(url, kw):
        seen.update(kw.get("params", {}))
        return Reply([{"word": "glad", "score": 9}, {"word": "joyful", "score": 7}])
    code, text = run_main(syn, ["happy", "--opposite"], datamuse)
    assert code == 0 and "glad" in text and "Opposites of happy" in text and seen["rel_ant"] == "happy"
    assert "Nothing found" in run_main(syn, ["zzz"], lambda u, k: Reply([]))[1]

    # ---- countries
    countries = load("utilities", "countries")
    japan = {"name": {"common": "Japan", "official": "Japan"}, "cca2": "JP", "cca3": "JPN", "capital": ["Tokyo"], "region": "Asia", "subregion": "Eastern Asia",
             "population": 125_000_000, "area": 377_930, "languages": {"jpn": "Japanese"}, "currencies": {"JPY": {"name": "Japanese yen", "symbol": "¥"}},
             "idd": {"root": "+8", "suffixes": ["1"]}, "timezones": ["UTC+09:00"], "tld": [".jp"], "borders": []}
    uk = {"name": {"common": "United Kingdom", "official": "UK of GB"}, "idd": {"root": "+4", "suffixes": ["4"]}}
    usa = {"name": {"common": "United States", "official": "USA"}, "idd": {"root": "+1", "suffixes": ["201", "202"]}}
    assert countries.calling_code(japan) == "+81" and countries.calling_code(usa) == "+1" and countries.calling_code({}) == ""
    rows = dict(countries.describe(japan))
    assert rows["Capital"] == "Tokyo" and rows["People"] == "125,000,000" and "Japanese yen (¥)" in rows["Money"] and rows["Calling code"] == "+81" and "per km2" in rows["Area"]
    assert dict(countries.describe({"name": {"common": "X"}}))["Capital"] == "none"

    def restapi(url, kw):
        if "/alpha/" in url:
            return Reply([japan]) if url.endswith("/jp") else Reply({}, 404)
        if "/name/united" in url:
            return Reply([uk, usa]) if not kw.get("params", {}).get("fullText") else Reply({}, 404)
        if "/name/japan" in url:
            return Reply([japan])
        if "/region/europe" in url:
            return Reply([{"name": {"common": "Small"}, "population": 5}, {"name": {"common": "Big"}, "population": 50}])
        return Reply({}, 404)
    code, text = run_main(countries, ["japan"], restapi)
    assert code == 0 and "Tokyo" in text and "+81" in text
    code, text = run_main(countries, ["jp"], restapi)
    assert code == 0 and "Japanese" in text
    code, text = run_main(countries, ["united"], restapi)
    assert code == 0 and "United Kingdom" in text and "United States" in text and "2 countries" in text, "several matches are listed"
    code, text = run_main(countries, ["--region", "europe"], restapi)
    assert code == 0 and text.index("Big") < text.index("Small"), "biggest first"
    assert run_main(countries, ["atlantis"], restapi)[0] == 1 and run_main(countries, ["--region", "mars"], restapi)[0] == 1 and run_main(countries, [])[0] == 1

    # ---- rates
    rates = load("utilities", "rates")
    assert rates.parse(["100", "usd", "eur"]) == (Decimal(100), "USD", ["EUR"], None, False)
    assert rates.parse(["250", "gbp", "to", "usd", "jpy"])[2] == ["USD", "JPY"] and "EUR" not in rates.parse(["eur"])[2] and rates.parse(["usd"])[0] == 1
    assert rates.parse(["100", "usd", "--date", "2024-12-24"])[3] == "2024-12-24" and rates.parse(["list"])[4] is True
    for bad in ([], ["0", "usd"], ["100", "dollars"], ["100", "usd", "--date", "yesterday"], ["-5", "usd", "eur"]):
        assert raises(lambda b=bad: rates.parse(b), ValueError), bad
    converted = rates.convert(Decimal(100), {"EUR": 0.92, "JPY": 150.5})
    assert converted["EUR"] == Decimal("92.0") and converted["JPY"] == Decimal("15050.0")
    assert rates.digits(Decimal("1234.567")) == "1,234.57" and rates.digits(Decimal("0.123456")) == "0.1235"
    asked = {}

    def frankfurter(url, kw):
        asked.update(url=url, **kw.get("params", {}))
        if url.endswith("currencies"):
            return Reply({"EUR": "Euro", "USD": "United States Dollar"})
        if kw.get("params", {}).get("base") == "XXX":
            return Reply({}, 404)
        return Reply({"amount": 1.0, "base": "USD", "date": "2026-10-07", "rates": {"EUR": 0.92}})
    code, text = run_main(rates, ["100", "usd", "eur"], frankfurter)
    assert code == 0 and "92.00" in text and "2026-10-07" in text and asked["base"] == "USD" and asked["symbols"] == "EUR" and asked["url"].endswith("/latest")
    code, text = run_main(rates, ["100", "usd", "eur", "--date", "2024-12-24"], frankfurter)
    assert asked["url"].endswith("/2024-12-24")
    assert "United States Dollar" in run_main(rates, ["list"], frankfurter)[1] and run_main(rates, ["10", "xxx", "eur"], frankfurter)[0] == 1

    # ---- emoji (a stand-in for the library)
    emoji_app = load("utilities", "emoji")
    library = types.SimpleNamespace(
        EMOJI_DATA={"👍": {"en": ":thumbs_up:", "alias": [":+1:", ":thumbsup:"]}, "🎉": {"en": ":party_popper:", "alias": [":tada:"]},
                    "🥳": {"en": ":partying_face:"}, "👋": {"en": ":waving_hand:", "alias": [":wave:"]}, "✋": {"status": 2}},
        emojize=lambda text, language="en": text.replace(":wave:", "👋").replace(":thumbs_up:", "👍"),
        demojize=lambda text: text.replace("👍", ":thumbs_up:"), emoji_count=lambda text: sum(text.count(c) for c in "👍🎉"))
    assert {name for _c, name in emoji_app.search(library, ["party"])} == {"party_popper", "partying_face"}
    assert [c for c, _n in emoji_app.search(library, ["thumbs", "up"])] == ["👍"] and [c for c, _n in emoji_app.search(library, ["tada"])] == ["🎉"]
    assert emoji_app.search(library, []) == [] and emoji_app.search(library, ["zzzzz"]) == []
    assert emoji_app.say(library, "hi :wave:") == "hi 👋" and emoji_app.plain(library, "ok 👍") == "ok :thumbs_up:" and emoji_app.count(library, "👍👍🎉") == 3
    sys.modules["emoji"] = library
    try:
        code, text = run_main(emoji_app, ["thumbs", "up"])
        assert code == 0 and ":thumbs_up:" in text
        code, text = run_main(emoji_app, ["--plain", "great", "👍"])
        assert code == 0 and ":thumbs_up:" in text
        assert "3 emoji" in run_main(emoji_app, ["--count", "👍👍🎉"])[1] and "No emoji" in run_main(emoji_app, ["qqqq"])[1] and run_main(emoji_app, [])[0] == 1
    finally:
        sys.modules.pop("emoji", None)

    # ---- higherlower
    hilo = load("games", "higherlower")
    deck = hilo.new_deck(random.Random(1))
    assert len(deck) == 52 and len(set(deck)) == 52 and len(hilo.new_deck(random.Random(1), jokers=True)) == 54
    assert hilo.value(("A", "♠")) == 14 and hilo.value(("2", "♥")) == 2 and hilo.value(("*", "joker")) is None
    assert hilo.judge(("5", "♠"), ("9", "♥"), "h") == "win" and hilo.judge(("5", "♠"), ("9", "♥"), "l") == "lose"
    assert hilo.judge(("9", "♠"), ("9", "♥"), "h") == "draw" and hilo.judge(("9", "♠"), ("*", "joker"), "l") == "lose"
    assert hilo.odds(("2", "♠"), [("3", "♠"), ("4", "♠")]) == (100, 0) and hilo.odds(("A", "♠"), []) == (0, 0)
    answers = iter(["h", "x", "l", "q"])
    from rich.console import Console
    out = io.StringIO()
    hilo.console = Console(file=out, force_terminal=False, width=120)
    hilo.console.input = lambda prompt="": next(answers)
    real_shuffle = random.shuffle
    assert hilo.main([]) == 0 and "Best streak" in out.getvalue() and "Type h for higher" in out.getvalue()
    random.shuffle = real_shuffle

    # ---- simon
    simon = load("games", "simon")
    sequence = simon.extend([], list("rgby"), random.Random(2))
    sequence = simon.extend(sequence, list("rgby"), random.Random(3))
    assert len(sequence) == 2 and set(sequence) <= set("rgby")
    assert simon.check(["r", "g"], "r g") == (True, 2) and simon.check(["r", "g"], "RG") == (True, 2) and simon.check(["r", "g", "b"], "r g y") == (False, 2)
    assert simon.check(["r", "g"], "r") == (False, 1) and simon.check(["r"], "r r") == (False, 1) and simon.check(["r"], "") == (False, 0)
    assert simon.score(0) == 0 and simon.score(3) == 10 + 12 + 14
    shown = []
    typed = iter(["r g", "q"])
    out = io.StringIO()
    simon.console = Console(file=out, force_terminal=False, width=120)
    simon.console.input = lambda prompt="": next(typed)
    simon.console.clear = lambda: shown.append("cleared")

    class Fixed(random.Random):
        def choice(self, seq):
            return seq[0]
    rounds = simon.play(list("rgby"), 0.0, Fixed(), sleep=lambda s: None)
    assert rounds == 0, "'r g' is wrong for a one-colour pattern, so no round was completed"
    typed = iter(["r", "q"])
    simon.console.input = lambda prompt="": next(typed)
    assert simon.play(list("rgby"), 0.0, Fixed(), sleep=lambda s: None) == 1, "one round right, then q"

    # ---- snakes
    snakes = load("games", "snakes")
    assert snakes.move(0, 4) == (14, "ladder") and snakes.move(10, 6) == (6, "snake") and snakes.move(10, 2) == (12, None)
    assert snakes.move(98, 4) == (98, None) and snakes.move(94, 6) == (100, None) and snakes.move(95, 3) == (78, "snake"), "100 must be reached exactly"
    assert snakes.move(97, 3) == (100, None) and snakes.move(77, 3) == (100, "ladder") and snakes.move(95, 6) == (95, None)
    assert not set(snakes.LADDERS) & set(snakes.SNAKES) and all(v > k for k, v in snakes.LADDERS.items()) and all(v < k for k, v in snakes.SNAKES.items())
    assert all(1 <= k < 100 for k in list(snakes.LADDERS) + list(snakes.SNAKES)) and all(1 < v <= 100 for v in list(snakes.LADDERS.values()) + list(snakes.SNAKES.values()))
    roll, position, _event = snakes.turn(0, random.Random(4))
    assert 1 <= roll <= 6 and position in (roll, snakes.LADDERS.get(roll, roll))
    drawing = snakes.board([5, 50])
    assert len(drawing.splitlines()) == 10 and "100" in drawing.splitlines()[0] and "Y" in drawing and "C" in drawing
    # a whole game between computers always ends
    rng = random.Random(7)
    positions = [0, 0]
    for turns in range(1, 5000):
        for p in range(2):
            _r, positions[p], _e = snakes.turn(positions[p], rng)
        if 100 in positions:
            break
    assert 100 in positions, "a game must end"

    # ---- the LAN scanner's new features
    lan = load("utilities", "lanscan")
    assert lan.vendor("B8:27:EB:12:34:56") == "Raspberry Pi" and lan.vendor("b8-27-eb-00-00-00") == "Raspberry Pi" and lan.vendor("") == ""
    assert lan.vendor("DA:A1:19:00:00:01").startswith("private address") and lan.vendor("00:11:22:33:44:55") == "" and lan.vendor("zz:zz:zz:00:00:00") == ""
    assert lan.services([22, 80, 4242]) == "22 ssh, 80 http, 4242" and lan.services([]) == ""
    assert lan.guess_kind([9100]) == "printer" and lan.guess_kind([], "Apple") == "Apple device" and lan.guess_kind([3389]).startswith("Windows")
    assert lan.guess_kind([], "Espressif (IoT)").startswith("smart-home") and lan.guess_kind([]) == "" and lan.guess_kind([22]) == "computer/server (SSH)"
    assert lan.parse_ports("22,80,8000-8003") == [22, 80, 8000, 8001, 8002, 8003] and lan.parse_ports("80,80") == [80]
    for bad in ("0", "70000", "abc", "10-5", "", "1-300"):
        assert raises(lambda b=bad: lan.parse_ports(b), ValueError), bad
    options = lan.parse_args(["192.168.0.0/24", "--ports", "22,80", "--sort", "speed", "--up", "--json", "--timeout", "0.2", "--save"])
    assert options["network"] == ipaddress.ip_network("192.168.0.0/24") and options["ports"] == [22, 80] and options["sort"] == "speed"
    assert options["up"] and options["json"] and options["timeout"] == 0.2 and options["save"] and not options["csv"]
    assert lan.parse_args(["--full"])["ports"] == lan.FULL_PORTS and len(lan.FULL_PORTS) == len(set(lan.FULL_PORTS))
    assert lan.parse_args(["--name", "192.168.1.5", "Living", "room", "TV"])["name"] == ("192.168.1.5", "Living room TV")
    for bad in (["--sort", "color"], ["--ports"], ["--bogus"], ["1.2.3.4/24", "5.6.7.8/24"], ["notanet"], ["--name", "192.168.1.5"], ["--timeout", "x"]):
        assert raises(lambda b=bad: lan.parse_args(b), ValueError), bad
    assert lan.allowed(ipaddress.ip_network("192.168.1.0/24")) and not lan.allowed(ipaddress.ip_network("8.8.8.0/24")) and not lan.allowed(ipaddress.ip_network("10.0.0.0/8"))
    assert not lan.allowed(ipaddress.ip_network("127.0.0.0/24")) and not lan.allowed(ipaddress.ip_network("fd00::/64"))

    def device(ip, mac="", name="", ports=(), seconds=None, label=""):
        return {"ip": ip, "mac": mac, "name": name, "ports": list(ports), "seconds": seconds, "label": label, "vendor": "", "kind": ""}
    a, b, c = device("192.168.1.2", "AA:00:00:00:00:01", "alpha", [80], 0.020), device("192.168.1.9", "AA:00:00:00:00:02", "", [], 0.005), device("192.168.1.30", "", "gamma", [22], None)
    assert [d["ip"] for d in lan.order([c, a, b], "ip")] == ["192.168.1.2", "192.168.1.9", "192.168.1.30"]
    assert [d["ip"] for d in lan.order([c, a, b], "speed")] == ["192.168.1.9", "192.168.1.2", "192.168.1.30"], "no answer time sorts last"
    assert [d["ip"] for d in lan.order([c, a, b], "name")][:2] == ["192.168.1.2", "192.168.1.30"], "devices without a name sort last"
    new_a = dict(a, ip="192.168.1.77")                                                # the same device, a new address
    d = device("192.168.1.50", "AA:00:00:00:00:99", "stranger")
    added, gone, moved = lan.compare([a, b], [new_a, d])
    assert [x["ip"] for x in added] == ["192.168.1.50"] and [x["ip"] for x in gone] == ["192.168.1.9"] and [(o["ip"], n["ip"]) for o, n in moved] == [("192.168.1.2", "192.168.1.77")]
    assert lan.compare([a], [a]) == ([], [], []) and lan.identity(c) == "192.168.1.30"
    rows = lan.rows_for([a, c], "192.168.1.30")
    assert rows[0]["ms"] == 20 and rows[1]["ms"] is None and rows[1]["this_device"] is True and rows[0]["name"] == "alpha"
    assert lan.as_csv(rows).splitlines()[0].startswith("ip,this_device,name") and "80" in lan.as_csv(rows).splitlines()[1]
    assert lan.as_csv([]).startswith("ip")
    # remembering names and the last scan, kept in the user's files
    lan.read_arp = lambda: {"192.168.1.5": "AA:BB:CC:00:00:05"}
    assert "Saved" in lan.give_name("192.168.1.5", "Living room TV") and lan.load_json(".lanscan-names.json", {}) == {"AA:BB:CC:00:00:05": "Living room TV"}
    assert "hardware address" in lan.give_name("192.168.1.99", "Nobody") and "not an address" in lan.give_name("tv", "x")
    assert "Removed" in lan.give_name("192.168.1.5", "") and lan.load_json(".lanscan-names.json", {}) == {}
    lan.save_json(".lanscan-last.json", {"when": "now", "devices": [a]})
    assert lan.load_json(".lanscan-last.json", {})["devices"][0]["name"] == "alpha" and lan.load_json(".missing.json", {}) == {}
    # the probe, against a real listening socket on this computer
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(5)
    port = server.getsockname()[1]
    try:
        address, answered, open_ports, seconds = lan.probe("127.0.0.1", [port], 0.5)
        assert answered and open_ports == [port] and seconds is not None and seconds < 0.5
    finally:
        server.close()
    if os.name != "nt":                                        # (Windows takes seconds to refuse a connection; elsewhere it is immediate)
        address, answered, open_ports, seconds = lan.probe("127.0.0.1", [port], 0.5)            # now closed: refused counts as an answer, with no open port
        assert answered and open_ports == [] and seconds is not None
    assert lan.probe("192.0.2.1", [9], 0.05)[1] is False, "nothing answers on the documentation network"
    code = run_main(lan, ["8.8.8.0/24"])
    assert code[0] == 1 and "private" in code[1]
    assert run_main(lan, ["--bogus"])[0] == 1
    print("apps batch 5: all checks passed")


if __name__ == "__main__":
    main()
