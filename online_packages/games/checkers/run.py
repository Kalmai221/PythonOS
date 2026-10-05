#!/usr/bin/env python3
"""Checkers (English draughts) against the computer. You are red (r, king R) and move up the board; the computer is white (w, king W).
Pieces move diagonally forward; a jump over an opponent piece is compulsory, and you must keep jumping if you can. Reach the far side
to be crowned: kings move both ways. Type a move as from-to squares, like  B6 A5, or a jump chain like  C3 E5 G7.
Commands: moves (list legal moves), q."""
import sys

from rich.console import Console
from rich.text import Text

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
N = 8
EMPTY = "."
DEPTH = {"easy": 1, "medium": 4, "hard": 6}


def new_board():
    b = [[EMPTY] * N for _ in range(N)]
    for r in range(3):
        for c in range(N):
            if (r + c) % 2 == 1:
                b[r][c] = "w"
    for r in range(5, 8):
        for c in range(N):
            if (r + c) % 2 == 1:
                b[r][c] = "r"
    return b


def owner(piece):
    return piece.lower() if piece != EMPTY else None


def directions(piece):
    if piece.isupper():
        return [(-1, -1), (-1, 1), (1, -1), (1, 1)]
    return [(-1, -1), (-1, 1)] if piece == "r" else [(1, -1), (1, 1)]


def jumps_from(board, r, c, piece=None, taken=(), origin=None):
    """All complete jump chains starting at (r, c): a list of (landing squares in order, captured squares). The pieces captured
    during a chain stay on the board until it ends, so none can be jumped twice. A man that reaches the far row is crowned and
    its move ends there."""
    piece = piece or board[r][c]
    origin = origin or (r, c)
    chains = []
    for dr, dc in directions(piece):
        mr, mc, tr, tc = r + dr, c + dc, r + 2 * dr, c + 2 * dc
        if not (0 <= tr < N and 0 <= tc < N):
            continue
        mid = board[mr][mc]
        if mid == EMPTY or owner(mid) == owner(piece) or (mr, mc) in taken:
            continue
        if board[tr][tc] != EMPTY and (tr, tc) != origin:
            continue
        crowns = (piece == "r" and tr == 0) or (piece == "w" and tr == N - 1)
        further = [] if crowns else jumps_from(board, tr, tc, piece, taken + ((mr, mc),), origin)
        if further:
            for path, caps in further:
                chains.append(([(tr, tc)] + path, [(mr, mc)] + caps))
        else:
            chains.append(([(tr, tc)], [(mr, mc)]))
    return chains


def legal_moves(board, who):
    """List of moves: (start, [path squares], [captured squares]). If any jump exists, only jumps are legal."""
    jumps, steps = [], []
    for r in range(N):
        for c in range(N):
            piece = board[r][c]
            if owner(piece) != who:
                continue
            for path, caps in jumps_from(board, r, c):
                jumps.append(((r, c), path, caps))
            for dr, dc in directions(piece):
                nr, nc = r + dr, c + dc
                if 0 <= nr < N and 0 <= nc < N and board[nr][nc] == EMPTY:
                    steps.append(((r, c), [(nr, nc)], []))
    return jumps or steps


def apply(board, move):
    """Apply a move to a copy of the board and return it."""
    (r, c), path, caps = move
    b = [row[:] for row in board]
    piece = b[r][c]
    b[r][c] = EMPTY
    for cr, cc in caps:
        b[cr][cc] = EMPTY
    er, ec = path[-1]
    if (piece == "r" and er == 0) or (piece == "w" and er == N - 1):
        piece = piece.upper()
    b[er][ec] = piece
    return b


def evaluate(board, who):
    score = 0
    for r in range(N):
        for c in range(N):
            p = board[r][c]
            if p == EMPTY:
                continue
            value = 5 if p.isupper() else 3 + (((N - 1 - r) if p == "r" else r) * 0.1)
            if 2 <= c <= 5:
                value += 0.1
            score += value if owner(p) == who else -value
    return score


