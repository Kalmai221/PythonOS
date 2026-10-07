#!/usr/bin/env python3
"""Checks the logic of the apps added in 1.0.12: contacts, countdown, loan, colors, cipher, morse, dupes, bulkrename, readability, life, maze,
nim, rps. Only the plain functions are called; nothing is shown on a screen and no network is used."""
import datetime
import functools
import importlib.util
import itertools
import os
import random
import shutil
import sys
import tempfile

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def load(kind, name):
    spec = importlib.util.spec_from_file_location("app3_" + name, os.path.join(REPO, "online_packages", kind, name, "run.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def winning(piles, misere, cache):
    """True if the player to move can force a win (brute force, to check the strategies in nim)."""
    key = tuple(sorted(piles))
    if key in cache:
        return cache[key]
    if sum(key) == 0:
        cache[key] = misere                      # the player to move faces an empty board: the opponent took the last stone
        return cache[key]
    result = False
    for i, p in enumerate(key):
        for n in range(1, p + 1):
            after = list(key)
            after[i] -= n
            if not winning(after, misere, cache):
                result = True
    cache[key] = result
    return result


def main():
    tmp = tempfile.mkdtemp()
    here = os.getcwd()
    try:
        os.chdir(tmp)

        # ---- contacts
        contacts = load("utilities", "contacts")
        people = [contacts.make("Ada  Lovelace", "555-0100", "ada@example.com", "met at the fair"), contacts.make("Alan Turing", "555-0199"),
                  contacts.make("Grace Hopper", "", "grace@navy.example")]
        assert people[0]["name"] == "Ada Lovelace"
        assert [c["name"] for c in contacts.search(people, "a")] == ["Ada Lovelace", "Alan Turing", "Grace Hopper"], "names that start with it come first"
        people.append(contacts.make("Lena Park"))
        assert [c["name"] for c in contacts.search(people, "l")][0] == "Lena Park", "a name that starts with it comes before names that only contain it"
        people.pop()
        assert [c["name"] for c in contacts.search(people, "555")] == ["Ada Lovelace", "Alan Turing"]
        assert contacts.search(people, "navy")[0]["name"] == "Grace Hopper" and contacts.search(people, "zzz") == []
        words, found = contacts.options(["Ada", "Lovelace", "--phone", "1", "--email", "a@b"])
        assert words == ["Ada", "Lovelace"] and found == {"phone": "1", "email": "a@b"}
        assert contacts.to_csv(people).splitlines()[0] == "name,phone,email,note" and "Ada Lovelace,555-0100" in contacts.to_csv(people)
        contacts.save(people)
        assert [c["name"] for c in contacts.load()] == ["Ada Lovelace", "Alan Turing", "Grace Hopper"]
        write(contacts.data_file(".contacts.json"), b"{broken")
        assert contacts.load() == []

        # ---- countdown
        countdown = load("utilities", "countdown")
        today = datetime.date(2026, 10, 7)
        assert countdown.parse_date("2026-12-20", today) == datetime.date(2026, 12, 20)
        assert countdown.parse_date("in 30 days", today) == datetime.date(2026, 11, 6)
        assert countdown.parse_date("in 2 weeks", today) == datetime.date(2026, 10, 21)
        assert countdown.parse_date("in 5 months", today) == datetime.date(2027, 3, 7)
        assert countdown.parse_date("in 1 month", datetime.date(2026, 1, 31)) == datetime.date(2026, 2, 28), "the day is clamped to a short month"
        assert countdown.parse_date("tomorrow", today) == datetime.date(2026, 10, 8)
        try:
            countdown.parse_date("someday", today)
            raise AssertionError("must fail")
        except ValueError:
            pass
        assert countdown.days_left("2026-10-10", today) == 3 and countdown.days_left("2026-10-01", today) == -6
        assert countdown.describe(0) == "today" and countdown.describe(1) == "tomorrow" and countdown.describe(-1) == "yesterday"
        assert countdown.describe(15) == "in 15 days (2 weeks 1 day)" and countdown.describe(-4) == "4 days ago"
        events = [{"name": "b", "date": "2026-12-01"}, {"name": "a", "date": "2026-10-20"}, {"name": "old", "date": "2026-01-01"}]
        assert [e["name"] for e in countdown.ordered(events, today)] == ["a", "b"]
        assert [e["name"] for e in countdown.ordered(events, today, past=True)] == ["old"]

        # ---- loan
        loan = load("utilities", "loan")
        assert abs(loan.payment(250000, 5.5, 30) - 1419.47) < 0.01
        assert abs(loan.payment(12000, 0, 1) - 1000) < 1e-9
        rows = loan.schedule(250000, 5.5, 30)
        assert len(rows) == 360 and rows[-1][4] < 0.01 and abs(sum(r[3] for r in rows) - 250000) < 0.01
        paid, interest = loan.totals(rows)
        assert abs(paid - interest - 250000) < 0.01 and 255000 < interest < 265000
        quick = loan.schedule(250000, 5.5, 30, extra=200)
        assert len(quick) < 360 and loan.totals(quick)[1] < interest, "paying extra shortens the loan and saves interest"
        try:
            loan.payment(1000, 5, 0)
            raise AssertionError("must fail")
        except ValueError:
            pass

        # ---- colors
        colors = load("utilities", "colors")
        assert colors.parse(["#ff8800"]) == (255, 136, 0) and colors.parse(["#f80"]) == (255, 136, 0) and colors.parse(["ff8800"]) == (255, 136, 0)
        assert colors.parse(["rgb", "255", "136", "0"]) == (255, 136, 0) and colors.parse(["hsl", "0", "100", "50"]) == (255, 0, 0)
        assert colors.parse(["coral"]) == (255, 127, 80) and colors.parse(["Sky", "Blue"]) == (135, 206, 235)
        assert colors.parse(["beige"]) == (245, 245, 220), "a name that looks like hex is still a name"
        for bad in (["nonsense"], ["rgb", "300", "0", "0"], ["#12"]):
            try:
                colors.parse(bad)
                raise AssertionError(bad)
            except ValueError:
                pass
        assert colors.to_hex((255, 136, 0)) == "#ff8800" and colors.to_hsl((255, 0, 0)) == (0, 100, 50) and colors.to_hsv((0, 0, 255)) == (240, 100, 100)
        assert colors.nearest_name((255, 130, 75)) == "coral" and colors.nearest_name((1, 1, 1)) == "black"
        assert colors.rotate((255, 0, 0), 180) == (0, 255, 255) and colors.shade((200, 100, 0), 0.5) == (100, 50, 0)
        assert colors.shade((0, 0, 0), 2) == (255, 255, 255)

        # ---- cipher
        cipher = load("utilities", "cipher")
        assert cipher.caesar("Hello, World", 3) == "Khoor, Zruog" and cipher.caesar("Khoor, Zruog", -3) == "Hello, World"
        assert cipher.caesar(cipher.caesar("Uryyb", 13), 13) == "Uryyb"
        assert cipher.atbash("Hello") == "Svool" and cipher.atbash(cipher.atbash("Any Text 123")) == "Any Text 123"
        assert cipher.vigenere("ATTACKATDAWN", "LEMON") == "LXFOPVEFRNHR" and cipher.vigenere("LXFOPVEFRNHR", "LEMON", decode=True) == "ATTACKATDAWN"
        assert cipher.vigenere("Attack at dawn!", "key", True) != "Attack at dawn!"
        assert cipher.rail_encode("WEAREDISCOVEREDFLEEATONCE", 3) == "WECRLTEERDSOEEFEAOCAIVDEN"
        assert cipher.rail_decode("WECRLTEERDSOEEFEAOCAIVDEN", 3) == "WEAREDISCOVEREDFLEEATONCE"
        for rails in range(2, 8):
            assert cipher.rail_decode(cipher.rail_encode("The quick brown fox", rails), rails) == "The quick brown fox"
        try:
            cipher.vigenere("x", "123")
            raise AssertionError("a key needs letters")
        except ValueError:
            pass
        secret = cipher.caesar("The quick brown fox jumps over the lazy dog and runs away from the farm", 7)
        assert cipher.crack(secret)[0][1] == 7 and cipher.crack(secret)[0][2].startswith("The quick")

        # ---- morse
        morse = load("utilities", "morse")
        assert morse.encode("SOS") == "... --- ..." and morse.encode("hi there") == ".... .. / - .... . .-. ."
        assert morse.decode("... --- ...") == "SOS" and morse.decode(".... .. / - .... . .-. .") == "HI THERE" and morse.decode(".-.- ...") == "?S"
        text = "Meet at 9, ok?"
        assert morse.decode(morse.encode(text)) == text.upper()
        assert morse.encode("~~~") == "" and len(morse.REVERSE) == len(morse.CODE)

        # ---- dupes
        dupes = load("utilities", "dupes")
        base = os.path.join(tmp, "dupes-test")
        write(os.path.join(base, "a.txt"), b"same content" * 200)
        write(os.path.join(base, "sub", "b.txt"), b"same content" * 200)
        write(os.path.join(base, "sub", "c.txt"), b"same content" * 200)
        write(os.path.join(base, "other.txt"), b"different!!!" * 200)
        write(os.path.join(base, "tiny1"), b"x")
        write(os.path.join(base, "tiny2"), b"x")
        write(os.path.join(base, "same-size.txt"), b"same content"[::-1] * 200)
        groups = dupes.find_duplicates(base)
        assert len(groups) == 1 and len(groups[0]) == 3, groups
        assert dupes.wasted(groups) == 2 * 2400 and dupes.human(2400) == "2.3 KB"
        assert len(dupes.find_duplicates(base, min_size=1)) == 2, "small files count when the limit is lowered"
        review = os.path.join(tmp, "review")
        assert dupes.move_extras(groups, review) == 2
        assert os.path.isfile(os.path.join(base, "a.txt")) and not os.path.exists(os.path.join(base, "sub", "b.txt")) and len(os.listdir(review)) == 2
        assert dupes.find_duplicates(base) == []

        # ---- bulkrename
        bulk = load("utilities", "bulkrename")
        assert bulk.plan(["IMG_1.jpg", "IMG_2.jpg", "notes.txt"], "replace", ["IMG_", "holiday_"]) == [("IMG_1.jpg", "holiday_1.jpg"), ("IMG_2.jpg", "holiday_2.jpg")]
        assert bulk.plan(["b.png", "a.png"], "number", ["pic_{n:03}"]) == [("a.png", "pic_001.png"), ("b.png", "pic_002.png")]
        assert bulk.plan(["My File.TXT"], "lower", []) == [("My File.TXT", "my file.TXT")] and bulk.plan(["My File.txt"], "snake", []) == [("My File.txt", "My_File.txt")]
        assert bulk.plan(["12-report.txt"], "regex", [r"^(\d+)-(.*)$", r"\2-\1"]) == [("12-report.txt", "report.txt-12")]
        for bad in (("regex", ["(", "x"]), ("number", ["{bad}"]), ("nope", []), ("replace", [""])):
            try:
                bulk.plan(["a"], *bad)
                raise AssertionError(bad)
            except ValueError:
                pass
        assert bulk.conflicts([("a.txt", "x.txt"), ("b.txt", "x.txt")], ["a.txt", "b.txt"]), "two files becoming one name are refused"
        assert bulk.conflicts([("a.txt", "b.txt")], ["a.txt", "b.txt"]), "a name already taken is refused"
        assert not bulk.conflicts([("a.txt", "b.txt"), ("b.txt", "a.txt")], ["a.txt", "b.txt"]), "a swap is fine"
        assert bulk.conflicts([("a.txt", "../evil")], ["a.txt"]) and bulk.conflicts([("a.txt", " ")], ["a.txt"])
        folder = os.path.join(tmp, "rename")
        for name, text in (("a.txt", b"A"), ("b.txt", b"B"), ("c.txt", b"C")):
            write(os.path.join(folder, name), text)
        bulk.apply(folder, [("a.txt", "b.txt"), ("b.txt", "a.txt"), ("c.txt", "d.txt")])
        assert open(os.path.join(folder, "b.txt"), "rb").read() == b"A" and open(os.path.join(folder, "a.txt"), "rb").read() == b"B"
        assert sorted(os.listdir(folder)) == ["a.txt", "b.txt", "d.txt"], "the swap and the chain lost nothing"

        # ---- readability
        reading = load("utilities", "readability")
        assert [reading.syllables(w) for w in ("cat", "table", "make", "beautiful", "the", "queue", "")] == [1, 2, 1, 3, 1, 1, 0]
        easy = reading.analyse("The cat sat. The dog ran. We had fun.")
        hard = reading.analyse("Notwithstanding considerable administrative complications, the committee unanimously authorised comprehensive reorganisation.")
        assert easy["words"] == 9 and easy["sentences"] == 3 and easy["flesch"] > 90 and hard["flesch"] < 20 and hard["grade"] > easy["grade"]
        assert reading.analyse("")["words"] == 0 and "flesch" not in reading.analyse("")
        counted = dict(reading.analyse("Python python PYTHON and the code code")["top"])
        assert counted == {"python": 3, "code": 2}, counted
        assert reading.describe_flesch(95) == "very easy" and reading.describe_flesch(10) == "very hard" and reading.describe_flesch(65) == "plain English"
        assert reading.analyse("one\n\ntwo\n\nthree")["paragraphs"] == 3

        # ---- life
        life = load("games", "life")
        blinker = life.parse(life.PATTERNS["blinker"], (5, 5))
        assert life.step(blinker) != blinker and life.step(life.step(blinker)) == blinker, "a blinker has period 2"
        block = life.parse(["##", "##"])
        assert life.step(block) == block, "a block never changes"
        glider = life.parse(life.PATTERNS["glider"])
        moved = functools.reduce(lambda cells, _: life.step(cells), range(4), glider)
        assert moved == {(x + 1, y + 1) for x, y in glider}, "a glider moves one cell diagonally every 4 generations"
        assert life.step(set()) == set() and life.step({(0, 0)}) == set()
        assert life.render({(1, 0)}, 3, 2) == ["·●·", "···"]
        assert len(life.random_start(20, 10, random.Random(1))) > 20
        assert len(life.step(life.parse(life.PATTERNS["rpentomino"], (0, 0)))) > 0

        # ---- maze
        maze = load("games", "maze")
        rng = random.Random(5)
        for width, height in ((8, 6), (14, 9), (3, 3)):
            m = maze.generate(width, height, rng)
            edges = sum(len(v) for v in m.values()) // 2
            assert edges == width * height - 1, "a perfect maze has exactly one route between any two cells"
            assert all(a in m[b] for a in m for b in m[a]), "passages work both ways"
            path = maze.solve(m, (0, 0), (width - 1, height - 1))
            assert path[0] == (0, 0) and path[-1] == (width - 1, height - 1)
            assert all(b in m[a] for a, b in zip(path, path[1:])), "every step of the answer goes through an open passage"
        tiny = {(0, 0): {(1, 0)}, (1, 0): {(0, 0)}, (0, 1): set(), (1, 1): set()}
        assert maze.move(tiny, (0, 0), "d") == (1, 0) and maze.move(tiny, (0, 0), "s") == (0, 0) and maze.move(tiny, (0, 0), "dxa") == (0, 0)
        assert maze.solve(tiny, (0, 0), (1, 1)) == []
        assert "@" in maze.draw(maze.generate(4, 3, rng), 4, 3, (0, 0), (3, 2)) and maze.draw(tiny, 2, 2, (0, 0), (1, 1)).count("\n") == 4

        # ---- nim: the strategy is checked against a brute-force search over every small game
        nim = load("games", "nim")
        assert nim.nim_sum([3, 4, 5]) == 2 and nim.nim_sum([1, 2, 3]) == 0
        for misere in (False, True):
            cache = {}
            for size in range(1, 4):
                for piles in itertools.product(range(0, 6), repeat=size):
                    if sum(piles) == 0:
                        continue
                    piles = list(piles)
                    move = nim.best_move(piles, misere)
                    if winning(piles, misere, cache):
                        assert move is not None, (piles, misere, "a winning position must have a winning move")
                        i, n = move
                        assert 1 <= n <= piles[i], (piles, move)
                        after = list(piles)
                        after[i] -= n
                        assert sum(after) > 0 or not misere, "taking the last stone loses misere nim"
                        assert not winning(after, misere, cache), (piles, move, misere, "the move must leave a lost position")
                    else:
                        assert move is None, (piles, misere, "a lost position has no winning move to offer")
        taken = nim.computer_move([2, 2], False, random.Random(1), mistake_chance=0.0)
        assert taken in ((0, 1), (0, 2), (1, 1), (1, 2)) and nim.computer_move([1, 2], False, random.Random(1), 0.0) == (1, 1)
        assert nim.computer_move([3, 4, 5], True, random.Random(2), 1.0)[1] >= 1, "a deliberate mistake is still a legal move"

        # ---- rps
        rps = load("games", "rps")
        for a, b in itertools.product(rps.FULL, repeat=2):
            assert rps.outcome(a, b) == -rps.outcome(b, a)
        assert rps.outcome("rock", "scissors") == 1 and rps.outcome("paper", "rock") == 1 and rps.outcome("spock", "lizard") == -1 and rps.outcome("rock", "rock") == 0
        assert all(sum(1 for b in rps.FULL if rps.outcome(a, b) == 1) == 2 for a in rps.FULL), "every move beats exactly two others"
        assert all((a, b) in rps.VERB for a in rps.FULL for b in rps.FULL[a]), "every winning pair has a verb"
        assert rps.counter_to("rock", ["rock", "paper", "scissors"]) == "paper"
        brain = rps.Predictor()
        for move in ["rock", "paper"] * 6:
            brain.learn(move)
        brain.last = "rock"
        assert all(rps.outcome(brain.guess(["rock", "paper", "scissors"], random.Random(i)), "paper") == 1 for i in range(10)), "it learns that paper follows rock"
        assert rps.Predictor().guess(["rock", "paper", "scissors"]) in ("rock", "paper", "scissors")
    finally:
        os.chdir(here)
        shutil.rmtree(tmp, ignore_errors=True)
    print("batch 3 apps: all checks passed")


if __name__ == "__main__":
    main()
