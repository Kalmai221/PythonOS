# pyos/paths.py - where PythonOS keeps its account database.
#
# Normally users.json sits next to the OS. On the live ISO with persistent storage, the session script points
# PYOS_USERS_FILE at a file on the data partition so accounts survive a restart of the machine.
import os

USER_DB = os.environ.get("PYOS_USERS_FILE") or "users.json"
