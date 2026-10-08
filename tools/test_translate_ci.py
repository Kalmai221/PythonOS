#!/usr/bin/env python3
"""The translation workflow's script (tools/translate_ci.py), with a fake translation engine: placeholders and protected words survive, results
that lost something or mean something else are thrown away, a person's translation always wins, old machine texts are dropped, the file is
written in a fixed order, and running it twice changes nothing. Nothing is downloaded and no real engine is used."""
import os
import re
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO_ROOT)
sys.path.insert(0, os.path.join(REPO_ROOT, "tools"))

import translate_ci as t  # noqa: E402

WORDS = {"hello": "hola", "world": "mundo", "files": "archivos", "removed": "eliminados", "report": "informe", "bug": "error", "not": "no",
         "found": "encontrado", "an": "un", "unexpected": "inesperado", "has": "ha", "been": "sido", "the": "el", "of": "de", "with": "con"}


class FakeEngine(t.Engine):
    """Translates the words it knows into 'Spanish' and back; keeps tokens unless told to mangle them."""

    def __init__(self, mangle=None, wrong_back=False):
        self.mangle, self.wrong_back, self.calls = mangle, wrong_back, []

    def _map(self, text, table):
        return re.sub(r"[A-Za-z]+", lambda m: table.get(m.group(0).lower(), m.group(0)), text)

    def translate(self, text, code):
        self.calls.append(text)
        out = self._map(text, WORDS)
        return self.mangle(out) if self.mangle else out

    def back(self, text, code):
        if self.wrong_back:
            return "completely different sentence here"
        return self._map(text, {v: k for k, v in WORDS.items()})


def factory(engine):
    return lambda codes: engine


