#!/usr/bin/env python3
"""The marketplace catalog in other languages: tools/translate_apps.py (what is translated, what is kept, when a text is translated again), the client
side (pyos/appi18n.py and the marketplace program showing the words), and that the catalogs list their languages. A fake translation engine is used;
nothing is downloaded."""
import io
import json
import os
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tools"))
os.chdir(REPO)
os.environ["PYOS_BUNDLED"] = "1"

import translate_apps as ta  # noqa: E402
import translate_ci  # noqa: E402
from pyos import appi18n  # noqa: E402


class Fake:
    """Translates by shouting (so it differs from the English and keeps the protected tokens)."""
    def __init__(self, ramble=False):
        self.calls, self.ramble = [], ramble

    def translate(self, text, code):
        self.calls.append((text, code))
        return (text.upper() + " " + text.upper() + " ") * 30 if self.ramble else text.upper()

    def back(self, text, code):
        return text


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(data if isinstance(data, str) else json.dumps(data))


def main():
    tmp = tempfile.mkdtemp(prefix="pyos-appi18n-")
    write(os.path.join(tmp, "utilities", "hn", "data.json"), {"name": "Hacker News", "description": "The top stories of Hacker News."})
    write(os.path.join(tmp, "games", "snake", "data.json"), {"name": "Snake", "description": "Eat apples, grow longer."})
    write(os.path.join(tmp, "games", "nodesc", "data.json"), {"name": "No description"})
    write(os.path.join(tmp, "categories.json"), [{"id": "tools", "title": "Tools", "blurb": "Everyday helpers"}, {"id": "games", "title": "Games", "blurb": ""}])
    apps, categories = ta.sources(tmp)
    assert apps == {"utilities/hn": "The top stories of Hacker News.", "games/snake": "Eat apples, grow longer."}, apps
    assert categories["tools"] == {"title": "Tools", "blurb": "Everyday helpers"}
    assert ta.LANGUAGES == ["es", "fr", "de"]

    out = os.path.join(tmp, "i18n")
    state = {code: ta.load(code, out) for code in ta.LANGUAGES}
    engine = Fake()
    result, report = ta.run(lambda codes: engine, apps, categories, state)
    for code in ta.LANGUAGES:
        assert result[code]["apps"]["games/snake"]["description"] == "EAT APPLES, GROW LONGER." and result[code]["apps"]["games/snake"]["from"] == ta.fingerprint("Eat apples, grow longer.")
        assert result[code]["categories"]["tools"]["title"] == "TOOLS" and result[code]["categories"]["tools"]["blurb"] == "EVERYDAY HELPERS"
        assert "blurb" not in result[code]["categories"]["games"], "an empty text is not translated"
        assert report[code]["added"] == 5 and not report[code]["thrown_away"]
    assert not any("Hacker News" == text for text, _c in engine.calls), "names are not sent to the engine as texts of their own"

    # written out, then a second run has nothing to do (and the file does not change)
    for code in ta.LANGUAGES:
        write(os.path.join(out, f"{code}.json"), ta.render(code, result[code]))
    again = {code: ta.load(code, out) for code in ta.LANGUAGES}
    engine2 = Fake()
    result2, report2 = ta.run(lambda codes: engine2, apps, categories, again)
    assert engine2.calls == [] and all(r["added"] == 0 and r["todo"] == 0 for r in report2.values())
    assert all(ta.render(c, result2[c]) == ta.render(c, result[c]) for c in ta.LANGUAGES), "running it twice changes nothing"
    assert json.loads(ta.render("es", result["es"]))["language"] == "es" and list(json.loads(ta.render("es", result["es"]))["apps"]) == ["games/snake", "utilities/hn"], "fixed order"

    # the English changes: translated again; an app that is gone: dropped; a correction by a person: kept, never touched
    changed = dict(apps, **{"games/snake": "Eat apples, grow longer, avoid the walls."})
    write(os.path.join(out, "corrections.json"), {"es": {"apps": {"utilities/hn": {"description": "Lo mejor de Hacker News."}}, "categories": {"tools": {"title": "Utilidades"}}}})
    state3 = {code: ta.load(code, out) for code in ta.LANGUAGES}
    engine3 = Fake()
    result3, report3 = ta.run(lambda codes: engine3, changed, categories, state3)
    assert [t for t, c in engine3.calls if c == "es"] == ["Eat apples, grow longer, avoid the walls."], engine3.calls
    assert result3["es"]["apps"]["games/snake"]["description"].startswith("EAT APPLES, GROW LONGER, AVOID")
    only_snake = {"games/snake": changed["games/snake"]}
    result4, report4 = ta.run(lambda codes: Fake(), only_snake, categories, state3)
    assert "utilities/hn" not in result4["fr"]["apps"] and report4["fr"]["dropped"] == 1
    # the person's words win when a client merges
    es = ta.merged("es", out)
    assert es["apps"]["utilities/hn"]["description"] == "Lo mejor de Hacker News." and es["categories"]["tools"]["title"] == "Utilidades" and es["categories"]["tools"]["blurb"] == "EVERYDAY HELPERS"
    # a result that rambles is thrown away and the English is used
    result5, report5 = ta.run(lambda codes: Fake(ramble=True), {"games/snake": "Eat apples."}, {}, {c: ({"apps": {}, "categories": {}}, {"apps": {}, "categories": {}}) for c in ta.LANGUAGES})
    assert report5["es"]["thrown_away"] and "games/snake" not in result5["es"]["apps"]
    assert "left in English" in ta.summary(report5) and "es" in ta.summary(report5)
    # nothing to do without files: --check says what is missing
    assert ta.plan(apps, categories, {"apps": {}, "categories": {}}, {"apps": {}, "categories": {}})

    # ---- the client
    table = appi18n.merge({"apps": {"a/x": {"description": "Hola", "from": "123"}, "a/y": {"description": "  "}}, "categories": {"tools": {"title": "Utilidades", "blurb": "Ayuda", "title_from": "1"}}},
                          {"apps": {"a/x": {"description": "Hola de nuevo"}}})
    assert table == {"apps": {"a/x": {"description": "Hola de nuevo"}, "a/y": {}}, "categories": {"tools": {"title": "Utilidades", "blurb": "Ayuda"}}}, table
    packages = [{"id": "a/x", "name": "X", "description": "Hello"}, {"id": "a/z", "name": "Z", "description": "Zed"}]
    cats = [{"id": "tools", "title": "Tools", "blurb": "Helpers"}, {"id": "other", "title": "Other"}]
    assert appi18n.attach(packages, cats, table) == 1
    assert appi18n.description(packages[0]) == "Hola de nuevo" and appi18n.description(packages[1]) == "Zed" and packages[0]["description"] == "Hello"
    assert appi18n.category_words(cats[0]) == ("Utilidades", "Ayuda") and appi18n.category_words(cats[1]) == ("Other", "")
    cache = os.path.join(tmp, "cache.json")
    assert appi18n.load_cached(cache, "es") is None
    appi18n.save_cached(cache, "es", table)
    assert appi18n.load_cached(cache, "es") == table and appi18n.load_cached(cache, "fr") is None
    assert appi18n.attach(None, None, None) == 0

    # the marketplace program: fetches the files for the language, shows the words, keeps searching by the English, and works offline from the cache
    from rich.console import Console

    from pyos import i18n
    from programs import marketplace as market
    fetched = []

    class Reply:
        def __init__(self, data):
            self.data = data

        def json(self):
            return self.data
    files = {"es.json": {"apps": {"a/x": {"description": "Hola mundo", "from": "1"}}, "categories": {"tools": {"title": "Herramientas"}}},
             "corrections.json": {"es": {"apps": {"a/x": {"description": "Hola, mundo corregido"}}}, "fr": {}}}

    def fake_get(url):
        fetched.append(url)
        name = url.rsplit("/", 1)[-1]
        if name not in files:
            raise market.requests.ConnectionError("down")
        return Reply(files[name])
    real_get, real_language, real_cache = market.http_get, i18n.language, market.I18N_CACHE
    market.http_get, market.I18N_CACHE = fake_get, __import__("pathlib").Path(tmp) / "market-i18n.json"
    try:
        i18n.language = lambda: "en"
        pk = [{"id": "a/x", "name": "X", "description": "Hello world", "tags": [], "category": "tools"}]
        ct = [{"id": "tools", "title": "Tools"}]
        market.translate_catalog(pk, ct, {"languages": ["es", "fr", "de"]})
        assert fetched == [] and "description_local" not in pk[0], "English: nothing is fetched"
        i18n.language = lambda: "es"
        market.translate_catalog(pk, ct, {"languages": ["es", "fr", "de"]})
        assert fetched == [f"{market.RAW_BASE}/i18n/es.json", f"{market.RAW_BASE}/i18n/corrections.json"], fetched
        assert pk[0]["description_local"] == "Hola, mundo corregido" and ct[0]["title_local"] == "Herramientas" and pk[0]["description"] == "Hello world"
        # an older catalog that lists no languages: nothing is asked for (and nothing breaks), the last copy is used if there is one
        fetched.clear()
        fresh = [{"id": "a/x", "name": "X", "description": "Hello world", "tags": [], "category": "tools"}]
        market.translate_catalog(fresh, [], {})
        assert fetched == [] and fresh[0]["description_local"] == "Hola, mundo corregido", "offline: the cached words"
        # the screens
        out = io.StringIO()
        market.console = Console(file=out, force_terminal=False, width=160)
        market.CATALOG["categories"] = ct
        pk[0].update({"version": "1.0.0", "files": [], "categories": ["tools"], "command": "x"})
        market.show_packages(pk, {}, "Apps")
        text = out.getvalue()
        assert "Hola, mundo corregido" in text and "Herramientas" in text and "Hello world" not in text
        assert market.search(pk, "hello") and market.search(pk, "mundo"), "found by the English and by the translated words"
        out.truncate(0)
        market.show_details(pk[0], {})
        assert "Hola, mundo corregido" in out.getvalue()
        # a failed download keeps the English and does not raise
        files.clear()
        broken = [{"id": "a/q", "name": "Q", "description": "Quiet", "tags": [], "category": "tools"}]
        market.I18N_CACHE = __import__("pathlib").Path(tmp) / "nothing.json"
        market.translate_catalog(broken, [], {"languages": ["es"]})
        assert "description_local" not in broken[0]
    finally:
        market.http_get, i18n.language, market.I18N_CACHE = real_get, real_language, real_cache

    # the catalogs list the languages the files cover (every API), and the real files are consistent
    for name in ("index.json", "index-api1.json", "index-api2.json"):
        with open(os.path.join(REPO, "online_packages", name), encoding="utf-8") as f:
            index = json.load(f)
        present = sorted(n[:-5] for n in os.listdir(os.path.join(REPO, "online_packages", "i18n")) if n.endswith(".json") and n != "corrections.json") if os.path.isdir(os.path.join(REPO, "online_packages", "i18n")) else []
        assert index.get("languages", []) == present, (name, index.get("languages"), present)
    print("marketplace translations: all checks passed")


if __name__ == "__main__":
    main()
