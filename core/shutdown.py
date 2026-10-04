from . import screens


def simulate_shutdown(restart=False):
    """The shutdown screen. Ends the process; with restart=True it returns so the caller can relaunch."""
    screens.shutdown_sequence("restart" if restart else "shutdown")
