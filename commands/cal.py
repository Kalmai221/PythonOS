import calendar
import datetime

from pyos import textcmd

config = {"name": "cal", "description": "Show a calendar (cal [month] [year]); no arguments shows this month."}


def execute(args=None):
    today = datetime.date.today()
    month, year = today.month, today.year
    values = list(args or [])
    try:
        if len(values) == 1:
            if len(values[0]) == 4:
                year, month = int(values[0]), None
            else:
                month = int(values[0])
        elif len(values) == 2:
            month, year = int(values[0]), int(values[1])
        elif values:
            raise ValueError
        if (month is not None and not 1 <= month <= 12) or not 1 <= year <= 9999:
            raise ValueError
    except ValueError:
        textcmd.console.print("[bold red]Usage:[/bold red] cal [month] [year]   (cal 2027 shows a whole year)")
        return False
    text = calendar.TextCalendar(firstweekday=0).formatyear(year) if month is None else calendar.TextCalendar(firstweekday=0).formatmonth(year, month)
    for line in text.splitlines():
        textcmd.emit(line)
    return True
