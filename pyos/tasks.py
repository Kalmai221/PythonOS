"""PythonOS's own task list: what is running inside PythonOS, as a small operating system would show it.

The host computer's processes are not PythonOS's business. Inside PythonOS the tasks are:
  init, kernel         always there
  shell                one per signed-in user (the prompt itself)
  services             scheduler, idle watch, battery watch, memory guard, clock sync, update and market checks...
  jobs                 commands started with &
  commands, apps       whatever is running right now (the marketplace, the editor, a game, taskman itself...); each is a child of what started it
Every task has a PID, a parent, a user, a state, CPU time, memory and the command line. CPU time is real (taken from the operating system's
per-thread counters); memory is PythonOS's real memory shared out between the tasks by what they are, so the total always matches `free`.
"""
import os
import threading
import time

_lock = threading.RLock()
_tasks = {}
_next_pid = 100
_local = threading.local()
_session = {"task": None}
_state = {"tids": {}, "children": {}, "at": 0.0}

# how much of PythonOS's memory a kind of task accounts for (relative weights)
WEIGHTS = {"init": 4, "kernel": 16, "shell": 6, "service": 2, "job": 2, "command": 1, "app": 6}


class Task:
    def __init__(self, pid, ppid, name, kind, user, cmd, thread=None, stop=None, protected=False):
        self.pid, self.ppid, self.name, self.kind, self.user = pid, ppid, name, kind, user
        self.cmd = cmd or name
        self.started = time.time()
        self.ended = None
        self.thread = thread               # a Thread object (services) or None
        self.tid = threading.get_native_id() if thread is None else None
        self.stop = stop                   # how to ask a service to stop
        self.protected = protected
        self.cpu_time = 0.0
        self.extra_rss = 0                 # memory of child processes this task is waiting for
        self.job_id = None
        self.state = "running"
        self.cpu_percent = 0.0
        self._mark = (time.time(), 0.0)

    def thread_id(self):
        if self.thread is not None:
            return getattr(self.thread, "native_id", None)
        return self.tid


def _boot_tasks():
    if _tasks:
        return
    started = time.time()
    try:
        import psutil
        started = psutil.Process(os.getpid()).create_time()
    except Exception:
        pass
    for pid, name, cmd in ((1, "init", "pyos-init"), (2, "kernel", "pyos-kernel")):
        task = Task(pid, 0 if pid == 1 else 1, name, name, "root", cmd, protected=True)
        task.started = started
        task.tid = threading.main_thread().native_id
        _tasks[pid] = task


def _make(name, kind, user, cmd, parent, thread=None, stop=None, protected=False):
    global _next_pid
    with _lock:
        _boot_tasks()
        pid = _next_pid
        _next_pid += 1
        if parent is None:
            parent = _tasks[1]
        task = Task(pid, parent.pid, name, kind, user, cmd, thread, stop, protected)
        _tasks[pid] = task
        return task


def _stack():
    if not hasattr(_local, "stack"):
        _local.stack = []
    return _local.stack


def current():
    stack = _stack()
    return stack[-1] if stack else (_session["task"] or None)


def start_session(user, tty="tty1"):
    """The shell for a signed-in user. Returns its task."""
    task = _make("shell", "shell", user, f"-pyos ({user})", None)
    task.cmd = f"-pyos ({user}) on {tty}"
    _session["task"] = task
    return task


def end_session(task):
    end(task)
    with _lock:
        for other in [t for t in _tasks.values() if t.kind in ("service", "job") and t.user == task.user and t.pid != task.pid]:
            if other.kind == "service":
                end(other)
    if _session["task"] is task:
        _session["task"] = None


def service(name, thread, user=None, stop=None, cmd=None):
    """A background service backed by a thread. It disappears from the list when its thread ends."""
    parent = _session["task"]
    return _make(name, "service", user or "root", cmd or f"pyos-{name}", parent, thread=thread, stop=stop)


def start_job(job_id, command, user):
    """A background job, called from the job's own thread."""
    task = _make("job", "job", user or "root", command, _session["task"])
    task.job_id = job_id
    _stack().append(task)
    return task


def end(task):
    with _lock:
        _sample()
        task.ended = time.time()
        _tasks.pop(task.pid, None)
    stack = _stack()
    if task in stack:
        stack.remove(task)


class running:
    """with tasks.running("marketplace", "app", user, "run marketplace"): ... - a task for as long as the block runs."""

    def __init__(self, name, kind="command", user=None, cmd=None):
        self.name, self.kind, self.user, self.cmd = name, kind, user, cmd
        self.task = None

    def __enter__(self):
        try:
            _sample()
            self.task = _make(self.name, self.kind, self.user or "root", self.cmd, current())
            _stack().append(self.task)
        except Exception:
            self.task = None
        return self.task

    def __exit__(self, *exc):
        if self.task is not None:
            try:
                end(self.task)
            except Exception:
                pass
        return False


