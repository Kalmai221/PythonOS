#!/usr/bin/env python3
"""A small text adventure engine, with a story called "The Lighthouse Keeper's Key". Type simple commands: go north, take lamp,
use key, look, inventory, examine <thing>, talk, save, load, help, quit. Stories are plain JSON: run  adventure <story.json>  to play
your own (see STORY below for the format)."""
import json
import os
import sys

from rich.console import Console
from rich.markup import escape

try:
    from pyos import appdata, fs
except ImportError:
    appdata = fs = None

console = Console()

# A story: rooms (description, exits, items), items (name, description, takeable), and rules for "use"/"talk".
STORY = {
    "title": "The Lighthouse Keeper's Key",
    "intro": "The storm has knocked out the light at Gull Point. The keeper left a note: the lamp room is locked and the key is "
             "somewhere on the island. Without the beam, a ship is heading for the rocks. You have until dawn.",
    "start": "beach",
    "goal": "lamp_room",
    "rooms": {
        "beach": {"desc": "A cold shingle beach. Waves pound the rocks. A path leads north to a cottage; steps lead up east to the lighthouse.",
                  "exits": {"north": "cottage", "east": "tower_base"}, "items": ["driftwood"]},
        "cottage": {"desc": "The keeper's cottage. A kettle is still warm. A door at the back leads to a shed (west); the beach is south.",
                    "exits": {"south": "beach", "west": "shed"}, "items": ["note", "matches", "lamp"]},
        "shed": {"desc": "A cramped shed full of tools. It is very dark; you can hardly see.",
                 "exits": {"east": "cottage"}, "items": ["oilcan"], "dark": True},
        "tower_base": {"desc": "The foot of the lighthouse. A heavy iron door is bolted shut and a spiral stair beyond it climbs into the dark. "
                              "The beach is west.",
                       "exits": {"west": "beach", "up": "stairs"}, "items": [], "locked": {"up": "iron_key"}},
        "stairs": {"desc": "The spiral stair. Up above, the lamp room door is shut.",
                   "exits": {"down": "tower_base", "up": "lamp_room"}, "items": [], "locked": {"up": "brass_key"}},
        "lamp_room": {"desc": "The great lamp room. The lens is dark: the lamp needs oil and a light.", "exits": {"down": "stairs"}, "items": []},
    },
    "items": {
        "driftwood": {"desc": "A long piece of driftwood. Something is wedged in a crack: an iron key!", "take": True,
                      "reveals": "iron_key", "revealed_text": "You work the iron key free from the driftwood."},
        "iron_key": {"desc": "A heavy iron key.", "take": True, "hidden": True},
        "note": {"desc": "The keeper's note: 'Brass key is in the oilcan. Light the lamp with oil AND a match. - J.'", "take": True},
        "matches": {"desc": "A box of dry matches.", "take": True},
        "lamp": {"desc": "A hand lantern. It will light the dark shed if you have matches.", "take": True},
        "oilcan": {"desc": "A dented oilcan, sloshing with lamp oil. Something rattles inside: a brass key!", "take": True,
                   "reveals": "brass_key", "revealed_text": "You tip the oilcan and a brass key drops out."},
        "brass_key": {"desc": "A small brass key.", "take": True, "hidden": True},
    },
    "light_source": "lamp",
    "win_text": "You pour the oil, strike a match and the great lens flares into life. A beam sweeps the sea - far out, a ship turns "
                "away from the rocks. You saved them.",
    "win_requires": ["oilcan", "matches"],
}
VERBS = {"n": "north", "s": "south", "e": "east", "w": "west", "u": "up", "d": "down", "l": "look", "i": "inventory", "x": "examine"}


