#!/usr/bin/env python3
"""Checks the logic of the apps added in 1.0.8: flashcards, expenses, habits, pomodoro, sokoban, lightsout, slide15."""
import datetime
import importlib.util
import os
import random
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))


def load(path):
    spec = importlib.util.spec_from_file_location("app_" + path.replace("/", "_"), os.path.join(ROOT, "online_packages", path, "run.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def solvable(soko, rows):
    """Breadth-first search over (worker, boxes): True when some sequence of moves puts every box on a goal."""
    import collections
    level = soko.Level(rows)
    start = (level.player, frozenset(level.boxes))
    seen, queue = {start}, collections.deque([start])
    while queue:
        player, boxes = queue.popleft()
        if set(boxes) == level.goals:
            return True
        for dx, dy in soko.MOVES.values():
            target = (player[0] + dx, player[1] + dy)
            if target in level.walls:
                continue
            after = boxes
            if target in boxes:
                beyond = (target[0] + dx, target[1] + dy)
                if beyond in level.walls or beyond in boxes:
                    continue
                after = (boxes - {target}) | {beyond}
            state = (target, frozenset(after))
            if state not in seen:
                seen.add(state)
                queue.append(state)
    return False


def main():
    day = datetime.date(2026, 10, 6)

    flash = load("utilities/flashcards")
    card = flash.new_card(" 2+2 ", " 4 ")
    assert card["q"] == "2+2" and card["box"] == 1
    flash.answer(card, True, day)
    assert card["box"] == 2 and card["due"] == "2026-10-07"
    flash.answer(card, True, day)
    flash.answer(card, True, day)
    assert card["box"] == 4 and card["due"] == "2026-10-10"
    for _ in range(10):
        flash.answer(card, True, day)
    assert card["box"] == flash.TOP_BOX
    flash.answer(card, False, day)
    assert card["box"] == 1 and card["due"] == "2026-10-06"
    assert flash.due_cards([card, {"q": "x", "a": "y", "box": 3, "due": "2099-01-01"}], day) == [card]

    spend = load("utilities/expenses")
    assert spend.parse_amount("12.5") == 1250 and spend.parse_amount("12,50") == 1250 and spend.parse_amount("1,200.00") == 120000
    assert spend.parse_amount("0") is None and spend.parse_amount("abc") is None and spend.parse_amount("1.234") is None
    assert spend.money(120005) == "1,200.05"
    items = []
    spend.add(items, 1000, "Food", "lunch", day)
    spend.add(items, 550, "food", "", day)
    spend.add(items, 3000, "rent", "", datetime.date(2026, 9, 30))
    totals, total = spend.month_totals(items, "2026-10")
    assert totals == {"food": 1550} and total == 1550

    habit = load("utilities/habits")
    days = []
    for back in (0, 1, 2, 5):
        habit.toggle(days, day - datetime.timedelta(days=back))
    assert habit.streak(days, day) == 3 and habit.best_streak(days) == 3
    assert habit.streak(days, day + datetime.timedelta(days=1)) == 3        # today not ticked yet: the streak is not lost
    assert habit.streak(days, day + datetime.timedelta(days=2)) == 0
    assert habit.toggle(days, day) is False and habit.streak(days, day) == 2

    pomo = load("utilities/pomodoro")
    assert pomo.clock(125) == "02:05" and pomo.parse([]) == (25, 5, 4) and pomo.parse(["50", "10", "3"]) == (50, 10, 3)
    assert pomo.parse(["x"]) is None and pomo.parse(["0"]) is None and pomo.parse(["25", "5", "99"]) is None

    soko = load("games/sokoban")
    level = soko.Level(soko.LEVELS[0])
    assert not level.solved() and level.move("d") and level.solved()
    assert level.undo() and not level.solved() and level.moves == 0
    assert not level.move("w")                                                    # a wall
    two = soko.Level(["#####", "#@$$#", "#####"])
    assert not two.move("d")                                                      # one box at a time
    for number, rows in enumerate(soko.LEVELS):
        built = soko.Level(rows)
        assert len(built.boxes) == len(built.goals) and built.player not in built.walls, f"level {number + 1} is not well formed"
        assert solvable(soko, rows), f"level {number + 1} cannot be solved"

    lights = load("games/lightsout")
    rng = random.Random(7)
    for _ in range(40):
        board = lights.new_board(rng=rng)
        answer = lights.solve(board)
        assert answer is not None
        for x, y in answer:
            lights.press(board, x, y)
        assert lights.solved(board)
    assert lights.parse_cell("b3") == (1, 2) and lights.parse_cell("z9") is None

    slide = load("games/slide15")
    for n in (3, 4, 5):
        board = slide.shuffled(n, rng=random.Random(n))
        assert sorted(board) == list(range(n * n)) and board != slide.solved_board(n)
    board = slide.solved_board(3)
    assert slide.slide(board, 3, 8) and board[-1] == 8 and board[-2] == 0 and not slide.slide(board, 3, 1)
    print("new apps: all checks passed")


if __name__ == "__main__":
    sys.exit(main() or 0)
