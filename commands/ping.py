import time
import requests
import socket
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt

console = Console()

# Default Configuration
config = {
    "target": "https://example.com",
    "attempts": 3,
    "timeout": 5,
    "max_requests": 20  # Prevent abuse
}

def ip_to_hostname(ip):
    """Try to resolve an IP address to a hostname."""
    try:
        hostname = socket.gethostbyaddr(ip)[0]
        return f"https://{hostname}"
    except socket.herror:
        return None  # No hostname found

def draw_menu(selected_index):
    """Generates the menu and prints it to the console."""
    console.clear()
    table = Table(title="[bold cyan]Ping Configuration Menu[/bold cyan]", expand=True)

    table.add_column("Setting", style="bold")
    table.add_column("Value", justify="center", style="yellow")
    table.add_column("Action", justify="right", style="blue")

    options = [
        ("Target Address", config["target"], "[Enter] to edit"),
        ("Attempts (Max 20)", str(config["attempts"]), "[Enter] to edit"),
        ("Timeout (seconds)", str(config["timeout"]), "[Enter] to edit"),
        ("Start Ping", "▶ Start", "[Enter]"),
        ("Exit", "❌ Quit", "[Enter]")
    ]

    for i, (setting, value, action) in enumerate(options):
        highlight = "[bold green]→[/bold green] " if i == selected_index else "   "
        table.add_row(f"{highlight}{setting}", value, action)

    console.print(table)

def interactive_config():
    """Interactive configuration menu."""
    selected_index = 0
    options = ["target", "attempts", "timeout", "start", "exit"]

    while True:
        draw_menu(selected_index)
        key = console.input("[bold cyan]Use [W/S] to move, [Enter] to select: [/bold cyan]").strip().lower()

        if key in ["w", "up"]:  # Move Up
            selected_index = (selected_index - 1) % len(options)
        elif key in ["s", "down"]:  # Move Down
            selected_index = (selected_index + 1) % len(options)
        elif key == "":  # Enter Key
            if options[selected_index] == "target":
                new_target = Prompt.ask("[bold yellow]Enter new target URL or IP[/bold yellow]", default=config["target"])
                config["target"] = new_target
            elif options[selected_index] == "attempts":
                new_attempts = Prompt.ask("[bold yellow]Enter number of attempts (Max 20)[/bold yellow]", default=str(config["attempts"]))
                config["attempts"] = max(1, min(20, int(new_attempts)))  # Prevent abuse
            elif options[selected_index] == "timeout":
                new_timeout = Prompt.ask("[bold yellow]Enter timeout (seconds)[/bold yellow]", default=str(config["timeout"]))
                config["timeout"] = max(1, int(new_timeout))  # Prevent 0-second timeout
            elif options[selected_index] == "start":
                ping_http()
            elif options[selected_index] == "exit":
                console.print("[bold yellow]Exiting Ping Menu...[/bold yellow]")
                break

def ping_http():
    """Ping a server using HTTP requests with configured settings."""
    server = config["target"]
    attempts = config["attempts"]
    timeout = config["timeout"]
    total_time = 0
    success_count = 0

    # If user entered an IP, attempt to resolve to a hostname
    if server.replace(".", "").isdigit():  # Basic check for IP address
        resolved = ip_to_hostname(server)
        if resolved:
            console.print(f"[bold cyan]Resolved {server} to {resolved}[/bold cyan]")
            server = resolved
        else:
            console.print("[bold red]This IP has no associated hostname![/bold red]")
            return

    # Ensure it has a scheme (http/https)
    if not server.startswith(("http://", "https://")):
        server = "https://" + server

    console.print(f"\n[bold cyan]Pinging {server} ({attempts} attempts, {timeout}s timeout)...[/bold cyan]\n")

    # Prevent abuse: Check total requests limit
    if attempts > config["max_requests"]:
        console.print(f"[bold red]Max request limit exceeded ({config['max_requests']} per session).[/bold red]")
        return

    for i in range(attempts):
        try:
            start_time = time.time()
            response = requests.get(server, timeout=timeout)
            response_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            total_time += response_time
            success_count += 1
            console.print(f"[green]Attempt {i+1}: {response.status_code} - {response_time:.2f}ms[/green]")
        except requests.RequestException as e:
            console.print(f"[red]Attempt {i+1}: Failed ({e})[/red]")

        time.sleep(1)  # **Enforce 1 second delay between requests**

    if success_count > 0:
        avg_time = total_time / success_count
        console.print(f"\n[bold green]Average response time: {avg_time:.2f}ms[/bold green]")
    else:
        console.print("\n[bold red]All attempts failed![/bold red]")

    console.input("\n[bold cyan]Press Enter to return to menu...[/bold cyan]")

def execute():
    """Main function to start the interactive ping menu."""
    interactive_config()
