import ast
import operator
from rich.console import Console
from rich.prompt import Prompt

# Command metadata
config = {
    "name": "calc",
    "description": "A simple calculator."
}

console = Console()

# Supported operators for safety
SUPPORTED_OPERATORS = {
    operator.add: "+",
    operator.sub: "-",
    operator.mul: "*",
    operator.truediv: "/",
    operator.floordiv: "//",
    operator.pow: "**",
    operator.mod: "%",
}

def safe_eval(expr):
    """Safely evaluate arithmetic expressions."""
    try:
        # Parse the expression safely
        node = ast.parse(expr, mode='eval')

        # Check if the expression contains only allowed operations
        for subnode in ast.walk(node):
            if isinstance(subnode, (ast.Name, ast.Call, ast.Attribute)):
                raise ValueError("Unsafe expression detected")

        # Compile the safe expression
        compiled_expr = compile(node, filename="<string>", mode="eval")

        # Evaluate the expression with no access to built-ins
        result = eval(compiled_expr, {"__builtins__": {}}, {})
        return result

    except Exception as e:
        return f"Error: {str(e)}"

def execute():
    console.print("[bold cyan]Simple Calculator (type 'exit' to quit)[/bold cyan]")
    while True:
        expr = Prompt.ask("[bold yellow]calc>[/bold yellow]", default="")

        # Handle 'exit' command
        if expr.lower() == "exit":
            console.print("[bold green]Exiting calculator...[/bold green]")
            break

        # Process the expression
        result = safe_eval(expr)

        # Print result
        if isinstance(result, (int, float)):
            console.print(f"[bold green]Result: {result}[/bold green]")
        else:
            console.print(f"[bold red]{result}[/bold red]")
