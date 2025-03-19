import requests
from rich.console import Console
from rich.table import Table

# Command metadata
config = {
    "name": "ipinfo",
    "description": "Displays public IP address information."
}

console = Console()

def get_ip_info():
    try:
        # Fetch IP information from ipinfo.io API
        response = requests.get("https://ipinfo.io/json")
        response.raise_for_status()
        data = response.json()

        # Create a table for displaying IP information
        table = Table(title="IP Information", show_header=True, header_style="bold magenta")
        table.add_column("Field", style="dim", width=20)
        table.add_column("Value", justify="left")

        # Adding data rows
        table.add_row("IP Address", data.get('ip', 'N/A'))
        table.add_row("Hostname", data.get('hostname', 'N/A'))
        table.add_row("Location", f"{data.get('city', 'N/A')}, {data.get('region', 'N/A')}, {data.get('country', 'N/A')}")
        table.add_row("Org", data.get('org', 'N/A'))
        table.add_row("Region Code", data.get('region', 'N/A'))
        table.add_row("City", data.get('city', 'N/A'))
        table.add_row("Country", data.get('country', 'N/A'))

        # Display the table
        console.print(table)

    except requests.RequestException as e:
        console.print(f"[bold red]Error fetching IP information:[/bold red] {e}")

def execute():
    """Main function to run the IP info command."""
    get_ip_info()
