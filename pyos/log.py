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