# ----------------------------------------------------------------------------------------- measuring
def _innermost(tid):
    best = None
    for task in _tasks.values():
        if task.thread_id() == tid and task.kind != "init" and task.kind != "kernel":
            if best is None or task.pid > best.pid:
                best = task
    return best or _tasks.get(2)


def _sample():
    """Hand out the CPU time used since the last sample to the task that was running on each thread."""
    try:
        import psutil
        me = psutil.Process(os.getpid())
        with _lock:
            _boot_tasks()
            now = time.time()
            for t in me.threads():
                total = t.user_time + t.system_time
                delta = total - _state["tids"].get(t.id, total)
                _state["tids"][t.id] = total
                if delta > 0:
                    owner = _innermost(t.id)
                    if owner:
                        owner.cpu_time += delta
            main_owner = _innermost(threading.main_thread().native_id)
            for child in me.children(recursive=True):
                try:
                    times = child.cpu_times()
                    total = times.user + times.system
                except psutil.Error:
                    continue
                delta = total - _state["children"].get(child.pid, total)
                _state["children"][child.pid] = total
                if delta > 0 and main_owner:
                    main_owner.cpu_time += delta
            _state["at"] = now
    except Exception:
        pass


def _prune():
    with _lock:
        for pid in [p for p, t in _tasks.items() if t.thread is not None and not t.thread.is_alive()]:
            _tasks.pop(pid, None)


def _memory():
    """Real RSS shared between the tasks. Returns {pid: bytes}."""
    try:
        import psutil
        me = psutil.Process(os.getpid())
        own = me.memory_info().rss
        children = {}
        main_owner = _innermost(threading.main_thread().native_id)
        for child in me.children(recursive=True):
            try:
                children[child.pid] = child.memory_info().rss
            except psutil.Error:
                continue
    except Exception:
        return {}
    extra = sum(children.values())
    for task in _tasks.values():
        task.extra_rss = 0
    if main_owner is not None:
        main_owner.extra_rss = extra
    tasks = list(_tasks.values())
    weight = sum(WEIGHTS.get(t.kind, 1) for t in tasks) or 1
    return {t.pid: int(own * WEIGHTS.get(t.kind, 1) / weight) + t.extra_rss for t in tasks}


def listing(user=None, everyone=True):
    """Rows for taskman and ps: every task (or only `user`'s and the system's when everyone is False)."""
    _prune()
    _sample()
    with _lock:
        _boot_tasks()
        memory = _memory()
        now = time.time()
        try:
            from pyos import resources
            budget = resources.budget()
        except Exception:
            budget = 0
        rows = []
        for task in sorted(_tasks.values(), key=lambda t: t.pid):
            if not everyone and task.user not in (user, "root"):
                continue
            mark_t, mark_cpu = task._mark
            if now - mark_t >= 1.0:
                task.cpu_percent = max(0.0, (task.cpu_time - mark_cpu) / (now - mark_t) * 100.0)
                task._mark = (now, task.cpu_time)
            task.state = "running" if _is_busy(task) else "sleeping"
            rss = memory.get(task.pid, 0)
            rows.append({"pid": task.pid, "ppid": task.ppid, "name": task.name, "kind": task.kind, "user": task.user, "state": task.state,
                         "cpu_percent": task.cpu_percent, "cpu_time": task.cpu_time, "rss": rss,
                         "memory_percent": rss * 100.0 / budget if budget else 0.0, "started": task.started, "cmd": task.cmd,
                         "protected": task.protected})
        return rows


def _is_busy(task):
    if task.kind in ("init", "kernel", "shell"):
        return task is current() or task.kind == "shell" and not _has_children(task)
    return task is current() or task.kind in ("app", "command", "job") and not _has_children(task)


def _has_children(task):
    return any(t.ppid == task.pid and t.kind in ("app", "command") for t in _tasks.values())


def summary(rows=None):
    rows = rows if rows is not None else listing()
    return {"total": len(rows), "running": sum(1 for r in rows if r["state"] == "running"),
            "sleeping": sum(1 for r in rows if r["state"] == "sleeping")}


def stop(pid, user, admin=False):
    """Stop a task the way a system would: a job is cancelled, a service is asked to stop. Returns (ok, message)."""
    with _lock:
        task = _tasks.get(pid)
    if task is None:
        return False, f"no such task: {pid}"
    if task.protected:
        return False, f"{task.name} ({pid}) is part of the system and cannot be stopped"
    if task.user not in (user, "root") and not admin:
        return False, f"task {pid} belongs to {task.user}"
    if task.kind == "job" and task.job_id is not None:
        from pyos import jobs
        if jobs.cancel(task.job_id):
            return True, f"asked job {task.job_id} ({task.cmd}) to stop"
        return False, f"job {task.job_id} is not running"
    if task.kind == "service":
        if not admin:
            return False, f"stopping the {task.name} service needs an administrator"
        if task.stop is None:
            return False, f"the {task.name} service cannot be stopped from here"
        task.stop()
        return True, f"stopped the {task.name} service"
    if task.kind == "shell":
        return False, "that is your shell; use logout"
    return False, f"{task.name} is running in front of you; close it from its own window (q, Ctrl+C)"
