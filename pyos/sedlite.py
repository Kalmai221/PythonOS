# pyos/sedlite.py - the part of sed that people use every day, for the sed command
#
#   s/pattern/replacement/[g][i]     replace (the pattern is a Python regular expression; \1 and & work in the replacement)
#   d                                delete the line
#   p                                print the line (twice, unless -n)
#   q                                stop after this line
#   addresses before a command:      5    5,8    $    /regex/    /regex/,/regex/    5,+2    and ! after the address to mean "not these lines"
# Several commands are separated by ; or by repeating -e. There is no hold space, no labels, no in-place edit (-i): use  sed ... file > new  instead.
import re


class SedError(Exception):
    """A script that cannot be understood: the message says where."""


class Address:
    def __init__(self, kind, value=None):
        self.kind, self.value = kind, value                  # kinds: line, last, regex, plus (the lines after the first address)

    def matches(self, number, last, line):
        if self.kind == "line":
            return number == self.value
        if self.kind == "last":
            return last
        return bool(self.value.search(line))


class Command:
    def __init__(self, start, end, negate, name, pattern=None, replacement=None, flags=0, count=1):
        self.start, self.end, self.negate, self.name = start, end, negate, name
        self.pattern, self.replacement, self.flags, self.count = pattern, replacement, flags, count
        self.active = False                                   # inside a range
        self.remaining = 0                                    # lines left in an N,+M range


def _read_address(text, i):
    if i < len(text) and text[i].isdigit():
        j = i
        while j < len(text) and text[j].isdigit():
            j += 1
        return Address("line", int(text[i:j])), j
    if i < len(text) and text[i] == "$":
        return Address("last"), i + 1
    if i < len(text) and text[i] == "/":
        j = i + 1
        while j < len(text) and text[j] != "/":
            j += 2 if text[j] == "\\" else 1
        if j >= len(text):
            raise SedError("an address starts with / but never ends")
        try:
            return Address("regex", re.compile(text[i + 1:j])), j + 1
        except re.error as e:
            raise SedError(f"the pattern /{text[i + 1:j]}/ is not valid ({e})") from None
    return None, i


def _split_s(text, i):
    """(pattern, replacement, flags text, next index) for 's' followed by a delimiter at text[i]."""
    if i >= len(text):
        raise SedError("s needs a pattern: s/old/new/")
    delimiter = text[i]
    parts, current, j = [], [], i + 1
    while j < len(text) and len(parts) < 2:
        char = text[j]
        if char == "\\" and j + 1 < len(text):
            if text[j + 1] == delimiter:
                current.append(delimiter)                      # an escaped delimiter is just that character
            else:
                current.append(char + text[j + 1])
            j += 2
            continue
        if char == delimiter:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
        j += 1
    if len(parts) < 2:
        raise SedError("s/old/new/ is missing its closing delimiter")
    k = j
    while k < len(text) and text[k] not in ";}\n" and text[k] != " ":
        k += 1
    return parts[0], parts[1], text[j:k], k


def parse(script):
    """[Command] for a script. Raises SedError."""
    commands = []
    i, text = 0, script.strip()
    while i < len(text):
        while i < len(text) and text[i] in "; \n\t":
            i += 1
        if i >= len(text):
            break
        start, i = _read_address(text, i)
        end = None
        if start is not None and i < len(text) and text[i] == ",":
            if i + 1 < len(text) and text[i + 1] == "+":
                j = i + 2
                while j < len(text) and text[j].isdigit():
                    j += 1
                if j == i + 2:
                    raise SedError("+ in an address needs a number")
                end, i = Address("plus", int(text[i + 2:j])), j
            else:
                end, i = _read_address(text, i + 1)
                if end is None:
                    raise SedError("an address range needs an end")
        while i < len(text) and text[i] == " ":
            i += 1
        negate = False
        if i < len(text) and text[i] == "!":
            negate, i = True, i + 1
        if i >= len(text):
            raise SedError("an address needs a command after it")
        name = text[i]
        i += 1
        if name == "s":
            pattern, replacement, flag_text, i = _split_s(text, i)
            flags, count = 0, 1
            for flag in flag_text:
                if flag == "g":
                    count = 0
                elif flag in "iI":
                    flags |= re.IGNORECASE
                else:
                    raise SedError(f"s does not know the flag '{flag}' (g and i work)")
            try:
                compiled = re.compile(pattern, flags)
            except re.error as e:
                raise SedError(f"the pattern '{pattern}' is not valid ({e})") from None
            commands.append(Command(start, end, negate, "s", compiled, replacement, flags, count))
        elif name in "dpq":
            commands.append(Command(start, end, negate, name))
        else:
            raise SedError(f"the command '{name}' is not supported (s, d, p and q are)")
    return commands


def _selected(command, number, last, line, remaining):
    """Whether `command` applies to this line; keeps the state of an address range."""
    if command.start is None:
        chosen = True
    elif command.end is None:
        chosen = command.start.matches(number, last, line)
    elif command.active:
        chosen = True
        if command.end.kind == "plus":
            command.remaining -= 1
            if command.remaining <= 0:
                command.active = False
        elif command.end.matches(number, last, line):
            command.active = False
    elif command.start.matches(number, last, line):
        chosen = True
        if command.end.kind == "plus":
            command.remaining = command.end.value
            command.active = command.remaining > 0
        elif command.end.kind == "line" and command.end.value <= number:
            command.active = False                             # 5,3 is just line 5
        else:
            command.active = not command.end.matches(number, last, line)
    else:
        chosen = False
    return chosen != command.negate


def replacement_for(match, template):
    """The replacement text for one match: & is the whole match, \\1 .. \\9 the groups, \\n a newline."""
    out, i = [], 0
    while i < len(template):
        char = template[i]
        if char == "\\" and i + 1 < len(template):
            nxt = template[i + 1]
            if nxt.isdigit():
                try:
                    out.append(match.group(int(nxt)) or "")
                except IndexError:
                    raise SedError(f"the replacement uses \\{nxt} but the pattern has no such group") from None
            elif nxt == "n":
                out.append("\n")
            elif nxt == "t":
                out.append("\t")
            else:
                out.append(nxt)
            i += 2
            continue
        out.append(match.group(0) if char == "&" else char)
        i += 1
    return "".join(out)


def run(commands, lines, quiet=False):
    """The output lines of the script applied to the input lines."""
    output = []
    total = len(lines)
    for command in commands:
        command.active = False
    for index, original in enumerate(lines):
        number, last, line = index + 1, index == total - 1, original
        printed_extra, deleted, stop = 0, False, False
        for command in commands:
            if not _selected(command, number, last, line, None):
                continue
            if command.name == "s":
                line = command.pattern.sub(lambda m, c=command: replacement_for(m, c.replacement), line, count=command.count)
            elif command.name == "d":
                deleted = True
                break
            elif command.name == "p":
                printed_extra += 1
            elif command.name == "q":
                stop = True
                break
        if not deleted:
            output.extend([line] * printed_extra)
            if not quiet:
                output.append(line)
        if stop:
            break
    return output
