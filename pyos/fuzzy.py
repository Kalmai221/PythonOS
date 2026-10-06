# pyos/fuzzy.py - "did you mean": the closest names to a word. Uses rapidfuzz when it is installed (better with typos and partial words),
# else difflib from the standard library.
import difflib

from pyos import optional


def close_matches(word, options, n=3, cutoff=0.6):
    """Up to n of `options` that look like `word`, best first. cutoff is 0 to 1 (1 = identical)."""
    options = list(options)
    fuzz = optional.get("rapidfuzz")
    if fuzz is not None:
        try:
            from rapidfuzz import fuzz as scorer, process
            found = process.extract(word, options, scorer=scorer.WRatio, limit=n, score_cutoff=max(0, cutoff * 100 + 15))
            return [name for name, _score, _index in found]
        except Exception:                                  # noqa: BLE001
            pass
    return difflib.get_close_matches(word, options, n=n, cutoff=cutoff)
