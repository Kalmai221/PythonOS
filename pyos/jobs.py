# pyos/jobs.py - background jobs ("some_command &")
#
# A job runs a command line in its own thread with its output captured, so it never scribbles over
# the prompt. When it finishes the user gets a notification and can read the output with `fg <id>`.
# Python cannot kill a running thread, so cancelling is cooperative: it sets a flag that long-running
# commands (sleep, the scheduler, ...) check with cancelled(). Jobs are meant for non-interactive,
# finite commands - a job that waits for typed input will simply stay running.
import threading
import time

from . import notify, stdio

_jobs = {}
_lock = threading.Lock()
_next_id = 1
_local = threading.local()


class Job:
    def __init__(self, job_id, command, user):
        self.id = job_id
        self.command = command
        self.user = user
        self.status = "running"      # running | done | failed | cancelled
        self.code = None
        self.started = time.time()
        self.ended = None
        self.output = ""
        self.cancel_event = threading.Event()
        self.thread = None

    def elapsed(self):
        return (self.ended or time.time()) - self.started


def start(command, runner, user=None):
    """Start `runner()` (returns an exit status) in a thread. Returns the Job."""
    global _next_id
    with _lock:
        job = Job(_next_id, command, user)
        _jobs[job.id] = job
        _next_id += 1

    def work():
        _local.job = job
        try:
            with stdio.capture() as buf:
                try:
                    job.code = runner()
                except BaseException as e:  # a crashing job must not take the shell down
                    buf.write(f"job crashed: {e}\n")
                    job.code = 1
                job.output = buf.getvalue()
        finally:
            job.ended = time.time()
            if job.cancel_event.is_set():
                job.status = "cancelled"
            else:
                job.status = "done" if not job.code else "failed"
            notify.notify(f"[{job.id}] {job.status}: {job.command}",
                          title="Background job", level="info" if job.status == "done" else "warn", user=job.user)

    job.thread = threading.Thread(target=work, name=f"job-{job.id}", daemon=True)
    job.thread.start()
    return job


def current():
    """The Job the calling thread is running, or None in the foreground."""
    return getattr(_local, "job", None)


def cancelled():
    """True if the job running in this thread was asked to stop. Long-running commands should poll this."""
    job = current()
    return bool(job and job.cancel_event.is_set())


def get(job_id):
    return _jobs.get(job_id)


def all_jobs(user=None):
    with _lock:
        jobs = list(_jobs.values())
    return [j for j in jobs if user is None or j.user in (None, user)]


def cancel(job_id):
    """Ask a job to stop. Returns False if there is no such running job."""
    job = _jobs.get(job_id)
    if not job or job.status != "running":
        return False
    job.cancel_event.set()
    return True


def forget_finished(user=None):
    with _lock:
        for job_id in [j.id for j in _jobs.values() if j.status != "running" and (user is None or j.user in (None, user))]:
            del _jobs[job_id]
