# pyos/appi18n.py - the marketplace catalog in the person's language
#
# CI translates what each app is (its description) and the category titles and blurbs into the languages PythonOS speaks, into
# online_packages/i18n/<language>.json (and a person's corrections into corrections.json). The files are for every marketplace API at once: a catalog
# lists the languages it has in "languages", and the marketplace reads the file of the language in use. App names are not translated.
# attach() adds the words to the packages as description_local and to the categories as title_local / blurb_local; the English fields are left alone,
# because they are what searches, ids and commands are matched against.
import json


def merge(generated, corrections):
    """A table {'apps': {id: {'description'}}, 'categories': {id: {'title', 'blurb'}}} from a language file with the corrections for that language on top."""
    table = {"apps": {}, "categories": {}}
    for kind in table:
        for ident, fields in ((generated or {}).get(kind) or {}).items():
            if isinstance(fields, dict):
                table[kind][ident] = {k: v for k, v in fields.items() if isinstance(v, str) and not k.endswith("from") and v.strip()}
        for ident, fields in ((corrections or {}).get(kind) or {}).items():
            if isinstance(fields, dict):
                table[kind].setdefault(ident, {}).update({k: v for k, v in fields.items() if isinstance(v, str) and v.strip()})
    return table


def attach(packages, categories, table):
    """Put the translated words on the packages and the categories of a catalog (in place). Returns how many descriptions were translated."""
    done = 0
    apps = (table or {}).get("apps") or {}
    for package in packages or []:
        text = (apps.get(package.get("id")) or {}).get("description")
        if text:
            package["description_local"] = text
            done += 1
    cats = (table or {}).get("categories") or {}
    for category in categories or []:
        fields = cats.get(category.get("id")) or {}
        if fields.get("title"):
            category["title_local"] = fields["title"]
        if fields.get("blurb"):
            category["blurb_local"] = fields["blurb"]
    return done


def description(package):
    """The description to show: the translation when there is one."""
    return package.get("description_local") or package.get("description", "")


def category_words(category):
    return category.get("title_local") or category.get("title", ""), category.get("blurb_local") or category.get("blurb", "")


def load_cached(path, language):
    """The table saved by the last visit to the marketplace for this language, or None."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data["table"] if data.get("language") == language else None
    except (OSError, ValueError, KeyError, AttributeError):
        return None


def save_cached(path, language, table):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"language": language, "table": table}, f, ensure_ascii=False)
    except OSError:
        pass
