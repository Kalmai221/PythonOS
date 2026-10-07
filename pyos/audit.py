# pyos/audit.py - the record of what administrators do, and the password prompt before the risky things
#
# record() writes a line to the system log that starts with "admin:", so `logs --admin` can show just these.
# elevate() asks an administrator for their password again before a sensitive action (deleting an account, changing a role or
# someone else's password, wiping the system). A correct password is remembered for a few minutes so a series of
# actions does not ask every time. Switch the prompt off with the admin_reauth setting.
import getpass
import threading
import time

from rich.console import Console

import pyos

console = Console()
GRACE_SECONDS = 5 * 60
_ok_until = {}
_lock = threading.Lock()
MARK = "admin: "


def record(action, detail="", level="INFO", user=None):
    """Add an 'admin:' line to the log."""
    who = user or pyos.userinfo()[0]
    pyos.log.log(f"{MARK}{action}" + (f" {detail}" if detail else ""), level, user=who)


def elevate(action):
    """True if the administrator may go ahead. Asks for their password unless they gave it in the last few minutes."""
    from pyos import settings
    me, role = pyos.userinfo()
    if role != "admin" or not me:
        return False
    if not settings.get("admin_reauth"):
        record(action, "(no password prompt: admin_reauth is off)")
        return True
    with _lock:
        if _ok_until.get(me, 0) > time.time():
            record(action)
            return True
    import users
    console.print(f"[bold yellow]Administrator action:[/bold yellow] {action}")
    for attempt in range(3):
        try:
            password = getpass.getpass(f"Password for {me}: ")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Cancelled.[/yellow]")
            record(action, "cancelled at the password prompt", "WARN", me)
            return False
        ok, _message = users.authenticate(me, password)
        if ok:
            with _lock:
                _ok_until[me] = time.time() + GRACE_SECONDS
            record(action)
            return True
        console.print("[bold red]Wrong password.[/bold red]")
    record(action, "refused: wrong password three times", "WARN", me)
    return False


def remember(user):
    """Treat `user`'s password as just given (sudo has checked it), so the actions inside the command do not ask again."""
    with _lock:
        _ok_until[user] = time.time() + GRACE_SECONDS


def forget(user=None):
    """Drop a remembered password (on logout or lock)."""
    with _lock:
        if user:
            _ok_until.pop(user, None)
        else:
            _ok_until.clear()
