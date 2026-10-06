# pyos/passwords.py - honest advice about a new password. Never blocks (users.validate_password has the hard rules); it only says how strong
# the password really is. Uses zxcvbn (patterns, dictionary words, keyboard walks, dates) when it is installed, else a simple measure.
import re

from pyos import optional

WORDS = ("weak", "weak", "fair", "good", "strong")


def score(password, username=None):
    """(0-4, hint or None). 0 is guessable at once, 4 is very hard to guess."""
    lib = optional.get("zxcvbn")
    if lib is not None:
        try:
            result = lib.zxcvbn(password[:72], user_inputs=[username] if username else [])
            feedback = result.get("feedback", {})
            hint = feedback.get("warning") or (feedback.get("suggestions") or [None])[0]
            return int(result["score"]), hint or None
        except Exception:                                  # noqa: BLE001
            pass
    classes = sum(bool(re.search(p, password)) for p in (r"[a-z]", r"[A-Z]", r"[0-9]", r"[^A-Za-z0-9]"))
    value = 0 if len(password) < 8 else 1 if len(password) < 10 else 2 if len(password) < 12 else 3
    if classes >= 3 and len(password) >= 12:
        value = 4
    if len(set(password)) < 4:
        value = min(value, 1)
    return value, ("A longer password, or a few unrelated words, is stronger." if value < 3 else None)


def advice(password, username=None):
    """A sentence for the person ('This password is weak: ...'), or None when it is good enough."""
    value, hint = score(password, username)
    if value >= 3:
        return None
    return f"This password is {WORDS[value]}" + (f": {hint}" if hint else ".") + " It works, but a longer one is safer."