class Game:
    def __init__(self, story):
        self.story = story
        self.room = story["start"]
        self.inventory = []
        self.found = set()                   # hidden items that have been revealed
        self.taken_from = {}                 # item -> room it was taken from (to hide it from the room list)
        self.moves = 0
        self.won = False
        self.rooms = {k: dict(v, items=list(v.get("items", []))) for k, v in story["rooms"].items()}

    # -------------------------------------------------------------- helpers
    def item(self, name):
        return self.story["items"].get(name, {})

    def has_light(self):
        room = self.rooms[self.room]
        if not room.get("dark"):
            return True
        light = self.story.get("light_source")
        return light in self.inventory and "matches" in self.inventory

    def describe(self):
        room = self.rooms[self.room]
        if not self.has_light():
            return "It is pitch dark. You can hardly move. (You need a light: a lamp and something to light it.)"
        text = room["desc"]
        things = [i for i in room["items"] if not self.item(i).get("hidden") or i in self.found]
        if things:
            text += "\nYou see: " + ", ".join(things) + "."
        text += "\nExits: " + ", ".join(room["exits"]) + "."
        return text

    def match_item(self, word, pool):
        word = word.strip().lower()
        for name in pool:
            if word == name or word == name.replace("_", " ") or word in name.split("_"):
                return name
        return None

    # --------------------------------------------------------------- verbs
    def go(self, direction):
        room = self.rooms[self.room]
        if not self.has_light() and self.room == "shed" and direction != "east":
            return "You stumble in the dark."
        target = room["exits"].get(direction)
        if not target:
            return "You cannot go that way."
        need = room.get("locked", {}).get(direction)
        if need and need not in self.inventory:
            return f"It is locked. You need the {need.replace('_', ' ')}."
        self.room = target
        self.moves += 1
        if target == self.story["goal"]:
            return self.describe()
        return self.describe()

    def take(self, word):
        if not self.has_light():
            return "You cannot find anything in the dark."
        pool = [i for i in self.rooms[self.room]["items"] if not self.item(i).get("hidden") or i in self.found]
        name = self.match_item(word, pool)
        if not name:
            return "There is no such thing here."
        if not self.item(name).get("take"):
            return "You cannot take that."
        self.rooms[self.room]["items"].remove(name)
        self.inventory.append(name)
        return f"Taken: {name.replace('_', ' ')}."

    def drop(self, word):
        name = self.match_item(word, self.inventory)
        if not name:
            return "You are not carrying that."
        self.inventory.remove(name)
        self.rooms[self.room]["items"].append(name)
        return "Dropped."

    def examine(self, word):
        pool = self.inventory + [i for i in self.rooms[self.room]["items"] if not self.item(i).get("hidden") or i in self.found]
        name = self.match_item(word, pool)
        if not name:
            return "You see no such thing."
        text = self.item(name)["desc"]
        info = self.item(name)
        if info.get("reveals") and info["reveals"] not in self.found:
            self.found.add(info["reveals"])
            where = self.room if name in self.rooms[self.room]["items"] else None
            if where:
                self.rooms[where]["items"].append(info["reveals"])
            else:
                self.inventory.append(info["reveals"])
            text += "\n" + info.get("revealed_text", "You find something.")
        return text

    def use(self, word):
        name = self.match_item(word, self.inventory)
        if not name:
            return "You are not carrying that."
        need = self.story.get("win_requires", [])
        if self.room == self.story["goal"] and all(n in self.inventory for n in need) and name in need:
            self.won = True
            return self.story["win_text"]
        if name == "lamp":
            return "The lamp is ready; it needs a match to light." if "matches" not in self.inventory else "You light the lamp. Its glow fills the room."
        return "Nothing happens."

    def command(self, line):
        words = line.lower().split()
        if not words:
            return ""
        verb, rest = VERBS.get(words[0], words[0]), " ".join(words[1:])
        if verb in ("north", "south", "east", "west", "up", "down"):
            return self.go(verb)
        if verb in ("go", "walk", "move"):
            return self.go(VERBS.get(rest, rest))
        if verb == "look":
            return self.describe()
        if verb == "inventory":
            return "You carry: " + (", ".join(self.inventory) or "nothing") + "."
        if verb in ("take", "get", "grab", "pick"):
            return self.take(rest.replace("up ", "", 1))
        if verb == "drop":
            return self.drop(rest)
        if verb in ("examine", "inspect", "read", "search"):
            return self.examine(rest)
        if verb in ("use", "light", "pour"):
            return self.use(rest or "lamp")
        return "I do not understand. Try: go north, take lamp, examine note, use matches, inventory, look, help."

    def state(self):
        return {"room": self.room, "inventory": self.inventory, "found": sorted(self.found), "moves": self.moves,
                "items": {k: v["items"] for k, v in self.rooms.items()}}

    def load_state(self, data):
        self.room, self.inventory, self.found, self.moves = data["room"], list(data["inventory"]), set(data["found"]), data["moves"]
        for k, items in data["items"].items():
            if k in self.rooms:
                self.rooms[k]["items"] = list(items)


def load_story(path):
    """A story file is JSON with the same keys as STORY above. Returns (story, error)."""
    try:
        with open(fs.resolve(path) if fs else path, encoding="utf-8") as f:
            story = json.load(f)
    except (OSError, ValueError, PermissionError) as e:
        return None, f"could not read the story: {e}"
    for key in ("title", "start", "goal", "rooms", "items"):
        if key not in story:
            return None, f"the story has no '{key}'"
    return story, None


def main(args):
    story = STORY
    if args:
        story, error = load_story(args[0])
        if error:
            console.print(f"[red]{escape(error)}[/red]")
            return
    game = Game(story)
    console.print(f"[bold cyan]{escape(story['title'])}[/bold cyan]\n{escape(story.get('intro', ''))}\n")
    console.print(escape(game.describe()))
    while not game.won:
        try:
            line = input("\n> ").strip()
        except EOFError:
            return
        low = line.lower()
        if low in ("q", "quit", "exit"):
            return
        if low == "help":
            console.print("Commands: go <direction> (or n/s/e/w/u/d), look, take <thing>, drop <thing>, examine <thing>, use <thing>, "
                          "inventory, save, load, quit.")
            continue
        if low == "save" and appdata:
            appdata.save("adventure_save", game.state())
            console.print("Saved.")
            continue
        if low == "load" and appdata:
            data = appdata.load("adventure_save")
            if data:
                game.load_state(data)
                console.print(escape(game.describe()))
            else:
                console.print("There is no saved game.")
            continue
        console.print(escape(game.command(line)))
    console.print(f"\n[bold green]{escape(game.story['win_text'])}[/bold green]\nYou finished in {game.moves} moves.")


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
