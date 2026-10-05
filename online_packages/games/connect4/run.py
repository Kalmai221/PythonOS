#!/usr/bin/env python3
"""Connect Four against the computer (or a friend): drop discs into a 7x6 grid and line up four in a row.
Type a column number 1-7. Levels: easy (random with common sense), medium and hard (look several moves ahead)."""
import random
import sys

from rich.console import Console
from rich.text import Text

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
COLS, ROWS = 7, 6
EMPTY, YOU, CPU = 0, 1, 2
DEPTH = {"easy": 2, "medium": 4, "hard": 6}


def new_board():
    return [[EMPTY] * COLS for _ in range(ROWS)]          # row 0 is the top


def legal(board):
    return [c for c in range(COLS) if board[0][c] == EMPTY]


def drop(board, col, who):
    """Put a disc in a column. Returns the row it landed in (the board is changed in place)."""
    for r in range(ROWS - 1, -1, -1):
        if board[r][col] == EMPTY:
            board[r][col] = who
            return r
    raise ValueError("column is full")


def undo(board, col):
    for r in range(ROWS):
        if board[r][col] != EMPTY:
            board[r][col] = EMPTY
            return


def winner(board):
    """The player with four in a row, or 0."""
    for r in range(ROWS):
        for c in range(COLS):
            who = board[r][c]
            if not who:
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                end_r, end_c = r + 3 * dr, c + 3 * dc
                if 0 <= end_r < ROWS and 0 <= end_c < COLS and all(board[r + i * dr][c + i * dc] == who for i in range(4)):
                    return who
    return 0


def full(board):
    return not legal(board)


def evaluate(board, who):
    """A rough score from `who`'s point of view: centre discs and open threes are good."""
    other = YOU if who == CPU else CPU
    score = sum(3 for r in range(ROWS) if board[r][COLS // 2] == who) - sum(3 for r in range(ROWS) if board[r][COLS // 2] == other)
    for r in range(ROWS):
        for c in range(COLS):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                end_r, end_c = r + 3 * dr, c + 3 * dc
                if not (0 <= end_r < ROWS and 0 <= end_c < COLS):
                    continue
                window = [board[r + i * dr][c + i * dc] for i in range(4)]
                mine, theirs = window.count(who), window.count(other)
                if theirs == 0:
                    score += {4: 1000, 3: 5, 2: 2}.get(mine, 0)
                if mine == 0:
                    score -= {4: 1000, 3: 6, 2: 2}.get(theirs, 0)
    return score


def search(board, depth, alpha, beta, maximizing):
    """Minimax with alpha-beta from the computer's point of view. Returns (score, column)."""
    w = winner(board)
    if w == CPU:
        return 100000 + depth, None
    if w == YOU:
        return -100000 - depth, None
    moves = sorted(legal(board), key=lambda c: abs(c - COLS // 2))      # centre first: better pruning
    if depth == 0 or not moves:
        return (evaluate(board, CPU) if moves else 0), None
    best_col = moves[0]
    if maximizing:
        best = -10 ** 9
        for c in moves:
            drop(board, c, CPU)
            score, _ = search(board, depth - 1, alpha, beta, False)
            undo(board, c)
            if score > best:
                best, best_col = score, c
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best, best_col
    best = 10 ** 9
    for c in moves:
        drop(board, c, YOU)
        score, _ = search(board, depth - 1, alpha, beta, True)
        undo(board, c)
        if score < best:
            best, best_col = score, c
        beta = min(beta, best)
        if alpha >= beta:
            break
    return best, best_col


def computer_move(board, level, rng=None):
    rng = rng or random
    options = legal(board)
    # always take a win, and block the opponent's win
    for who in (CPU, YOU):
        for c in options:
            drop(board, c, who)
            wins = winner(board) == who
            undo(board, c)
            if wins:
                return c
    if level == "easy" and rng.random() < 0.5:
        return rng.choice(options)
    return search(board, DEPTH[level], -10 ** 9, 10 ** 9, True)[1]


def render(board, last=None):
    out = Text(" " + "   ".join(str(c + 1) for c in range(COLS)) + "\n", style="bold dim")
    for r in range(ROWS):
        out.append("|", style="blue")
        for c in range(COLS):
            v = board[r][c]
            ch, style = ("O", "bold red") if v == YOU else ("O", "bold yellow") if v == CPU else (".", "dim")
            if last == (r, c):
                style += " reverse"
            out.append(f" {ch} ", style=style)
            out.append("|", style="blue")
        out.append("\n")
    out.append("+" + "---+" * COLS + "\n", style="blue")
    return out


def play(level, two_player=False):
    board = new_board()
    turn = YOU
    last = None
    console.print(f"[bold]Connect Four[/bold] ({'two players' if two_player else level}). You are [red]red[/red]"
                  + ("; player two is [yellow]yellow[/yellow]" if two_player else "") + ". Type a column 1-7, q to quit.")
    while True:
        console.print(render(board, last), end="")
        w = winner(board)
        if w:
            console.print(f"[bold {'red' if w == YOU else 'yellow'}]{'Red' if w == YOU else ('Yellow' if two_player else 'The computer')} wins![/bold {'red' if w == YOU else 'yellow'}]")
            return w
        if full(board):
            console.print("[bold]A draw.[/bold]")
            return 0
        if turn == YOU or two_player:
            try:
                text = input(f"{'Red' if turn == YOU else 'Yellow'}, column> ").strip().lower()
            except EOFError:
                return None
            if text in ("q", "quit"):
                return None
            if not text.isdigit() or not 1 <= int(text) <= COLS or int(text) - 1 not in legal(board):
                console.print("[yellow]Pick a column from 1 to 7 that is not full.[/yellow]")
                continue
            col = int(text) - 1
        else:
            col = computer_move(board, level)
            console.print(f"[dim]The computer plays column {col + 1}.[/dim]")
        last = (drop(board, col, turn), col)
        turn = CPU if turn == YOU else YOU


def main():
    stats = appdata.load("connect4", {"won": 0, "lost": 0, "drawn": 0}) if appdata else None
    while True:
        text = input("Level: easy, medium, hard, or two (two players); q to quit> ").strip().lower() or "medium"
        if text == "q":
            return
        if text not in DEPTH and text != "two":
            continue
        result = play(text if text != "two" else "easy", two_player=text == "two")
        if result is None:
            return
        if stats is not None and text != "two":
            stats["won" if result == YOU else "lost" if result == CPU else "drawn"] += 1
            appdata.save("connect4", stats)
            console.print(f"[dim]Won {stats['won']}, lost {stats['lost']}, drawn {stats['drawn']}[/dim]")
        if input("Again? [y/N] ").strip().lower() != "y":
            return


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
