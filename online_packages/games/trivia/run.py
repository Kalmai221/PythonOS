#!/usr/bin/env python3
"""Trivia: ten multiple-choice questions. Works offline with the built-in questions; with internet it can also fetch
fresh ones from the Open Trivia Database (opentdb.com)."""
import html
import random

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

try:
    import requests
except ImportError:
    requests = None
try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()

# (category, question, correct answer, three wrong answers)
BANK = [
    ("Science", "What is the chemical symbol for gold?", "Au", ["Ag", "Gd", "Go"]),
    ("Science", "Which planet is known as the Red Planet?", "Mars", ["Venus", "Jupiter", "Mercury"]),
    ("Science", "What gas do plants absorb from the air?", "Carbon dioxide", ["Oxygen", "Nitrogen", "Helium"]),
    ("Science", "How many bones does an adult human have?", "206", ["186", "212", "256"]),
    ("Science", "What is the hardest natural substance?", "Diamond", ["Quartz", "Steel", "Granite"]),
    ("Science", "What is the speed of light closest to?", "300,000 km/s", ["30,000 km/s", "3,000,000 km/s", "300 km/s"]),
    ("Science", "Which organ pumps blood around the body?", "The heart", ["The liver", "The lungs", "The kidney"]),
    ("Science", "What is H2O commonly called?", "Water", ["Hydrogen peroxide", "Salt", "Ice cream"]),
    ("Geography", "What is the capital of Australia?", "Canberra", ["Sydney", "Melbourne", "Perth"]),
    ("Geography", "Which is the longest river in Africa?", "The Nile", ["The Congo", "The Niger", "The Zambezi"]),
    ("Geography", "Which country has the most people?", "India", ["USA", "Indonesia", "Brazil"]),
    ("Geography", "What is the smallest country in the world?", "Vatican City", ["Monaco", "Malta", "San Marino"]),
    ("Geography", "Mount Everest is on the border of Nepal and which country?", "China", ["India", "Bhutan", "Pakistan"]),
    ("Geography", "Which ocean is the largest?", "Pacific", ["Atlantic", "Indian", "Arctic"]),
    ("Geography", "What is the capital of Canada?", "Ottawa", ["Toronto", "Vancouver", "Montreal"]),
    ("History", "In which year did the Second World War end?", "1945", ["1939", "1944", "1950"]),
    ("History", "Who was the first person to walk on the Moon?", "Neil Armstrong", ["Buzz Aldrin", "Yuri Gagarin", "John Glenn"]),
    ("History", "Which empire built the Colosseum?", "The Roman Empire", ["The Greek Empire", "The Ottoman Empire", "The Persian Empire"]),
    ("History", "The Titanic sank in which year?", "1912", ["1905", "1920", "1898"]),
    ("History", "Who painted the Mona Lisa?", "Leonardo da Vinci", ["Michelangelo", "Raphael", "Rembrandt"]),
    ("History", "Which wall fell in 1989?", "The Berlin Wall", ["The Great Wall", "Hadrian's Wall", "Wall Street"]),
    ("Technology", "What does CPU stand for?", "Central Processing Unit", ["Computer Personal Unit", "Central Program Utility", "Core Processing Update"]),
    ("Technology", "Which language is PythonOS written in?", "Python", ["Java", "Rust", "Pascal"]),
    ("Technology", "What does HTTP stand for?", "HyperText Transfer Protocol", ["High Transfer Text Process", "Hyper Tool Transfer Plan", "Home Text Transport Path"]),
    ("Technology", "How many bits are in a byte?", "8", ["4", "16", "10"]),
    ("Technology", "Who created the Linux kernel?", "Linus Torvalds", ["Bill Gates", "Steve Jobs", "Dennis Ritchie"]),
    ("Technology", "What does 'www' stand for?", "World Wide Web", ["Wide World Web", "Web World Wide", "World Web Window"]),
    ("Technology", "What is 2 to the power of 10?", "1024", ["1000", "512", "2048"]),
    ("Nature", "What is the largest mammal?", "The blue whale", ["The elephant", "The giraffe", "The hippo"]),
    ("Nature", "How many legs does a spider have?", "8", ["6", "10", "12"]),
    ("Nature", "Which bird is known for not being able to fly and living in Antarctica?", "Penguin", ["Ostrich", "Kiwi", "Emu"]),
    ("Nature", "What do bees make?", "Honey", ["Silk", "Wax paper", "Syrup"]),
    ("Nature", "Which is the fastest land animal?", "Cheetah", ["Lion", "Horse", "Greyhound"]),
    ("Nature", "A baby kangaroo is called a...", "Joey", ["Cub", "Pup", "Kit"]),
    ("Culture", "How many strings does a standard guitar have?", "6", ["4", "5", "8"]),
    ("Culture", "Who wrote 'Romeo and Juliet'?", "William Shakespeare", ["Charles Dickens", "Jane Austen", "Mark Twain"]),
    ("Culture", "Which sport uses a shuttlecock?", "Badminton", ["Tennis", "Squash", "Golf"]),
    ("Culture", "How many players are in a football (soccer) team on the pitch?", "11", ["9", "10", "12"]),
    ("Culture", "In chess, which piece can only move diagonally?", "The bishop", ["The rook", "The knight", "The pawn"]),
    ("Culture", "What colour do you get by mixing blue and yellow?", "Green", ["Purple", "Orange", "Brown"]),
    ("Maths", "What is the square root of 144?", "12", ["14", "11", "13"]),
    ("Maths", "How many sides does a hexagon have?", "6", ["5", "7", "8"]),
    ("Maths", "What is 15% of 200?", "30", ["20", "25", "35"]),
    ("Maths", "What is the value of pi to two decimal places?", "3.14", ["3.12", "3.41", "3.16"]),
    ("Maths", "What is 7 x 8?", "56", ["54", "49", "64"]),
]

