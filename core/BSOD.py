from . import screens


def simulate_bsod(error_message):
    """The crash screen: explain, log, then restart PythonOS (unless it is crashing in a loop)."""
    screens.crash_screen(error_message)
