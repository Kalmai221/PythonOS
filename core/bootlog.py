"""Boot timings: every boot saves how long each real step took (.OSData/boot.json, the last 10 boots)."""
import json
import os
import time

BOOT_FILE = os.path.join(".OSData", "boot.json")
KEEP = 10


def load():
    try:
        with open(BOOT_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def save_boot(steps, total_ms, animation_ms=0.0):
    """Remember one boot. Never raises: a full disk must not stop PythonOS starting."""
    try:
        boots = load()
        boots.append({"time": time.time(), "total_ms": round(total_ms, 1), "animation_ms": round(animation_ms, 1), "steps": steps})
        os.makedirs(os.path.dirname(BOOT_FILE), exist_ok=True)
        with open(BOOT_FILE, "w", encoding="utf-8") as f:
            json.dump(boots[-KEEP:], f)
    except OSError:
        pass


def averages(boots=None):
    """{step name: average ms over the saved boots} in boot order."""
    boots = boots if boots is not None else load()
    totals, counts, order = {}, {}, []
    for b in boots:
        for s in b.get("steps", []):
            if s["name"] not in totals:
                order.append(s["name"])
            totals[s["name"]] = totals.get(s["name"], 0) + s["ms"]
            counts[s["name"]] = counts.get(s["name"], 0) + 1
    return {n: totals[n] / counts[n] for n in order}
