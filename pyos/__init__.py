# pyos/__init__.py
from .system import system
from .shutdown import shutdown, ShutdownRequested
from .userinfo import userinfo
from .logout import logout
from . import paths, fs, log, stdio, resources, tasks, marketapi, services
from . import trail, screenlog, apprun, sysmem, bugs
from . import sandbox, settings, theme, notify, appdata, jobs, scheduler, lockdown, export, editor, startup, paging, shellvars, prompt, optional, fuzzy, passwords

# Rich's prompts print their prompt themselves, which readline then overwrites when you edit the line: see pyos/richinput.py
try:
    from . import richinput, spinner
    richinput.patch()
    spinner.patch()                                         # plain "-\|/" spinners on the Linux text console (no Braille in its font): see pyos/spinner.py
except Exception:                                           # noqa: BLE001 - without Rich (or with another version) the prompts simply stay as they were
    pass
