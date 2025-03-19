import json
from rich.console import Console

# Initialize the console for rich output
console = Console()

USER_DB = "users.json"
SESSION_FILE = "current_user.json"

def load_session():
    """Load the current user session from current_user.json."""
    try:
        with open(SESSION_FILE, 'r') as f:
            return json.load(f)  # Returns the entire session data
    except (FileNotFoundError, KeyError):
        return None

def userinfo():
    """Return the logged-in user's username and role from current_user.json."""
    session_data = load_session()
    if session_data:
        username = session_data.get('username')  # Get the username
        role = session_data.get('role')  # Get the role
        return [username, role]  # Return a list with username and role
    else:
        return [None, None]  # Return a list with None if no user is logged in