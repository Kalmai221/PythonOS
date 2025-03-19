from rich.console import Console
import os
import shell
import users

# Initialize the console for rich output
console = Console()

SESSION_FILE = "current_user.json"

def logout():
    MAX_ATTEMPTS = 3  # Set the maximum number of login attempts
    attempts = 0
    username = None
    try:
        os.remove('current_user.json')
        console.print("[bold green]Logged out successfully![/bold green]")
        while attempts < MAX_ATTEMPTS:
            username = users.login_after_logout()
            if username:
                shell.start_shell(username)
                break
            else:
                attempts += 1
                remaining_attempts = MAX_ATTEMPTS - attempts
                if remaining_attempts > 0:
                    console.print(f"[bold yellow]Login failed. {remaining_attempts} attempts remaining...[/bold yellow]")
                else:
                    console.print("[bold red]Login failed. Shutting down...[/bold red]")
                    raise KeyboardInterrupt
    except FileNotFoundError:
        console.print("[bold yellow]No active session found![/bold yellow]")
