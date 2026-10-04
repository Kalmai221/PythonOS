import json
from rich.console import Console

# Initialize the console for rich output
console = Console()

from .paths import USER_DB
SESSION_FILE = "current_user.json"

def load_session():
    """Load the current user session from current_user.json."""
    try:
        with open(SESSION_FILE, 'r') as f:
            return json.load(f)  # Returns the entire session data
    except (FileNotFoundError, KeyError):
        return None

def userinfo():
    """Return [username, role] for the logged-in user.

    The role is read from users.json rather than trusted from the session file,
    so editing current_user.json cannot grant admin rights.
    """
    session_data = load_session()
    if not session_data:
        return [None, None]
    username = session_data.get('username')
    try:
        with open(USER_DB, 'r') as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return [None, None]
    if username not in users:
        return [None, None]
    return [username, users[username].get('role')]
