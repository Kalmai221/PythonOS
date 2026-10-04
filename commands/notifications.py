import datetime
from rich.console import Console
from rich.markup import escape
from rich.table import Table
import pyos
from pyos import notify, settings

console = Console()
config = {
    "name": "notifications",
    "description": "Show recent notifications (notifications [clear|test <message>]).",
    "alias": ["notify"],
}


def execute(args=None):
    args = list(args or [])
    user = pyos.userinfo()[0]
    if args and args[0] == "clear":
        notify.clear(user)
        console.print("[green]Notifications cleared.[/green]")
        return True
    if args and args[0] == "test":
        notify.notify(" ".join(args[1:]) or "This is a test notification.", title="Test", user=user)
        return True

    items = notify.history(user, limit=30)
    if not items:
        console.print("[dim]No notifications.[/dim]")
        return True
    table = Table(header_style="bold blue", expand=True)
    table.add_column("When", no_wrap=True)
    table.add_column("From", style="cyan", no_wrap=True)
    table.add_column("Message")
    for item in items:
        when = datetime.datetime.fromtimestamp(item["time"])
        table.add_row(when.strftime("%b %d ") + settings.format_time(when)[:5], escape(item["title"]), escape(str(item["message"])))
    console.print(table)
    if not settings.get("notifications"):
        console.print("[dim]Notifications are switched off (settings set notifications on).[/dim]")
    return True
