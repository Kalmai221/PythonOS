#!/usr/bin/env python3
"""Reversi (Othello) against the computer. Place a disc so that it traps a line of the other colour between your new disc and one of
yours; the trapped discs flip. You are black (#). Type a square like D3. 'pass' is only allowed when you have no move."""
import sys

from rich.console import Console
from rich.text import Text

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
N = 8
EMPTY, BLACK, WHITE = 0, 1, 2
DIRS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
DEPTH = {"easy": 1, "medium": 3, "hard": 5}
WEIGHTS = [[100, -20, 10, 5, 5, 10, -20, 100], [-20, -50, -2, -2, -2, -2, -50, -20], [10, -2, -1, -1, -1, -1, -2, 10],
           [5, -2, -1, -1, -1, -1, -2, 5], [5, -2, -1, -1, -1, -1, -2, 5], [10, -2, -1, -1, -1, -1, -2, 10],
           [-20, -50, -2, -2, -2, -2, -50, -20], [100, -20, 10, 5, 5, 10, -20, 100]]


def new_board():
    b = [[EMPTY] * N for _ in range(N)]
    b[3][3] = b[4][4] = WHITE
    b[3][4] = b[4][3] = BLACK
    return b


def other(who):
    return WHITE if who == BLACK else BLACK


def flips(board, r, c, who):
    """Discs that would flip if `who` played at (r, c); empty if the move is illegal."""
    if board[r][c] != EMPTY:
        return []
    out = []
    for dr, dc in DIRS:
        line, rr, cc = [], r + dr, c + dc
        while 0 <= rr < N and 0 <= cc < N and board[rr][cc] == other(who):
            line.append((rr, cc))
            rr, cc = rr + dr, cc + dc
        if line and 0 <= rr < N and 0 <= cc < N and board[rr][cc] == who:
            out.extend(line)
    return out


def moves(board, who):
    return [(r, c) for r in range(N) for c in range(N) if flips(board, r, c, who)]


def play_move(board, r, c, who):
    """Apply a legal move in place and return the discs flipped."""
    f = flips(board, r, c, who)
    board[r][c] = who
    for fr, fc in f:
        board[fr][fc] = who
    return f


def count(board):
    black = sum(row.count(BLACK) for row in board)
    white = sum(row.count(WHITE) for row in board)
    return black, white


def game_over(board):
    return not moves(board, BLACK) and not moves(board, WHITE)


def evaluate(board, who):
    """Positional weights plus mobility, from `who`'s point of view; discs count more near the end."""
    mine = sum(WEIGHTS[r][c] for r in range(N) for c in range(N) if board[r][c] == who)
    theirs = sum(WEIGHTS[r][c] for r in range(N) for c in range(N) if board[r][c] == other(who))
    mobility = len(moves(board, who)) - len(moves(board, other(who)))
    b, w = count(board)
    discs = (b - w) if who == BLACK else (w - b)
    filled = b + w
    return mine - theirs + 4 * mobility + (discs * 3 if filled > 54 else 0)


def search(board, depth, alpha, beta, who, root):
    available = moves(board, who)
    if depth == 0 or game_over(board):
        return evaluate(board, root), None
    if not available:
        return search(board, depth - 1, alpha, beta, other(who), root)[0], None
    best_move = available[0]
    if who == root:
        best = -10 ** 9
        for r, c in available:
            copy = [row[:] for row in board]
            play_move(copy, r, c, who)
            score = search(copy, depth - 1, alpha, beta, other(who), root)[0]
            if score > best:
                best, best_move = score, (r, c)
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best, best_move
    best = 10 ** 9
    for r, c in available:
        copy = [row[:] for row in board]
        play_move(copy, r, c, who)
        score = search(copy, depth - 1, alpha, beta, other(who), root)[0]
        if score < best:
            best, best_move = score, (r, c)
        beta = min(beta, best)
        if alpha >= beta:
            break
    return best, best_move


def computer_move(board, level, who=WHITE):
    return search(board, DEPTH[level], -10 ** 9, 10 ** 9, who, who)[1]


def render(board, hints=()):
    out = Text("   " + " ".join("ABCDEFGH") + "\n", style="dim")
    for r in range(N):
        out.append(f"{r + 1:>2} ", style="dim")
        for c in range(N):
            v = board[r][c]
            if v == BLACK:
                out.append("# ", style="bold white")
            elif v == WHITE:
                out.append("O ", style="bold yellow")
            elif (r, c) in hints:
                out.append("+ ", style="green")
            else:
                out.append(". ", style="dim")
        out.append("\n")
    return out


def parse_square(text):
    text = text.strip().upper()
    if len(text) == 2 and text[0] in "ABCDEFGH" and text[1] in "12345678":
        return int(text[1]) - 1, ord(text[0]) - 65
    return None


def play(level):
    board = new_board()
    turn = BLACK
    console.print(f"[bold]Reversi[/bold] ({level}). You are # (black); the computer is O. Type a square like D3, 'hint' for your moves, q to quit.")
    while not game_over(board):
        b, w = count(board)
        available = moves(board, turn)
        console.print(render(board, hints=available if turn == BLACK else ()), end="")
        console.print(f"[dim]You {b} - {w} computer[/dim]")
        if not available:
            console.print(f"[yellow]{'You have' if turn == BLACK else 'The computer has'} no move and passes.[/yellow]")
            turn = other(turn)
            continue
        if turn == BLACK:
            try:
                text = input("move> ").strip().lower()
            except EOFError:
                return None
            if text in ("q", "quit"):
                return None
            if text == "hint":
                console.print("[dim]Legal squares: " + ", ".join(f"{chr(65 + c)}{r + 1}" for r, c in available) + "[/dim]")
                continue
            sq = parse_square(text)
            if not sq or sq not in available:
                console.print("[yellow]That is not a legal move (a + marks the legal squares).[/yellow]")
                continue
            play_move(board, *sq, BLACK)
        else:
            r, c = computer_move(board, level)
            flipped = play_move(board, r, c, WHITE)
            console.print(f"[dim]The computer plays {chr(65 + c)}{r + 1} and flips {len(flipped)}.[/dim]")
        turn = other(turn)
    b, w = count(board)
    console.print(render(board), end="")
    console.print(f"[bold]{'You win' if b > w else 'The computer wins' if w > b else 'A draw'}: {b} to {w}.[/bold]")
    return 1 if b > w else -1 if w > b else 0


def main():
    stats = appdata.load("reversi", {"won": 0, "lost": 0, "drawn": 0}) if appdata else None
    while True:
        level = input("Level: easy, medium, hard (q to quit)> ").strip().lower() or "medium"
        if level == "q":
            return
        if level not in DEPTH:
            continue
        result = play(level)
        if result is None:
            return
        if stats is not None:
            stats["won" if result > 0 else "lost" if result < 0 else "drawn"] += 1
            appdata.save("reversi", stats)
        if input("Again? [y/N] ").strip().lower() != "y":
            return


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
