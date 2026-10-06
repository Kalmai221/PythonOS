"""The look of the Setup Wizard: light or dark like the system, one accent colour, cards instead of plain radio buttons, a header with the
step you are on. tkinter only (it ships with Python and is bundled into the program)."""
import platform
import subprocess
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

LIGHT = {"bg": "#f4f5f8", "surface": "#ffffff", "surface2": "#eef0f5", "text": "#16181d", "muted": "#5d6472", "border": "#d7dae3",
         "accent": "#3b78ff", "accent_hover": "#2f65dd", "accent_text": "#ffffff", "warn": "#a35a00", "ok": "#1a7f4b", "header": "#10141c"}
DARK = {"bg": "#101216", "surface": "#181b21", "surface2": "#20242c", "text": "#eceff4", "muted": "#9aa2b1", "border": "#2b303a",
        "accent": "#5b8cff", "accent_hover": "#7aa2ff", "accent_text": "#0b0f14", "warn": "#f0b44c", "ok": "#4cc38a", "header": "#0a0c10"}


def system_is_dark():
    """True when the system is set to a dark appearance (Windows apps mode, macOS dark mode, GNOME / GTK dark)."""
    system = platform.system()
    try:
        if system == "Windows":
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
                return winreg.QueryValueEx(key, "AppsUseLightTheme")[0] == 0
        if system == "Darwin":
            out = subprocess.run(["defaults", "read", "-g", "AppleInterfaceStyle"], capture_output=True, text=True, timeout=3)
            return "dark" in out.stdout.lower()
        import os
        if "dark" in os.environ.get("GTK_THEME", "").lower():
            return True
        out = subprocess.run(["gsettings", "get", "org.gnome.desktop.interface", "color-scheme"], capture_output=True, text=True, timeout=3)
        return "dark" in out.stdout.lower()
    except Exception:
        return False


class Theme:
    def __init__(self, dark=None):
        self.dark = system_is_dark() if dark is None else dark
        self.c = DARK if self.dark else LIGHT
        names = set(tkfont.families())
        base = next((f for f in ("Segoe UI", "SF Pro Text", "Helvetica Neue", "Cantarell", "Noto Sans", "DejaVu Sans") if f in names), "TkDefaultFont")
        self.family = base
        self.mono = next((f for f in ("Cascadia Mono", "Consolas", "Menlo", "DejaVu Sans Mono") if f in names), "TkFixedFont")

    def font(self, size=10, weight="normal"):
        return (self.family, size, weight)


