# pyos/i18n.py - the language of the system's own messages
#
# tr("English text") returns the text in the chosen language, or the English text when there is no translation, so a missing
# translation can never break anything. Placeholders use str.format: tr("{n} commands", n=3).
# Language: the `language` setting (auto = PYOS_LANG, then the computer's language, then English). Add a language by adding
# a dictionary to pyos/locales.py and its code to LANGUAGES. Commands, file names and the manual stay in English on purpose:
# what you type is the same everywhere.
import os

LANGUAGES = {"en": "English", "es": "Español", "fr": "Français", "de": "Deutsch"}


def _from_environment():
    for name in ("PYOS_LANG", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = (os.environ.get(name) or "").lower()
        if value[:2] in LANGUAGES:
            return value[:2]
    try:
        import locale
        value = (locale.getlocale()[0] or "").lower()
        if value[:2] in LANGUAGES:
            return value[:2]
    except Exception:
        pass
    return "en"


def language():
    """The code of the language in use: es, fr, de or en."""
    try:
        from pyos import settings
        chosen = settings.get("language")
    except Exception:
        chosen = "auto"
    if chosen in LANGUAGES:
        return chosen
    return _from_environment()


def tr(text, **values):
    """`text` in the chosen language (English if it has no translation), with {placeholders} filled from `values`."""
    code = language()
    if code != "en":
        from pyos import locales
        text = locales.CATALOGS.get(code, {}).get(text, text)
    if values:
        try:
            return text.format(**values)
        except (KeyError, IndexError, ValueError):
            return text
    return text