def main():
    # protection: placeholders, <arguments>, key letters, flags, file names, command names and versions come back exactly
    sample = "Run pkg install <name> with --fix, see {n} files in config.json (a) allow, PythonOS 1.0.13"
    for fmt in t.TOKEN_FORMATS:
        masked, parts = t.protect(sample, fmt)
        assert parts == ["pkg", "<name>", "--fix", "{n}", "config.json", "(a)", "PythonOS", "1.0.13"], parts
        assert "{n}" not in masked and "<name>" not in masked and "--fix" not in masked
        assert t.restore(masked, parts, fmt) == sample
        assert t.restore(masked.replace(fmt.format(n=3), ""), parts, fmt) is None, "a lost token is detected"
        assert t.restore(masked + fmt.format(n=0), parts, fmt) is None, "a doubled token is detected"

    # what is worth translating: not text that is only tokens or a few letters
    assert not t.worth_translating(t.protect("(n)o", t.TOKEN_FORMATS[0])[0])
    assert not t.worth_translating(t.protect("{n}", t.TOKEN_FORMATS[0])[0])
    assert t.worth_translating(t.protect("hello world {n}", t.TOKEN_FORMATS[0])[0])

    # one message: translated with the placeholder intact
    engine = FakeEngine()
    text, why = t.translate_one(engine, "hello world {n}", "es")
    assert text == "hola mundo {n}" and why is None, (text, why)
    assert "{n}" not in engine.calls[0], "the engine never saw the placeholder"
    # an engine that eats the first kind of token: the next kind is tried
    first_kind = t.TOKEN_FORMATS[0]
    eats_first = FakeEngine(mangle=lambda s: s.replace(first_kind.format(n=0), ""))
    text, why = t.translate_one(eats_first, "removed {n} files", "es")
    assert text == "eliminados {n} archivos" and len(eats_first.calls) == 2, (text, eats_first.calls)
    # an engine that eats every token kind: thrown away, the English stays
    eats_all = FakeEngine(mangle=lambda s: re.sub(r"⟦\d+⟧|XQ\d+Z|\[\d+\]", "", s))
    text, why = t.translate_one(eats_all, "removed {n} files", "es")
    assert text is None and "must stay" in why
    # a result that means something else when translated back is thrown away
    text, why = t.translate_one(FakeEngine(wrong_back=True), "hello world", "es")
    assert text is None and "translated back" in why
    # an unchanged result and a failing engine are thrown away too
    text, why = t.translate_one(FakeEngine(), "Zzz Qqq", "es")
    assert text is None and "unchanged" in why

    class Broken(t.Engine):
        def translate(self, text, code):
            raise RuntimeError("model missing")
    assert t.translate_one(Broken(), "hello world", "es") == (None, "the engine failed (RuntimeError)")

    # the plan: a person's text is never retranslated, an existing machine text is kept, a message that is gone is dropped
    keys = ["hello world", "removed {n} files", "report the bug", "the files"]
    human = {"es": {"hello world": "HOLA A MANO"}, "fr": {}, "de": {}}
    auto = {"es": {"removed {n} files": "old machine text", "gone message": "x", "hello world": "machine copy of a text a person now has"}, "fr": {}, "de": {}}
    todo, drop = t.plan(keys, human, auto)
    assert todo["es"] == ["report the bug", "the files"] and sorted(drop["es"]) == ["gone message", "hello world"], (todo, drop)
    assert todo["fr"] == keys

    # a whole run: only what is missing is translated, the report counts it, and a person's catalog is untouched
    engine = FakeEngine()
    result, report = t.run(factory(engine), keys, human, auto)
    assert result["es"] == {"removed {n} files": "old machine text", "report the bug": "informe el error", "the files": "el archivos"}, result["es"]
    assert report["es"]["added"] == 2 and report["es"]["dropped"] == 2
    assert human["es"] == {"hello world": "HOLA A MANO"}
    assert not any("old machine text" in c for c in engine.calls)
    # messages the engine cannot do safely stay out of the file and are listed in the report
    result, report = t.run(factory(FakeEngine(wrong_back=True)), ["hello world"], {c: {} for c in t.LANGUAGES}, {c: {} for c in t.LANGUAGES})
    assert result["es"] == {} and report["es"]["thrown_away"] and "translated back" in report["es"]["thrown_away"][0][1]
    # a dry run translates nothing
    engine = FakeEngine()
    result, report = t.run(factory(engine), keys, human, auto, dry_run=True)
    assert engine.calls == [] and report["es"]["todo"] == 2

    # the file: fixed order, valid Python, and a second run changes nothing
    catalogs = {"es": {"b": "B", "a": 'A "quoted"\nline'}, "fr": {}, "de": {"é": "ü"}}
    text = t.render(catalogs)
    assert text == t.render({"es": {"a": 'A "quoted"\nline', "b": "B"}, "fr": {}, "de": {"é": "ü"}}), "the order does not depend on how it was built"
    namespace = {}
    exec(compile(text, "locales_auto.py", "exec"), namespace)                            # nosec - text this test just made
    assert namespace["ES"] == catalogs["es"] and namespace["DE"] == {"é": "ü"} and namespace["FR"] == {}
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "locales_auto.py")
        assert t.load_auto(path) == {"es": {}, "fr": {}, "de": {}}, "no file yet"
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        assert t.load_auto(path)["es"] == catalogs["es"]
        again, _ = t.run(factory(FakeEngine()), ["a", "b", "é"], {c: {} for c in t.LANGUAGES}, t.load_auto(path))
        assert again["es"] == catalogs["es"] and t.render(again) == text, "nothing to do: the same file"

    # the summary names what was left in English
    out = t.summary({"es": {"added": 3, "dropped": 1, "thrown_away": [("bad {n}", "its {placeholders} differ")], "todo": 4}})
    assert "**es**: 3 added, 1 dropped, 1 left in English (of 4 to do)" in out and "bad {n}" in out

    # the real catalogs: a person's text wins over a machine one, and a missing text falls back to the machine one
    from pyos import locales
    assert set(locales.HUMAN) == {"es", "fr", "de"} and all(locales.HUMAN[c] for c in locales.HUMAN)
    import pyos.locales_auto as auto_module
    for code, name in t.LANGUAGES.items():
        for key, value in getattr(auto_module, name).items():
            assert key not in locales.HUMAN[code], f"{code}: {key[:50]!r} is in the generated file but a person has translated it"
            assert locales.CATALOGS[code][key] == value
    print("translation workflow script: all checks passed")


if __name__ == "__main__":
    main()