ROUND = 10


def online_questions(amount=ROUND):
    """Fetch questions from opentdb.com; returns [] if offline."""
    if requests is None:
        return []
    try:
        data = requests.get(f"https://opentdb.com/api.php?amount={amount}&type=multiple", timeout=8).json()
        if data.get("response_code") != 0:
            return []
        return [(html.unescape(q["category"]), html.unescape(q["question"]), html.unescape(q["correct_answer"]),
                 [html.unescape(a) for a in q["incorrect_answers"]]) for q in data["results"]]
    except Exception:
        return []


def ask(number, total, question):
    category, text, right, wrong = question
    options = [right] + list(wrong)
    random.shuffle(options)
    body = f"[bold]{escape(text)}[/bold]\n\n" + "\n".join(f"  [cyan]{'abcd'[i]}[/cyan]) {escape(o)}" for i, o in enumerate(options))
    console.print(Panel(body, title=f"Question {number}/{total}  [dim]{escape(category)}[/dim]", border_style="blue", expand=False))
    while True:
        try:
            answer = input("Your answer (a-d)> ").strip().lower()
        except EOFError:
            return None
        if answer in ("q", "quit"):
            return None
        if answer in ("a", "b", "c", "d"):
            break
    if options["abcd".index(answer)] == right:
        console.print("[bold green]Correct![/bold green]")
        return True
    console.print(f"[bold red]Not quite.[/bold red] The answer is [bold]{escape(right)}[/bold].")
    return False


def main():
    console.print("[bold]Trivia[/bold]  [dim]'q' quits a round[/dim]")
    stats = appdata.load("trivia", {"rounds": 0, "best": 0}) if appdata else {"rounds": 0, "best": 0}
    while True:
        source = input("Questions from [b]uilt-in or [o]nline? [B/o/q]> ").strip().lower()[:1] or "b"
        if source == "q":
            return
        questions = []
        if source == "o":
            with console.status("Fetching questions..."):
                questions = online_questions()
            if not questions:
                console.print("[yellow]Could not reach the question service, using the built-in questions.[/yellow]")
        if not questions:
            questions = random.sample(BANK, ROUND)
        score = 0
        for i, q in enumerate(questions, 1):
            result = ask(i, len(questions), q)
            if result is None:
                break
            score += bool(result)
        else:
            console.print(f"\n[bold]You scored {score}/{len(questions)}.[/bold]")
            stats["rounds"] += 1
            stats["best"] = max(stats["best"], score)
            if appdata:
                appdata.save("trivia", stats)
            console.print(f"[dim]Rounds played: {stats['rounds']}   best score: {stats['best']}[/dim]")
        if input("Another round? [y/N] ").strip().lower() != "y":
            return


def execute():
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute()
