# pyos/locales.py - the translations of the system's own messages (see pyos/i18n.py). The keys are the English texts.
#
# Nobody writes translations here any more: the Translations workflow (.github/workflows/translations.yml, tools/translate_ci.py) machine-translates
# every message into Spanish, French and German and keeps the result in pyos/locales_auto.py. These three dictionaries are only for CORRECTIONS: a
# text written here always wins over the machine's, and the generated file then drops its own copy at the next run. They start empty.
#
#     ES = {"Cancelled.": "Cancelado."}
#
# A message with no translation anywhere shows in English, which is always safe.

ES = {"never": "nunca"}

FR = {}

DE = {}

# what people wrote: tools/translate_ci.py never touches these, and only translates what is missing from them
HUMAN = {"es": dict(ES), "fr": dict(FR), "de": dict(DE)}

# machine translations made by CI for everything else (pyos/locales_auto.py); a person's text always wins
from pyos import locales_auto  # noqa: E402

for _table, _auto in ((ES, locales_auto.ES), (FR, locales_auto.FR), (DE, locales_auto.DE)):
    for _key, _text in _auto.items():
        _table.setdefault(_key, _text)

CATALOGS = {"es": ES, "fr": FR, "de": DE}
