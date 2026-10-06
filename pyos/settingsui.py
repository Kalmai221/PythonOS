"""The Settings app: every setting in one full-screen program, grouped by what it is about (prompt_toolkit).

Left: the groups (Display, System, Security, Updates, Storage, Power, Services, Apps, About). Right: the settings of the chosen group with their
values. Change one in place: Enter or Space flips an on/off setting and steps through a list of choices (Left goes back), numbers and text open
a line to type in. `r` puts the chosen setting back to its default. The same rules as `settings set` apply, and an administrator's change is
written to the admin log.
"""
import os

from . import settings

GROUPS = [
    ("display", "Display", ("language", "theme", "prompt_style", "clock_24h", "clear_screens", "auto_clear_lines", "notifications")),
    ("system", "System", ("memory_limit_mb", "app_memory_percent", "light_mode")),
    ("security", "Security", ("auto_lock_minutes", "idle_logout_minutes", "admin_reauth", "confirm_delete")),
    ("updates", "Updates", ("update_check", "market_update_check", "report_relay")),
    ("storage", "Storage", ("use_trash", "trash_days")),
    ("power", "Power", ("low_battery_percent", "critical_battery_percent")),
]
MEMORY_HINT = "MB: 512, 1024, 2048, 4096... or 0 for all of the machine's memory"


def label_of(key):
    return key.replace("_", " ").capitalize()


def show(value):
    return "on" if value is True else "off" if value is False else ("none" if value == "" else str(value))


class Row:
    """One line of the right-hand side: kind is 'setting', 'service', 'app', 'option' (an app's option) or 'info'."""

    def __init__(self, kind, label, value="", description="", key=None, extra=None):
        self.kind, self.label, self.value, self.description, self.key, self.extra = kind, label, value, description, key, extra


def setting_rows(keys):
    rows = []
    current = settings.load()
    for key in keys:
        if key not in settings.SCHEMA:
            continue
        default, allowed, description = settings.SCHEMA[key]
        mark = "" if current[key] == default else "  (changed)"
        unit = " MB" if key.endswith("_mb") and current[key] else ""
        rows.append(Row("setting", label_of(key), show(current[key]) + unit + mark, description + f"   [default: {show(default)}]", key))
    return rows


def other_keys():
    used = {k for _i, _t, keys in GROUPS for k in keys}
    return [k for k in settings.SCHEMA if k not in used]


def service_rows():
    from . import services
    rows = []
    for r in services.rows():
        value = ("running" if r["state"] == "running" else r["state"]) + ("" if r["autostart"] else ", off at sign-in")
        rows.append(Row("service", r["description"], value, f"{r['name']}: Enter switches it on or off at sign-in, t starts or stops it now (administrators)", r["name"]))
    return rows


def installed_apps_with_options():
    try:
        from programs import marketplace
        from . import appsettings
        return {pid: info for pid, info in marketplace.installed_packages().items() if appsettings.schema(info.get("meta"))}
    except Exception:
        return {}


def app_rows():
    rows = []
    for pid, info in installed_apps_with_options().items():
        from . import appsettings
        rows.append(Row("app", info["name"], f"{len(appsettings.schema(info['meta']))} option(s)", "Enter opens the options of " + info["name"], pid, info))
    return rows or [Row("info", "No installed app has options", "", "Apps can offer options; they appear here when you install one that does")]


def option_rows(pid, info, user):
    from . import appsettings
    saved = appsettings.values(pid, info["meta"], user)
    rows = []
    for entry in appsettings.schema(info["meta"]):
        mark = "" if saved[entry["key"]] == entry.get("default") else "  (changed)"
        rows.append(Row("option", entry.get("label") or label_of(entry["key"]), show(saved[entry["key"]]) + mark, f"{entry['key']}", entry["key"], entry))
    return rows


def about_rows():
    import platform
    from . import archinfo, resources, userinfo
    rows = [Row("info", "PythonOS", "", "")]
    try:
        import json
        with open("config.json", encoding="utf-8") as f:
            rows[0].value = str(json.load(f).get("version", "?"))
    except (OSError, ValueError):
        rows[0].value = "?"
    total, used, _free, percent = resources.snapshot()
    rows += [Row("info", "Signed in as", userinfo()[0] or "-", ""),
             Row("info", "Computer", f"{platform.system()} {platform.release()}, {archinfo.describe()}", ""),
             Row("info", "Memory", f"{used // resources.MB} of {total // resources.MB} MB used ({percent:.0f}%); PythonOS owns {resources.describe()}", ""),
             Row("info", "Where it runs", os.path.abspath("."), "")]
    return rows


def pages():
    out = [(gid, title, (lambda keys=keys: setting_rows(keys))) for gid, title, keys in GROUPS]
    extra = other_keys()
    if extra:
        out.append(("other", "Other", lambda: setting_rows(extra)))
    out += [("services", "Services", service_rows), ("apps", "Apps", app_rows), ("about", "About", about_rows)]
    return out


