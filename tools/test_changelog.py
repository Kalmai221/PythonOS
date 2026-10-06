#!/usr/bin/env python3
"""Checks that CHANGELOG.md can be split by who gets a change (PythonOS, Exports, Website, Development) the way make_core and release_notes read it."""
import os
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "OS_Export"))


def main():
    import make_core
    import release_notes
    import stage
    version = stage.version()
    parts = make_core.changelog_parts(version)
    assert parts.get("PythonOS"), f"the {version} section of CHANGELOG.md has no '### PythonOS' bullets"
    assert set(parts) <= set(make_core.PARTS), f"unknown part in {version}: {set(parts) - set(make_core.PARTS)}"
    notes = make_core.changelog_notes(version)
    assert notes and all(l.startswith("- ") for l in notes.splitlines())
    assert not (set(notes.splitlines()) & set(make_core.changelog_notes(version, "Exports").splitlines())), "a bullet is in both PythonOS and Exports"
    old = make_core.changelog_parts("1.0.7")
    assert list(old) == ["PythonOS"] and old["PythonOS"], "a section written before the split must count as all PythonOS"
    assert make_core.changelog_parts("0.0.0") == {} and make_core.changelog_notes("0.0.0") == ""
    page = release_notes.build(version, {"exports": {}}, {})
    assert "PythonOS updates" in page and ("Export updates" in page or not parts.get("Exports"))
    print("changelog: all checks passed")


if __name__ == "__main__":
    sys.exit(main() or 0)
