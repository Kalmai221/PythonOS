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


def on_signal(signum=None, frame=None):
    """Signal handler for the power button of the live ISO / a virtual machine's shutdown signal (SIGUSR1, sent by the ACPI handler of the
    image). It runs in the main thread, so raising here interrupts whatever PythonOS is waiting on, and main.py shows the shutdown screens."""
    _pending.set()
    raise ShutdownRequested()


def install_signal_handler():
    """Make SIGUSR1 mean "shut down" where the system has that signal (Linux, macOS); does nothing on Windows. Returns True when installed."""
    import signal
    if not hasattr(signal, "SIGUSR1") or threading.current_thread() is not threading.main_thread():
        return False
    try:
        signal.signal(signal.SIGUSR1, on_signal)
    except (ValueError, OSError):
        return False
    return True