def apply(root, theme):
    """Style the window and every ttk widget (the stick screen is built with ttk) with the theme."""
    c = theme.c
    root.configure(background=c["bg"])
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    base = theme.font(10)
    style.configure(".", background=c["bg"], foreground=c["text"], fieldbackground=c["surface"], bordercolor=c["border"], lightcolor=c["bg"],
                    darkcolor=c["bg"], troughcolor=c["surface2"], focuscolor=c["accent"], font=base)
    style.configure("TFrame", background=c["bg"])
    style.configure("TLabel", background=c["bg"], foreground=c["text"], font=base)
    style.configure("TLabelframe", background=c["bg"], bordercolor=c["border"], relief="solid")
    style.configure("TLabelframe.Label", background=c["bg"], foreground=c["muted"], font=theme.font(10, "bold"))
    style.configure("TButton", background=c["surface2"], foreground=c["text"], bordercolor=c["border"], padding=(14, 7), relief="flat", font=base)
    style.map("TButton", background=[("active", c["border"]), ("disabled", c["surface2"])], foreground=[("disabled", c["muted"])])
    style.configure("Accent.TButton", background=c["accent"], foreground=c["accent_text"], bordercolor=c["accent"], padding=(18, 8), font=theme.font(10, "bold"))
    style.map("Accent.TButton", background=[("active", c["accent_hover"]), ("disabled", c["surface2"])], foreground=[("disabled", c["muted"])])
    style.configure("TCheckbutton", background=c["bg"], foreground=c["text"], font=base)
    style.map("TCheckbutton", background=[("active", c["bg"])])
    style.configure("TRadiobutton", background=c["bg"], foreground=c["text"], font=base)
    style.map("TRadiobutton", background=[("active", c["bg"])])
    style.configure("TEntry", fieldbackground=c["surface"], foreground=c["text"], bordercolor=c["border"], padding=6)
    style.configure("TCombobox", fieldbackground=c["surface"], foreground=c["text"], background=c["surface2"], bordercolor=c["border"], padding=5,
                    arrowcolor=c["muted"])
    style.map("TCombobox", fieldbackground=[("readonly", c["surface"])], foreground=[("readonly", c["text"])])
    style.configure("Horizontal.TProgressbar", background=c["accent"], troughcolor=c["surface2"], bordercolor=c["surface2"], lightcolor=c["accent"],
                    darkcolor=c["accent"], thickness=10)
    style.configure("Treeview", background=c["surface"], fieldbackground=c["surface"], foreground=c["text"], bordercolor=c["border"], rowheight=28, font=base)
    style.configure("Treeview.Heading", background=c["surface2"], foreground=c["muted"], font=theme.font(9, "bold"), relief="flat")
    style.map("Treeview", background=[("selected", c["accent"])], foreground=[("selected", c["accent_text"])])
    style.configure("Muted.TLabel", foreground=c["muted"])
    style.configure("Warn.TLabel", foreground=c["warn"])
    style.configure("Title.TLabel", font=theme.font(15, "bold"))
    root.option_add("*TCombobox*Listbox.background", c["surface"])
    root.option_add("*TCombobox*Listbox.foreground", c["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", c["accent"])
    return style


class Header(tk.Canvas):
    """A band across the top: the mark, the name, and the steps as dots so you can see where you are."""

    def __init__(self, parent, theme, title="PythonOS Setup", height=72):
        super().__init__(parent, height=height, highlightthickness=0, background=theme.c["header"])
        self.theme, self.title_text, self.steps, self.at = theme, title, 0, 0
        self.bind("<Configure>", lambda _e: self.draw())

    def set_steps(self, at, total):
        self.at, self.steps = at, total
        self.draw()

    def draw(self):
        self.delete("all")
        width, height = self.winfo_width(), int(self["height"])
        c = self.theme.c
        accent = "#4fe3c1"
        self.create_rectangle(0, 0, width, height, fill=c["header"], outline="")
        self.create_rectangle(0, height - 3, width, height, fill=c["accent"], outline="")           # a thin accent line along the bottom
        self.create_text(26, height // 2 - 2, text=">_", fill=accent, font=(self.theme.mono, 22, "bold"), anchor="w")
        self.create_text(86, height // 2 - 2, text=self.title_text, fill="#ffffff", font=self.theme.font(17, "bold"), anchor="w")
        if self.steps:
            x = width - 28 - (self.steps - 1) * 20
            for i in range(self.steps):
                filled = i < self.at
                self.create_oval(x + i * 20 - 5, height // 2 - 7, x + i * 20 + 5, height // 2 + 3, fill=c["accent"] if filled else "", outline=c["accent"] if filled else "#5d6472", width=2)


class Card(tk.Frame):
    """A choice shown as a card: click it to choose. The chosen one has the accent colour round it."""

    def __init__(self, parent, theme, variable, value, title, detail="", tag="", compact=False):
        super().__init__(parent, background=theme.c["surface"], highlightthickness=2, cursor="hand2")
        self.theme, self.variable, self.value = theme, variable, value
        c = theme.c
        self.title = tk.Label(self, text=title, font=theme.font(11, "bold"), background=c["surface"], foreground=c["text"], anchor="w", justify="left")
        top, bottom = (5, 5) if compact else (9, 9)
        self.title.pack(fill="x", padx=14, pady=(top, 0))
        self.detail = None
        if detail:
            self.detail = tk.Label(self, text=detail, font=theme.font(9), background=c["surface"], foreground=c["muted"], anchor="w", justify="left", wraplength=600)
            self.detail.pack(fill="x", padx=14, pady=(0, bottom))
        else:
            self.title.pack_configure(pady=bottom)
        if tag:
            self.tag = tk.Label(self, text=tag, font=theme.font(8, "bold"), background=c["accent"], foreground=c["accent_text"], padx=6)
            self.tag.place(relx=1.0, x=-12, y=10, anchor="ne")
        for widget in (self, self.title, self.detail):
            if widget is not None:
                widget.bind("<Button-1>", lambda _e: self.choose())
        variable.trace_add("write", lambda *_: self.refresh())
        self.refresh()

    def choose(self):
        self.variable.set(self.value)

    def refresh(self):
        chosen = self.variable.get() == self.value
        self.configure(highlightbackground=self.theme.c["accent"] if chosen else self.theme.c["border"],
                       highlightcolor=self.theme.c["accent"])
        self.configure(background=self.theme.c["surface"])


def button(parent, theme, text, command, primary=False):
    return ttk.Button(parent, text=text, command=command, style="Accent.TButton" if primary else "TButton")
