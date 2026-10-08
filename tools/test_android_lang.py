"""The Android installer's texts: every t("...") in MainActivity.kt has a Spanish, French and German wording with the same
{0}, {1} ... placeholders and the same format codes. (The Kotlin is compiled by the Android build, so this is the cheap guard.)"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "OS_Export" / "Android" / "installer" / "src" / "main" / "java" / "com" / "pythonos" / "installer"
LITERAL = r'"((?:[^"\\]|\\.)*)"'


def main():
    code = (SRC / "MainActivity.kt").read_text(encoding="utf-8")
    lang = (SRC / "Lang.kt").read_text(encoding="utf-8")
    keys = set(re.findall(r'\bt\(' + LITERAL, code))
    bad = []
    for name in ("ES", "FR", "DE"):
        start = lang.index("val %s = mapOf(" % name)
        block = lang[start:lang.index("\n    )", start)]
        table = dict(re.findall(r'^\s+' + LITERAL + r' to ' + LITERAL + ',?$', block, re.M))
        for key in sorted(keys - set(table)):
            bad.append("%s: no wording for %r" % (name, key))
        for key, value in table.items():
            if key not in keys and key not in ("Installed", "Latest", "Device"):
                bad.append("%s: unused text %r" % (name, key))
            if sorted(re.findall(r"\{\d\}|%\w", key)) != sorted(re.findall(r"\{\d\}|%\w", value)):
                bad.append("%s: placeholders differ in %r" % (name, key))
    if bad:
        print("\n".join(bad))
        return 1
    print("android installer texts: %d texts in 3 languages, placeholders match" % len(keys))
    return 0


if __name__ == "__main__":
    sys.exit(main())
