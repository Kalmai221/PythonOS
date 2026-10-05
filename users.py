import os
import json
import hashlib
import getpass
import hmac
import secrets
from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel
from rich.table import Table
import time
import pyos

from pyos.paths import USER_DB
console = Console()

# Load or create user database
def load_or_create_user_db():
    if not os.path.exists(USER_DB):
        with open(USER_DB, "w") as f:
            json.dump({}, f)

PBKDF2_ROUNDS = 200_000
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_SECONDS = 30
MAX_LOCKOUT_SECONDS = 15 * 60
LOCKOUT_FILE = os.path.join(".OSData", "lockout.json")
MIN_PASSWORD_LENGTH = 6


def _lockout_read():
    try:
        with open(LOCKOUT_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _lockout_write(data):
    os.makedirs(os.path.dirname(LOCKOUT_FILE), exist_ok=True)
    tmp = LOCKOUT_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, LOCKOUT_FILE)


def lockout_remaining(username):
    """Seconds this account is still locked for (0 = not locked). Survives restarts, so rebooting does not reset it,
    and every further batch of mistakes doubles the wait (up to 15 minutes)."""
    count, last = _lockout_read().get(username, [0, 0])
    if count < MAX_LOGIN_ATTEMPTS:
        return 0
    batches = count // MAX_LOGIN_ATTEMPTS
    wait = min(MAX_LOCKOUT_SECONDS, LOCKOUT_SECONDS * 2 ** (batches - 1))
    return max(0, int(wait - (time.time() - last)) + 1) if time.time() - last < wait else 0


def _note_failure(username):
    data = _lockout_read()
    count = data.get(username, [0, 0])[0] + 1
    data[username] = [count, time.time()]
    _lockout_write(data)


def _clear_failures(username):
    data = _lockout_read()
    if data.pop(username, None) is not None:
        _lockout_write(data)


def validate_password(password, username=None):
    """None if the password is acceptable, otherwise a sentence saying what is wrong."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if username and password.lower() == username.lower():
        return "Password must not be the same as the user name."
    if len(set(password)) == 1:
        return "Password must not be a single repeated character."
    return None


def authenticate(username, password):
    """Check a username and password, applying and recording lockouts. Returns (ok, message)."""
    users = get_users()
    wait = lockout_remaining(username)
    if wait:
        return False, f"Too many failed attempts. Try again in {wait}s."
    if username in users and verify_password(password, users[username]['password']):
        _clear_failures(username)
        if not users[username]['password'].startswith("pbkdf2$"):
            users[username]['password'] = hash_password(password)  # upgrade legacy hash
            save_users(users)
        return True, ""
    _note_failure(username)
    pyos.log.log("login failed", "WARN", user=username or "?")
    return False, "Incorrect username or password."


def hash_password(password):
    """Hash a password with salted PBKDF2-SHA256 ("pbkdf2$rounds$salt$hash")."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ROUNDS).hex()
    return f"pbkdf2${PBKDF2_ROUNDS}${salt}${digest}"


def verify_password(password, stored):
    """Check a password against a stored hash (also accepts legacy unsalted SHA-256)."""
    if stored.startswith("pbkdf2$"):
        _, rounds, salt, digest = stored.split("$")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
        return hmac.compare_digest(candidate, digest)
    legacy = hashlib.sha256(password.encode()).hexdigest()
    return hmac.compare_digest(legacy, stored)


def save_users(users):
    """Write the user database atomically so a crash cannot corrupt it."""
    tmp = USER_DB + ".tmp"
    with open(tmp, "w") as f:
        json.dump(users, f, indent=4)
    os.replace(tmp, USER_DB)

