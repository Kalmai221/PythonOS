from . import screens


def simulate_shutdown_wipe():
    """Factory reset: erase accounts, settings, files and packages, then power off."""
    screens.shutdown_sequence("wipe")