# ------------------------------------------------------------------------------------------ changing things
def apply_setting(key, text, user, role):
    """Set a setting from text (the same checks as `settings set`). Returns the new value; raises ValueError with a readable message."""
    value = settings.parse_value(key, text)
    if role == "admin":
        from . import audit
        audit.record("changed a setting", f"{key}={value}")
    settings.set(key, value)
    if key == "memory_limit_mb":
        from . import resources
        resources.apply()
    return value


def next_choice(key, step=1):
    default, allowed, _description = settings.SCHEMA[key]
    options = [True, False] if allowed is bool else list(allowed) if isinstance(allowed, tuple) else None
    if options is None:
        return None
    current = settings.get(key)
    index = options.index(current) if current in options else 0
    return options[(index + step) % len(options)]


def build(user, role, input=None, output=None):
    """The Settings app as a prompt_toolkit Application (not started)."""
    from prompt_toolkit import Application
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import ConditionalContainer, HSplit, Layout, VSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.styles import Style
    from prompt_toolkit.widgets import TextArea

    from . import services as svc
    all_pages = pages()
    state = {"page": 0, "row": 0, "focus": "rows", "message": "", "mode": None, "action": None, "prompt": "", "sub": None}

    def rows_now():
        if state["sub"]:
            pid, info = state["sub"]
            return option_rows(pid, info, user)
        return all_pages[state["page"]][2]()

    def current_row():
        rows = rows_now()
        if not rows:
            return None
        state["row"] = max(0, min(state["row"], len(rows) - 1))
        return rows[state["row"]]

    def say(text):
        state["message"] = text

    def left():
        out = []
        for index, (_gid, title, _fn) in enumerate(all_pages):
            chosen = index == state["page"]
            style = "class:pagecur" if chosen and state["focus"] == "pages" else "class:pagesel" if chosen else ""
            out.append((style, f"  {title:<16}"))
            out.append(("", "\n"))
        return out[:-1]

    def right():
        rows = rows_now()
        out = []
        if state["sub"]:
            out.append(("class:title", f" {state['sub'][1]['name']}   (Esc goes back)\n\n"))
        for index, row in enumerate(rows):
            under = index == state["row"] and state["focus"] == "rows"
            style = "class:cursor" if under else "class:changed" if "(changed)" in row.value else ""
            out.append((style, f" {row.label:<34} {row.value} "))
            out.append(("", "\n"))
        return out[:-1] if rows else [("class:dim", " (nothing here)")]

    def bottom():
        if state["mode"] == "input":
            return [("class:prompt", f" {state['prompt']} ")]
        row = current_row()
        text = state["message"] or (row.description if row else "")
        return [("class:status", f" {text} ")]

    def keyline():
        return [("class:keys", " Up/Down move   Tab switch side   Enter/Space change   Left/Right step a choice   r default   q quit ")]

    box = TextArea(height=1, multiline=False, prompt="", style="class:input")

    def ask(prompt, action, initial=""):
        state.update(mode="input", prompt=prompt, action=action)
        box.text = initial
        box.buffer.cursor_position = len(initial)
        app.layout.focus(box)

    def accept(_buffer):
        action, text = state["action"], box.text
        state.update(mode=None, action=None)
        app.layout.focus(rows_window)
        if action:
            action(text)
        return True

    box.accept_handler = accept
    normal = Condition(lambda: state["mode"] is None)
    inputting = Condition(lambda: state["mode"] == "input")
    keys = KeyBindings()

    def change(row, step=1):
        say("")
        try:
            if row.kind == "setting":
                default, allowed, _d = settings.SCHEMA[row.key]
                if allowed is bool or isinstance(allowed, tuple):
                    value = next_choice(row.key, step)
                    apply_setting(row.key, "on" if value is True else "off" if value is False else value, user, role)
                    say(f"{row.key} = {show(value)}")
                else:
                    hint = MEMORY_HINT if row.key == "memory_limit_mb" else ("an https:// address, or none" if allowed is str else "a whole number")
                    ask(f"{label_of(row.key)} ({hint}):", lambda text: _set_text(row.key, text), "" if settings.get(row.key) == "" else str(settings.get(row.key)))
            elif row.kind == "service":
                if role != "admin":
                    return say("only an administrator can change services")
                off = svc.is_disabled(row.key)
                if not off and svc.get(row.key).critical:
                    return say(f"{row.key} asks for your password before it is switched off: use  service disable {row.key}")
                svc.set_disabled(row.key, not off)
                if not off:
                    svc.stop(row.key)
                say(f"{row.key} {'will start' if off else 'is switched off'} at sign-in")
            elif row.kind == "app":
                state.update(sub=(row.key, row.extra), row=0)
            elif row.kind == "option":
                from . import appsettings
                entry = row.extra
                if entry["type"] in ("bool", "choice"):
                    options = [True, False] if entry["type"] == "bool" else list(entry["choices"])
                    saved = appsettings.values(state["sub"][0], state["sub"][1]["meta"], user)[entry["key"]]
                    nxt = options[(options.index(saved) + step) % len(options)] if saved in options else options[0]
                    appsettings.set_value(state["sub"][0], entry, "on" if nxt is True else "off" if nxt is False else nxt, user)
                    say(f"{entry['key']} = {show(nxt)}")
                else:
                    ask(f"{row.label}:", lambda text: _set_option(entry, text))
        except (ValueError, OSError) as e:
            say(str(e))

    def _set_text(key, text):
        try:
            value = apply_setting(key, text.strip() or ("none" if settings.SCHEMA[key][1] is str else text), user, role)
            say(f"{key} = {show(value)}")
        except ValueError as e:
            say(str(e))

    def _set_option(entry, text):
        from . import appsettings
        try:
            appsettings.set_value(state["sub"][0], entry, text, user)
            say(f"{entry['key']} saved")
        except ValueError as e:
            say(str(e))

    def stepable(row):
        """A row whose value goes through a short list (on/off, choices), so Left and Right can step it."""
        if row.kind == "setting":
            allowed = settings.SCHEMA[row.key][1]
            return allowed is bool or isinstance(allowed, tuple)
        return row.kind == "option" and row.extra["type"] in ("bool", "choice")

    @keys.add("q", filter=normal)
    @keys.add("escape", filter=normal, eager=True)
    def _quit(event):
        if state["sub"]:
            state.update(sub=None, row=0)
        else:
            event.app.exit()

    @keys.add("tab", filter=normal)
    def _tab(event):
        state["focus"] = "pages" if state["focus"] == "rows" else "rows"

    @keys.add("up", filter=normal)
    @keys.add("k", filter=normal)
    def _up(event):
        if state["focus"] == "pages":
            state.update(page=max(0, state["page"] - 1), row=0, sub=None)
        else:
            state["row"] = max(0, state["row"] - 1)
        say("")

    @keys.add("down", filter=normal)
    @keys.add("j", filter=normal)
    def _down(event):
        if state["focus"] == "pages":
            state.update(page=min(len(all_pages) - 1, state["page"] + 1), row=0, sub=None)
        else:
            state["row"] = min(max(0, len(rows_now()) - 1), state["row"] + 1)
        say("")

    @keys.add("enter", filter=normal)
    @keys.add("space", filter=normal)
    def _enter(event):
        if state["focus"] == "pages":
            state["focus"] = "rows"
            return
        row = current_row()
        if row:
            change(row, 1)

    @keys.add("right", filter=normal)
    @keys.add("l", filter=normal)
    def _right(event):
        if state["focus"] == "pages":
            state["focus"] = "rows"
            return
        row = current_row()
        if row and stepable(row):
            change(row, 1)

    @keys.add("left", filter=normal)
    @keys.add("h", filter=normal)
    def _left(event):
        if state["focus"] == "rows":
            row = current_row()
            if row and stepable(row):
                change(row, -1)
                return
            state["focus"] = "pages"

    @keys.add("r", filter=normal)
    def _reset(event):
        row = current_row()
        if row and row.kind == "setting":
            default = settings.SCHEMA[row.key][0]
            try:
                apply_setting(row.key, "on" if default is True else "off" if default is False else (str(default) if default != "" else "none"), user, role)
                say(f"{row.key} is back to {show(default)}")
            except ValueError as e:
                say(str(e))
        elif row and row.kind == "option":
            from . import appsettings
            appsettings.reset(state["sub"][0], row.key, user)
            say(f"{row.key} is back to its default")

    @keys.add("t", filter=normal)
    def _toggle_service(event):
        row = current_row()
        if not row or row.kind != "service":
            return
        if role != "admin":
            return say("only an administrator can change services")
        if svc.get(row.key).critical and svc.instance(row.key) is not None:
            return say("the battery monitor asks for your password: use  service stop battery-watch")
        ok, message = svc.stop(row.key) if svc.instance(row.key) is not None else svc.start(row.key, user)
        say(message)

    @keys.add("escape", filter=inputting, eager=True)
    def _cancel(event):
        state.update(mode=None, action=None)
        app.layout.focus(rows_window)

    rows_window = Window(FormattedTextControl(right, focusable=True), wrap_lines=False)
    app = Application(
        layout=Layout(HSplit([
            Window(FormattedTextControl([("class:header", " PythonOS Settings ")]), height=1, style="class:header"),
            VSplit([Window(FormattedTextControl(left), width=20), Window(width=1, char="|", style="class:dim"), rows_window]),
            ConditionalContainer(box, filter=inputting),
            Window(FormattedTextControl(bottom), height=1, style="class:status"),
            Window(FormattedTextControl(keyline), height=1, style="class:keys")]), focused_element=rows_window),
        key_bindings=keys, full_screen=True, mouse_support=False, input=input, output=output,
        style=Style.from_dict({"header": "reverse bold", "cursor": "reverse", "pagecur": "reverse", "pagesel": "bold", "changed": "fg:ansiyellow",
                               "status": "reverse", "keys": "fg:ansibrightblack", "prompt": "reverse bold", "dim": "fg:ansibrightblack", "title": "bold",
                               "input": "bold"}))
    return app


def run(user, role):
    build(user, role).run()
