# pyos/shellvars.py - shell variables and aliases (the alias, unalias, export, unset and source commands, and $NAME in command lines).
#
#   NAME=value        sets a variable for this session; export NAME=value does the same and lists it in `env`
#   $NAME ${NAME}     the value in any later word (also $USER $HOME $HOST $PWD, which always exist, and $? the last status)
#   alias ll="ls -l"  a short name for a command with arguments; aliases are kept for the person who made them (~/.pyos_aliases)
#   ~/.pyosrc         lines run at every login (set variables, make aliases: the same lines you type at the prompt)
# An alias only expands the first word of a command, and never expands itself again, so it cannot loop.
import json
import os
import re
import shlex

import pyos.fs as fs

NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
ASSIGN_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.S)
VAR_RE = re.compile(r"\$(?:\{([A-Za-z_][A-Za-z0-9_]*)\}|([A-Za-z_][A-Za-z0-9_]*))")
RESERVED = {"alias", "unalias", "exit"}          # names an alias may not take over: they are how you undo a mistake
MAX_DEPTH = 5

_variables = {}
_exported = set()
_aliases = {}
_aliases_for = None          # the user the aliases in memory belong to


# ---------------------------------------------------------------- variables
def builtin(name):
    """The always-present variables, or None."""
    import pyos
    if name == "USER":
        return pyos.userinfo()[0] or ""
    if name == "HOME":
        user = pyos.userinfo()[0]
        return fs.display(fs.home_dir(user), tilde=False) if user else ""
    if name == "HOST":
        return fs.hostname()
    if name == "PWD":
        return fs.display(fs.current_dir(), tilde=False)
    return None


def get(name):
    if name in _variables:
        return _variables[name]
    found = builtin(name)
    return found if found is not None else ""


def set_variable(name, value, export=False):
    if not NAME_RE.match(name):
        raise ValueError(f"'{name}' is not a valid variable name (letters, digits and _, not starting with a digit)")
    _variables[name] = value
    if export:
        _exported.add(name)


def unset(name):
    _variables.pop(name, None)
    _exported.discard(name)


def exported():
    return {n: _variables[n] for n in sorted(_exported) if n in _variables}


def everything():
    return dict(sorted(_variables.items()))


def expand(word, status=0):
    """$? and $NAME in one word. An undefined variable becomes empty, like a real shell."""
    word = word.replace("$?", str(status))
    return VAR_RE.sub(lambda m: get(m.group(1) or m.group(2)), word)


def assignment(argv):
    """(name, value) when the command is just NAME=value, else None."""
    if len(argv) == 1:
        match = ASSIGN_RE.match(argv[0])
        if match:
            return match.group(1), match.group(2)
    return None


# ---------------------------------------------------------------- aliases
def _file():
    user = fs.current_user()[0]
    return os.path.join(fs.home_dir(user), ".pyos_aliases") if user else None


def load_aliases():
    """Read the current person's aliases from their home folder (call at login)."""
    global _aliases, _aliases_for
    _aliases, _aliases_for = {}, fs.current_user()[0]
    path = _file()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        _aliases = {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str) and NAME_RE.match(k.replace("-", "_").replace(".", "_"))}
    except (OSError, ValueError, TypeError):
        _aliases = {}
    return _aliases


def aliases():
    if _aliases_for != fs.current_user()[0]:
        load_aliases()
    return dict(sorted(_aliases.items()))


def _save():
    path = _file()
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_aliases, f, indent=2)
    except OSError:
        pass


def set_alias(name, value):
    if not re.match(r"^[A-Za-z0-9_.-]+$", name):
        raise ValueError(f"'{name}' is not a valid alias name")
    if name in RESERVED:
        raise ValueError(f"'{name}' cannot be an alias: it is how you undo a mistake")
    if not value.strip():
        raise ValueError("an alias needs a command, for example: alias ll=\"ls -l\"")
    aliases()
    _aliases[name] = value
    _save()


def remove_alias(name):
    aliases()
    found = _aliases.pop(name, None) is not None
    if found:
        _save()
    return found


def clear_aliases():
    aliases()
    _aliases.clear()
    _save()


def apply(argv):
    """argv with an alias on its first word replaced by what it stands for."""
    seen = set()
    for _ in range(MAX_DEPTH):
        if not argv or argv[0] in seen:
            break
        known = aliases()
        if argv[0] not in known:
            break
        seen.add(argv[0])
        try:
            argv = shlex.split(known[argv[0]]) + list(argv[1:])
        except ValueError:
            break
    return argv


# ---------------------------------------------------------------- the login file
def rc_lines():
    """The commands of ~/.pyosrc (comments and empty lines left out)."""
    user = fs.current_user()[0]
    if not user:
        return []
    try:
        with open(os.path.join(fs.home_dir(user), ".pyosrc"), encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip() and not l.strip().startswith("#")]
    except OSError:
        return []
