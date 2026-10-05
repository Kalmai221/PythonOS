#!/usr/bin/env python3
"""Trivia Pack: ten themed question sets (movies, music, space, sports, food, animals, books and art, inventions, language, nature and
earth) with 10 questions each, all built in so it works offline. Pick a category or take a mixed round."""
import random
import sys

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel

try:
    from pyos import appdata
except ImportError:
    appdata = None

console = Console()

# category -> [(question, right answer, [three wrong answers])]
PACK = {
    "Movies": [
        ("Which film features the quote 'May the Force be with you'?", "Star Wars", ["Star Trek", "Dune", "Alien"]),
        ("Who directed 'Jaws' (1975)?", "Steven Spielberg", ["George Lucas", "Francis Ford Coppola", "Ridley Scott"]),
        ("In 'The Lion King', what is the name of Simba's father?", "Mufasa", ["Scar", "Rafiki", "Zazu"]),
        ("Which silent film won the first Academy Award for Best Picture (1929)?", "Wings", ["Sunrise", "Metropolis", "The Jazz Singer"]),
        ("What is the name of the toy cowboy in 'Toy Story'?", "Woody", ["Buzz", "Rex", "Slinky"]),
        ("Which actor played Jack in 'Titanic'?", "Leonardo DiCaprio", ["Brad Pitt", "Tom Cruise", "Matt Damon"]),
        ("Which film series features a ring that must be destroyed in Mount Doom?", "The Lord of the Rings", ["Harry Potter", "Narnia", "The Hobbit: Smaug"]),
        ("What colour is the pill Neo takes to learn the truth in 'The Matrix'?", "Red", ["Blue", "Green", "Yellow"]),
        ("Which animated film features a fish named Nemo?", "Finding Nemo", ["Shark Tale", "The Little Mermaid", "Moana"]),
        ("Who played the Joker in 'The Dark Knight' (2008)?", "Heath Ledger", ["Joaquin Phoenix", "Jared Leto", "Jack Nicholson"]),
    ],
    "Music": [
        ("How many strings does a violin have?", "4", ["5", "6", "3"]),
        ("Which band recorded 'Bohemian Rhapsody'?", "Queen", ["The Beatles", "Led Zeppelin", "Pink Floyd"]),
        ("Which instrument has 88 keys?", "Piano", ["Organ", "Accordion", "Harp"]),
        ("Who composed 'The Four Seasons'?", "Vivaldi", ["Mozart", "Bach", "Beethoven"]),
        ("What is the term for playing a piece of music loudly?", "Forte", ["Piano", "Adagio", "Legato"]),
        ("Which Beatle was known as the 'quiet one'?", "George Harrison", ["John Lennon", "Paul McCartney", "Ringo Starr"]),
        ("How many notes are in a standard major scale (before the octave repeats)?", "7", ["5", "8", "12"]),
        ("Which country is the birthplace of the tango?", "Argentina", ["Spain", "Cuba", "Brazil"]),
        ("Which brass instrument has a slide?", "Trombone", ["Trumpet", "Tuba", "French horn"]),
        ("Beethoven's Symphony No. 9 includes which famous 'Ode'?", "Ode to Joy", ["Ode to Spring", "Ode to Night", "Ode to Freedom"]),
    ],
    "Space": [
        ("Which planet is famous for its bright rings?", "Saturn", ["Mars", "Venus", "Mercury"]),
        ("What is the name of our galaxy?", "The Milky Way", ["Andromeda", "Triangulum", "Whirlpool"]),
        ("Which planet is closest to the Sun?", "Mercury", ["Venus", "Earth", "Mars"]),
        ("What is the largest planet in the Solar System?", "Jupiter", ["Saturn", "Neptune", "Uranus"]),
        ("What force keeps the planets in orbit around the Sun?", "Gravity", ["Magnetism", "Friction", "Inertia only"]),
        ("How long does light from the Sun take to reach Earth, about?", "8 minutes", ["8 seconds", "8 hours", "1 day"]),
        ("Which space telescope, launched in 1990, is named after an astronomer?", "Hubble", ["Kepler", "Spitzer", "Chandra"]),
        ("Which planet is known for its Great Red Spot?", "Jupiter", ["Mars", "Saturn", "Neptune"]),
        ("What is the name of Earth's only natural satellite?", "The Moon", ["Titan", "Phobos", "Europa"]),
        ("Who was the first human in space (1961)?", "Yuri Gagarin", ["Neil Armstrong", "Alan Shepard", "John Glenn"]),
    ],
    "Sports": [
        ("How many players are on the court for one basketball team?", "5", ["6", "7", "4"]),
        ("In which sport do you score a 'birdie'?", "Golf", ["Tennis", "Cricket", "Archery"]),
        ("How often are the Summer Olympic Games held?", "Every 4 years", ["Every 2 years", "Every 3 years", "Every 5 years"]),
        ("What is the diameter of a basketball hoop, about?", "46 cm (18 in)", ["30 cm", "60 cm", "90 cm"]),
        ("Which country has won the most men's football World Cups?", "Brazil", ["Germany", "Argentina", "Italy"]),
        ("How many holes are on a standard round of golf?", "18", ["9", "12", "21"]),
        ("In tennis, what score comes after 30?", "40", ["35", "45", "50"]),
        ("What is the length of a marathon, about?", "42 km", ["26 km", "50 km", "36 km"]),
        ("Which sport is played at Wimbledon?", "Tennis", ["Cricket", "Golf", "Badminton"]),
        ("How many rings are in the Olympic symbol?", "5", ["4", "6", "7"]),
    ],
    "Food and Drink": [
        ("Which country is sushi from?", "Japan", ["China", "Thailand", "Korea"]),
        ("What is the main ingredient of guacamole?", "Avocado", ["Tomato", "Lime", "Pepper"]),
        ("Which fruit is dried to make raisins?", "Grapes", ["Plums", "Cherries", "Figs"]),
        ("What type of pasta is shaped like little rice grains?", "Orzo", ["Penne", "Fusilli", "Farfalle"]),
        ("Which spice is the most expensive by weight, from crocus flowers?", "Saffron", ["Vanilla", "Cardamom", "Cinnamon"]),
        ("What is tofu made from?", "Soybeans", ["Rice", "Wheat", "Chickpeas"]),
        ("Which drink is made by infusing leaves of Camellia sinensis?", "Tea", ["Coffee", "Cocoa", "Mate"]),
        ("Which cheese is traditionally used on a Margherita pizza?", "Mozzarella", ["Cheddar", "Brie", "Gouda"]),
        ("What is the main ingredient in hummus?", "Chickpeas", ["Lentils", "Black beans", "Peas"]),
        ("In which country did the croissant become famous (though it came from Austria)?", "France", ["Italy", "Spain", "Belgium"]),
    ],
    "Animals": [
        ("What is a group of lions called?", "A pride", ["A pack", "A herd", "A flock"]),
        ("Which is the largest living land animal?", "African elephant", ["Hippopotamus", "Giraffe", "White rhino"]),
        ("How many hearts does an octopus have?", "3", ["1", "2", "8"]),
        ("Which bird can fly backwards?", "Hummingbird", ["Eagle", "Sparrow", "Owl"]),
        ("What is a baby swan called?", "Cygnet", ["Cub", "Fledgling", "Gosling"]),
        ("Which mammal lays eggs?", "Platypus", ["Armadillo", "Bat", "Otter"]),
        ("What do pandas mainly eat?", "Bamboo", ["Fish", "Eucalyptus", "Grass"]),
        ("How many legs does an insect have?", "6", ["4", "8", "10"]),
        ("What is the largest animal that has ever lived?", "The blue whale", ["Megalodon", "Argentinosaurus", "The African elephant"]),
        ("What is the only mammal capable of true flight?", "Bat", ["Flying squirrel", "Colugo", "Sugar glider"]),
    ],
    "Books and Art": [
        ("Who wrote 'Pride and Prejudice'?", "Jane Austen", ["Charlotte Bronte", "George Eliot", "Mary Shelley"]),
        ("Who painted 'The Starry Night'?", "Vincent van Gogh", ["Claude Monet", "Pablo Picasso", "Salvador Dali"]),
        ("In which city is the Louvre museum?", "Paris", ["London", "Rome", "Madrid"]),
        ("Who wrote '1984'?", "George Orwell", ["Aldous Huxley", "Ray Bradbury", "H. G. Wells"]),
        ("Which artist is famous for cutting off part of his own ear?", "Van Gogh", ["Picasso", "Monet", "Rembrandt"]),
        ("What is the first book of the Harry Potter series?", "Harry Potter and the Philosopher's Stone", ["The Chamber of Secrets", "The Goblet of Fire", "The Prisoner of Azkaban"]),
        ("Who sculpted 'David' (1501-1504)?", "Michelangelo", ["Donatello", "Bernini", "Rodin"]),
        ("Who wrote 'The Hobbit'?", "J. R. R. Tolkien", ["C. S. Lewis", "Roald Dahl", "T. H. White"]),
        ("Which movement was Salvador Dali part of?", "Surrealism", ["Cubism", "Impressionism", "Pop art"]),
        ("Who wrote the play 'Hamlet'?", "William Shakespeare", ["Christopher Marlowe", "Ben Jonson", "Oscar Wilde"]),
    ],
    "Inventions": [
        ("Who is credited with inventing the practical telephone (1876)?", "Alexander Graham Bell", ["Thomas Edison", "Nikola Tesla", "Samuel Morse"]),
        ("Which invention by Johannes Gutenberg changed the spread of knowledge?", "The printing press", ["The telescope", "The compass", "The clock"]),
        ("Who built the first successful powered aeroplane flight in 1903?", "The Wright brothers", ["Louis Bleriot", "Charles Lindbergh", "Alberto Santos-Dumont"]),
        ("What did Tim Berners-Lee invent in 1989?", "The World Wide Web", ["The transistor", "Email", "The modem"]),
        ("Which material, invented in 1907, was the first fully synthetic plastic?", "Bakelite", ["Nylon", "Polythene", "Celluloid"]),
        ("Who invented the first practical light bulb (with Swan, in the 1870s)?", "Thomas Edison", ["Nikola Tesla", "Michael Faraday", "Alessandro Volta"]),
        ("Which Italian physicist invented the battery (voltaic pile)?", "Alessandro Volta", ["Galileo Galilei", "Enrico Fermi", "Guglielmo Marconi"]),
        ("What did Marie Curie discover with Pierre Curie, besides polonium?", "Radium", ["Uranium", "Helium", "Plutonium"]),
        ("Which device did Galileo famously improve in 1609?", "The telescope", ["The microscope", "The barometer", "The clock"]),
        ("What does a Geiger counter measure?", "Radiation", ["Sound", "Temperature", "Pressure"]),
    ],
    "Language": [
        ("What is the most spoken first language in the world?", "Mandarin Chinese", ["English", "Spanish", "Hindi"]),
        ("Which language is mainly spoken in Brazil?", "Portuguese", ["Spanish", "French", "Italian"]),
        ("How many letters are in the English alphabet?", "26", ["24", "25", "28"]),
        ("What do you call a word that sounds like its meaning, like 'buzz'?", "Onomatopoeia", ["Alliteration", "Metaphor", "Palindrome"]),
        ("Which of these is a palindrome?", "Level", ["Lever", "Candle", "Radish"]),
        ("What is 'thank you' in Spanish?", "Gracias", ["Merci", "Danke", "Grazie"]),
        ("Which writing system is used for Russian?", "Cyrillic", ["Latin", "Greek", "Arabic"]),
        ("What is a word opposite in meaning to another called?", "An antonym", ["A synonym", "A homonym", "An acronym"]),
        ("What is 'hello' in Japanese?", "Konnichiwa", ["Annyeong", "Nihao", "Sawasdee"]),
        ("What does 'carpe diem' mean?", "Seize the day", ["Time flies", "Know thyself", "Peace be with you"]),
    ],
    "Nature and Earth": [
        ("What is the largest ocean on Earth?", "Pacific", ["Atlantic", "Indian", "Arctic"]),
        ("What is the tallest mountain above sea level?", "Mount Everest", ["K2", "Kilimanjaro", "Denali"]),
        ("Which gas makes up most of Earth's atmosphere?", "Nitrogen", ["Oxygen", "Carbon dioxide", "Argon"]),
        ("What is the longest river in South America?", "The Amazon", ["The Orinoco", "The Parana", "The Magdalena"]),
        ("What type of rock is formed from cooled lava?", "Igneous", ["Sedimentary", "Metamorphic", "Mineral"]),
        ("Which layer of the Earth do we live on?", "The crust", ["The mantle", "The outer core", "The inner core"]),
        ("What causes the tides, mainly?", "The Moon's gravity", ["The wind", "The Sun's heat", "Earth's rotation only"]),
        ("What is the driest continent?", "Antarctica", ["Africa", "Australia", "Asia"]),
        ("Which is the largest hot desert in the world?", "The Sahara", ["The Gobi", "The Kalahari", "The Arabian"]),
        ("What is the process by which plants make food using sunlight?", "Photosynthesis", ["Respiration", "Digestion", "Fermentation"]),
    ],
}
ROUND = 10


