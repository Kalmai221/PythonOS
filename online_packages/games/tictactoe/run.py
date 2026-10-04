#!/usr/bin/env python3
import random
from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()
LINES = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]


def winner(board):
    for a, b, c in LINES:
        if board[a] != " " and board[a] == board[b] == board[c]:
            return board[a]
    return None


def show(board):
    table = Table(show_header=False, show_lines=True, box=None, padding=(0, 2))
    for r in range(3):
        cells = []
        for c in range(3):
            v = board[r * 3 + c]
            cells.append(f"[bold red]{v}[/bold red]" if v == "X" else f"[bold cyan]{v}[/bold cyan]" if v == "O"
                         else f"[dim]{r * 3 + c + 1}[/dim]")
        table.add_row(*cells)
    console.print(table)


def minimax(board, mark):
    """Best score for O: +1 O wins, -1 X wins, 0 draw (perfect play)."""
    w = winner(board)
    if w:
        return 1 if w == "O" else -1
    free = [i for i, v in enumerate(board) if v == " "]
    if not free:
        return 0
    scores = []
    for i in free:
        board[i] = mark
        scores.append(minimax(board, "X" if mark == "O" else "O"))
        board[i] = " "
    return max(scores) if mark == "O" else min(scores)


def computer_move(board, level="medium"):
    """easy: random. medium: win/block/centre. hard: never loses."""
    free = [i for i, v in enumerate(board) if v == " "]
    if level == "easy":
        return random.choice(free)
    if level == "hard":
        best = []
        top = -2
        for i in free:
            board[i] = "O"
            s = minimax(board, "X")
            board[i] = " "
            if s > top:
                top, best = s, [i]
            elif s == top:
                best.append(i)
        return random.choice(best)
    for mark in ("O", "X"):
        for i in free:
            trial = board[:]
            trial[i] = mark
            if winner(trial) == mark:
                return i
    for i in (4, 0, 2, 6, 8):
        if i in free:
            return i
    return random.choice(free)


def play_round(level):
    board = [" "] * 9
    while True:
        console.clear()
        console.print("[bold]Tic-Tac-Toe[/bold]  you are [red]X[/red]\n")
        show(board)
        move = Prompt.ask("\nYour move (1-9, q to quit)").strip().lower()
        if move == "q":
            return "quit"
        if not move.isdigit() or not 1 <= int(move) <= 9 or board[int(move) - 1] != " ":
            console.print("[yellow]Pick a free square from 1 to 9.[/yellow]")
            console.input("Press Enter...")
            continue
        board[int(move) - 1] = "X"
        if not winner(board) and " " in board:
            board[computer_move(board, level)] = "O"
        result = winner(board)
        if result or " " not in board:
            console.clear()
            show(board)
            console.print("\n[bold green]You win![/bold green]" if result == "X"
                          else "\n[bold red]The computer wins.[/bold red]" if result == "O"
                          else "\n[bold yellow]It's a draw.[/bold yellow]")
            return result or "draw"


def main():
    score = {"X": 0, "O": 0, "draw": 0}
    level = Prompt.ask("Difficulty", choices=["easy", "medium", "hard"], default="medium")
    record = appdata.load("tictactoe", {"X": 0, "O": 0, "draw": 0}) if appdata else None
    while True:
        result = play_round(level)
        if result == "quit":
            break
        score[result] += 1
        console.print(f"Score - you: {score['X']}  computer: {score['O']}  draws: {score['draw']}")
        if record is not None:
            record[result] += 1
            appdata.save("tictactoe", record)
            console.print(f"[dim]All time - you: {record['X']}  computer: {record['O']}  draws: {record['draw']}[/dim]")
        if Prompt.ask("Play again?", choices=["y", "n"], default="y") == "n":
            break


if __name__ == "__main__":
    main()


def execute():
    main()
