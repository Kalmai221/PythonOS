# pyos/power.py - battery watching for laptops and tablets
#
# A thread started after login looks at the battery every 30 seconds. When it is not charging:
#   - at low_battery_percent (default 15)  -> one warning notification, and the same on screen before the next prompt
#   - at critical_battery_percent (5)      -> a one-minute warning, then a normal shutdown (never a sudden power cut, so the
#                                            files and the persistent storage are closed properly)
# Plugging the charger in at any point cancels it. Computers without a battery (and phones, where Android looks after this) do
# nothing. The settings can be 0 to switch either step off.
import threading
import time

CHECK_SECONDS = 30
GRACE_SECONDS = 60


def battery():
    """(percent, plugged in) or None when there is no battery."""
    try:
        import psutil
        info = psutil.sensors_battery()
    except Exception:
        return None
    if info is None or info.percent is None:
        return None
    return float(info.percent), bool(info.power_plugged)


def decide(percent, plugged, low, critical, warned_low):
    """What to do for this reading: 'none', 'low' (warn once), 'critical' (start the countdown) or 'recovered'."""
    if plugged:
        return "recovered" if warned_low else "none"
    if critical and percent <= critical:
        return "critical"
    if low and percent <= low and not warned_low:
        return "low"
    return "none"


class Watcher(threading.Thread):
    def __init__(self, user, notify, request_shutdown, read=battery, sleep=time.sleep):
        super().__init__(name="battery-watch", daemon=True)
        self.user, self.notify, self.request_shutdown = user, notify, request_shutdown
        self.read, self.sleep = read, sleep
        self.warned_low = False
        self.stopped = threading.Event()

    def step(self):
        """One check. Returns the decision (for tests)."""
        from pyos import settings
        reading = self.read()
        if reading is None:
            return "none"
        percent, plugged = reading
        action = decide(percent, plugged, settings.get("low_battery_percent"), settings.get("critical_battery_percent"), self.warned_low)
        if action == "low":
            self.warned_low = True
            self.notify(f"Battery low ({percent:.0f}%). Plug in the charger.", "warn")
        elif action == "recovered":
            self.warned_low = False
        elif action == "critical":
            self.notify(f"Battery critical ({percent:.0f}%). PythonOS will shut down in {GRACE_SECONDS} seconds to protect your files. "
                        "Plug in the charger to cancel.", "error")
            for _ in range(GRACE_SECONDS):
                if self.stopped.is_set():
                    return action
                self.sleep(1)
                again = self.read()
                if again is None or again[1]:
                    self.notify("Charger connected: shutdown cancelled.", "info")
                    return "cancelled"
            self.request_shutdown()
        return action

    def run(self):
        while not self.stopped.is_set():
            try:
                self.step()
            except Exception:
                pass
            self.stopped.wait(CHECK_SECONDS)

    def stop(self):
        self.stopped.set()
