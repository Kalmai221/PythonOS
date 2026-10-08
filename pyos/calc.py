# pyos/calc.py - a calculator that only does arithmetic, for the calc command
#
# The expression is read with Python's own parser and then walked by hand: numbers, + - * / // % **, brackets, a few functions and constants. Nothing
# else is ever evaluated (no names, no calls except the listed functions, no attributes), so typing something odd cannot run code. Powers are
# limited so that 9**9**9 does not freeze the computer.
import ast
import math
import operator

MAX_EXPONENT = 10_000
MAX_DIGITS = 5_000
CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau, "inf": math.inf}
FUNCTIONS = {"sqrt": math.sqrt, "sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin, "acos": math.acos, "atan": math.atan,
             "log": math.log, "ln": math.log, "log10": math.log10, "log2": math.log2, "exp": math.exp, "abs": abs, "round": round, "floor": math.floor,
             "ceil": math.ceil, "min": min, "max": max, "fact": math.factorial, "factorial": math.factorial, "gcd": math.gcd, "radians": math.radians,
             "degrees": math.degrees, "sum": lambda *a: sum(a)}
BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
          ast.Mod: operator.mod, ast.Pow: operator.pow}


class CalcError(Exception):
    """An expression that cannot be calculated: the message says why in plain words."""


def _walk(node):
    if isinstance(node, ast.Expression):
        return _walk(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _walk(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp) and type(node.op) in BINARY:
        left, right = _walk(node.left), _walk(node.right)
        if isinstance(node.op, ast.Pow):
            if abs(right) > MAX_EXPONENT or (isinstance(left, int) and isinstance(right, int) and right > 0 and abs(left).bit_length() * right > MAX_DIGITS * 4):
                raise CalcError("that power is too big to work out here")
        try:
            return BINARY[type(node.op)](left, right)
        except ZeroDivisionError:
            raise CalcError("dividing by zero") from None
        except OverflowError:
            raise CalcError("the number is too big") from None
    if isinstance(node, ast.Name):
        if node.id in CONSTANTS:
            return CONSTANTS[node.id]
        raise CalcError(f"I do not know '{node.id}' (constants: {', '.join(CONSTANTS)})")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCTIONS and not node.keywords:
        arguments = [_walk(a) for a in node.args]
        try:
            return FUNCTIONS[node.func.id](*arguments)
        except (ValueError, TypeError, OverflowError) as e:
            raise CalcError(f"{node.func.id} cannot take that ({e})") from None
    if isinstance(node, ast.Call):
        name = node.func.id if isinstance(node.func, ast.Name) else "that"
        raise CalcError(f"I do not know the function '{name}' (try: {', '.join(sorted(FUNCTIONS)[:8])}, ...)")
    raise CalcError("I can only do arithmetic: numbers, + - * / // % **, brackets, and functions such as sqrt(2)")


def evaluate(text):
    """The value of an arithmetic expression. Raises CalcError."""
    text = text.strip().replace("^", "**") if text else ""
    if not text:
        raise CalcError("give a calculation, for example: calc 2 + 3 * 4")
    if len(text) > 500:
        raise CalcError("that expression is too long")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError:
        raise CalcError("that is not a calculation I can read") from None
    value = _walk(tree)
    if isinstance(value, int) and len(str(abs(value))) > MAX_DIGITS:
        raise CalcError("the answer has too many digits to show")
    return value


def show(value):
    """The value for a person: whole numbers as they are, others with up to 12 significant digits and no trailing zeros."""
    if isinstance(value, int):
        return str(value)
    if value != value or value in (math.inf, -math.inf):
        return str(value)
    if float(value).is_integer() and abs(value) < 1e15:
        return str(int(value))
    return f"{value:.12g}"
