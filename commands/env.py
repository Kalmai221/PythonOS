import os

import pyos
import pyos.fs as fs
from pyos import textcmd

config = {"name": "env", "description": "Show who and where you are: user, home, host, folder, PythonOS settings of the session."}

SHOWN = ("PYOS_LIVE", "PYOS_INSTALLED", "PYOS_LOCKDOWN", "PYOS_PERSISTENT", "PYOS_CORE_OVERLAY", "TERM", "LANG", "COLUMNS", "LINES")


def execute(args=None):
    user, role = pyos.userinfo()
    textcmd.emit(f"USER={user}")
    textcmd.emit(f"ROLE={role}")
    textcmd.emit(f"HOME={fs.display(fs.home_dir(user), tilde=False)}")
    textcmd.emit(f"HOST={fs.hostname()}")
    textcmd.emit(f"PWD={fs.display(fs.current_dir(), tilde=False)}")
    for name in SHOWN:
        if os.environ.get(name):
            textcmd.emit(f"{name}={os.environ[name]}")
    return True
