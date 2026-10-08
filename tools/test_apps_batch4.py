#!/usr/bin/env python3
"""Checks the apps added in 1.0.13 that use libraries and web services: holidays, phone, cronwhen, mockdata, sunmoon, iss, quake, books, pokedex, pypi.

Nothing is downloaded and no network is used: the libraries that are not installed here are replaced by small stand-ins that behave the way the
real ones are documented to, and the web services by canned answers, so this checks the apps' own logic (reading the answers, the arguments, the
output), not the services. Only the plain functions and main() are called."""
import datetime
import importlib.util
import io
import os
import sys
import types

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def load(kind, name):
    spec = importlib.util.spec_from_file_location("app4_" + name, os.path.join(REPO, "online_packages", kind, name, "run.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Reply:
    def __init__(self, data, status=200):
        self.data, self.status_code = data, status

    def json(self):
        return self.data

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(str(self.status_code))


def run_main(module, argv, replies=None):
    """main(argv) with the screen captured and requests.get answering from `replies` (a function of the URL). -> (exit code, text)."""
    import requests
    from rich.console import Console
    out = io.StringIO()
    module.console = Console(file=out, force_terminal=False, width=120)
    real_get, real_stdout = requests.get, sys.stdout
    if replies is not None:
        requests.get = lambda url, **kw: replies(url, kw)
    sys.stdout = out
    try:
        code = module.main(argv)
    finally:
        requests.get, sys.stdout = real_get, real_stdout
    return code, out.getvalue()


def main():
    # ---- holidays (the library replaced by a stand-in)
    stub = types.ModuleType("holidays")

    def country_holidays(code, subdiv=None, years=None):
        if code == "ZZ":
            raise NotImplementedError(code)
        return {datetime.date(years, 1, 1): "New Year's Day", datetime.date(years, 7, 4): "Independence Day", datetime.date(years, 12, 25): "Christmas Day"}
    stub.country_holidays = country_holidays
    stub.list_supported_countries = lambda: {"US": ["CA", "NY"], "GB": []}
    sys.modules["holidays"] = stub
    holi = load("utilities", "holidays")
    assert [n for _d, n in holi.year_list(stub, "us", 2026)] == ["New Year's Day", "Independence Day", "Christmas Day"]
    assert holi.next_holiday(stub, "US", datetime.date(2026, 7, 5)) == (datetime.date(2026, 12, 25), "Christmas Day")
    assert holi.next_holiday(stub, "US", datetime.date(2026, 12, 26)) == (datetime.date(2027, 1, 1), "New Year's Day"), "looks into next year"
    assert holi.next_holiday(stub, "US", datetime.date(2026, 7, 4))[0] == datetime.date(2026, 7, 4), "today counts"
    assert holi.parse_args(["US", "2027"])[:2] == ("US", 2027) and holi.parse_args(["DE", "next"])[3] == "next"
    assert holi.parse_args(["FR", "2026-07-14"])[2] == datetime.date(2026, 7, 14) and holi.parse_args(["US", "--state", "CA"])[4] == "CA"
    assert holi.parse_args(["--countries"])[3] == "countries"
    try:
        holi.parse_args([])
        raise AssertionError("a country is needed")
    except ValueError:
        pass
    code, text = run_main(holi, ["US", "2026"])
    assert code == 0 and "Independence Day" in text and "04 Jul" in text
    code, text = run_main(holi, ["US", "2026-07-04"])
    assert code == 0 and "Independence Day" in text
    code, text = run_main(holi, ["US", "2026-07-05"])
    assert "not a public holiday" in text
    code, text = run_main(holi, ["ZZ"])
    assert code == 1 and "do not know" in text
    assert run_main(holi, ["--countries"])[1].split() == ["GB", "US"]

    # ---- phone (a stand-in for phonenumbers, passed in as the `libs` tuple)
    phone = load("utilities", "phone")
    assert phone.split_args(["+44", "20", "7946", "0958"]) == ("+44 20 7946 0958", None)
    assert phone.split_args(["020", "7946", "0958", "gb"]) == ("020 7946 0958", "GB")
    assert phone.split_args(["415", "--json"]) == ("415", None), "--json is not part of the number"

    class ParseError(Exception):
        def __init__(self, name):
            self.error_type = types.SimpleNamespace(name=name)
    fmt = types.SimpleNamespace(INTERNATIONAL=1, NATIONAL=2, E164=3)
    pn = types.SimpleNamespace(
        NumberParseException=ParseError, PhoneNumberFormat=fmt,
        parse=lambda text, region: (_ for _ in ()).throw(ParseError("NOT_A_NUMBER")) if "x" in text else text,
        number_type=lambda n: types.SimpleNamespace(name="FIXED_LINE_OR_MOBILE"), is_valid_number=lambda n: True, is_possible_number=lambda n: True,
        format_number=lambda n, f: {1: "+44 20 7946 0958", 2: "020 7946 0958", 3: "+442079460958"}[f], region_code_for_number=lambda n: "GB")
    libs = (pn, types.SimpleNamespace(name_for_number=lambda n, lang: ""), types.SimpleNamespace(description_for_number=lambda n, lang: "London"),
            types.SimpleNamespace(time_zones_for_number=lambda n: ("Europe/London",)))
    info = phone.describe(libs, "020 7946 0958", "GB")
    assert info["valid"] and info["international"] == "+44 20 7946 0958" and info["place"] == "London" and info["type"] == "fixed line or mobile"
    try:
        phone.describe(libs, "xyz", "GB")
        raise AssertionError("not a number")
    except ValueError as e:
        assert "does not look like" in str(e)

    # ---- cronwhen (stand-ins for cron-descriptor and croniter)
    cron = load("utilities", "cronwhen")
    assert cron.normalise("  @daily ") == "0 0 * * *" and cron.normalise("*/5   * * * *") == "*/5 * * * *"
    try:
        cron.normalise("* * *")
        raise AssertionError("five fields")
    except ValueError:
        pass
    assert cron.parse(["*/5", "*", "*", "*", "*", "-n", "3"]) == ("*/5 * * * *", 3)
    sys.modules["cron_descriptor"] = types.SimpleNamespace(get_description=lambda e: "Every 5 minutes")

    class Croniter:
        def __init__(self, expression, start):
            self.t = start

        def get_next(self, kind):
            self.t += datetime.timedelta(minutes=5)
            return self.t
    sys.modules["croniter"] = types.SimpleNamespace(croniter=Croniter)
    assert cron.explain("*/5 * * * *") == "Every 5 minutes"
    times = cron.upcoming("*/5 * * * *", 3, datetime.datetime(2026, 1, 1, 0, 0))
    assert times[0] == datetime.datetime(2026, 1, 1, 0, 5) and len(times) == 3
    assert len(cron.upcoming("@daily", 500)) == 50, "capped"
    code, text = run_main(cron, ["*/5", "*", "*", "*", "*", "-n", "2"])
    assert code == 0 and "Every 5 minutes" in text
    assert run_main(cron, ["* *"])[0] == 1

    # ---- mockdata (a stand-in for Faker)
    mock = load("utilities", "mockdata")

    class Fake:
        def __getattr__(self, name):
            return lambda: f"{name}-value\nline2" if name == "address" else f"{name}-value"
    assert mock.make(Fake(), "name", 3) == ["name-value"] * 3 and mock.make(Fake(), "text", 1) == ["paragraph-value"]
    person = mock.make(Fake(), "person", 2)
    assert len(person) == 2 and person[0]["address"] == "address-value, line2" and set(person[0]) == {"name", "email", "phone", "address", "company", "job"}
    try:
        mock.make(Fake(), "shoe", 1)
        raise AssertionError("unknown kind")
    except ValueError as e:
        assert "Kinds:" in str(e)
    assert len(mock.make(Fake(), "name", 9999)) == 200, "capped"
    assert mock.parse(["email", "3", "--locale", "de_DE", "--seed", "7"]) == ("email", 3, {"locale": "de_DE", "seed": 7, "csv": False})
    assert mock.to_csv(person).splitlines()[0] == "name,email,phone,address,company,job"

    class Faker(Fake):
        seeded = None

        def __init__(self, locale):
            if locale == "xx_XX":
                raise AttributeError(locale)

        @classmethod
        def seed(cls, n):
            cls.seeded = n
    sys.modules["faker"] = types.SimpleNamespace(Faker=Faker)
    code, text = run_main(mock, ["name", "2", "--seed", "5"])
    assert code == 0 and text.count("name-value") == 2 and Faker.seeded == 5
    assert run_main(mock, ["name", "--locale", "xx_XX"])[0] == 1 and run_main(mock, ["name", "x"])[0] == 1

    # ---- sunmoon
    sun = load("utilities", "sunmoon")
    assert [sun.phase_name(v)[0] for v in (0, 3, 7, 10, 14, 17, 21, 24, 27.9)] == [
        "New moon", "Waxing crescent", "First quarter", "Waxing gibbous", "Full moon", "Waning gibbous", "Last quarter", "Waning crescent", "New moon"]
    assert sun.lit_percent(0) == 0 and sun.lit_percent(14) == 100 and sun.lit_percent(7) == 50
    assert sun.day_length(datetime.datetime(2026, 6, 21, 4, 43), datetime.datetime(2026, 6, 21, 21, 21)) == "16h 38m"
    assert sun.parse(["new", "york", "2026-12-21", "--week"]) == ("new york", datetime.date(2026, 12, 21), True)
    try:
        sun.parse([])
        raise AssertionError("a city is needed")
    except ValueError:
        pass

    # ---- iss
    iss = load("utilities", "iss")
    reading = {"latitude": -12.5, "longitude": 130.25, "altitude": 418.6, "velocity": 27580.4, "visibility": "daylight", "timestamp": 1790000000}
    lines = iss.describe(reading)
    assert "12.50° S, 130.25° E" in lines[0] and "419 km" in lines[1] and "27,580 km/h" in lines[2] and "daylight" in lines[3]
    code, text = run_main(iss, [], lambda url, kw: Reply(reading))
    assert code == 0 and "130.25° E" in text
    import requests
    code, text = run_main(iss, [], lambda url, kw: (_ for _ in ()).throw(requests.ConnectionError("down")))
    assert code == 1 and "Could not read" in text
    assert run_main(iss, ["--watch", "x"])[0] == 1

    # ---- quake
    quake = load("utilities", "quake")
    feed = {"features": [
        {"properties": {"mag": 4.6, "place": "10 km N of Somewhere", "time": 1790000000000, "url": "u1"}, "geometry": {"coordinates": [10.5, 20.5, 35.2]}},
        {"properties": {"mag": 6.1, "place": "Offshore", "time": 1790003600000, "url": "u2"}, "geometry": {"coordinates": [1, 2, 10]}},
        {"properties": {"mag": None, "place": "no magnitude"}, "geometry": {"coordinates": [0, 0, 0]}},
        {"properties": {"mag": 2.0, "place": "tiny"}, "geometry": {"coordinates": [0, 0]}}]}
    rows = quake.parse(feed)
    assert [r[0] for r in rows] == [6.1, 4.6, 2.0] and rows[1][2] == 35.2 and rows[2][2] == 0
    assert [r[0] for r in quake.parse(feed, 4.5)] == [6.1, 4.6]
    assert quake.feed_url().endswith("significant_week.geojson") and quake.feed_url("month", 5).endswith("4.5_month.geojson")
    assert quake.feed_url("day").endswith("2.5_day.geojson") and quake.feed_url("day", 0.5).endswith("all_day.geojson")
    try:
        quake.feed_url("year")
        raise AssertionError("bad period")
    except ValueError:
        pass
    code, text = run_main(quake, ["day", "4"], lambda url, kw: Reply(feed))
    assert code == 0 and "Offshore" in text and "tiny" not in text and "6.1" in text
    assert run_main(quake, ["fortnight"])[0] == 1

    # ---- books
    books = load("utilities", "books")
    params, count = books.build_query(["dune", "-n", "5"])
    assert params["title"] == "dune" and params["limit"] == 5 and count == 5
    assert books.build_query(["--author", "J.", "Tolkien"])[0]["author"] == "J. Tolkien" and books.build_query(["--isbn", "123"])[0]["isbn"] == "123"
    assert books.build_query(["x", "-n", "500"])[1] == 30, "capped"
    try:
        books.build_query([])
        raise AssertionError("nothing to look for")
    except ValueError:
        pass
    answer = {"docs": [{"title": "Dune", "author_name": ["Frank Herbert"], "first_publish_year": 1965, "number_of_pages_median": 412, "edition_count": 120},
                       {"author_name": ["nobody"]}, {"title": "Dune Messiah"}]}
    found = books.parse(answer)
    assert [b["title"] for b in found] == ["Dune", "Dune Messiah"] and found[1]["authors"] == "unknown" and found[0]["year"] == 1965
    code, text = run_main(books, ["dune"], lambda url, kw: Reply(answer))
    assert code == 0 and "Frank Herbert" in text and "1965" in text
    code, text = run_main(books, ["zzzz"], lambda url, kw: Reply({"docs": []}))
    assert code == 0 and "Nothing found" in text

    # ---- pokedex
    pokedex = load("games", "pokedex")
    pokemon = {"name": "mr-mime", "id": 122, "height": 13, "weight": 545, "types": [{"type": {"name": "psychic"}}, {"type": {"name": "fairy"}}],
               "abilities": [{"ability": {"name": "soundproof"}}, {"ability": {"name": "filter"}, "is_hidden": True}],
               "stats": [{"stat": {"name": "hp"}, "base_stat": 40}, {"stat": {"name": "special-attack"}, "base_stat": 100}]}
    species = {"flavor_text_entries": [{"language": {"name": "fr"}, "flavor_text": "bonjour"},
                                       {"language": {"name": "en"}, "flavor_text": "A\fclown that\nmimes."}]}
    info = pokedex.describe(pokemon, species)
    assert info["height"] == 1.3 and info["weight"] == 54.5 and info["types"] == ["psychic", "fairy"]
    assert info["abilities"] == ["soundproof", "filter (hidden)"] and info["stats"] == [("HP", 40), ("Sp. Attack", 100)]
    assert info["entry"] == "A clown that mimes." and pokedex.entry_text(None) == ""
    assert pokedex.bar(0) == "░" * 20 and pokedex.bar(255) == "█" * 20

    def pokeapi(url, kw):
        return Reply(species if "species" in url else pokemon) if url.endswith(("/122", "mr-mime")) or "species/122" in url else Reply({}, 404)
    code, text = run_main(pokedex, ["Mr", "Mime"], pokeapi)
    assert code == 0 and "#122 Mr Mime" in text and "clown" in text and "Sp. Attack" in text
    code, text = run_main(pokedex, ["nothingmon"], pokeapi)
    assert code == 1 and "No Pokemon" in text

    # ---- pypi
    pypi = load("utilities", "pypi")
    assert pypi.url_for("requests") == "https://pypi.org/pypi/requests/json" and pypi.url_for("requests", "2.31.0").endswith("/2.31.0/json")
    for bad in ("../etc", "a b", ""):
        try:
            pypi.url_for(bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    package = {"info": {"name": "demo", "version": "2.0", "summary": "A demo", "license": "MIT", "requires_python": ">=3.8", "author": "Ada",
                        "project_urls": {"Home": "https://example.org"}, "requires_dist": ["rich>=13", "pytest ; extra == 'test'", "idna ; python_version < '3.9'"]},
               "releases": {"1.0": [{"upload_time_iso_8601": "2025-01-02T00:00:00Z"}], "2.0": [{"upload_time_iso_8601": "2026-03-04T00:00:00Z"}],
                            "0.9": [{"upload_time_iso_8601": "2024-05-06T00:00:00Z", "yanked": True}], "0.1": []}}
    facts = pypi.parse(package)
    assert facts["requires"] == ["rich>=13", "idna"] and facts["recent"] == [("2.0", "2026-03-04"), ("1.0", "2025-01-02")] and facts["releases"] == 4
    assert facts["licence"] == "MIT" and facts["python"] == ">=3.8" and facts["home"] == "https://example.org"
    code, text = run_main(pypi, ["demo"], lambda url, kw: Reply(package))
    assert code == 0 and "demo 2.0" in text and "pip install demo" in text and "rich>=13" in text
    code, text = run_main(pypi, ["nope"], lambda url, kw: Reply({}, 404))
    assert code == 1 and "No package" in text
    assert run_main(pypi, [])[0] == 1 and run_main(pypi, ["../x"], lambda url, kw: Reply({}))[0] == 1
    print("apps batch 4: all checks passed")


if __name__ == "__main__":
    main()
