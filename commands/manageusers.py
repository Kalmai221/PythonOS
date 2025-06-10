from users import register, delete_user, view_users, change_password, change_role
from rich.console import Console
from rich.prompt import Prompt
import pyos

console = Console()

config = {
    "name": "manageusers",
    "description": "Manage the users that can access the OS"
}


def execute():
    user_info = pyos.userinfo()
    if user_info[1] == "admin":
        console.print(
            "[bold yellow]Welcome to the User Management System[/bold yellow]")

        while True:
            console.print("[bold yellow]Please select an option:[/bold yellow]")
            console.print("[1] Create a new user")
            console.print("[2] Delete a user")
            console.print("[3] Change a user's role")
            console.print("[4] View all users")
            console.print("[5] Change a user's password")
            console.print("[6] Exit")

            choice = Prompt.ask(
                "[bold yellow]Enter the number of your choice[/bold yellow]",
                choices=["1", "2", "3", "4", "5", "6"])

            if choice == "1":
                # Create a new user
                username = register()
                if username:
                    console.print(
                        f"[bold green]User {username} registered successfully![/bold green]"
                    )
            elif choice == "2":
                # Delete a user
                delete_user()
            elif choice == "3":
                change_role()
            elif choice == "4":
                # View all users
                view_users()
            elif choice == "5":
                # Change a user's password
                change_password()
            elif choice == "6":
                # Exit the program
                console.print("[bold green]Exiting...[/bold green]")
                break
            else:
                console.print("[bold red]Invalid choice. Please select a valid option.[/bold red]")

            # Ask if the user wants to perform another action
            again = Prompt.ask(
                "[bold yellow]Do you want to perform another action? (yes/no)",
                choices=["yes", "no"])
            pyos.system("clear")
            if again.lower() == "no":
                break
    else:
        console.print(
            "[bold red]You do not have permission to use this command[/bold red]"
        )
