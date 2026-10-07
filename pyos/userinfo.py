import json
import os
from rich.console import Console

# Initialize the console for rich output
console = Console()

from .paths import USER_DB
SESSION_FILE = "current_user.json"

def load_session():
    """Load the current user session from current_user.json."""
    try:
        with open(SESSION_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)  # Returns the entire session data
        return data if isinstance(data, dict) else None
    except (OSError, ValueError, KeyError):
        return None

def userinfo():
    """Return [username, role] for the logged-in user.

    The role is read from users.json rather than trusted from the session file,
    so editing current_user.json cannot grant admin rights.
    """
    # An app running under the package permission guard is not allowed to read the account database (it holds password
    # hashes), so the guard hands it the answer instead: "name:role", worked out before the guard was installed.
    sandboxed = os.environ.get("PYOS_SANDBOX_USER")
    if sandboxed:
        name, _, role = sandboxed.partition(":")
        return [name or None, role or None]
    session_data = load_session()
    if not session_data:
        return [None, None]
    username = session_data.get('username')
    try:
        with open(USER_DB, 'r', encoding='utf-8') as f:
            users = json.load(f)
    except (OSError, ValueError):
        return [None, None]
    if not isinstance(users, dict) or not isinstance(users.get(username), dict):
        return [None, None]
    return [username, users[username].get('role')]


def diagnose():
    """Why userinfo() does not say "admin", in one line (for the message of a command that needs an administrator)."""
    name, role = userinfo()
    if role == "admin":
        return "you are an administrator"
    if os.environ.get("PYOS_SANDBOX_USER"):
        return f"this runs inside an app's sandbox as '{name}' with the role '{role}'"
    session = load_session()
    if not session:
        return f"there is no login session ({SESSION_FILE} in {os.getcwd()} is missing or unreadable)"
    try:
        with open(USER_DB, 'r', encoding='utf-8') as f:
            users = json.load(f)
    except OSError as e:
        return f"the account database {USER_DB} cannot be read ({e.__class__.__name__})"
    except ValueError:
        return f"the account database {USER_DB} is damaged"
    who = session.get('username')
    if not isinstance(users, dict) or who not in users:
        return f"'{who}' is not in the account database {USER_DB}"
    return f"'{who}' has the role '{users[who].get('role')}' in {USER_DB}, not 'admin'"

