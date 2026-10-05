# pyos/log.py - system log written to /var/log/system.log
import os
import datetime

LOG_FILE = os.path.join(os.path.abspath("files"), "var", "log", "system.log")
MAX_BYTES = 256 * 1024


def log(message, level="INFO", user=None):
    """Append a line to the system log. Never raises."""
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_BYTES:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.writelines(lines[len(lines) // 2:])
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        who = f" {user}:" if user else ""
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"{stamp} [{level}]{who} {message}\n")
    except Exception:
        pass


# ------------------------------------------------------------------ reading
import re as _re
import time as _time

_LINE = _re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[(\w+)\](?: (\S+?):)? (.*)$")
LEVELS = {"debug": 0, "info": 1, "warn": 2, "warning": 2, "error": 3}


def parse_when(text, now=None):
    """'today', 'yesterday', '2h', '30m', '3d', '2026-10-05' or '2026-10-05 14:30' -> datetime. Raises ValueError."""
    now = now or datetime.datetime.now()
    text = text.strip().lower()
    if text == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if text == "yesterday":
        return (now - datetime.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    m = _re.fullmatch(r"(\d+)([mhd])", text)
    if m:
        return now - datetime.timedelta(**{{"m": "minutes", "h": "hours", "d": "days"}[m.group(2)]: int(m.group(1))})
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text, fmt)
        except ValueError:
            pass
    raise ValueError(f"'{text}' is not a time - try today, yesterday, 2h, 3d, 2026-10-05 or '2026-10-05 14:30'")


def entries(path=None):
    """Parsed log lines: [{time (datetime), level, user, message, raw}]."""
    out = []
    try:
        with open(path or LOG_FILE, encoding="utf-8", errors="replace") as f:
            for raw in f:
                m = _LINE.match(raw.rstrip("\n"))
                if not m:
                    continue
                out.append({"time": datetime.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S"), "level": m.group(2).upper(),
                            "user": m.group(3) or "", "message": m.group(4), "raw": raw.rstrip("\n")})
    except OSError:
        pass
    return out


def query(items, user=None, level=None, since=None, until=None, text=None, only_user=None):
    """Filter entries. level is a minimum (warn shows warn and error). only_user limits to that user's lines plus system
    lines that name nobody (what a non-admin may see)."""
    floor = LEVELS.get((level or "").lower())
    result = []
    for e in items:
        if only_user is not None and e["user"] not in ("", only_user):
            continue
        if user and e["user"] != user:
            continue
        if floor is not None and LEVELS.get(e["level"].lower(), 1) < floor:
            continue
        if since and e["time"] < since:
            continue
        if until and e["time"] > until:
            continue
        if text and text.lower() not in e["message"].lower() and text.lower() not in e["user"].lower():
            continue
        result.append(e)
    return result
