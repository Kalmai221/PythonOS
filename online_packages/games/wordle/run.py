#!/usr/bin/env python3
"""Wordle: guess the five-letter word in six tries. Green = right place, yellow = wrong place, grey = not in the word.
Play the word of the day (the same for everyone on a given date) or a random word."""
import datetime
import random
import zlib

from rich.console import Console
from rich.text import Text

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()

WORDS = """about above actor adapt admit adult after again agent agree ahead alarm album alert alike alive allow alone along
alter among anger angle angry apart apple apply arena argue arise armor aside asset audio avoid awake award aware badly baker
basic beach began begin being below bench birth black blade blame blank blast blaze blend bless blind block blood bloom board
boost booth bound brain brand brave bread break breed brick bride brief bring broad broke brown brush build built bunch burst
cabin cable candy carry catch cause chain chair charm chart chase cheap check cheer chess chest chief child chill choir civic
claim class clean clear clerk click cliff climb clock close cloth cloud coach coast count court cover crack craft crane crash
crazy cream crime cross crowd crown crush curve cycle daily dance dealt death debut delay depth dirty doubt dozen draft drain
drama dream dress drift drink drive eager early earth eight elect elite empty enemy enjoy enter equal error event every exact
exist extra faint fairy faith false fancy fault feast fence fever field fifty fight final first flame flash fleet flesh float
flood floor flour focus force forge forth forty forum found frame frank fresh front fruit funny giant given glass globe glory
grace grade grain grand grant grape graph grass great green greet grief group grown guard guess guest guide habit happy harsh
heart heavy hence honey honor horse hotel house human humor ideal image imply index inner input irony issue ivory jelly joint
judge juice knife knock known label labor large laser later laugh layer learn least leave legal lemon level light limit linen
liver local logic loose lover lower lucky lunch magic major maker march match maybe mayor meant medal media melon mercy merit
metal meter might minor minus mixed model money month moral motor mount mouse mouth movie music naive nerve never newly night
noble noise north novel nurse ocean offer often olive onion opera orbit order other ought paint panel paper party pasta patch
pause peace pearl phase phone photo piano piece pilot pitch pixel pizza place plain plane plant plate plaza point polar pound
power press price pride prime print prior prize proof proud prove queen quick quiet quite quote radio raise range rapid ratio
reach react ready realm rebel refer relax reply rider ridge right rigid river robot rocky rough round route royal rural salad
sauce scale scene scope score sense serve seven shade shake shall shape share sharp sheep sheet shelf shell shift shine shirt
shock shoot shore short shown sight silly since sixth sixty skill sleep slice slide small smart smile smoke snake solid solve
sorry sound south space spare speak speed spell spend spice spine split spoke sport staff stage stair stamp stand stare start
state steam steel stick still stock stone stood store storm story stove strip study stuff style sugar suite sunny super sweet
swift swing sword table taste teach thank theme there thick thing think third those three throw thumb tiger tight timer title
toast today token tooth topic total touch tough towel tower trace track trade trail train treat trend trial tribe trick truck
truly trust truth twice uncle under union unity until upper upset urban usage usual valid value video virus visit vital vivid
vocal voice waste watch water wheel where which while white whole whose width woman world worry worse worst worth would wound
write wrong yield young youth zebra""".split()
WORDS = sorted(set(w for w in WORDS if len(w) == 5 and w.isalpha()))


def score(guess, answer):
    """List of 'g' (green), 'y' (yellow), 'x' (grey) per letter, handling repeated letters correctly."""
    result = ["x"] * len(guess)
    remaining = {}
    for i, (g, a) in enumerate(zip(guess, answer)):
        if g == a:
            result[i] = "g"
        else:
            remaining[a] = remaining.get(a, 0) + 1
    for i, g in enumerate(guess):
        if result[i] == "x" and remaining.get(g, 0) > 0:
            result[i] = "y"
            remaining[g] -= 1
    return result


def daily_word(day=None):
    day = day or datetime.date.today()
    return WORDS[zlib.crc32(day.isoformat().encode()) % len(WORDS)]


STYLE = {"g": "bold white on green", "y": "bold black on yellow", "x": "bold white on grey35"}


def render(guess, marks):
    text = Text("  ")
    for ch, m in zip(guess, marks):
        text.append(f" {ch.upper()} ", style=STYLE[m])
        text.append(" ")
    return text


def keyboard(guesses, answer):
    state = {}
    for guess in guesses:
        for ch, m in zip(guess, score(guess, answer)):
            if m == "g" or (m == "y" and state.get(ch) != "g") or ch not in state:
                state[ch] = m
    lines = []
    for row in ("qwertyuiop", "asdfghjkl", "zxcvbnm"):
        line = Text()
        for ch in row:
            line.append(f" {ch} ", style=STYLE[state[ch]] if ch in state else "dim")
        lines.append(line)
    return lines


def play(answer):
    guesses = []
    while len(guesses) < 6:
        for guess in guesses:
            console.print(render(guess, score(guess, answer)))
        for _ in range(6 - len(guesses)):
            console.print(Text("  " + "[ ] " * 5, style="dim"))
        for line in keyboard(guesses, answer):
            console.print(line)
        try:
            guess = input(f"Guess {len(guesses) + 1}/6> ").strip().lower()
        except EOFError:
            return None
        if guess in ("q", "quit"):
            console.print(f"The word was [bold]{answer.upper()}[/bold].")
            return None
        if len(guess) != 5 or not guess.isalpha():
            console.print("[yellow]Type a five-letter word.[/yellow]")
            continue
        guesses.append(guess)
        if guess == answer:
            console.print(render(guess, score(guess, answer)))
            console.print(f"[bold green]Got it in {len(guesses)}![/bold green]")
            return len(guesses)
    console.print(f"[bold red]Out of guesses.[/bold red] The word was [bold]{answer.upper()}[/bold].")
    return 0


def record(won_in):
    if not appdata or won_in is None:
        return
    stats = appdata.load("wordle", {"played": 0, "won": 0, "streak": 0, "best_streak": 0})
    stats["played"] += 1
    if won_in:
        stats["won"] += 1
        stats["streak"] += 1
        stats["best_streak"] = max(stats["best_streak"], stats["streak"])
    else:
        stats["streak"] = 0
    appdata.save("wordle", stats)
    console.print(f"[dim]Played {stats['played']}, won {stats['won']}, streak {stats['streak']} (best {stats['best_streak']})[/dim]")


def main():
    console.print("[bold]Wordle[/bold]  [dim]six guesses; 'q' gives up[/dim]")
    while True:
        mode = input("[d]aily word, [r]andom word, [q]uit> ").strip().lower()[:1] or "d"
        if mode == "q":
            return
        won = play(daily_word() if mode == "d" else random.choice(WORDS))
        if mode == "d":
            record(won)
        if input("Again? [y/N] ").strip().lower() != "y":
            return


def execute():
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute()