def search(board, depth, alpha, beta, turn, root):
    options = legal_moves(board, turn)
    if not options:
        return (-1000 - depth) if turn == root else (1000 + depth), None
    if depth == 0:
        return evaluate(board, root), None
    best_move = options[0]
    other = "r" if turn == "w" else "w"
    if turn == root:
        best = -10 ** 9
        for m in options:
            score = search(apply(board, m), depth - 1, alpha, beta, other, root)[0]
            if score > best:
                best, best_move = score, m
            alpha = max(alpha, best)
            if alpha >= beta:
                break
        return best, best_move
    best = 10 ** 9
    for m in options:
        score = search(apply(board, m), depth - 1, alpha, beta, other, root)[0]
        if score < best:
            best, best_move = score, m
        beta = min(beta, best)
        if alpha >= beta:
            break
    return best, best_move


def computer_move(board, level, who="w"):
    return search(board, DEPTH[level], -10 ** 9, 10 ** 9, who, who)[1]


def name(sq):
    return f"{chr(65 + sq[1])}{N - sq[0]}"


def parse_square(text):
    text = text.strip().upper()
    if len(text) == 2 and text[0] in "ABCDEFGH" and text[1] in "12345678":
        return N - int(text[1]), ord(text[0]) - 65
    return None


def describe(move):
    start, path, caps = move
    return " ".join([name(start)] + [name(p) for p in path])


def find_move(board, who, squares):
    """The legal move that matches the squares typed (from, then each landing square; a single jump may omit nothing)."""
    for m in legal_moves(board, who):
        if [m[0]] + m[1] == squares:
            return m
    # allow typing only start and final landing square when it is unambiguous
    matches = [m for m in legal_moves(board, who) if len(squares) == 2 and m[0] == squares[0] and m[1][-1] == squares[1]]
    return matches[0] if len(matches) == 1 else None


def render(board):
    out = Text("   A B C D E F G H\n", style="dim")
    for r in range(N):
        out.append(f"{N - r:>2} ", style="dim")
        for c in range(N):
            p = board[r][c]
            style = "bold red" if owner(p) == "r" else "bold white" if owner(p) == "w" else "dim"
            out.append(f"{p} ", style=style)
        out.append("\n")
    return out


def play(level):
    board = new_board()
    turn = "r"
    console.print(f"[bold]Checkers[/bold] ({level}). You are red (r, kings R). Type a move like  B6 A5  or a jump chain  C3 E5 G7. 'moves' lists them.")
    while True:
        console.print(render(board), end="")
        options = legal_moves(board, turn)
        if not options:
            console.print("[bold green]You win - the computer has no moves![/bold green]" if turn == "w" else "[bold red]You have no moves - the computer wins.[/bold red]")
            return turn == "w"
        if turn == "r":
            if any(m[2] for m in options):
                console.print("[yellow]You must jump.[/yellow]")
            try:
                text = input("move> ").strip().lower()
            except EOFError:
                return None
            if text in ("q", "quit"):
                return None
            if text == "moves":
                console.print(", ".join(describe(m) for m in options))
                continue
            squares = [parse_square(t) for t in text.split()]
            move = find_move(board, "r", squares) if squares and all(squares) else None
            if not move:
                console.print("[yellow]That is not a legal move. Type 'moves' to see them.[/yellow]")
                continue
        else:
            move = computer_move(board, level)
            console.print(f"[dim]The computer plays {describe(move)}[/dim]")
        board = apply(board, move)
        turn = "w" if turn == "r" else "r"


def main():
    stats = appdata.load("checkers", {"won": 0, "lost": 0}) if appdata else None
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
            stats["won" if result else "lost"] += 1
            appdata.save("checkers", stats)
        if input("Again? [y/N] ").strip().lower() != "y":
            return


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
