"""The PythonOS Flash window (tkinter: it comes with Python and is bundled into the packaged programs)."""
import os
import platform
import queue
import subprocess
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import flashlib as lib

PHASES = {"download": "Downloading the image...", "check": "Checking the image...", "write": "Writing to the stick...",
          "verify": "Reading the stick back to check it...", "done": "Done", "error": "Stopped"}


class FlashFrame(ttk.Frame):
    """The whole "write a stick" screen. It is a frame so it can be a page of the setup wizard or fill a window of its own (App below)."""

    def __init__(self, parent, iso=None, arch=None, minimal=False, on_close=None, close_text="Quit"):
        super().__init__(parent)
        self.on_close = on_close or (lambda: self.winfo_toplevel().destroy())
        self.close_text = close_text
        self.events = queue.Queue()
        self.drives = []
        self.busy = False
        self.source = tk.StringVar(value="file" if iso else "download")
        wanted = arch or lib.machine_arch()
        self.arch = tk.StringVar(value="ARM 64-bit (aarch64)" if wanted == "aarch64" else "PC (x86_64)")
        self.minimal = tk.BooleanVar(value=bool(minimal))
        self.path = tk.StringVar(value=iso or "")
        self.verify = tk.BooleanVar(value=True)
        self.sure = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="Choose an image and a stick.")
        self._build()
        self.refresh()
        self.after(100, self._poll)

    # ------------------------------------------------------------------------------------------ layout
    def _build(self):
        pad = {"padx": 14, "pady": 6}
        ttk.Label(self, text="Make a bootable USB stick", font=("TkDefaultFont", 16, "bold")).pack(anchor="w", padx=14, pady=(10, 0))
        ttk.Label(self, text="Writes a PythonOS image to a USB stick so a computer can start from it. Everything on the stick is erased.",
                  wraplength=640).pack(anchor="w", padx=14)

        image = ttk.LabelFrame(self, text=" 1. The image ")
        image.pack(fill="x", **pad)
        row = ttk.Frame(image)
        row.pack(fill="x", padx=8, pady=4)
        ttk.Radiobutton(row, text="Download the latest PythonOS", variable=self.source, value="download", command=self._update).pack(side="left")
        self.arch_box = ttk.Combobox(row, textvariable=self.arch, values=["PC (x86_64)", "ARM 64-bit (aarch64)"], state="readonly", width=22)
        self.arch_box.pack(side="left", padx=8)
        self.minimal_box = ttk.Checkbutton(row, text="Minimal (smaller)", variable=self.minimal)
        self.minimal_box.pack(side="left")
        ttk.Label(image, text=f"For the computer that will start from the stick. Chosen for this computer ({lib.describe_machine()}); "
                              "change it if the stick is for a different kind of computer.", style="Muted.TLabel", wraplength=600).pack(anchor="w", padx=30)
        row = ttk.Frame(image)
        row.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Radiobutton(row, text="Use a file I have", variable=self.source, value="file", command=self._update).pack(side="left")
        self.entry = ttk.Entry(row, textvariable=self.path)
        self.entry.pack(side="left", fill="x", expand=True, padx=8)
        self.browse = ttk.Button(row, text="Browse...", command=self._browse)
        self.browse.pack(side="left")

        stick = ttk.LabelFrame(self, text=" 2. The USB stick ")
        stick.pack(fill="both", expand=True, **pad)
        self.tree = ttk.Treeview(stick, columns=("drive", "size", "name"), show="headings", height=5, selectmode="browse")
        for column, text, width in (("drive", "Drive", 150), ("size", "Size", 90), ("name", "Name", 360)):
            self.tree.heading(column, text=text)
            self.tree.column(column, width=width, anchor="w")
        self.tree.pack(fill="both", expand=True, padx=8, pady=(6, 2))
        self.tree.bind("<<TreeviewSelect>>", lambda _e: self._update())
        row = ttk.Frame(stick)
        row.pack(fill="x", padx=8, pady=(0, 6))
        ttk.Button(row, text="Refresh", command=self.refresh).pack(side="left")
        ttk.Label(row, text="Only USB sticks are listed, never the drive this computer runs from.", style="Muted.TLabel").pack(side="left", padx=10)

        options = ttk.Frame(self)
        options.pack(fill="x", **pad)
        ttk.Checkbutton(options, text="Read the stick back to check it afterwards (recommended)", variable=self.verify).pack(anchor="w")
        ttk.Checkbutton(options, text="I understand everything on the selected stick will be erased", variable=self.sure,
                        command=self._update).pack(anchor="w")

        buttons = ttk.Frame(self)
        buttons.pack(fill="x", padx=14, pady=4)
        self.go = ttk.Button(buttons, text="Write to the stick", command=self.start)
        self.go.pack(side="left")
        ttk.Button(buttons, text=self.close_text, command=self.on_close).pack(side="right")

        self.bar = ttk.Progressbar(self, mode="determinate", maximum=100)
        self.bar.pack(fill="x", padx=14, pady=(8, 2))
        ttk.Label(self, textvariable=self.status, wraplength=640).pack(anchor="w", padx=14)
        self._update()

    def _update(self):
        download = self.source.get() == "download"
        self.arch_box.configure(state="readonly" if download and not self.busy else "disabled")
        self.minimal_box.configure(state="normal" if download and not self.busy else "disabled")
        self.entry.configure(state="disabled" if download or self.busy else "normal")
        self.browse.configure(state="disabled" if download or self.busy else "normal")
        ready = bool(self.tree.selection()) and self.sure.get() and not self.busy and (download or bool(self.path.get().strip()))
        self.go.configure(state="normal" if ready else "disabled")

    def _browse(self):
        chosen = filedialog.askopenfilename(title="Choose a PythonOS image", filetypes=[("Disc images", "*.iso"), ("All files", "*.*")])
        if chosen:
            self.path.set(chosen)
            self._update()

    def refresh(self):
        try:
            self.drives = lib.list_drives()
        except (OSError, SystemExit) as e:
            self.drives = []
            self.status.set(f"Could not list the drives: {e}")
        self.tree.delete(*self.tree.get_children())
        for index, d in enumerate(self.drives):
            self.tree.insert("", "end", iid=str(index), values=(d["id"], lib.human(d["size"]), d["name"]))
        if not self.drives:
            self.status.set("No USB stick found. Plug one in (at least 1 GB), then press Refresh.")
        self._update()

    # ------------------------------------------------------------------------------------------ the work
    def start(self):
        selected = self.tree.selection()
        if not selected:
            return
        drive = self.drives[int(selected[0])]
        iso, expected = None, None
        if self.source.get() == "file":
            iso = self.path.get().strip()
            if not os.path.isfile(iso):
                messagebox.showerror("PythonOS Flash", "That image file does not exist.")
                return
            expected = lib.expected_hash(iso)
            if expected is None and not messagebox.askyesno(
                    "PythonOS Flash", "There is no SHA256SUMS file next to the image, so it cannot be checked.\n\nWrite it anyway?"):
                return
        if not messagebox.askokcancel("Erase the stick?", f"Everything on\n\n{drive['id']}   {lib.human(drive['size'])}   {drive['name']}\n\n"
                                      "will be erased. This cannot be undone.", icon="warning"):
            return
        self.busy = True
        self._update()
        self.bar["value"] = 0
        threading.Thread(target=self._work, args=(drive, iso, expected, self.verify.get()), daemon=True).start()

    def _emit(self, phase, done=0, total=0, message=""):
        self.events.put((phase, done, total, message))

    def _work(self, drive, iso, expected, verify):
        try:
            if iso is None:                                           # download the latest release
                arch = "aarch64" if "aarch64" in self.arch.get() else "x86_64"
                self._emit("download", 0, 1, "Looking up the latest release...")
                sums = lib.latest_sums()
                name = lib.pick_iso(sums, arch, self.minimal.get())
                if not name:
                    return self._emit("error", message=f"The latest release has no {'minimal ' if self.minimal.get() else ''}image for {arch}.")
                iso = lib.download_iso(name, sums[name], progress=self._emit)
            elif expected is not None:
                if lib.sha256_file(iso, self._emit) != expected:
                    return self._emit("error", message="The image does not match its checksum: it is damaged or has been changed. Nothing was written.")
            self._write(drive, iso, verify)
        except (OSError, ValueError) as e:
            self._emit("error", message=str(e))

    def _write(self, drive, iso, verify):
        if lib.is_admin():                                            # already an administrator (or root): write directly
            ok, message = lib.flash(iso, drive, verify, self._emit)
            return self._emit("done" if ok else "error", message=message)
        progress_file = tempfile.NamedTemporaryFile(prefix="pythonos-flash-", suffix=".log", delete=False).name
        command = lib.self_command() + ["--worker", "--iso", iso, "--device", drive["id"], "--progress-file", progress_file]
        if not verify:
            command.append("--no-verify")
        self._emit("write", 0, 1, "Asking for administrator rights...")
        outcome = {}
        runner = threading.Thread(target=lambda: outcome.update(code=lib.run_privileged(command, hidden=True)), daemon=True)
        runner.start()
        offset, finished = 0, False
        while True:
            events, offset = lib.read_progress(progress_file, offset)
            for phase, done, total, message in events:
                self._emit(phase, done, total, message)
                finished = finished or phase in ("done", "error")
            if finished:
                break
            if not runner.is_alive():
                events, offset = lib.read_progress(progress_file, offset)
                for phase, done, total, message in events:
                    self._emit(phase, done, total, message)
                    finished = finished or phase in ("done", "error")
                if not finished:
                    code = outcome.get("code")
                    self._emit("error", message=("No way to ask for administrator rights was found (needs pkexec or sudo): run the wizard in a terminal "
                                                 "with sudo ./wizard.sh --cli" if code == 126 else
                                                 "Administrator rights were not given, or the write did not start. Nothing was changed."))
                break
            threading.Event().wait(0.2)
        try:
            os.remove(progress_file)
        except OSError:
            pass

    def _poll(self):
        try:
            while True:
                phase, done, total, message = self.events.get_nowait()
                text = PHASES.get(phase, phase)
                if phase in ("done", "error"):
                    self.busy = False
                    self.status.set(message or text)
                    self.bar["value"] = 100 if phase == "done" else self.bar["value"]
                    (messagebox.showinfo if phase == "done" else messagebox.showerror)("PythonOS Flash", message or text)
                    self._update()
                else:
                    self.status.set(message or (f"{text} {lib.human(done)} of {lib.human(total)}" if total else text))
                    if total:
                        self.bar["value"] = 100 * done / total
        except queue.Empty:
            pass
        self.after(100, self._poll)


class App(tk.Tk):
    """The stand-alone Flash window (PythonOS-Wizard --flash)."""

    def __init__(self, iso=None):
        super().__init__()
        self.title("PythonOS Flash")
        self.geometry("680x660")
        self.minsize(620, 620)
        try:
            import wizardtheme
            wizardtheme.apply(self, wizardtheme.Theme())
        except Exception:
            pass
        FlashFrame(self, iso=iso).pack(fill="both", expand=True)


def run(iso=None):
    App(iso).mainloop()
    return 0
