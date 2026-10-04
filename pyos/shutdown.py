import threading


class ShutdownRequested(KeyboardInterrupt):
    """Raised to end PythonOS cleanly. It is a KeyboardInterrupt so main.py's existing handler runs the shutdown
    screen, but the shell recognises it and lets it through (a real Ctrl+C just prints ^C and carries on)."""


_pending = threading.Event()


def shutdown():
    """Ask PythonOS to shut down. Safe to call from any thread."""
    _pending.set()
    if threading.current_thread() is threading.main_thread():
        raise ShutdownRequested()
    import _thread
    _thread.interrupt_main()        # wakes the main thread, which then sees pending() and shuts down


def pending():
    return _pending.is_set()