def get_users():
    """Get the list of registered users"""
    try:
        with open(USER_DB, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_session(username, role):
    """Save the current user session with username and role."""
    with open('current_user.json', 'w') as f:
        json.dump({'username': username, 'role': role}, f)  # Save both username and role

def load_session():
    """Load the current user session"""
    try:
        with open('current_user.json', 'r') as f:
            return json.load(f)['username']
    except (FileNotFoundError, KeyError):
        return None

def register():
    """Register a new user"""
    username = Prompt.ask("[bold yellow]New username[/bold yellow]").strip()
    users = get_users()

    if not username or not username.replace("_", "").replace("-", "").isalnum():
        console.print("[bold red]Usernames may only contain letters, numbers, '-' and '_'.[/bold red]")
        return None

    if username in users:
        console.print("[bold red]User already exists![/bold red]")
        return None

    password = getpass.getpass("New password: ")
    problem = validate_password(password, username)
    if problem:
        console.print(f"[bold red]{problem}[/bold red]")
        return None
    if getpass.getpass("Confirm password: ") != password:
        console.print("[bold red]Passwords do not match.[/bold red]")
        return None

    # Determine if the new user is an admin or a regular user
    is_admin = len(users) == 0  # First user is admin
    role = "admin" if is_admin else "user"

    users[username] = {
        "password": hash_password(password),
        "role": role
    }
    save_users(users)
    pyos.fs.ensure_home(username)
    pyos.log.log(f"account created (role: {role})", user=username)

    console.print(f"[bold green]User registered successfully! Role: {role}[/bold green]")
    return username

def delete_user():
    """Delete a user"""
    current_user = load_session()
    users = get_users()

    if users.get(current_user, {}).get('role') != 'admin':
        console.print("[bold red]You do not have permission to delete users.[/bold red]")
        return

    username = Prompt.ask("[bold yellow]Enter the username to delete[/bold yellow]").strip()
    if username not in users:
        console.print(f"[bold red]User {username} not found.[/bold red]")
        return

    if username == current_user:
        console.print("[bold red]You cannot delete the account you are logged in with.[/bold red]")
        return

    from pyos import audit
    if not audit.elevate(f"delete the account '{username}'"):
        console.print("[bold red]Not deleted.[/bold red]")
        return

    del users[username]
    save_users(users)
    pyos.log.log(f"account deleted by {current_user}", "WARN", user=username)

    console.print(f"[bold green]User {username} deleted successfully![/bold green]")

def view_users():
    """View all users"""
    users = get_users()
    current_user = load_session()  # Get the current logged-in user
    if users:
        table = Table(title="Registered Users", header_style="bold", border_style="blue")
        table.add_column("User", style="bold")
        table.add_column("Role")
        for username, details in users.items():
            label = f"{username} [bold cyan](you)[/bold cyan]" if username == current_user else username
            table.add_row(label, details['role'])
        console.print(table)
    else:
        console.print("[bold red]No users found.[/bold red]")

def change_password():
    """Change a password. Admins can change anyone's; other users only their own."""
    current_user = load_session()
    users = get_users()

    if current_user not in users:
        console.print("[bold red]You must be logged in to change a password.[/bold red]")
        return False

    is_admin = users[current_user]['role'] == 'admin'
    if is_admin:
        username = Prompt.ask("[bold yellow]Enter the username whose password you want to change[/bold yellow]").strip()
    else:
        username = current_user
    if username not in users:
        console.print("[bold red]User not found.[/bold red]")
        return False

    if username == current_user:
        old = getpass.getpass("Current password: ")
        if not verify_password(old, users[username]['password']):
            console.print("[bold red]Incorrect password.[/bold red]")
            return False

    new_password = getpass.getpass(f"Enter a new password for {username}: ")
    problem = validate_password(new_password, username)
    if problem:
        console.print(f"[bold red]{problem}[/bold red]")
        return False
    if getpass.getpass("Confirm new password: ") != new_password:
        console.print("[bold red]Passwords do not match.[/bold red]")
        return False
    users[username]['password'] = hash_password(new_password)
    save_users(users)
    pyos.log.log(f"password changed for {username}", "WARN" if username != current_user else "INFO", user=current_user)
    console.print(f"[bold green]Password for {username} changed successfully![/bold green]")
    return True

def change_role():
    """Change the role of a user between admin and user."""
    users = get_users()

    if users.get(load_session(), {}).get('role') != 'admin':
        console.print("[bold red]You do not have permission to change roles.[/bold red]")
        return False

    username = Prompt.ask("[bold yellow]Enter the username whose role you want to change[/bold yellow]").strip()
    if username not in users:
        console.print("[bold red]User not found.[/bold red]")
        return False

    current_role = users[username]['role']

    # Ask for the new role
    new_role = Prompt.ask(
        "[bold yellow]Enter the new role (admin/user)[/bold yellow]",
        choices=["admin", "user"]
    )

    # If changing from admin to user, check if at least one admin remains
    if current_role == "admin" and new_role == "user":
        admin_count = sum(1 for user in users.values() if user['role'] == "admin")
        if admin_count <= 1:
            console.print("[bold red]There must be at least one admin in the system.[/bold red]")
            return False

    from pyos import audit
    if not audit.elevate(f"change the role of '{username}' from {current_role} to {new_role}"):
        console.print("[bold red]Role not changed.[/bold red]")
        return False

    # Change the role
    users[username]['role'] = new_role
    save_users(users)
    pyos.system("clear")
    console.print(f"[bold green]Role for {username} changed to {new_role} successfully![/bold green]")
    return True


def login():
    """Handle user login (with a lockout that grows with repeated failures and survives restarts)"""
    users = get_users()
    username = input("Username: ").strip()

    wait = lockout_remaining(username)
    if wait:
        console.print(f"[bold red]Too many failed attempts. Try again in {wait}s.[/bold red]")
        return None

    password = getpass.getpass("Password: ")
    ok, message = authenticate(username, password)   # same message for unknown user / wrong password
    if not ok:
        console.print(f"[bold red]{message}[/bold red]")
        return None

    users = get_users()
    os.system("cls" if os.name == "nt" else "clear")
    console.print(f"[bold green]Welcome back, {username}![/bold green] [dim]({users[username]['role']})[/dim]")
    save_session(username, users[username]['role'])  # Save username and role
    pyos.fs.ensure_home(username)
    pyos.log.log("login ok", user=username)
    return username

def logout():
    """Logout the current user by removing session"""
    try:
        pyos.system("clear")
        os.remove('current_user.json')
        console.print("[bold green]Logged out successfully![/bold green]")
        time.sleep(2)
        pyos.system("clear")
    except FileNotFoundError:
        console.print("[bold yellow]No active session found![/bold yellow]")

def user_menu():
    """Display user management menu"""
    while True:
        choice = Prompt.ask("[bold yellow]Select an option[/bold yellow]", choices=["Login", "Register", "View Users", "Change Password", "Delete User"], show_choices=True)
        if choice == "Login":
            return login()
        elif choice == "Register":
            return register()
        elif choice == "View Users":
            view_users()
        elif choice == "Change Password":
            change_password()
        elif choice == "Delete User":
            delete_user()

def register_and_login():
    """Create the first account and sign it in, so it has a session straight away."""
    username = register()
    if username:
        save_session(username, get_users()[username]['role'])
    return username


def boot_sequence():
    """Boot the system and check user session"""
    load_or_create_user_db()  # Ensure the user database is loaded
    users_data = get_users()

    # If users exist, proceed to login, else go to register
    if users_data:
        console.print(Panel("Please log in to continue.", title="[bold cyan]Login[/bold cyan]", border_style="blue", expand=False))
        return login()
    else:
        console.print(Panel("No users found. Create the first account (it will be an admin).",
                            title="[bold cyan]Setup[/bold cyan]", border_style="blue", expand=False))
        return register_and_login()

def login_after_logout():
    """Boot the system and check user session"""
    load_or_create_user_db()  # Ensure the user database is loaded
    users_data = get_users()

    # If users exist, proceed to login, else go to register
    if users_data:
        console.print(Panel("Please log in to continue.", title="[bold cyan]Login[/bold cyan]", border_style="blue", expand=False))
        return login()
    else:
        console.print(Panel("No users found. Create the first account (it will be an admin).",
                            title="[bold cyan]Setup[/bold cyan]", border_style="blue", expand=False))
        return register_and_login()