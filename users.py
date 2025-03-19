import os
import json
import hashlib
import getpass
from rich.console import Console
from rich.prompt import Prompt
import time
import pyos

USER_DB = "users.json"
console = Console()

# Load or create user database
def load_or_create_user_db():
    if not os.path.exists(USER_DB):
        with open(USER_DB, "w") as f:
            json.dump({}, f)

def hash_password(password):
    """Hash the password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def get_users():
    """Get the list of registered users"""
    with open(USER_DB, "r") as f:
        return json.load(f)

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

    if username in users:
        console.print("[bold red]User already exists![/bold red]")
        return None

    password = getpass.getpass("New password: ")

    # Determine if the new user is an admin or a regular user
    is_admin = len(users) == 0  # First user is admin
    role = "admin" if is_admin else "user"

    with open(USER_DB, "r+") as f:
        users[username] = {
            "password": hash_password(password),
            "role": role
        }
        f.seek(0)
        json.dump(users, f, indent=4)

    console.print(f"[bold green]User  registered successfully! Role: {role}[/bold green]")
    return username

def delete_user():
    """Delete a user"""
    current_user = load_session()
    users = get_users()

    if users[current_user]['role'] != 'admin':
        console.print("[bold red]You do not have permission to delete users.[/bold red]")
        return

    username = Prompt.ask("[bold yellow]Enter the username to delete[/bold yellow]").strip()
    if username not in users:
        console.print(f"[bold red]User {username} not found.[/bold red]")
        return

    del users[username]
    with open(USER_DB, "w") as f:
        json.dump(users, f, indent=4)

    console.print(f"[bold green]User {username} deleted successfully![/bold green]")

def view_users():
    """View all users"""
    users = get_users()
    current_user = load_session()  # Get the current logged-in user
    if users:
        console.print("[bold yellow]Registered Users:[/bold yellow]")
        for username, details in users.items():
            # Add "- You" next to the current logged-in user
            if username == current_user:
                console.print(f"- {username} [bold cyan](You)[/bold cyan] - Role: {details['role']}")
            else:
                console.print(f"- {username} - Role: {details['role']}")
    else:
        console.print("[bold red]No users found.[/bold red]")

def change_password():
    """Change the password for a user"""
    current_user = load_session()
    users = get_users()

    if users[current_user]['role'] != 'admin':
        console.print("[bold red]You do not have permission to change other users' passwords.[/bold red]")
        return False

    username = Prompt.ask("[bold yellow]Enter the username whose password you want to change[/bold yellow]").strip()
    if username not in users:
        console.print("[bold red]User  not found.[/bold red]")
        return False

    new_password = getpass.getpass(f"Enter a new password for {username}: ").strip()
    users[username]['password'] = hash_password(new_password)

    with open(USER_DB, "w") as f:
        json.dump(users, f, indent=4)
    console.print(f"[bold green]Password for {username} changed successfully![/bold green]")
    return True

def change_role():
    """Change the role of a user between admin and user."""
    users = get_users()

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

    # Change the role
    users[username]['role'] = new_role
    with open(USER_DB, "w") as f:
        json.dump(users, f, indent=4)
    pyos.system("clear")
    console.print(f"[bold green]Role for {username} changed to {new_role} successfully![/bold green]")
    return True


def login():
    """Handle user login"""
    users = get_users()
    username = input("Username: ").strip()
    if username not in users:
        console.print("[bold red]User  not found.[/bold red]")
        return None
    password = getpass.getpass("Password: ")
    if users[username]['password'] == hash_password(password):
        os.system("clear")
        console.print(f"[bold green]Welcome back, {username}! Role: {users[username]['role']}[/bold green]")
        save_session(username, users[username]['role'])  # Save username and role
        return username
    else:
        console.print("[bold red]Incorrect password.[/bold red]")
        return None

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

def boot_sequence():
    """Boot the system and check user session"""
    load_or_create_user_db()  # Ensure the user database is loaded
    users_data = get_users()

    # If users exist, proceed to login, else go to register
    if users_data:
        console.print("[bold yellow]Users found. Please log in.[/bold yellow]")
        return login()
    else:
        console.print("[bold yellow]No users found. Please create an account.[/bold yellow]")
        return register()

def login_after_logout():
    """Boot the system and check user session"""
    load_or_create_user_db()  # Ensure the user database is loaded
    users_data = get_users()

    # If users exist, proceed to login, else go to register
    if users_data:
        console.print("[bold yellow]Users found. Please log in.[/bold yellow]")
        return login()
    else:
        console.print("[bold yellow]No users found. Please create an account.[/bold yellow]")
        return register()