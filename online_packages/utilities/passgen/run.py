#!/usr/bin/env python3
"""Password generator and strength checker. Makes random passwords or easy-to-remember passphrases using your system's secure random
numbers, and estimates how strong a password is. Nothing you type here is saved or sent anywhere.
Usage: passgen [length]  |  passgen phrase [words]  |  passgen check  (no arguments opens a menu)."""
import math
import re
import secrets
import string
import sys

from rich.console import Console
from rich.prompt import Confirm, IntPrompt, Prompt

console = Console()
WORDS = """able acid aged also area army away baby back ball band bank base bath bear beat been bell belt best bike bird blow blue boat body
bold bone book boom born boss both bowl bulk burn bush busy cafe cake call calm came camp card care cart case cash cast cave cell chat
chef chin city clay clip club coal coat code coin cold come cook cool cope copy core cost crew crop cube cure dark data dawn dead deal
dear deep deer desk dial dice diet dirt dish dive dock does dome door dose down draw dream drop drum duck dust duty each earn east easy
edge else even ever exam face fact fail fair fall farm fast fate fear feed feel fern file fill film find fine fire firm fish five flag
flat flow foam fold folk food foot form fort four free frog from fuel full fund gain game gate gear gift girl give glad glow goal gold
golf good grab gray grew grid grin grip grow gulf hair half hall hand hang hard harm hash have hawk head heal heap hear heat help herb
here hero hide high hill hint hold hole home hook hope horn host hour huge hunt idea inch iron isle item jade jazz join joke jump junk
jury just keen keep kind king kiss kite knee knot know lake lamp land lane last late lawn lead leaf lean left lens less lift like lime
line link lion list live load loan lock loft logo long look loop lost loud love luck lump lunch main make mall many mark mask mast
meal mean meet melt memo menu mesh mild milk mind mine mint miss mode moon more moss most move much must myth nail name navy near neat
neck need nest news next nice nine node none noon norm nose note noun oath odds okay once only open oral oval oven over pace pack page
paid pair palm park part pass past path peak pear peel pick pier pile pine pink pipe plan play plot plug plus poem pole pond pool port
pose post pour pray pull pump pure push quad quiz race rack rail rain rank rare rate read real reef rely rent rest rice rich ride ring
rise risk road rock role roll roof room root rope rose ruby rule rush safe sage sail salt same sand save scan seal seat seed seek self
sell send shed ship shop shot show shut sick side sign silk sing sink site size skin slim slip slow snap snow soap sock soft soil sold
sole some song soon sort soul soup spin spot star stay stem step stir stop such suit sure swan swim tail take tale talk tall tank tape
task team tell tent term test text than that them then they thin this tide tidy tile time tiny tire toad told tone tool top torn tour
town trap tray tree trim trip true tube tune turn twin type unit upon urge used user vase very vest view vine visa void vote wage wait
wake walk wall want warm wave weak wear weld well went were west what when whom wide wife wild will wind wine wing wire wise wish with
wolf wood wool word wore work worm wrap yard yarn year yoga zero zone zoom""".split()
WORDS = sorted(set(WORDS))
AMBIGUOUS = set("Il1O0o")


