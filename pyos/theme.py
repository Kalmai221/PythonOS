# pyos/theme.py - colour themes. Roles map to rich styles; ansi() gives raw escape codes for the prompt.
from . import settings

# role -> rich style
THEMES = {
    "default": {"accent": "cyan", "title": "bold cyan", "success": "green", "warning": "yellow", "error": "red",
                "border": "blue", "dim": "dim", "prompt_user": "bold green", "prompt_path": "bold blue"},
    "ocean": {"accent": "bright_cyan", "title": "bold bright_cyan", "success": "bright_green", "warning": "yellow",
              "error": "bright_red", "border": "bright_blue", "dim": "dim", "prompt_user": "bold bright_cyan",
              "prompt_path": "bold bright_blue"},
    "forest": {"accent": "green", "title": "bold green", "success": "bright_green", "warning": "yellow",
               "error": "red", "border": "green", "dim": "dim", "prompt_user": "bold bright_green",
               "prompt_path": "bold yellow"},
    "sunset": {"accent": "bright_yellow", "title": "bold bright_yellow", "success": "green", "warning": "bright_yellow",
               "error": "bright_red", "border": "red", "dim": "dim", "prompt_user": "bold bright_red",
               "prompt_path": "bold bright_yellow"},
    "mono": {"accent": "white", "title": "bold white", "success": "white", "warning": "white", "error": "bold white",
             "border": "white", "dim": "dim", "prompt_user": "bold white", "prompt_path": "white"},
    "contrast": {"accent": "bright_yellow", "title": "bold bright_yellow", "success": "bright_green",
                 "warning": "bright_yellow", "error": "bold bright_red", "border": "bright_white", "dim": "white",
                 "prompt_user": "bold bright_white", "prompt_path": "bold bright_yellow"},
}

_COLOURS = {"black": 30, "red": 31, "green": 32, "yellow": 33, "blue": 34, "magenta": 35, "cyan": 36, "white": 37}
_ATTRS = {"bold": 1, "dim": 2, "italic": 3, "underline": 4}


def name():
    chosen = settings.get("theme")
    return chosen if chosen in THEMES else "default"


def style(role):
    """The rich style string for a role in the current theme."""
    return THEMES[name()].get(role, "")


def tag(role, text):
    """Wrap text in rich markup for a role: tag('success', 'ok') -> '[green]ok[/green]'."""
    s = style(role)
    return f"[{s}]{text}[/{s}]" if s else text


def sgr(rich_style):
    """Convert a simple rich style ('bold bright_green') into an ANSI SGR parameter string ('1;92')."""
    codes = []
    for word in rich_style.split():
        if word in _ATTRS:
            codes.append(_ATTRS[word])
        elif word in _COLOURS:
            codes.append(_COLOURS[word])
        elif word.startswith("bright_") and word[7:] in _COLOURS:
            codes.append(_COLOURS[word[7:]] + 60)
    return ";".join(str(c) for c in codes) or "0"


def ansi(role):
    """Raw escape code that starts a role's style (for prompts)."""
    return f"\033[{sgr(style(role))}m"
