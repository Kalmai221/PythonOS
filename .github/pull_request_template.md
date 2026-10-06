## What

<!-- What does this change, in a sentence? -->

## Why

<!-- The problem, or the issue it closes (Closes #123). -->

## How I checked it

<!-- What you ran, and on which system (Windows, Linux, Android, ISO/VM, Docker). -->

## What a user will see

<!-- New or changed text, commands or defaults. "Nothing" is a fine answer. -->

## Checklist

- [ ] `python tools/smoke_test.py` passes
- [ ] `python tools/audit_lockdown.py` passes (nothing new can run programs)
- [ ] New command: manual page, help group and a smoke test line
- [ ] New or changed app: version raised, changelog line, `python tools/build_index.py` run and the index files committed
- [ ] Website or docs: `python tools/build_site.py` run and `site/` committed
- [ ] `CHANGELOG.md` has a line under the right heading (PythonOS, Exports, Website, Development)
