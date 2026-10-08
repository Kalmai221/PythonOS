"""The Android installer's and app's texts: every t("...") in MainActivity.kt has a Spanish, French and German wording with the same
{0}, {1} ... placeholders and the same format codes. (The Kotlin is compiled by the Android build, so this is the cheap guard.)"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASE = ROOT / "OS_Export" / "Android"
APPS = {"installer": BASE / "installer" / "src" / "main" / "java" / "com" / "pythonos" / "installer",
        "app": BASE / "app" / "src" / "main" / "java" / "com" / "pythonos" / "app"}
LITERAL = r'"((?:[^"\\]|\\.)*)"'
EXTRA_OK = ("Installed", "Latest", "Device", "Language / Idioma / Langue / Sprache")     # used through padEnd / a mixed-language title


def check(name, src):
    code = (src / "MainActivity.kt").read_text(encoding="utf-8")
    lang = (src / "Lang.kt").read_text(encoding="utf-8")
    keys = set(re.findall(r'\bt\(' + LITERAL, code))
    bad = []
    for code_name in ("ES", "FR", "DE"):
        start = lang.index("val %s = mapOf(" % code_name)
        block = lang[start:lang.index("\n    )", start)]
        table = dict(re.findall(r'^\s+' + LITERAL + r' to ' + LITERAL + ',?$', block, re.M))
        for key in sorted(keys - set(table)):
            bad.append("%s %s: no wording for %r" % (name, code_name, key))
        for key, value in table.items():
            if key not in keys and key not in EXTRA_OK:
                bad.append("%s %s: unused text %r" % (name, code_name, key))
            if sorted(re.findall(r"\{\d\}|%\w", key)) != sorted(re.findall(r"\{\d\}|%\w", value)):
                bad.append("%s %s: placeholders differ in %r" % (name, code_name, key))
    print("android %s: %d texts in 3 languages" % (name, len(keys)))
    return bad


def main():
    bad = []
    for name, src in APPS.items():
        bad += check(name, src)
    if bad:
        print("\n".join(bad))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
