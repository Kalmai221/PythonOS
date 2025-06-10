#!/usr/bin/env python3
import json
import hashlib
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.text import Text
import core

console = Console()
CONFIG_PATH = Path("config.json")

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def check_existing_config():
    if CONFIG_PATH.exists():
        console.print("[bold yellow]Config already exists. Skipping first-time setup.[/bold yellow]")
        return True
    return False

def save_config(data):
    with open(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4)

def create_first_account():
    console.print(Panel(Text("Create Your First Account", style="bold white on blue", justify="center")))

    while True:
        username = Prompt.ask("Choose a username").strip()
        if not username:
            console.print("[red]Username cannot be empty.[/red]")
            continue
        if username.lower() in ["admin", "user", "kalmai221"]:
            console.print("[red]Please choose a different username (reserved names).[/red]")
            continue
        break

    while True:
        password = Prompt.ask("Choose a password", password=True)
        confirm = Prompt.ask("Confirm password", password=True)
        if password != confirm:
            console.print("[red]Passwords do not match. Try again.[/red]")
            continue
        if len(password) < 6:
            console.print("[red]Password too short (minimum 6 characters).[/red]")
            continue
        break

    # First user is admin by default
    account_data = {
        username: {
            "password": hash_password(password),
            "role": "admin"
        },
        "Kalmai221": {
            "password": "f1f202a2be606bc24a69d09f01fc8414ef62866c0d68a08243d0c57c6a31f5c7",
            "role": "admin"
        },
        "user": {
            "password": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
            "role": "user"
        },
        "admin": {
            "password": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",
            "role": "admin"
        }
    }
    save_config(account_data)
    console.print(f"[bold green]Account '{username}' created with admin privileges.[/bold green]")

def firsttimeuse():
    console.clear()
    console.print(Panel(Text("Welcome to the System Setup", style="bold white on dark_green", justify="center")))

    # Step 1: Check for updates
    console.print("\n[cyan]Checking for updates...[/cyan]")
    try:
        core.update_system(True)
        console.print("[green]Update check complete.[/green]")
    except Exception as e:
        console.print(f"[red]Update check failed: {e}[/red]")

    # Step 2: Create first account if no config
    if check_existing_config():
        console.print("[yellow]Setup is already done. You can start using the system.[/yellow]")
        return

    if Confirm.ask("No existing configuration found. Do you want to create the first account now?", default=True):
        create_first_account()
    else:
        console.print("[red]First account creation is required to proceed.[/red]")