#!/usr/bin/env python3
"""Chess against the computer, written in plain Python (nothing to install). Full rules: castling, en passant,
promotion, check, checkmate and stalemate. Enter moves like e2e4 (or e7e8q to promote)."""
import random
import time

from rich.console import Console
from rich.prompt import Prompt
from rich.text import Text

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
START = ["rnbqkbnr", "pppppppp", "........", "........", "........", "........", "PPPPPPPP", "RNBQKBNR"]
VALUES = {"p": 100, "n": 320, "b": 330, "r": 500, "q": 900, "k": 0}
GLYPH = {"K": "K", "Q": "Q", "R": "R", "B": "B", "N": "N", "P": "P", "k": "k", "q": "q", "r": "r", "b": "b", "n": "n", "p": "p"}
KNIGHT = [(1, 2), (2, 1), (-1, 2), (-2, 1), (1, -2), (2, -1), (-1, -2), (-2, -1)]
KING = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
BISHOP = [(1, 1), (1, -1), (-1, 1), (-1, -1)]
ROOK = [(1, 0), (-1, 0), (0, 1), (0, -1)]
CENTRE = {(3, 3), (3, 4), (4, 3), (4, 4)}


class Position:
    """Board as a list of 8 lists (row 0 = rank 8). White is uppercase and moves up the board."""

    def __init__(self):
        self.board = [list(r) for r in START]
        self.white = True
        self.castle = {"K": True, "Q": True, "k": True, "q": True}
        self.ep = None                       # square a pawn can capture en passant on
        self.history = []

    def copy(self):
        p = Position.__new__(Position)
        p.board = [r[:] for r in self.board]
        p.white, p.castle, p.ep, p.history = self.white, dict(self.castle), self.ep, []
        return p

    # ------------------------------------------------------------ moves
    def mine(self, piece, white=None):
        white = self.white if white is None else white
        return piece != "." and piece.isupper() == white

    def attacked(self, r, c, by_white):
        """Is square (r, c) attacked by the side `by_white`?"""
        b = self.board
        pr = r + 1 if by_white else r - 1                  # a pawn attacking (r,c) stands one rank behind it
        for dc in (-1, 1):
            if 0 <= pr < 8 and 0 <= c + dc < 8 and b[pr][c + dc] == ("P" if by_white else "p"):
                return True
        for dr, dc in KNIGHT:
            rr, cc = r + dr, c + dc
            if 0 <= rr < 8 and 0 <= cc < 8 and b[rr][cc] == ("N" if by_white else "n"):
                return True
        for dr, dc in KING:
            rr, cc = r + dr, c + dc
            if 0 <= rr < 8 and 0 <= cc < 8 and b[rr][cc] == ("K" if by_white else "k"):
                return True
        for dirs, kinds in ((BISHOP, "bq"), (ROOK, "rq")):
            for dr, dc in dirs:
                rr, cc = r + dr, c + dc
                while 0 <= rr < 8 and 0 <= cc < 8:
                    piece = b[rr][cc]
                    if piece != ".":
                        if piece.isupper() == by_white and piece.lower() in kinds:
                            return True
                        break
                    rr, cc = rr + dr, cc + dc
        return False

    def king_square(self, white):
        target = "K" if white else "k"
        for r in range(8):
            for c in range(8):
                if self.board[r][c] == target:
                    return r, c
        return None

    def in_check(self, white=None):
        white = self.white if white is None else white
        sq = self.king_square(white)
        return sq is not None and self.attacked(sq[0], sq[1], not white)

    def pseudo_moves(self):
        moves, b = [], self.board
        for r in range(8):
            for c in range(8):
                piece = b[r][c]
                if not self.mine(piece):
                    continue
                kind = piece.lower()
                if kind == "p":
                    step, start, last = (-1, 6, 0) if self.white else (1, 1, 7)
                    if 0 <= r + step < 8 and b[r + step][c] == ".":
                        self._pawn(moves, r, c, r + step, c, last)
                        if r == start and b[r + 2 * step][c] == ".":
                            moves.append((r, c, r + 2 * step, c, None))
                    for dc in (-1, 1):
                        rr, cc = r + step, c + dc
                        if 0 <= rr < 8 and 0 <= cc < 8:
                            if b[rr][cc] != "." and not self.mine(b[rr][cc]):
                                self._pawn(moves, r, c, rr, cc, last)
                            elif (rr, cc) == self.ep:
                                moves.append((r, c, rr, cc, None))
                elif kind in "nk":
                    for dr, dc in (KNIGHT if kind == "n" else KING):
                        rr, cc = r + dr, c + dc
                        if 0 <= rr < 8 and 0 <= cc < 8 and not self.mine(b[rr][cc]):
                            moves.append((r, c, rr, cc, None))
                    if kind == "k":
                        self._castling(moves, r, c)
                else:
                    dirs = (BISHOP if kind == "b" else ROOK if kind == "r" else BISHOP + ROOK)
                    for dr, dc in dirs:
                        rr, cc = r + dr, c + dc
                        while 0 <= rr < 8 and 0 <= cc < 8:
                            if self.mine(b[rr][cc]):
                                break
                            moves.append((r, c, rr, cc, None))
                            if b[rr][cc] != ".":
                                break
                            rr, cc = rr + dr, cc + dc
        return moves

    @staticmethod
    def _pawn(moves, r, c, rr, cc, last):
        if rr == last:
            moves.extend((r, c, rr, cc, p) for p in "qrbn")
        else:
            moves.append((r, c, rr, cc, None))

    def _castling(self, moves, r, c):
        white, home = self.white, 7 if self.white else 0
        if (r, c) != (home, 4) or self.in_check():
            return
        b = self.board
        rights = ("K", "Q") if white else ("k", "q")
        if self.castle[rights[0]] and b[home][5] == b[home][6] == "." and b[home][7] == ("R" if white else "r") \
                and not self.attacked(home, 5, not white) and not self.attacked(home, 6, not white):
            moves.append((r, c, home, 6, None))
        if self.castle[rights[1]] and b[home][1] == b[home][2] == b[home][3] == "." and b[home][0] == ("R" if white else "r") \
                and not self.attacked(home, 3, not white) and not self.attacked(home, 2, not white):
            moves.append((r, c, home, 2, None))

    def legal_moves(self):
        legal = []
        for m in self.pseudo_moves():
            trial = self.copy()
            trial.apply(m)
            if not trial.in_check(self.white):
                legal.append(m)
        return legal

    def apply(self, move):
        r, c, rr, cc, promo = move
        b = self.board
        piece, taken = b[r][c], b[rr][cc]
        b[rr][cc], b[r][c] = piece, "."
        kind = piece.lower()
        if kind == "p" and (rr, cc) == self.ep and taken == ".":
            b[r][cc] = "."                                   # en passant capture
        if kind == "p" and promo:
            b[rr][cc] = promo.upper() if self.white else promo
        self.ep = ((r + rr) // 2, c) if kind == "p" and abs(rr - r) == 2 else None
        if kind == "k":
            if abs(cc - c) == 2:                             # move the rook too
                rook_from, rook_to = (7, 5) if cc == 6 else (0, 3)
                b[rr][rook_to], b[rr][rook_from] = b[rr][rook_from], "."
            for k in ("K", "Q") if self.white else ("k", "q"):
                self.castle[k] = False
        for sq, k in (((7, 0), "Q"), ((7, 7), "K"), ((0, 0), "q"), ((0, 7), "k")):
            if (r, c) == sq or (rr, cc) == sq:
                self.castle[k] = False
        self.white = not self.white

    def status(self):
        if self.legal_moves():
            return "check" if self.in_check() else "play"
        return "checkmate" if self.in_check() else "stalemate"


# ----------------------------------------------------------------- notation
def square(text):
    if len(text) == 2 and text[0] in "abcdefgh" and text[1] in "12345678":
        return 8 - int(text[1]), "abcdefgh".index(text[0])
    return None


def name(r, c):
    return "abcdefgh"[c] + str(8 - r)


def parse_move(text, position):
    text = text.strip().lower().replace("-", "").replace(" ", "")
    if len(text) in (4, 5):
        a, b = square(text[:2]), square(text[2:4])
        if a and b:
            promo = text[4] if len(text) == 5 else None
            for m in position.legal_moves():
                if (m[0], m[1], m[2], m[3]) == (a[0], a[1], b[0], b[1]) and (m[4] == promo or (m[4] == "q" and promo is None)):
                    return m
    return None


# --------------------------------------------------------------------- AI
def evaluate(p):
    score = 0
    for r in range(8):
        for c in range(8):
            piece = p.board[r][c]
            if piece == ".":
                continue
            value = VALUES[piece.lower()]
            if piece.lower() in "pnb":
                value += 12 if (r, c) in CENTRE else 0
            if piece.lower() == "p":
                value += (6 - r) * 5 if piece.isupper() else (r - 1) * 5     # advance pawns
            score += value if piece.isupper() else -value
    return score


def search(p, depth, alpha, beta):
    """Alpha-beta; returns the score from White's point of view."""
    moves = p.legal_moves()
    if not moves:
        return (-100000 - depth if p.white else 100000 + depth) if p.in_check() else 0
    if depth == 0:
        return evaluate(p)
    moves.sort(key=lambda m: -VALUES.get(p.board[m[2]][m[3]].lower(), 0))
    best = -10 ** 9 if p.white else 10 ** 9
    for m in moves:
        child = p.copy()
        child.apply(m)
        score = search(child, depth - 1, alpha, beta)
        if p.white:
            best, alpha = max(best, score), max(alpha, score)
        else:
            best, beta = min(best, score), min(beta, score)
        if beta <= alpha:
            break
    return best


def computer_move(p, level):
    moves = p.legal_moves()
    if level == 1:
        captures = [m for m in moves if p.board[m[2]][m[3]] != "."]
        return random.choice(captures or moves)
    depth = 2 if level == 2 else 3
    scored = []
    for m in moves:
        child = p.copy()
        child.apply(m)
        scored.append((search(child, depth - 1, -10 ** 9, 10 ** 9), random.random(), m))
    pick = max if p.white else min
    return pick(scored)[2]


# ---------------------------------------------------------------- display
def show(p, last=None, flipped=False):
    rows = range(7, -1, -1) if flipped else range(8)
    cols = range(7, -1, -1) if flipped else range(8)
    text = Text()
    for r in rows:
        text.append(f" {8 - r} ", style="dim")
        for c in cols:
            piece = p.board[r][c]
            light = (r + c) % 2 == 0
            bg = "on grey50" if light else "on grey23"
            if last and (r, c) in ((last[0], last[1]), (last[2], last[3])):
                bg = "on dark_goldenrod"
            fg = "bold bright_white" if piece.isupper() else "bold bright_cyan"
            text.append(f" {GLYPH.get(piece, ' ') if piece != '.' else ' '} ", style=f"{fg} {bg}")
        text.append("\n")
    letters = "hgfedcba" if flipped else "abcdefgh"
    text.append("    " + "  ".join(letters), style="dim")
    console.print(text)


def record(result):
    if not appdata:
        return
    stats = appdata.load("chess", {"won": 0, "lost": 0, "drawn": 0})
    stats[result] = stats.get(result, 0) + 1
    appdata.save("chess", stats)
    console.print(f"[dim]Record: {stats['won']} won, {stats['lost']} lost, {stats['drawn']} drawn[/dim]")


def play():
    level = int(Prompt.ask("Difficulty (1 easy, 2 medium, 3 hard)", choices=["1", "2", "3"], default="2"))
    colour = Prompt.ask("Play as", choices=["white", "black"], default="white")
    human_white = colour == "white"
    p, last = Position(), None
    console.print("[dim]Type moves like e2e4. Commands: moves (list legal moves), resign, quit.[/dim]")
    while True:
        show(p, last, flipped=not human_white)
        state = p.status()
        if state in ("checkmate", "stalemate"):
            if state == "stalemate":
                console.print("[bold yellow]Stalemate - a draw.[/bold yellow]")
                return record("drawn")
            won = p.white != human_white
            console.print("[bold green]Checkmate - you win![/bold green]" if won else "[bold red]Checkmate - the computer wins.[/bold red]")
            return record("won" if won else "lost")
        if p.white == human_white:
            if state == "check":
                console.print("[bold red]Check![/bold red]")
            try:
                text = Prompt.ask("Your move").strip().lower()
            except EOFError:
                return
            if text in ("quit", "q"):
                return
            if text == "resign":
                console.print("[red]You resigned.[/red]")
                return record("lost")
            if text == "moves":
                console.print(", ".join(name(m[0], m[1]) + name(m[2], m[3]) + (m[4] or "") for m in p.legal_moves()))
                continue
            move = parse_move(text, p)
            if not move:
                console.print("[yellow]That is not a legal move. Type 'moves' to see them.[/yellow]")
                continue
        else:
            with console.status("Computer is thinking..."):
                time.sleep(0.2)
                move = computer_move(p, level)
            console.print(f"[dim]Computer plays {name(move[0], move[1])}{name(move[2], move[3])}{move[4] or ''}[/dim]")
        p.apply(move)
        last = move


def execute():
    try:
        while True:
            play()
            if Prompt.ask("Play again?", choices=["y", "n"], default="n") == "n":
                return
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute()