def generate(length=16, upper=True, lower=True, digits=True, symbols=True, avoid_ambiguous=False):
    """A random password with at least one character of every kind that was asked for."""
    pools = []
    if lower:
        pools.append(string.ascii_lowercase)
    if upper:
        pools.append(string.ascii_uppercase)
    if digits:
        pools.append(string.digits)
    if symbols:
        pools.append("!@#$%^&*()-_=+[]{};:,.?")
    if not pools:
        raise ValueError("Choose at least one kind of character.")
    if avoid_ambiguous:
        pools = ["".join(c for c in p if c not in AMBIGUOUS) for p in pools]
    if length < len(pools):
        raise ValueError(f"The length must be at least {len(pools)}.")
    chars = [secrets.choice(p) for p in pools]
    everything = "".join(pools)
    chars += [secrets.choice(everything) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def passphrase(words=5, separator="-", capitalise=True, number=True):
    chosen = [secrets.choice(WORDS) for _ in range(words)]
    if capitalise:
        chosen = [w.capitalize() for w in chosen]
    text = separator.join(chosen)
    return text + (separator + str(secrets.randbelow(100))) if number else text


def entropy_bits(password):
    """A rough strength estimate: length times the log of the size of the character set used. Common words and patterns weaken it."""
    pool = 0
    for test, size in ((r"[a-z]", 26), (r"[A-Z]", 26), (r"[0-9]", 10), (r"[^a-zA-Z0-9]", 32)):
        if re.search(test, password):
            pool += size
    bits = len(password) * math.log2(pool) if pool else 0
    lowered = password.lower()
    if re.fullmatch(r"(.)\1+", password):
        bits = min(bits, 4)
    if any(seq in lowered for seq in ("password", "qwerty", "letmein", "123456", "abcdef", "iloveyou", "admin")):
        bits = min(bits, 20)
    if re.fullmatch(r"[a-z]+\d{0,4}", lowered) and len(password) < 12:
        bits = min(bits, 36)
    return bits


def rate(bits):
    if bits < 28:
        return "very weak", "red"
    if bits < 40:
        return "weak", "dark_orange"
    if bits < 60:
        return "fair", "yellow"
    if bits < 80:
        return "strong", "green"
    return "very strong", "bright_green"


def crack_time(bits):
    """Time for a fast attacker (10 billion guesses a second) to try half the possibilities."""
    seconds = 2 ** max(bits - 1, 0) / 1e10
    for limit, unit in ((60, "seconds"), (3600, "minutes"), (86400, "hours"), (86400 * 365, "days"), (86400 * 365 * 1000, "years"),
                        (86400 * 365 * 1e6, "thousand years"), (86400 * 365 * 1e9, "million years")):
        if seconds < limit:
            divisor = {"seconds": 1, "minutes": 60, "hours": 3600, "days": 86400, "years": 86400 * 365,
                       "thousand years": 86400 * 365 * 1000, "million years": 86400 * 365 * 1e6}[unit]
            return f"about {max(seconds / divisor, 1):,.0f} {unit}" if seconds >= 1 else "instantly"
    return "longer than the age of the universe"


def show_strength(password):
    bits = entropy_bits(password)
    label, colour = rate(bits)
    console.print(f"Strength: [{colour}]{label}[/{colour}]  (about {bits:.0f} bits; a fast attacker would need {crack_time(bits)})")
    tips = []
    if len(password) < 12:
        tips.append("make it at least 12 characters long")
    if not re.search(r"[A-Z]", password) or not re.search(r"[a-z]", password):
        tips.append("mix upper and lower case")
    if not re.search(r"\d", password):
        tips.append("add a digit")
    if not re.search(r"[^a-zA-Z0-9]", password):
        tips.append("add a symbol, or use a long passphrase instead")
    if tips:
        console.print("[dim]Tips: " + "; ".join(tips) + ".[/dim]")


def main(args):
    if args and args[0].isdigit():
        pw = generate(max(4, min(128, int(args[0]))))
        console.print(pw, markup=False, highlight=False)
        show_strength(pw)
        return
    if args and args[0] in ("phrase", "passphrase"):
        words = int(args[1]) if len(args) > 1 and args[1].isdigit() else 5
        pw = passphrase(max(3, min(12, words)))
        console.print(pw, markup=False, highlight=False)
        show_strength(pw)
        return
    if args and args[0] == "check":
        show_strength(Prompt.ask("Password to check (not saved)", password=True))
        return
    while True:
        choice = Prompt.ask("(p)assword, p(h)rase, (c)heck strength, (q)uit", choices=["p", "h", "c", "q"], default="p")
        if choice == "q":
            return
        if choice == "p":
            length = IntPrompt.ask("Length", default=16)
            options = dict(upper=Confirm.ask("Capital letters?", default=True), digits=Confirm.ask("Digits?", default=True),
                           symbols=Confirm.ask("Symbols?", default=True), avoid_ambiguous=Confirm.ask("Avoid look-alike characters (l 1 I O 0)?", default=False))
            try:
                for _ in range(3):
                    console.print(generate(max(4, min(128, length)), **options), markup=False, highlight=False)
            except ValueError as e:
                console.print(f"[red]{e}[/red]")
        elif choice == "h":
            words = max(3, min(12, IntPrompt.ask("Words", default=5)))
            for _ in range(3):
                console.print(passphrase(words), markup=False, highlight=False)
            console.print("[dim]Passphrases of 5+ random words are long, strong and easier to remember.[/dim]")
        else:
            show_strength(Prompt.ask("Password to check (not saved)", password=True))


def execute(args=None):
    try:
        main(list(args or []))
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
