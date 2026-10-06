"""The PythonOS Setup Wizard window (tkinter): detects the computer, asks what you want, downloads the right file, does the next step."""
import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk

import flashgui
import flashlib as flash
import wizardlib as wiz
import wizardtheme as look


class Wizard(tk.Tk):
    def __init__(self, goal=None):
        super().__init__()
        self.title("PythonOS Setup")
        self.geometry("760x700")
        self.minsize(700, 640)
        self.theme = look.Theme()
        look.apply(self, self.theme)
        self.env = None
        self.release = None
        self.history = []
        self.events = queue.Queue()
        self.goal = tk.StringVar(value=goal or "install")
        self.software = tk.StringVar(value="virtualbox")
        self.phone = tk.StringVar(value="universal")
        self.target = tk.StringVar(value="this")
        self.minimal = tk.BooleanVar(value=False)
        self.folder = tk.StringVar(value=wiz.default_folder())
        self.auto = tk.BooleanVar(value=True)
        self.pick = tk.StringVar(value="")
        self.plan = None
        self.result = None
        self.page_frame = None
        self.header = look.Header(self, self.theme)
        self.header.pack(fill="x")
        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True, padx=26, pady=(14, 6))
        nav = ttk.Frame(self)
        nav.pack(fill="x", padx=26, pady=(4, 18))
        self.back_button = look.button(nav, self.theme, "Back", self.back)
        self.back_button.pack(side="left")
        look.button(nav, self.theme, "Close", self.destroy).pack(side="right")
        self.next_button = look.button(nav, self.theme, "Next", self.next, primary=True)
        self.next_button.pack(side="right", padx=10)
        self.show("loading")
        threading.Thread(target=self._load, daemon=True).start()
        self.after(100, self._poll)

    # ------------------------------------------------------------------------------------------ loading
    def _load(self):
        try:
            env = wiz.detect_environment()
            self.events.put(("env", env))
            self.events.put(("release", wiz.fetch_release()))
        except Exception as e:                                       # noqa: BLE001 - any failure is shown on the screen
            self.events.put(("failed", f"{type(e).__name__}: {e}"))

    def _poll(self):
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "env":
                    self.env = value
                elif kind == "release":
                    self.release = value
                    if self.current == "loading":
                        self.show("goal")
                elif kind == "failed":
                    if self.current == "loading":
                        self.show("failed", message=value)
                elif kind == "progress":
                    self._progress(*value)
                elif kind == "finished":
                    self.result = value
                    self.show("done")
        except queue.Empty:
            pass
        self.after(100, self._poll)

    # ------------------------------------------------------------------------------------------ navigation
    current = ""

    def sequence(self):
        """The pages of this journey, in order, for the dots in the header."""
        goal = self.goal.get()
        middle = {"vm": ["software"], "android": ["phone"], "usb": ["usb"], "download": ["files"]}.get(goal, [])
        tail = [] if goal == "usb" else ["review", "progress", "done"]
        return ["goal"] + middle + tail

    def show(self, page, remember=True, **options):
        if remember and self.current and self.current not in ("loading", "progress"):
            self.history.append(self.current)
        self.current = page
        if self.page_frame is not None:
            self.page_frame.destroy()
        frame = ttk.Frame(self.body)
        frame.pack(fill="both", expand=True)
        self.page_frame = frame
        order = self.sequence()
        self.header.set_steps(order.index(page) + 1 if page in order else 0, len(order) if page in order else 0)
        self.back_button.configure(state="normal" if self.history and page not in ("progress", "done") else "disabled")
        self.next_button.configure(state="normal", text="Next")
        getattr(self, "_page_" + page)(frame, **options)

    def back(self):
        if self.history:
            self.show(self.history.pop(), remember=False)

    def next(self):
        page = self.current
        goal = self.goal.get()
        if page == "goal":
            self.show({"vm": "software", "android": "phone", "usb": "usb", "download": "files"}.get(goal, "review"))
        elif page in ("software", "phone", "files"):
            self.show("review")
        elif page == "review":
            self.start()
        elif page == "done":
            self.destroy()

    def _title(self, frame, text, hint=""):
        ttk.Label(frame, text=text, style="Title.TLabel", wraplength=690).pack(anchor="w", pady=(2, 2))
        if hint:
            ttk.Label(frame, text=hint, style="Muted.TLabel", wraplength=690, justify="left").pack(anchor="w", pady=(0, 10))

    def _cards(self, frame, variable, options):
        """Each option as a card. options: (value, title, detail) or (value, title, detail, tag)."""
        for option in options:
            value, title, detail = option[0], option[1], option[2]
            tag = option[3] if len(option) > 3 else ""
            compact = len(options) > 6
            look.Card(frame, self.theme, variable, value, title, detail, tag, compact=compact).pack(fill="x", pady=2 if compact else 4)

    def _text(self, frame, lines, height):
        c = self.theme.c
        box = tk.Text(frame, height=height, wrap="word", relief="flat", font=self.theme.font(10), background=c["bg"], foreground=c["text"],
                      highlightthickness=0, borderwidth=0, spacing3=7)
        box.insert("1.0", "\n".join(lines))
        box.configure(state="disabled")
        return box

    # ------------------------------------------------------------------------------------------ pages
    def _page_loading(self, frame):
        self._title(frame, "Looking at this computer and the latest release...")
        bar = ttk.Progressbar(frame, mode="indeterminate")
        bar.pack(fill="x", pady=24)
        bar.start(12)
        self.back_button.configure(state="disabled")
        self.next_button.configure(state="disabled")

    def _page_failed(self, frame, message=""):
        self._title(frame, "The latest release could not be loaded", "Check your internet connection. " + message)
        look.button(frame, self.theme, "Try again", lambda: (self.show("loading", remember=False), threading.Thread(target=self._load, daemon=True).start()),
                    primary=True).pack(anchor="w")
        look.button(frame, self.theme, "Open the releases page in the browser", lambda: __import__("webbrowser").open(wiz.RELEASES_PAGE)).pack(anchor="w", pady=8)
        self.next_button.configure(state="disabled")

    def _page_goal(self, frame):
        self._title(frame, "What do you want to do?", "This computer: " + wiz.describe_environment(self.env) + "\nLatest release: " + self.release.version)
        if self.env["note"]:
            ttk.Label(frame, text=self.env["note"], style="Warn.TLabel", wraplength=690).pack(anchor="w", pady=(0, 6))
        options = [(g, t, d, "RECOMMENDED" if g == "install" else "") for g, t, d in wiz.GOALS]
        self._cards(frame, self.goal, options)

    def _page_software(self, frame):
        self._title(frame, "Which virtual machine program?", "Programs found on this computer are marked. The wizard downloads the file that program needs.")
        options = []
        for key, title, detail in wiz.VM_SOFTWARE:
            options.append((key, title, detail, "FOUND" if key in self.env["tools"] else ""))
        found_keys = [k for k, *_ in wiz.VM_SOFTWARE if k in self.env["tools"] and k != "docker"]
        if self.software.get() not in [o[0] for o in options] or (found_keys and self.software.get() not in found_keys):
            self.software.set(found_keys[0] if found_keys else "virtualbox")
        self._cards(frame, self.software, options)
        if self.env["arch"] == "aarch64":
            ttk.Label(frame, text="This is an ARM computer: the ARM live image (ISO) is used for every program.", style="Warn.TLabel").pack(anchor="w", pady=6)

    def _page_phone(self, frame):
        self._title(frame, "What kind of Android device?")
        self._cards(frame, self.phone, [("universal", "I am not sure", "A tiny installer app (about 1 MB) finds out which one your device needs and downloads it.", "EASIEST"),
                                        ("aarch64", "A phone or tablet (almost all of them)", "The full app for ARM devices, about 25 MB."),
                                        ("x86_64", "A Chromebook or an Android emulator on a PC", "Intel / AMD processors.")])

    def _page_files(self, frame):
        self._title(frame, "Choose a file")
        names = sorted(e["name"] for e in self.release.entries if e["os"] not in ("system",))
        c = self.theme.c
        box = tk.Listbox(frame, height=14, exportselection=False, relief="flat", font=self.theme.font(10), background=c["surface"], foreground=c["text"],
                         selectbackground=c["accent"], selectforeground=c["accent_text"], highlightthickness=1, highlightbackground=c["border"])
        for name in names:
            size = self.release.size(name)
            box.insert("end", f"  {name}    {flash.human(size) if size else ''}")
        box.pack(fill="both", expand=True)
        box.bind("<<ListboxSelect>>", lambda _e: self.pick.set(names[box.curselection()[0]]) if box.curselection() else None)
        if names:
            box.selection_set(0)
            self.pick.set(names[0])

    def _page_usb(self, frame):
        arch = flash.machine_arch() if self.target.get() == "this" else self.target.get()
        flashgui.FlashFrame(frame, arch=arch, minimal=self.minimal.get(), on_close=lambda: self.show("goal", remember=False),
                            close_text="Done").pack(fill="both", expand=True)
        self.next_button.configure(state="disabled")

    def _page_review(self, frame):
        goal = self.goal.get()
        options = {"software": self.software.get(), "abi": self.phone.get()}
        self.plan = wiz.make_plan("download", [self.pick.get()], "none", []) if goal == "download" else wiz.plan_for(goal, self.env, self.release, **options)
        plan = self.plan
        self._title(frame, "Here is what will happen")
        lines = []
        for name in plan["files"]:
            size = self.release.size(name)
            lines.append(f"•  Download {name}" + (f"  ({flash.human(size)})" if size else ""))
        if plan["files"]:
            lines.append("•  Check each download against the release's SHA256SUMS (a file that does not match is deleted).")
        lines += ["•  " + line for line in plan["steps"] + plan["notes"]]
        if not plan["files"] and plan["action"] not in ("docker-run",):
            lines.insert(0, "•  Nothing can be downloaded for this choice in the latest release.")
        card = tk.Frame(frame, background=self.theme.c["surface"], highlightthickness=1, highlightbackground=self.theme.c["border"])
        card.pack(fill="x", pady=4)
        inner = self._text(card, lines, max(4, min(12, len(lines) * 2)))
        inner.configure(background=self.theme.c["surface"])
        inner.pack(fill="x", padx=14, pady=10)
        if plan["files"]:
            row = ttk.Frame(frame)
            row.pack(fill="x", pady=10)
            ttk.Label(row, text="Save to").pack(side="left")
            ttk.Entry(row, textvariable=self.folder).pack(side="left", fill="x", expand=True, padx=8)
            look.button(row, self.theme, "Browse...", self._choose_folder).pack(side="left")
        extra = {"android-apk": "adb" in self.env["tools"], "docker-run": "docker" in self.env["tools"],
                 "vm": plan.get("software") == "virtualbox" and "virtualbox" in self.env["tools"]}.get(plan["action"], False)
        if extra:
            label = {"android-apk": "Also install it on a phone connected with a cable", "docker-run": "Start it in Docker now",
                     "vm": "Also import it into VirtualBox"}[plan["action"]]
            ttk.Checkbutton(frame, text=label, variable=self.auto).pack(anchor="w", pady=4)
        ok = bool(plan["files"]) or plan["action"] == "docker-run"
        self.next_button.configure(text="Download and continue" if plan["files"] else "Continue", state="normal" if ok else "disabled")

    def _choose_folder(self):
        chosen = filedialog.askdirectory(initialdir=self.folder.get())
        if chosen:
            self.folder.set(chosen)

    def _page_progress(self, frame):
        self._title(frame, "Working...")
        self.bar = ttk.Progressbar(frame, mode="determinate", maximum=100)
        self.bar.pack(fill="x", pady=10)
        self.status = tk.StringVar(value="Starting...")
        ttk.Label(frame, textvariable=self.status, wraplength=690, style="Muted.TLabel").pack(anchor="w")
        self.back_button.configure(state="disabled")
        self.next_button.configure(state="disabled")

    def _page_done(self, frame):
        ok, lines, paths = self.result
        self._title(frame, "All done" if ok else "That did not work")
        card = tk.Frame(frame, background=self.theme.c["surface"], highlightthickness=1, highlightbackground=self.theme.c["border"])
        card.pack(fill="x", pady=4)
        box = self._text(card, lines or ["Finished."], 4)
        box.configure(background=self.theme.c["surface"])
        box.pack(fill="x", padx=14, pady=10)
        if self.plan and self.plan["action"] == "vm":
            ttk.Label(frame, text="Next", style="Title.TLabel").pack(anchor="w", pady=(10, 2))
            steps = self._text(frame, [f"{i}.  {s}" for i, s in enumerate(self.plan["steps"], 1)], 6)
            steps.pack(fill="x")
        row = ttk.Frame(frame)
        row.pack(fill="x", pady=10)
        if paths:
            look.button(row, self.theme, "Show the file", lambda: wiz.open_folder(paths[0])).pack(side="left", padx=(0, 8))
            if paths[0].endswith(".iso"):
                look.button(row, self.theme, "Write it to a USB stick...", lambda: self.show("usb")).pack(side="left")
        look.button(row, self.theme, "Start over", lambda: (self.history.clear(), self.show("goal", remember=False))).pack(side="right")
        self.next_button.configure(text="Close", state="normal")
        self.back_button.configure(state="disabled")

    # ------------------------------------------------------------------------------------------ the work
    def start(self):
        plan = self.plan
        if plan["action"] == "none" and not plan["files"]:
            return
        self.show("progress")
        auto = self.auto.get()
        folder = self.folder.get().strip() or wiz.default_folder()

        def progress(phase, done, total):
            self.events.put(("progress", (phase, done, total)))

        def say(text):
            self.events.put(("progress", ("say", 0, text)))

        def work():
            try:
                self.events.put(("finished", wiz.execute(plan, self.release, self.env, folder, progress, say, lambda _text: auto)))
            except Exception as e:                                   # noqa: BLE001
                self.events.put(("finished", (False, [f"{type(e).__name__}: {e}"], [])))

        threading.Thread(target=work, daemon=True).start()

    def _progress(self, phase, done, total):
        if phase == "say":
            self.status.set(total)
        elif total:
            self.bar["value"] = 100 * done / total
            self.status.set(f"{'Downloading' if phase == 'download' else phase.capitalize()}: {flash.human(done)} of {flash.human(total)}")


def run(goal=None):
    Wizard(goal).mainloop()
    return 0
