#!/usr/bin/env python3
"""Machine-translates the marketplace catalog's texts: what each app is (its description) and the category titles and blurbs. Meant to run in CI
(.github/workflows/translations.yml, and the translate job of build-os.yml), which opens a pull request with the result; PythonOS never runs it.

    python tools/translate_apps.py                  translate what is missing or changed and write online_packages/i18n/<language>.json
    python tools/translate_apps.py --dry-run        only say what would be translated
    python tools/translate_apps.py --check          exit 1 when a language file is out of date (for the website and release checks)
    python tools/translate_apps.py --summary FILE   also write the pull request text to FILE

The files are for every marketplace API at once: the catalogs (index.json, index-api1.json, index-api2.json) say which languages exist (a "languages"
list), and the marketplace of any PythonOS reads online_packages/i18n/<language>.json next to them. An older PythonOS simply never asks.

  * app names are not translated (they are names: "Pokedex", "xkcd", "Hacker News"); descriptions and category texts are
  * a text written by a person in online_packages/i18n/corrections.json always wins and is never touched
  * each translated text remembers a short fingerprint of the English it came from ("from"), so a changed English description is translated again
  * the engine and the safety checks are those of tools/translate_ci.py (placeholders and command names are protected; a result that rambles or
    comes back unchanged is thrown away and stays English)
"""
import argparse
import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import translate_ci  # noqa: E402

CATALOG = os.path.join(ROOT, "online_packages")
OUT = os.path.join(CATALOG, "i18n")
LANGUAGES = list(translate_ci.LANGUAGES)                 # es, fr, de (the languages PythonOS has, without English)


def fingerprint(text):
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]


def sources(catalog=CATALOG):
    """({app id: description}, {category id: {title, blurb}}) in English, read from every app's data.json and categories.json."""
    apps = {}
    for kind in sorted(os.listdir(catalog)):
        folder = os.path.join(catalog, kind)
        if not os.path.isdir(folder) or kind == "i18n":
            continue
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name, "data.json")
            if os.path.isfile(path):
                with open(path, encoding="utf-8") as f:
                    meta = json.load(f)
                if str(meta.get("description", "")).strip():
                    apps[f"{kind}/{name}"] = str(meta["description"]).strip()
    categories = {}
    path = os.path.join(catalog, "categories.json")
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            for c in json.load(f):
                categories[c["id"]] = {"title": c.get("title", ""), "blurb": c.get("blurb", "")}
    return apps, categories


def load(code, out=OUT):
    """(generated, corrections) for a language: dicts shaped {"apps": {id: {...}}, "categories": {id: {...}}}."""
    def read(path):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}
    generated = read(os.path.join(out, f"{code}.json"))
    corrections = read(os.path.join(out, "corrections.json")).get(code, {})
    return {"apps": dict(generated.get("apps", {})), "categories": dict(generated.get("categories", {}))}, {
        "apps": dict(corrections.get("apps", {})), "categories": dict(corrections.get("categories", {}))}


def plan(apps, categories, generated, corrections):
    """[(kind, id, field, English text)] that need translating for one language: nothing a person corrected, nothing whose English is unchanged."""
    todo = []
    for app_id, text in apps.items():
        if "description" in corrections["apps"].get(app_id, {}):
            continue
        if generated["apps"].get(app_id, {}).get("from") != fingerprint(text):
            todo.append(("apps", app_id, "description", text))
    for cat_id, fields in categories.items():
        for field in ("title", "blurb"):
            text = fields.get(field, "")
            if text and field not in corrections["categories"].get(cat_id, {}):
                if generated["categories"].get(cat_id, {}).get(f"{field}_from") != fingerprint(text):
                    todo.append(("categories", cat_id, field, text))
    return todo


def run(engine_factory, apps, categories, state, dry_run=False):
    """The new generated tables per language and a report. `state` is {code: (generated, corrections)}."""
    result, report, engine = {}, {}, None
    for code in LANGUAGES:
        generated, corrections = state[code]
        new = {"apps": {k: dict(v) for k, v in generated["apps"].items() if k in apps}, "categories": {k: dict(v) for k, v in generated["categories"].items() if k in categories}}
        todo = plan(apps, categories, generated, corrections)
        report[code] = {"added": 0, "thrown_away": [], "todo": len(todo), "dropped": len(generated["apps"]) - len(new["apps"]) + len(generated["categories"]) - len(new["categories"])}
        if not dry_run and todo:
            engine = engine or engine_factory(LANGUAGES)
            for kind, ident, field, text in todo:
                translated, why = translate_ci.translate_one(engine, text, code)
                if translated is None:
                    report[code]["thrown_away"].append((f"{ident} {field}", why))
                    continue
                entry = new[kind].setdefault(ident, {})
                entry[field] = translated
                entry["from" if kind == "apps" else f"{field}_from"] = fingerprint(text)
                report[code]["added"] += 1
        result[code] = new
    return result, report


def render(code, table):
    """The file's text: fixed order, so running it twice changes nothing."""
    ordered = {"language": code, "version": 1,
               "apps": {k: table["apps"][k] for k in sorted(table["apps"])},
               "categories": {k: table["categories"][k] for k in sorted(table["categories"])}}
    return json.dumps(ordered, indent=1, ensure_ascii=False, sort_keys=False) + "\n"


def merged(code, out=OUT):
    """What a client shows: the generated table with the corrections on top (used by the check and the tests)."""
    generated, corrections = load(code, out)
    for kind in ("apps", "categories"):
        for ident, fields in corrections[kind].items():
            generated[kind].setdefault(ident, {}).update({k: v for k, v in fields.items() if not k.endswith("from")})
    return generated


def summary(report):
    lines = ["Machine translations of the marketplace catalog, made by CI. App names are not translated. A person's correction in "
             "`online_packages/i18n/corrections.json` always wins; a text that could not be translated safely stays English.", ""]
    for code, info in report.items():
        lines.append(f"- **{code}**: {info['added']} added, {len(info['thrown_away'])} left in English (of {info['todo']} to do)")
    left = [(code, what, why) for code, info in report.items() for what, why in info["thrown_away"]]
    if left:
        lines += ["", "Left in English:", ""] + [f"- {code}: `{what}` - {why}" for code, what, why in left[:30]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--summary")
    parser.add_argument("--verify-back", action="store_true")
    args = parser.parse_args(argv)
    translate_ci.VERIFY_BACK = args.verify_back
    apps, categories = sources()
    state = {code: load(code) for code in LANGUAGES}
    if args.check:
        stale = {code: plan(apps, categories, *state[code]) for code in LANGUAGES}
        for code, todo in stale.items():
            if todo:
                print(f"{code}: {len(todo)} text(s) are not translated or are out of date (e.g. {todo[0][1]} {todo[0][2]})")
        return 1 if any(stale.values()) else 0
    result, report = run(translate_ci.ArgosEngine, apps, categories, state, args.dry_run)
    text = summary(report)
    print(text)
    if args.summary:
        with open(args.summary, "w", encoding="utf-8") as f:
            f.write(text)
    if args.dry_run:
        return 0
    os.makedirs(OUT, exist_ok=True)
    changed = False
    for code in LANGUAGES:
        path = os.path.join(OUT, f"{code}.json")
        new = render(code, result[code])
        old = open(path, encoding="utf-8").read() if os.path.isfile(path) else ""
        if new != old:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(new)
            changed = True
            print(f"wrote {path}")
    if not changed:
        print("nothing changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
