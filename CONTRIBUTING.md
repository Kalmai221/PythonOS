# Contributing to PythonOS

Fixes, new commands, new apps and better docs are all welcome. The full guide is on the website (Documentation, then Pull requests); this is the short version.

1. **Open an issue first** for anything bigger than a few lines, or for a change in how something works.
2. **Set up:** `git clone`, `python -m pip install -r requirements.txt`, then `python main.py` runs PythonOS from the checkout. Python 3.9 or newer.
3. **Match the code around yours.** Python 3.9 only, no new dependencies unless there is no other way, and it must work on Windows, Linux and Android. Running programs is reviewed: `tools/audit_lockdown.py` fails on any new use of `subprocess`, `os.system` or `eval`.
4. **Run the checks** before you open the pull request:

   ```
   python tools/smoke_test.py
   python tools/audit_lockdown.py
   python tools/check_docs.py
   python tools/build_index.py     # commit the index files if they change
   python tools/build_site.py      # if you touched site_src/ (commit site/ too)
   ```

5. **New command:** a file in `commands/`, a manual page in `pyos/manpages.py`, a help group in `pyos/helpview.py`, a line in `tools/smoke_test.py`.
6. **New or changed app:** see the Apps API page; raise the app's `version` when you change it.
7. **Changelog:** one line in the newest section of `CHANGELOG.md`, under `### PythonOS`, `### Exports`, `### Website` or `### Development`.
8. **Open the pull request** and fill in the template. GitHub runs the same checks plus more (pylint, ruff, Windows, macOS, Python 3.9 and 3.14). A maintainer reviews it; push more commits to the same branch to answer comments.

The website sources are in `site_src/`; `site/` is generated from them (`python tools/build_site.py`).
