# pyos/readline_stub.py - no-op stand-in for platforms without a readline module
# (some Android and minimal Linux builds). Input still works, just without
# history, line editing and tab completion.
_history = []


def parse_and_bind(*args, **kwargs):
    pass


def set_completer(*args, **kwargs):
    pass


def set_completer_delims(*args, **kwargs):
    pass


def get_line_buffer():
    return ""


def read_history_file(*args, **kwargs):
    pass


def write_history_file(*args, **kwargs):
    pass


def add_history(line):
    _history.append(line)


def get_current_history_length():
    return len(_history)


def get_history_item(index):
    return _history[index - 1] if 1 <= index <= len(_history) else None