def questions_for(category, rng=None, amount=ROUND):
    rng = rng or random
    if category == "Mixed":
        pool = [(c, *q) for c, qs in PACK.items() for q in qs]
    else:
        pool = [(category, *q) for q in PACK[category]]
    return rng.sample(pool, min(amount, len(pool)))


def ask(number, total, item, rng=None):
    rng = rng or random
    category, text, right, wrong = item
    options = [right] + list(wrong)
    rng.shuffle(options)
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
    stats = appdata.load("triviapack", {}) if appdata else {}
    names = list(PACK) + ["Mixed"]
    while True:
        for i, n in enumerate(names, 1):
            best = stats.get(n)
            console.print(f"  [cyan]{i}[/cyan] {n}" + (f"  [dim](best {best}/{ROUND})[/dim]" if best is not None else ""))
        pick = input("Category number (q to quit)> ").strip().lower()
        if pick in ("q", "quit"):
            return
        if not pick.isdigit() or not 1 <= int(pick) <= len(names):
            continue
        category = names[int(pick) - 1]
        score, items = 0, questions_for(category)
        for i, item in enumerate(items, 1):
            result = ask(i, len(items), item)
            if result is None:
                break
            score += result
        else:
            console.print(f"\n[bold]{category}: {score}/{len(items)}[/bold]")
            if appdata and score > stats.get(category, -1):
                stats[category] = score
                appdata.save("triviapack", stats)
        if input("Another round? [y/N] ").strip().lower() != "y":
            return


def execute(args=None):
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        console.print()


if __name__ == "__main__":
    execute(sys.argv[1:])
