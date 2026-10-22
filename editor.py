#!/usr/bin/env python3
"""FIFA 17 Player Editor -- a Tkinter GUI for editing players in a FIFA 17 database.

Usage:  python3 editor.py [database.db] [meta.XML]
"""

import csv
import datetime
import json
import os
import random
import shutil
import sys
import tkinter as tk
import unicodedata
from tkinter import colorchooser, filedialog, messagebox, ttk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import crests  # noqa: E402
import fifadb  # noqa: E402

SEASON_START = datetime.date(2016, 7, 1)  # FIFA 17 career start, used for ages
# Saving puts the DB, its meta XML, language files and this list of what was made in
# the editor into one folder, so a restart still knows which players are yours.
PROJECT_FILE = "editor_project.json"
SETTINGS_PATH = os.path.join(os.path.expanduser("~"), ".config", "fifa17_editor.json")


def project_dir_for(dbpath):
    """The folder the first save of a loose database creates next to it."""
    stem = os.path.splitext(os.path.basename(dbpath))[0]
    return os.path.join(os.path.dirname(os.path.abspath(dbpath)), f"{stem} project")


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None

POSITIONS = ["GK", "SW", "RWB", "RB", "RCB", "CB", "LCB", "LB", "LWB", "RDM", "CDM",
             "LDM", "RM", "RCM", "CM", "LCM", "LM", "RAM", "CAM", "LAM", "RF", "CF",
             "LF", "RW", "RS", "ST", "LS", "LW"]

ATTRIBUTE_GROUPS = [
    ("Physical", ["acceleration", "sprintspeed", "agility", "balance", "reactions",
                         "jumping", "stamina", "strength", "aggression"]),
    ("Attacking", ["crossing", "finishing", "headingaccuracy", "shortpassing", "volleys",
                   "shotpower", "longshots", "positioning"]),
    ("Skill", ["dribbling", "curve", "freekickaccuracy", "longpassing", "ballcontrol",
               "vision", "penalties", "composure"]),
    ("Defending", ["marking", "standingtackle", "slidingtackle", "interceptions"]),
    ("GK", ["gkdiving", "gkhandling", "gkkicking", "gkpositioning", "gkreflexes"]),
]

LABELS = {
    "sprintspeed": "Sprint Speed", "headingaccuracy": "Heading Accuracy",
    "shortpassing": "Short Passing", "shotpower": "Shot Power", "longshots": "Long Shots",
    "freekickaccuracy": "Free Kick Accuracy", "longpassing": "Long Passing",
    "ballcontrol": "Ball Control", "standingtackle": "Standing Tackle",
    "slidingtackle": "Sliding Tackle", "gkdiving": "GK Diving", "gkhandling": "GK Handling",
    "gkkicking": "GK Kicking", "gkpositioning": "GK Positioning", "gkreflexes": "GK Reflexes",
    "overallrating": "Overall", "potential": "Potential",
    "weakfootabilitytypecode": "Weak Foot", "skillmoves": "Skill Moves",
    "attackingworkrate": "Attacking Work Rate", "defensiveworkrate": "Defensive Work Rate",
    "internationalrep": "International Reputation", "preferredfoot": "Preferred Foot",
    "preferredposition1": "Main Position", "preferredposition2": "Alt. Position 2",
    "preferredposition3": "Alt. Position 3", "preferredposition4": "Alt. Position 4",
    "height": "Height (cm)", "weight": "Weight (kg)", "birthdate": "Birth Date",
    "nationality": "Nationality", "contractvaliduntil": "Contract Until",
    "playerjointeamdate": "Joined Team", "isretiring": "Retiring", "gender": "Gender",
    "emotion": "Emotion", "jerseynumber": "Jersey Number", "position": "Team Position",
    "teamid": "Club", "teamname": "Name", "leagueid": "League",
    "attackrating": "Attack", "midfieldrating": "Midfield", "defenserating": "Defence",
    "domesticprestige": "Domestic Prestige", "internationalprestige": "International Prestige",
    "transferbudget": "Transfer Budget", "clubworth": "Club Worth",
    "foundationyear": "Founded", "teamstadiumcapacity": "Stadium Capacity",
    "stadiumname": "Stadium Name",
    "headclasscode": "Face type", "hashighqualityhead": "High-quality head",
    "headtypecode": "Head shape", "skintonecode": "Skin tone", "skintypecode": "Skin type",
    "eyecolorcode": "Eye colour", "eyebrowcode": "Eyebrows", "hairtypecode": "Hairstyle",
    "haircolorcode": "Hair colour", "facialhairtypecode": "Beard",
    "facialhaircolorcode": "Beard colour", "sideburnscode": "Sideburns",
    "bodytypecode": "Body type", "shoetypecode": "Boots", "shoedesigncode": "Boot design",
    "shoecolorcode1": "Boot colour 1", "shoecolorcode2": "Boot colour 2",
    "gkglovetypecode": "GK gloves", "jerseystylecode": "Shirt style",
    "jerseysleevelengthcode": "Sleeve length", "jerseyfit": "Shirt fit",
    "socklengthcode": "Sock length",
    **{f"accessorycode{i}": f"Accessory {i}" for i in range(1, 5)},
    **{f"accessorycolourcode{i}": f"Accessory {i} colour" for i in range(1, 5)},
}

TRAITS = {
    "trait1": ["Inflexibility", "Long Throw-in", "Power Free-Kick", "Diver", "Injury Prone",
               "Injury Free", "Avoids Weaker Foot", "Dives Into Tackles",
               "Beats Offside Trap", "Selfish", "Leadership", "Argues With Officials",
               "Early Crosser", "Finesse Shot", "Flair", "Long Passer", "Long Shot Taker",
               "Speed Dribbler", "Playmaker", "GK Up For Corners", "Puncher",
               "GK Long Throw", "Power Header", "GK One On One", "Giant Throw-in",
               "Outside Foot Shot", "Crowd Favourite", "Swerve Pass", "Second Wind",
               "Acrobatic Clearance"],
    "trait2": ["Skilled Dribbling", "Flair Passes", "Fancy Flicks", "Stutter Penalty",
               "Chipped Penalty", "Bicycle Kicks", "Diving Header", "Driven Pass",
               "GK Flat Kick", "One Club Player", "Team Player", "Chip Shot",
               "Technical Dribbler", "Rushes Out Of Goal", "Backs Into Player",
               "Set Play Specialist", "Takes Finesse Free Kicks", "Target Forward",
               "Cautious With Crosses", "Comes For Crosses"],
}

CHOICES = {
    "preferredfoot": {1: "Right", 2: "Left"},
    "attackingworkrate": {0: "Medium", 1: "High", 2: "Low"},
    "defensiveworkrate": {0: "Medium", 1: "High", 2: "Low"},
    "skillmoves": {i: "★" * (i + 1) for i in range(5)},
    "weakfootabilitytypecode": {i: "★" * i for i in range(1, 6)},
    "internationalrep": {i: "★" * i for i in range(1, 6)},
    "gender": {0: "Male", 1: "Female"},
    "isretiring": {0: "No", 1: "Yes"},
    "headclasscode": {0: "Real face (scanned)", 1: "Generic face", 2: "Other (2)"},
    "hashighqualityhead": {0: "No", 1: "Yes"},
}
for _p in ("preferredposition1", "preferredposition2", "preferredposition3",
           "preferredposition4"):
    CHOICES[_p] = {**({-1: "None"} if _p != "preferredposition1" else {}),
                   **dict(enumerate(POSITIONS))}


# Appearance tab. Code meanings aren't documented, so each code shows players
# who use the same value instead of a name.
LOOK_GROUPS = [
    ("Face", ["headtypecode", "skintonecode", "skintypecode", "eyecolorcode",
              "eyebrowcode"]),
    ("Hair & beard", ["hairtypecode", "haircolorcode", "facialhairtypecode",
                      "facialhaircolorcode", "sideburnscode"]),
    ("Body", ["bodytypecode"]),
    ("Accessories", [f"accessory{k}code{i}" for i in range(1, 5)
                     for k in ("", "colour")]),
    ("Boots & gloves", ["shoetypecode", "shoedesigncode", "shoecolorcode1",
                        "shoecolorcode2", "gkglovetypecode"]),
    ("Kit style", ["jerseystylecode", "jerseysleevelengthcode", "jerseyfit",
                   "socklengthcode"]),
]
# Only visible on generic faces (a scanned head brings its own), so their examples
# come from generic-face players.
HEAD_LOOK = {n for g, names in LOOK_GROUPS if g in ("Face", "Hair & beard") for n in names}


def label_for(name):
    return LABELS.get(name, name.capitalize())


def fold(text):
    """Lower-case and strip accents so 'muller' finds 'Müller'."""
    norm = unicodedata.normalize("NFKD", text)
    return "".join(c for c in norm if not unicodedata.combining(c)).lower()


def rating_color(v):
    if v >= 80:
        return "#2e9e44"
    if v >= 70:
        return "#8bb92d"
    if v >= 60:
        return "#d9a400"
    if v >= 50:
        return "#e07b00"
    return "#d0352b"


# ---------------------------------------------------------------------------
# Bound controls: each one edits one field of one table row
# ---------------------------------------------------------------------------

class Bound:
    """Base for a widget bound to (table, field) of the current player's row."""

    def __init__(self, app, table, field):
        self.app = app
        self.table = table
        self.field = table.by_name[field]

    def row(self):
        return self.app.row_for(self.table)

    def value(self):
        r = self.row()
        return None if r is None else self.table.get(r, self.field)

    def commit(self, value):
        r = self.row()
        if r is None:
            return
        try:
            if self.table.get(r, self.field) == value:
                return
            self.table.set(r, self.field, value)
        except fifadb.DBError as exc:
            messagebox.showerror("Invalid value", str(exc))
            self.app.refresh_controls()
            return
        self.app.on_edited(self)


class AttrSlider(Bound):
    def __init__(self, app, parent, table, field, gridrow):
        super().__init__(app, table, field)
        self.var = tk.IntVar()
        ttk.Label(parent, text=label_for(self.field.name)).grid(
            row=gridrow, column=0, sticky="w", padx=(0, 10), pady=2)
        self.scale = ttk.Scale(parent, from_=self.field.low, to=self.field.high,
                               orient="horizontal", length=220,
                               command=self._on_scale)
        self.scale.grid(row=gridrow, column=1, sticky="ew", pady=2)
        self.spin = ttk.Spinbox(parent, from_=self.field.low, to=self.field.high,
                                width=5, textvariable=self.var, command=self._on_spin)
        self.spin.grid(row=gridrow, column=2, padx=6)
        self.spin.bind("<Return>", lambda e: self._on_spin())
        self.spin.bind("<FocusOut>", lambda e: self._on_spin())
        self.badge = tk.Label(parent, width=4, fg="white", font=("TkDefaultFont", 9, "bold"))
        self.badge.grid(row=gridrow, column=3)

    def load(self):
        v = self.value()
        if v is None:
            return
        self.var.set(v)
        self.scale.set(v)
        self._paint(v)

    def _paint(self, v):
        self.badge.configure(text=str(v), bg=rating_color(v))

    def _on_scale(self, raw):
        if self.app.loading:
            return
        v = int(round(float(raw)))
        self.var.set(v)
        self._paint(v)
        self.commit(v)

    def _on_spin(self):
        if self.app.loading:
            return
        try:
            v = int(self.spin.get())
        except ValueError:
            self.load()
            return
        v = max(self.field.low, min(self.field.high, v))
        self.app.loading = True
        self.scale.set(v)
        self.app.loading = False
        self._paint(v)
        self.commit(v)


class Choice(Bound):
    def __init__(self, app, parent, table, field, gridrow, options):
        super().__init__(app, table, field)
        self.options = options  # value -> text
        self.reverse = {t: v for v, t in options.items()}
        ttk.Label(parent, text=label_for(self.field.name)).grid(
            row=gridrow, column=0, sticky="w", padx=(0, 10), pady=2)
        self.combo = ttk.Combobox(parent, values=list(options.values()), state="readonly",
                                  width=28)
        self.combo.grid(row=gridrow, column=1, sticky="w", pady=2)
        self.combo.bind("<<ComboboxSelected>>", self._on_select)

    def load(self):
        v = self.value()
        if v is None:
            return
        self.combo.set(self.options.get(v, f"Unknown ({v})"))

    def _on_select(self, _):
        if not self.app.loading and self.combo.get() in self.reverse:
            self.commit(self.reverse[self.combo.get()])


class NumberEntry(Bound):
    def __init__(self, app, parent, table, field, gridrow, label=None):
        super().__init__(app, table, field)
        f = self.field
        ttk.Label(parent, text=label or label_for(f.name)).grid(
            row=gridrow, column=0, sticky="w", padx=(0, 10), pady=2)
        self.var = tk.StringVar()
        if f.type == fifadb.TYPE_INT:
            self.entry = ttk.Spinbox(parent, from_=f.low, to=f.high, textvariable=self.var,
                                     width=12, command=self._on_commit)
        else:
            width = 30 if f.type == fifadb.TYPE_STRING else 12
            self.entry = ttk.Entry(parent, textvariable=self.var, width=width)
        self.entry.grid(row=gridrow, column=1, sticky="w", pady=2)
        hint = ""
        if f.type == fifadb.TYPE_INT:
            hint = f"{f.low} – {f.high}"
        elif f.type == fifadb.TYPE_DATE:
            hint = "YYYY-MM-DD"
        elif f.type == fifadb.TYPE_STRING:
            hint = f"max {f.depth // 8 - 1} chars"
        ttk.Label(parent, text=hint, foreground="gray").grid(
            row=gridrow, column=2, sticky="w", padx=6)
        self.entry.bind("<Return>", lambda e: self._on_commit())
        self.entry.bind("<FocusOut>", lambda e: self._on_commit())

    def load(self):
        v = self.value()
        if v is None:
            return
        if self.field.type == fifadb.TYPE_DATE:
            try:
                v = fifadb.days_to_date(v).isoformat()
            except (OverflowError, ValueError):
                pass
        elif self.field.type == fifadb.TYPE_REAL:
            v = f"{v:g}"
        self.var.set(str(v))

    def _on_commit(self):
        if self.app.loading or self.row() is None:
            return
        text = self.var.get().strip()
        try:
            if self.field.type == fifadb.TYPE_DATE:
                value = fifadb.date_to_days(datetime.date.fromisoformat(text))
            elif self.field.type == fifadb.TYPE_INT:
                value = int(text)
            elif self.field.type == fifadb.TYPE_REAL:
                value = float(text)
            else:
                value = text
        except ValueError:
            messagebox.showerror("Invalid value",
                                 f"'{text}' is not a valid value for {self.field.name}.")
            self.load()
            return
        if self.field.type == fifadb.TYPE_REAL:
            current = self.value()
            if current is not None and abs(current - value) < 1e-6:
                return
        self.commit(value)


class TraitBits(Bound):
    def __init__(self, app, parent, table, field, names):
        super().__init__(app, table, field)
        self.vars = []
        cols = 3
        n = min(self.field.depth, len(names))
        for bit in range(n):
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(parent, text=f"{names[bit]}", variable=var,
                                 command=self._on_toggle)
            cb.grid(row=bit // cols, column=bit % cols, sticky="w", padx=6, pady=2)
            self.vars.append(var)

    def load(self):
        v = self.value()
        if v is None:
            return
        for bit, var in enumerate(self.vars):
            var.set(bool(v >> bit & 1))

    def _on_toggle(self):
        if self.app.loading:
            return
        v = self.value() or 0
        for bit, var in enumerate(self.vars):
            v = (v | (1 << bit)) if var.get() else (v & ~(1 << bit))
        self.commit(v)


class LookCode(Bound):
    """A look code with ◀ ▶ that step through the values other players use (unused
    codes may have no model in the game), and players who share the current value."""

    def __init__(self, app, parent, table, field, gridrow):
        super().__init__(app, table, field)
        ttk.Label(parent, text=label_for(field)).grid(
            row=gridrow, column=0, sticky="w", padx=(0, 10), pady=2)
        box = ttk.Frame(parent)
        box.grid(row=gridrow, column=1, sticky="w", pady=2)
        ttk.Button(box, text="◀", width=2, command=lambda: self._step(-1)).pack(side="left")
        self.var = tk.StringVar()
        self.entry = ttk.Entry(box, textvariable=self.var, width=6, justify="center")
        self.entry.pack(side="left", padx=2)
        ttk.Button(box, text="▶", width=2, command=lambda: self._step(1)).pack(side="left")
        self.hint = tk.StringVar()
        ttk.Label(parent, textvariable=self.hint, foreground="gray").grid(
            row=gridrow, column=2, sticky="w", padx=6)
        self.entry.bind("<Return>", lambda e: self._on_commit())
        self.entry.bind("<FocusOut>", lambda e: self._on_commit())

    def load(self):
        v = self.value()
        if v is None:
            return
        self.var.set(str(v))
        self.hint.set(self.app.look_examples(self.field.name, v))

    def _set(self, v):
        self.commit(v)
        self.load()

    def _step(self, d):
        v = self.value()
        if v is None:
            return
        used = self.app.look_values(self.field.name)
        nxt = [u for u in used if u > v] if d > 0 else [u for u in used if u < v][::-1]
        if nxt or used:
            self._set(nxt[0] if nxt else (used[0] if d > 0 else used[-1]))  # wrap around

    def _on_commit(self):
        if self.app.loading or self.row() is None:
            return
        try:
            v = int(self.var.get().strip())
        except ValueError:
            self.load()
            return
        if not self.field.low <= v <= self.field.high:
            messagebox.showerror("Invalid value", f"{label_for(self.field.name)} must be "
                                 f"between {self.field.low} and {self.field.high}.")
            self.load()
            return
        self._set(v)


class _FaceNote:
    """Warns that face/hair codes don't show on a player with a scanned face."""
    derived = True

    def __init__(self, app, table, var):
        self.app, self.table, self.var = app, table, var
        self.field = None

    def load(self):
        r = self.app.row_for(self.table)
        if r is None or "headclasscode" not in self.table.by_name:
            return
        if self.table.get(r, "headclasscode") == 0:
            self.var.set("⚠ This player has a real (scanned) face: the game uses the scan, "
                         "so Face and Hair & beard codes below won't show.\nSet Face type to "
                         "'Generic face' to build a look yourself.")
        else:
            self.var.set("Generic face: the codes below decide the look. Examples next to "
                         "each code are generic-face players using the same value.")


class _CreatedNote:
    """Shows whether the player is registered in createplayer."""
    derived = True

    def __init__(self, app, table, var):
        self.app, self.table, self.var = app, table, var
        self.field = None

    def load(self):
        if self.app.current_pid is None:
            return
        on = fifadb.created_player_row(self.app.db, self.app.current_pid) is not None
        self.var.set("✔ registered for in-game Create Player" if on else "")


def scrollable(parent):
    """Return (outer_frame, inner_frame) where inner scrolls vertically."""
    outer = ttk.Frame(parent)
    canvas = tk.Canvas(outer, highlightthickness=0)
    sb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas, padding=12)
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    win = canvas.create_window((0, 0), window=inner, anchor="nw")
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
    canvas.configure(yscrollcommand=sb.set)
    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    def wheel(event):
        if event.num == 4:
            canvas.yview_scroll(-3, "units")
        elif event.num == 5:
            canvas.yview_scroll(3, "units")
        else:
            canvas.yview_scroll(int(-event.delta / 40), "units")

    def bind_wheel(_):
        canvas.bind_all("<MouseWheel>", wheel)
        canvas.bind_all("<Button-4>", wheel)
        canvas.bind_all("<Button-5>", wheel)

    def unbind_wheel(_):
        canvas.unbind_all("<MouseWheel>")
        canvas.unbind_all("<Button-4>")
        canvas.unbind_all("<Button-5>")

    outer.bind("<Enter>", bind_wheel)
    outer.bind("<Leave>", unbind_wheel)
    return outer, inner


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

class EditorApp:
    def __init__(self, root):
        self.root = root
        self.db = None
        self.original = None
        self.loading = False
        self.current_pid = None
        self.controls = []
        self.edited_pids = set()
        self.created_pids = set()  # players added in the editor (kept in PROJECT_FILE)
        self.created_tids = set()
        self.project_dir = None
        self.sort_col, self.sort_rev = "name", False

        root.title("FIFA 17 Player Editor")
        root.geometry("1250x780")
        root.minsize(900, 560)
        root.protocol("WM_DELETE_WINDOW", self.quit)
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure("Treeview", rowheight=24)
        style.configure("Header.TLabel", font=("TkDefaultFont", 16, "bold"))
        style.configure("Sub.TLabel", foreground="#555")

        self._build_menu()
        self.status = tk.StringVar(value="Open a FIFA database (File ▸ Open database…).")
        ttk.Label(root, textvariable=self.status, relief="sunken", anchor="w",
                  padding=(8, 3)).pack(side="bottom", fill="x")

        self.paned = ttk.PanedWindow(root, orient="horizontal")
        self.paned.pack(fill="both", expand=True)
        self._build_list()
        self.detail = ttk.Frame(self.paned)
        self.paned.add(self.detail, weight=3)
        self._show_welcome()

        root.bind("<Control-s>", lambda e: self.save())
        root.bind("<Control-o>", lambda e: self.open_dialog())
        root.bind("<Control-f>", lambda e: self.search_entry.focus_set())
        root.bind("<Control-n>", lambda e: self.new_player())
        root.bind("<Control-t>", lambda e: self.edit_teams())
        self.team_window = None
        self.locs = []  # fifadb.LocFile for each open data/loc/<language>.db

    # -- layout ---------------------------------------------------------------
    def _build_menu(self):
        m = tk.Menu(self.root)
        fm = tk.Menu(m, tearoff=False)
        fm.add_command(label="Open database…", accelerator="Ctrl+O", command=self.open_dialog)
        fm.add_command(label="Save", accelerator="Ctrl+S", command=self.save)
        fm.add_command(label="Save project as…", command=self.save_as)
        fm.add_separator()
        fm.add_command(label="Open language files…", command=self.open_locs)
        fm.add_separator()
        fm.add_command(label="Export players to CSV…", command=self.export_csv)
        fm.add_separator()
        fm.add_command(label="Quit", command=self.quit)
        m.add_cascade(label="File", menu=fm)
        em = tk.Menu(m, tearoff=False)
        em.add_command(label="New player…", accelerator="Ctrl+N", command=self.new_player)
        em.add_separator()
        em.add_command(label="Revert this player", command=self.revert_player)
        em.add_command(label="Revert all changes", command=self.revert_all)
        m.add_cascade(label="Edit", menu=em)
        tm = tk.Menu(m, tearoff=False)
        tm.add_command(label="Edit teams…", accelerator="Ctrl+T", command=self.edit_teams)
        tm.add_command(label="New team… (on hold)", command=self.new_team)
        m.add_cascade(label="Teams", menu=tm)
        hm = tk.Menu(m, tearoff=False)
        hm.add_command(label="Database info", command=self.show_info)
        m.add_cascade(label="Help", menu=hm)
        self.root.config(menu=m)

    def _build_list(self):
        left = ttk.Frame(self.paned, padding=6)
        self.paned.add(left, weight=2)
        bar = ttk.Frame(left)
        bar.pack(fill="x")
        ttk.Label(bar, text="Search").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh_list())
        self.search_entry = ttk.Entry(bar, textvariable=self.search_var)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=6)
        bar2 = ttk.Frame(left)
        bar2.pack(fill="x", pady=(6, 6))
        ttk.Label(bar2, text="Team").pack(side="left")
        self.team_var = tk.StringVar(value="All teams")
        self.team_combo = ttk.Combobox(bar2, textvariable=self.team_var, state="readonly")
        self.team_combo.pack(side="left", fill="x", expand=True, padx=(16, 6))
        self.team_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_list())
        self.only_edited = tk.BooleanVar()
        ttk.Checkbutton(bar2, text="Mine only", variable=self.only_edited,
                        command=self.refresh_list).pack(side="left")

        cols = ("id", "name", "ovr", "pot", "pos", "age", "team")
        heads = ("ID", "Name", "OVR", "POT", "Pos", "Age", "Team")
        widths = (65, 190, 45, 45, 45, 40, 160)
        frame = ttk.Frame(left)
        frame.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for c, h, w in zip(cols, heads, widths):
            self.tree.heading(c, text=h, command=lambda c=c: self.sort_by(c))
            self.tree.column(c, width=w, anchor="w" if c in ("name", "team") else "center",
                             stretch=c in ("name", "team"))
        self.tree.tag_configure("edited", background="#fff3c4")
        self.tree.tag_configure("created", background="#d6f5d6")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.count_var = tk.StringVar()
        ttk.Label(left, textvariable=self.count_var, style="Sub.TLabel").pack(anchor="w")

    def _show_welcome(self):
        for w in self.detail.winfo_children():
            w.destroy()
        box = ttk.Frame(self.detail, padding=40)
        box.pack(expand=True)
        ttk.Label(box, text="FIFA 17 Player Editor", style="Header.TLabel").pack(pady=(0, 10))
        ttk.Label(box, justify="center", text=(
            "Open a FIFA database file (fifa_si_db.db / fifa_ng_db.DB or a squad file).\n"
            "The matching *-meta.XML describes the fields; it is picked up automatically\n"
            "when it sits next to the database or next to this program.")).pack()
        ttk.Button(box, text="Open database…", command=self.open_dialog).pack(pady=16)

    def _build_detail(self):
        for w in self.detail.winfo_children():
            w.destroy()
        self.controls = []
        P = self.players

        head = ttk.Frame(self.detail, padding=(14, 10, 14, 4))
        head.pack(fill="x")
        self.h_name = tk.StringVar()
        self.h_sub = tk.StringVar()
        self.h_ovr = tk.Label(head, width=4, font=("TkDefaultFont", 22, "bold"), fg="white")
        self.h_ovr.pack(side="left", padx=(0, 12))
        txt = ttk.Frame(head)
        txt.pack(side="left", fill="x", expand=True)
        ttk.Label(txt, textvariable=self.h_name, style="Header.TLabel").pack(anchor="w")
        ttk.Label(txt, textvariable=self.h_sub, style="Sub.TLabel").pack(anchor="w")
        ttk.Button(head, text="Revert player", command=self.revert_player).pack(side="right")
        ttk.Button(head, text="New player…", command=self.new_player).pack(side="right", padx=6)

        nb = ttk.Notebook(self.detail)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # Profile
        outer, f = scrollable(nb)
        nb.add(outer, text="Profile")
        r = 0
        for name in ("overallrating", "potential"):
            if name in P.by_name:
                self.controls.append(AttrSlider(self, f, P, name, r))
                r += 1
        for name in ("preferredposition1", "preferredposition2", "preferredposition3",
                     "preferredposition4", "preferredfoot", "weakfootabilitytypecode",
                     "skillmoves", "attackingworkrate", "defensiveworkrate",
                     "internationalrep"):
            if name in P.by_name:
                self.controls.append(Choice(self, f, P, name, r, CHOICES[name]))
                r += 1
        if "nationality" in P.by_name and self.nation_names:
            opts = {k: f"{v} ({k})" for k, v in sorted(self.nation_names.items(),
                                                       key=lambda kv: kv[1])}
            self.controls.append(Choice(self, f, P, "nationality", r, opts))
            r += 1
        for name in ("birthdate", "height", "weight", "contractvaliduntil",
                     "playerjointeamdate"):
            if name in P.by_name:
                self.controls.append(NumberEntry(self, f, P, name, r))
                r += 1
        for name in ("gender", "isretiring"):
            if name in P.by_name:
                self.controls.append(Choice(self, f, P, name, r, CHOICES[name]))
                r += 1

        # Attribute tabs
        for title, names in ATTRIBUTE_GROUPS:
            names = [n for n in names if n in P.by_name]
            if not names:
                continue
            outer, f = scrollable(nb)
            nb.add(outer, text=title)
            f.columnconfigure(1, weight=1)
            for i, name in enumerate(names):
                self.controls.append(AttrSlider(self, f, P, name, i))
            avg = tk.StringVar()
            ttk.Label(f, textvariable=avg, style="Sub.TLabel", wraplength=520).grid(
                row=len(names), column=0, columnspan=3, sticky="w", pady=(12, 0))
            self.controls.append(_GroupAverage(self, P, names, avg))

        # Traits
        trait_fields = [t for t in ("trait1", "trait2") if t in P.by_name]
        if trait_fields:
            outer, f = scrollable(nb)
            nb.add(outer, text="Traits")
            for i, tname in enumerate(trait_fields):
                lf = ttk.LabelFrame(f, text=f"{tname}", padding=8)
                lf.grid(row=i, column=0, sticky="ew", pady=6)
                self.controls.append(TraitBits(self, lf, P, tname, TRAITS[tname]))
            ttk.Label(f, style="Sub.TLabel", text=(
                "Trait names follow community documentation for FIFA 17 and may be "
                "off by one in some versions;\ncheck the raw trait1/trait2 numbers in "
                "'All fields' if something looks wrong.")).grid(
                row=len(trait_fields), column=0, sticky="w", pady=8)

        # Appearance
        look = [(g, [n for n in names if n in P.by_name]) for g, names in LOOK_GROUPS]
        look = [(g, names) for g, names in look if names]
        if look:
            outer, f = scrollable(nb)
            nb.add(outer, text="Appearance")
            top = ttk.Frame(f)
            top.grid(row=0, column=0, sticky="ew")
            ttk.Button(top, text="Copy look from player…",
                       command=lambda: CopyLookDialog(self)).pack(side="left")
            ttk.Button(top, text="Random generic look",
                       command=self.random_look).pack(side="left", padx=6)
            if "createplayer" in self.db.tables:
                ttk.Button(top, text="Customise in-game…",
                           command=lambda: self.make_in_game_editable(self.current_pid)
                           ).pack(side="left")
                cp = tk.StringVar()
                ttk.Label(top, textvariable=cp, style="Sub.TLabel").pack(side="left", padx=6)
                self.controls.append(_CreatedNote(self, P, cp))
            note = tk.StringVar()
            ttk.Label(f, textvariable=note, style="Sub.TLabel", wraplength=480,
                      justify="left").grid(row=1, column=0, sticky="w", pady=(8, 4))
            self.controls.append(_FaceNote(self, P, note))
            lf = ttk.LabelFrame(f, text="Face type", padding=8)
            lf.grid(row=2, column=0, sticky="ew", pady=6)
            for i, name in enumerate(n for n in ("headclasscode", "hashighqualityhead")
                                     if n in P.by_name):
                self.controls.append(Choice(self, lf, P, name, i, CHOICES[name]))
            for i, (title, names) in enumerate(look):
                lf = ttk.LabelFrame(f, text=title, padding=8)
                lf.grid(row=3 + i, column=0, sticky="ew", pady=6)
                for j, name in enumerate(names):
                    self.controls.append(LookCode(self, lf, P, name, j))
            ttk.Label(f, style="Sub.TLabel", wraplength=480, justify="left", text=(
                "◀ ▶ step through the codes other players already use. Typed codes nobody "
                "uses may have no model in the game. Real faces live in the player's own "
                "Frostbite bundle, so they can't be copied to another player.")).grid(
                row=3 + len(look), column=0, sticky="w", pady=8)

        # Club (teamplayerlinks)
        if self.tpl is not None:
            outer, f = scrollable(nb)
            nb.add(outer, text="Club")
            self.club_frame = f
            self.club_label = tk.StringVar()
            ttk.Label(f, textvariable=self.club_label, style="Sub.TLabel").grid(
                row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
            r = 1
            if "teamid" in self.tpl.by_name and self.team_names:
                self.controls.append(Choice(self, f, self.tpl, "teamid", r,
                                            self.team_options()))
                r += 1
            for name in ("jerseynumber", "position", "form", "injury"):
                if name in self.tpl.by_name:
                    self.controls.append(NumberEntry(self, f, self.tpl, name, r))
                    r += 1

        # Every field, raw
        outer, f = scrollable(nb)
        nb.add(outer, text="All fields")
        for i, fld in enumerate(P.fields):
            if fld.name == "playerid":
                continue
            self.controls.append(NumberEntry(self, f, P, fld.name, i, label=fld.name))

    # -- data -----------------------------------------------------------------
    def open_dialog(self):
        if not self.confirm_discard():
            return
        path = filedialog.askopenfilename(
            title="Open FIFA database",
            filetypes=[("FIFA database / saves", "*.db *.DB Squads* Career* Settings*"),
                       ("All files", "*")])
        if path:
            self.open(path)

    # -- project folder ----------------------------------------------------------
    def _load_project(self, path):
        """Pick up PROJECT_FILE next to `path`: what was made here, language files."""
        if self.project_dir:  # language files of the previous project stay with it
            self.locs = [l for l in self.locs if not os.path.abspath(l.path).startswith(
                self.project_dir + os.sep)]
        self.project_dir = None
        self.created_pids, self.created_tids = set(), set()
        folder = os.path.dirname(os.path.abspath(path))
        data = read_json(os.path.join(folder, PROJECT_FILE))
        if not data or data.get("database") != os.path.basename(path):
            return
        self.project_dir = folder
        self._load_project_ids(data)
        errors = []
        for rel in data.get("language_files", []):
            p = os.path.join(folder, rel)
            if any(os.path.abspath(l.path) == os.path.abspath(p) for l in self.locs):
                continue
            try:
                self.locs.append(fifadb.LocFile(p))
            except Exception as exc:
                errors.append(f"{rel}: {exc}")
        if errors:
            messagebox.showwarning("Language files", "Couldn't reopen:\n" + "\n".join(errors))

    def _load_project_ids(self, data):
        self.created_pids = {p["id"] for p in data.get("created_players", [])
                             if p.get("id") in self.pid_row}
        self.created_tids = {t["id"] for t in data.get("created_teams", [])
                             if t.get("id") in self.team_names}
        self.edited_pids = {p for p in data.get("edited_players", []) if p in self.pid_row}

    def _write_project_file(self):
        folder = self.project_dir
        ingame = {p for p in self.created_pids | self.edited_pids
                  if fifadb.created_player_row(self.db, p) is not None}
        data = {
            "editor": "FIFA 17 Player Editor",
            "saved": datetime.datetime.now().isoformat(timespec="seconds"),
            "database": os.path.basename(self.db.path),
            "meta": os.path.basename(self.meta_path),
            "frosty_import_over": f"data/db/{self.frosty_slot()}" if self.frosty_slot() else "",
            "created_players": [{"id": p, "name": self.player_name(p),
                                 "customisable_in_game": p in ingame}
                                for p in sorted(self.created_pids)],
            "created_teams": [{"id": t, "name": self.team_names.get(t, "")}
                              for t in sorted(self.created_tids)],
            "edited_players": sorted(self.edited_pids - self.created_pids),
            "language_files": [os.path.relpath(l.path, folder) for l in self.locs
                               if os.path.abspath(l.path).startswith(folder + os.sep)],
        }
        try:
            with open(os.path.join(folder, PROJECT_FILE), "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
        except OSError as exc:
            messagebox.showwarning("Project file not saved",
                                   f"The database was saved, but {PROJECT_FILE} wasn't:\n{exc}")

    def _remember(self, path):
        """Reopen this database next time the editor starts without arguments."""
        try:
            os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
            with open(SETTINGS_PATH, "w", encoding="utf-8") as fh:
                json.dump({"last_database": os.path.abspath(path),
                           "last_meta": os.path.abspath(self.meta_path)}, fh, indent=2)
        except OSError:
            pass

    def find_meta(self, dbpath):
        here = os.path.dirname(os.path.abspath(__file__))
        dbdir = os.path.dirname(os.path.abspath(dbpath))
        stem = os.path.splitext(os.path.basename(dbpath))[0].lower()
        candidates = []
        for d in (dbdir, here, os.path.dirname(here)):
            try:
                names = os.listdir(d)
            except OSError:
                continue
            for n in names:
                if n.lower().endswith("-meta.xml"):
                    candidates.append(os.path.join(d, n))
        exact = [c for c in candidates if os.path.basename(c).lower() == stem + "-meta.xml"]
        # a renamed copy like fifa_ng_db_v2.DB still belongs to fifa_ng_db-meta.XML
        prefix = sorted((c for c in candidates
                         if stem.startswith(os.path.basename(c).lower()[:-len("-meta.xml")])),
                        key=lambda c: -len(os.path.basename(c)))
        return (exact or prefix or candidates or [None])[0]

    def open(self, path, meta_path=None):
        with open(path, "rb") as fh:
            head = fh.read(256).lstrip(b"\xef\xbb\xbf \r\n\t")
        if head.startswith(b"<"):
            messagebox.showinfo("That's the meta XML", (
                "The *-meta.XML only describes the database layout; it contains no players.\n\n"
                "Open the database itself instead: the .db/.DB file exported with Frosty "
                "Editor (same folder as the XML in the Legacy Explorer), or a squad file "
                "saved from the game (Documents/FIFA 17/settings/Squads…).\n\n"
                "The XML is picked up automatically when it sits next to the database."))
            return
        if not os.path.exists(os.path.join(os.path.dirname(os.path.abspath(path)),
                                           PROJECT_FILE)):
            proj = project_dir_for(path)
            data = read_json(os.path.join(proj, PROJECT_FILE))
            saved = os.path.join(proj, data.get("database", "")) if data else ""
            if saved and os.path.isfile(saved) and messagebox.askyesno("Saved project", (
                    f"You have a saved project for this database:\n{proj}\n\n"
                    "Open the project (with your changes) instead of the original?")):
                path, meta_path = saved, None
        meta_path = meta_path or self.find_meta(path)
        if not meta_path:
            meta_path = filedialog.askopenfilename(
                title="Select the matching meta XML",
                filetypes=[("Meta XML", "*.xml *.XML"), ("All files", "*")])
            if not meta_path:
                return
        try:
            meta = fifadb.Meta(meta_path)
            db = fifadb.Database(path, meta)
        except Exception as exc:
            messagebox.showerror("Could not open database", f"{type(exc).__name__}: {exc}")
            return
        stem = os.path.splitext(os.path.basename(path))[0].lower()
        named_for_it = os.path.basename(meta_path).lower() == stem + "-meta.xml"
        if (stem.startswith("fifa_") and meta.dbname and not named_for_it
                and not stem.startswith(meta.dbname.lower())):
            db.warnings.insert(0, (
                f"The meta XML describes '{meta.dbname}', but you opened '{stem}'. "
                f"Values will be wrong — use {stem}-meta.XML instead."))
        if "players" not in db.tables:
            messagebox.showerror("No players", "This database has no 'players' table.\n"
                                 f"Tables found: {', '.join(sorted(db.tables)) or 'none'}")
            return
        if self.team_window and self.team_window.win.winfo_exists():
            self.team_window.win.destroy()  # it holds the previous database's tables
        self.team_window = None
        self.db = db
        self.meta_path = meta_path
        self._snapshot()
        self.edited_pids = set()
        self.current_pid = None
        self._index()
        self._load_project(path)
        self._build_detail()
        self.refresh_list()
        self.root.title(f"FIFA 17 Player Editor — {os.path.basename(path)}" +
                        (f"  ({os.path.basename(self.project_dir)})"
                         if self.project_dir else ""))
        self._remember(path)
        self.update_status()
        if db.warnings:
            messagebox.showwarning("Warnings", "\n\n".join(db.warnings))

    def _index(self):
        db = self.db
        self.players = db.tables["players"]
        P = self.players
        self.pid_row = {P.get(r, "playerid"): r for r in P.rows()}
        self._look_index = None

        self.names = {}
        for tname in ("playernames", "dcplayernames"):
            t = db.tables.get(tname)
            if t and "nameid" in t.by_name and "name" in t.by_name:
                for r in t.rows():
                    self.names[t.get(r, "nameid")] = t.get(r, "name")
        self.edited_names = {}
        t = db.tables.get("editedplayernames")
        if t:
            for r in t.rows():
                self.edited_names[t.get(r, "playerid")] = r

        self.team_names = {}
        t = db.tables.get("teams")
        if t and "teamname" in t.by_name:
            for r in t.rows():
                self.team_names[t.get(r, "teamid")] = t.get(r, "teamname")
        self.nation_names = {}
        t = db.tables.get("nations")
        if t and "nationname" in t.by_name:
            for r in t.rows():
                self.nation_names[t.get(r, "nationid")] = t.get(r, "nationname")

        self.tpl = db.tables.get("teamplayerlinks")
        self.pid_links = {}
        if self.tpl is not None:
            for r in self.tpl.rows():
                self.pid_links.setdefault(self.tpl.get(r, "playerid"), []).append(r)
        teams_used = sorted({self.team_names.get(self.tpl.get(r, "teamid"), "")
                             for rows in self.pid_links.values() for r in rows} - {""}) \
            if self.tpl is not None else []
        self.team_combo.configure(values=["All teams"] + teams_used)
        self.team_var.set("All teams")

    def team_options(self):
        """teamid -> "Name (id)", sorted by name, for team pickers."""
        return {tid: f"{name} ({tid})" for tid, name in
                sorted(self.team_names.items(), key=lambda kv: fold(kv[1]))}

    def league_options(self):
        t = self.db.tables.get("leagues")
        if not t:
            return {}
        names = {t.get(r, "leagueid"): t.get(r, "leaguename").strip() for r in t.rows()}
        return {lid: f"{n} ({lid})" for lid, n in sorted(names.items(),
                                                         key=lambda kv: fold(kv[1]))}

    def player_name(self, pid):
        P, r = self.players, self.pid_row[pid]
        if pid in self.edited_names:
            t, er = self.db.tables["editedplayernames"], self.edited_names[pid]
            common = t.get(er, "commonname") if "commonname" in t.by_name else ""
            if common:
                return common
            return f"{t.get(er, 'firstname')} {t.get(er, 'surname')}".strip()

        def nm(field):
            return self.names.get(P.get(r, field), "") if field in P.by_name else ""
        common = nm("commonnameid")
        if common:
            return common
        full = f"{nm('firstnameid')} {nm('lastnameid')}".strip()
        return full or f"Player {pid}"

    def look_index(self):
        """field -> value -> (all players, generic-face players), each a list of pids
        best-rated first. Built on first use."""
        if self._look_index is None:
            P = self.players
            fields = [n for _, names in LOOK_GROUPS for n in names if n in P.by_name]
            has_ovr = "overallrating" in P.by_name
            has_cls = "headclasscode" in P.by_name
            idx = {n: {} for n in fields}
            for r in P.rows():
                pid = P.get(r, "playerid")
                key = (-P.get(r, "overallrating") if has_ovr else 0, pid)
                generic = has_cls and P.get(r, "headclasscode") == 1
                for n in fields:
                    both = idx[n].setdefault(P.get(r, n), ([], []))
                    both[0].append(key)
                    if generic:
                        both[1].append(key)
            for by_val in idx.values():
                for lists in by_val.values():
                    for lst in lists:
                        lst.sort()
                        lst[:] = [pid for _, pid in lst]
            self._look_index = idx
        return self._look_index

    def look_values(self, field):
        return sorted(self.look_index()[field])

    def look_examples(self, field, value):
        every, generic = self.look_index()[field].get(value, ([], []))
        pool = generic if field in HEAD_LOOK and generic else every
        others = [p for p in pool if p != self.current_pid]
        if not others:
            return "no other player uses this code"
        names = ", ".join(self.player_name(p) for p in others[:3])
        return f"{len(pool)} use it, e.g. {names}"

    def set_player_fields(self, values):
        """Write several players-table fields of the current player at once."""
        pid = self.current_pid
        P, r = self.players, self.pid_row[pid]
        changed = False
        for name, v in values.items():
            if name in P.by_name and P.get(r, name) != v:
                P.set(r, name, v)
                changed = True
        if changed:
            self._mark_edited(pid)
            self.refresh_controls()
            self.update_status()
        return changed

    def make_in_game_editable(self, pid, ask=True):
        """Register `pid` in createplayer so the game's Create Player may edit it."""
        if pid is None:
            return
        P, r = self.players, self.pid_row[pid]
        if fifadb.created_player_row(self.db, pid) is not None:
            messagebox.showinfo("Customise in-game", "This player is already registered.",
                                parent=self.root)
            return
        real = "headclasscode" in P.by_name and P.get(r, "headclasscode") == 0
        if ask and not messagebox.askyesno("Customise in-game", (
                "Experimental: registers this player in the game's Create Player table so "
                "you can try to change face, hair and accessories inside FIFA 17 "
                "(Customise ▸ Edit Teams ▸ Edit Player / Create Player).\n\n"
                "Not tested in-game yet; keep a backup of your Frosty mod.\n" +
                ("\nThis player has a real face; it will be switched to a generic face.\n"
                 if real else "") + "\nContinue?"), icon="warning", parent=self.root):
            return
        try:
            fifadb.register_created_player(self.db, pid)
        except fifadb.DBError as exc:
            messagebox.showerror("Customise in-game", str(exc), parent=self.root)
            return
        if real:
            P.set(r, "headclasscode", 1)
            P.set(r, "hashighqualityhead", 0)
        self._mark_edited(pid)
        if pid == self.current_pid:
            self.refresh_controls()
        self.update_status()

    def look_fields(self, groups):
        return {n for g, names in LOOK_GROUPS if g in groups for n in names
                if n in self.players.by_name}

    def random_look(self):
        """Copy face, hair & beard from a random generic-face player, preferring the same
        nationality so skin tone and features stay plausible."""
        pid = self.current_pid
        if pid is None:
            return
        P, r = self.players, self.pid_row[pid]
        if "headclasscode" not in P.by_name:
            return
        values = {}
        if P.get(r, "headclasscode") == 0:
            if not messagebox.askyesno("Random generic look", (
                    "This player has a real (scanned) face, so a generic look won't show "
                    "in-game.\n\nSwitch them to a generic face?"), parent=self.root):
                return
            values.update(headclasscode=1, hashighqualityhead=0)
        generic = [p for p, rr in self.pid_row.items()
                   if p != pid and P.get(rr, "headclasscode") == 1]
        if not generic:
            return
        if "nationality" in P.by_name:
            nat = P.get(r, "nationality")
            same = [p for p in generic if P.get(self.pid_row[p], "nationality") == nat]
            generic = same or generic
        src = random.choice(generic)
        sr = self.pid_row[src]
        for n in self.look_fields(("Face", "Hair & beard")):
            values[n] = P.get(sr, n)
        self.set_player_fields(values)
        self.status.set(f"Look copied from {self.player_name(src)} ({src}). "
                        "Press again for another.")

    def player_team(self, pid):
        """Club first: national teams are listed after clubs in teamplayerlinks."""
        teams = [self.team_names.get(self.tpl.get(r, "teamid"), "")
                 for r in self.pid_links.get(pid, [])] if self.tpl is not None else []
        return teams

    def player_age(self, pid):
        try:
            bd = fifadb.days_to_date(self.players.get(self.pid_row[pid], "birthdate"))
        except (KeyError, OverflowError, ValueError):
            return ""
        return (SEASON_START - bd).days // 365

    def summary(self, pid):
        P, r = self.players, self.pid_row[pid]
        pos = P.get(r, "preferredposition1") if "preferredposition1" in P.by_name else -1
        teams = self.player_team(pid)
        return {
            "id": pid,
            "name": self.player_name(pid),
            "ovr": P.get(r, "overallrating") if "overallrating" in P.by_name else "",
            "pot": P.get(r, "potential") if "potential" in P.by_name else "",
            "pos": POSITIONS[pos] if 0 <= pos < len(POSITIONS) else "",
            "age": self.player_age(pid),
            "team": teams[0] if teams else "",
            "teams": teams,
        }

    def row_for(self, table):
        if self.current_pid is None:
            return None
        if table is self.players:
            return self.pid_row[self.current_pid]
        if table is self.tpl:
            links = self.pid_links.get(self.current_pid)
            return links[0] if links else None
        return None

    # -- list -----------------------------------------------------------------
    def refresh_list(self):
        if not self.db:
            return
        q = fold(self.search_var.get().strip())
        team = self.team_var.get()
        rows = []
        for pid in self.pid_row:
            s = self.summary(pid)
            if q and q not in fold(s["name"]) and q != str(pid):
                continue
            if team != "All teams" and team not in s["teams"]:
                continue
            if self.only_edited.get() and pid not in self.edited_pids | self.created_pids:
                continue
            rows.append(s)
        key = self.sort_col

        def sortkey(s):
            v = s[key]
            return (0, v) if isinstance(v, int) else (1, fold(str(v)))
        rows.sort(key=sortkey, reverse=self.sort_rev)
        self.tree.delete(*self.tree.get_children())
        for s in rows:
            self.tree.insert("", "end", iid=str(s["id"]),
                             values=tuple(s[c] for c in ("id", "name", "ovr", "pot", "pos",
                                                          "age", "team")),
                             tags=self._tags(s["id"]))
        self.count_var.set(f"{len(rows)} of {len(self.pid_row)} players")
        if self.current_pid is not None and self.tree.exists(str(self.current_pid)):
            self.tree.selection_set(str(self.current_pid))
            self.tree.see(str(self.current_pid))

    def sort_by(self, col):
        self.sort_rev = not self.sort_rev if self.sort_col == col else col in ("ovr", "pot")
        self.sort_col = col
        self.refresh_list()

    def on_select(self, _):
        sel = self.tree.selection()
        if not sel:
            return
        pid = int(sel[0])
        if pid == self.current_pid:
            return
        self.root.focus_set()  # commit any half-typed entry for the previous player
        self.root.update_idletasks()
        self.current_pid = pid
        self.refresh_controls()

    def refresh_controls(self):
        if self.current_pid is None:
            return
        self.loading = True
        try:
            for c in self.controls:
                c.load()
        finally:
            self.loading = False
        s = self.summary(self.current_pid)
        self.h_name.set(s["name"])
        nat = ""
        if "nationality" in self.players.by_name:
            nat = self.nation_names.get(
                self.players.get(self.pid_row[self.current_pid], "nationality"), "")
        bits = [s["pos"], f"Age {s['age']}", nat, " / ".join(s["teams"]),
                f"ID {s['id']}"]
        self.h_sub.set("  ·  ".join(str(b) for b in bits if b))
        if s["ovr"] != "":
            self.h_ovr.configure(text=str(s["ovr"]), bg=rating_color(s["ovr"]))
        if self.tpl is not None and hasattr(self, "club_label"):
            team = s["teams"][0] if s["teams"] else "no team"
            self.club_label.set(f"Editing link to: {team}")

    def _tags(self, pid):
        if pid in self.created_pids:
            return ("created",)
        return ("edited",) if pid in self.edited_pids else ()

    def _mark_edited(self, pid):
        self.edited_pids.add(pid)
        if self.tree.exists(str(pid)):
            s = self.summary(pid)
            self.tree.item(str(pid), tags=self._tags(pid),
                           values=tuple(s[c] for c in ("id", "name", "ovr", "pot", "pos",
                                                        "age", "team")))

    def on_edited(self, control):
        pid = self.current_pid
        self._mark_edited(pid)
        # keep every other widget showing the same field in sync
        self.loading = True
        try:
            for c in self.controls:
                if c is not control and (c.table is control.table and
                                         getattr(c, "field", None) is control.field
                                         or getattr(c, "derived", False)):
                    c.load()
        finally:
            self.loading = False
        if control.table is self.tpl and control.field.name == "teamid":
            self.refresh_controls()  # header shows the club
            if self.team_window and self.team_window.win.winfo_exists():
                self.team_window.refresh_squad()
        if control.field.name == "overallrating":
            v = self.players.get(self.pid_row[pid], "overallrating")
            self.h_ovr.configure(text=str(v), bg=rating_color(v))
        self.update_status()

    def update_status(self):
        if not self.db:
            return
        n = len(self.edited_pids)
        unsaved = f"  ·  {n} player(s) edited, unsaved" if self.db.dirty else ""
        slot = f"  ·  Frosty: import over data/db/{self.frosty_slot()}" \
            if self.frosty_slot() else ""
        locs = ""
        if self.locs:
            dirty = sum(l.dirty for l in self.locs)
            locs = f"  ·  {len(self.locs)} language file(s)" + (
                f", {dirty} unsaved" if dirty else "")
        self.status.set(f"{self.db.path}  ·  {len(self.pid_row)} players{slot}{locs}{unsaved}")

    def frosty_slot(self):
        """The legacy file this database replaces in Frosty, from its schema name.
        Importing it over a different one (e.g. fifa_si_db) makes the game reject it."""
        name = (self.db.meta.dbname or "").lower() if self.db else ""
        return name + ".db" if name.startswith("fifa_") else ""

    # -- edit actions ---------------------------------------------------------
    def _snapshot(self):
        """Remember the saved bytes and where each table's records were in them
        (rows can be appended, which moves later tables)."""
        self.original = bytes(self.db.data)
        self.orig_layout = {n: (t.records_start, t.n_rows) for n, t in self.db.tables.items()}

    def _restore_rows(self, pid):
        P = self.players
        tables = [(P, [self.pid_row[pid]])]
        if self.tpl is not None:
            tables.append((self.tpl, self.pid_links.get(pid, [])))
        for t, rows in tables:
            orig_start, orig_rows = self.orig_layout[t.name]
            for r in rows:
                if r >= orig_rows:  # added since the last save; nothing to restore
                    continue
                s = t.records_start + r * t.record_size
                o = orig_start + r * t.record_size
                if self.db.data[s:s + t.record_size] != self.original[o:o + t.record_size]:
                    self.db.data[s:s + t.record_size] = self.original[o:o + t.record_size]
                    t.dirty = True
                    self.db.dirty = True

    def new_player(self):
        if not self.db:
            return
        missing = [n for n in ("teamplayerlinks", "dcplayernames")
                   if n not in self.db.tables]
        if missing:
            messagebox.showerror("New player", "This database has no " + ", ".join(missing) +
                                 " table, so players can't be added to it.")
            return
        self.root.focus_set()
        self.root.update_idletasks()
        NewPlayerDialog(self)

    def edit_teams(self, team_id=None):
        if not self.db:
            return
        if "teams" not in self.db.tables:
            messagebox.showerror("Teams", "This database has no teams table.")
            return
        if self.team_window and self.team_window.win.winfo_exists():
            self.team_window.win.lift()
            if team_id is not None:
                self.team_window.reload(team_id)
            return
        self.team_window = TeamWindow(self, team_id)

    def new_team(self):
        if not self.db:
            return
        if not messagebox.askyesno("New team — on hold", (
                "Creating teams is on hold and not finished yet: new teams can show "
                "missing kits, generic faces, or break career mode.\n\n"
                "Open the New team dialog anyway?"), icon="warning", default="no",
                parent=self.root):
            return
        missing = [t for t, _ in fifadb.TEAM_KEYED if t not in self.db.tables]
        if missing:
            messagebox.showerror("New team", "This database lacks tables needed for teams: " +
                                 ", ".join(missing))
            return
        self.root.focus_set()
        self.root.update_idletasks()
        NewTeamDialog(self)

    def add_team(self, template_tid, name, league_id, squad, team_id=None, asset_id=None):
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        try:
            tid, pid_map = fifadb.create_team(self.db, template_tid, name, league_id,
                                              squad, team_id, asset_id)
        except fifadb.DBError as exc:
            messagebox.showerror("New team", str(exc))
            return None
        finally:
            self.root.config(cursor="")
        a15, a10, a3 = fifadb.short_names(name)
        old = self.set_team_loc_names(tid, (name, a15, a10, a3, a10))
        if team_id is not None and not self.locs:
            messagebox.showinfo("New team", (
                "This kit slot already has a name in the game's language files, which the "
                "game shows instead of yours.\n\nOpen your data/loc/*.db files (File ▸ Open "
                "language files…) and set the names in the Teams window, then import them "
                "in Frosty too."))
        elif old:
            self.status.set(f"Replaced on-screen names {old} in {len(self.locs)} language file(s)")
        self.created_tids.add(tid)
        if squad == fifadb.SQUAD_COPY:
            self.edited_pids.update(pid_map.values())
            self.created_pids.update(pid_map.values())
        self.after_teams_changed()
        self.update_status()
        self.edit_teams(tid)
        return tid

    def open_locs(self):
        paths = filedialog.askopenfilenames(
            title="Open language files (exported from Frosty: data/loc/*.db)",
            filetypes=[("FIFA language files", "*.db *.DB"), ("All files", "*")])
        if not paths:
            return
        self.root.config(cursor="watch")
        self.root.update_idletasks()
        errors = []
        try:
            for p in paths:
                if any(os.path.abspath(l.path) == os.path.abspath(p) for l in self.locs):
                    continue
                try:
                    self.locs.append(fifadb.LocFile(p))
                except Exception as exc:
                    errors.append(f"{os.path.basename(p)}: {exc}")
        finally:
            self.root.config(cursor="")
        if errors:
            messagebox.showerror("Language files", "\n".join(errors))
        self.update_status()
        if self.team_window and self.team_window.win.winfo_exists():
            self.team_window.load_loc_names()

    def set_team_loc_names(self, tid, names):
        """Write (full, abbr15, abbr10, abbr3, commentary) into every open language
        file where that key already exists; returns the replaced full names."""
        old = set()
        for loc in self.locs:
            prev = loc.get(f"TeamName_{tid}")
            for key, text in zip(fifadb.LocFile.TEAM_KEYS, names):
                if text:
                    try:
                        loc.set(key.format(tid), text)
                    except fifadb.DBError as exc:
                        messagebox.showerror("Language files", f"{loc.language}: {exc}")
                        return old
            if prev:
                old.add(prev)
        self.update_status()
        return old

    def after_teams_changed(self):
        """Team names or squads changed: rebuild lookups and every team picker."""
        self._index()
        self._build_detail()
        self.refresh_list()
        self.refresh_controls()

    def add_player(self, template_pid, team_id, jersey, first, last, common, jersey_name,
                   team_position):
        try:
            pid = fifadb.create_player(self.db, self.pid_row[template_pid], team_id, jersey,
                                       first, last, common, jersey_name, team_position)
        except fifadb.DBError as exc:
            messagebox.showerror("New player", str(exc))
            return None
        self._index()
        self.edited_pids.add(pid)
        self.created_pids.add(pid)
        self.current_pid = pid
        self.search_var.set("")  # refreshes the list and selects the new player
        self.refresh_controls()
        self.update_status()
        return pid

    def revert_player(self):
        if self.current_pid is None:
            return
        self._restore_rows(self.current_pid)
        self.edited_pids.discard(self.current_pid)
        self.refresh_list()
        self.refresh_controls()
        self.update_status()

    def revert_all(self):
        if not self.db or not self.db.dirty:
            return
        if not messagebox.askyesno("Revert all", "Discard all unsaved changes?"):
            return
        if self.db.grown:  # the layout changed; re-read the saved file instead
            self.db.dirty = False
            self.open(self.db.path, self.meta_path)
            return
        self.db.data[:] = self.original
        for t in self.db.tables.values():
            t.dirty = False
        self.db.dirty = False
        self.edited_pids.clear()
        data = read_json(os.path.join(self.project_dir, PROJECT_FILE)) \
            if self.project_dir else None
        if data:
            self._load_project_ids(data)  # back to what the last save recorded
        self.refresh_list()
        self.refresh_controls()
        self.update_status()

    def save(self):
        if not self.db:
            return
        self.root.focus_set()
        self.root.update_idletasks()
        if self.project_dir:
            if self._write(self.db.path, os.path.join(self.project_dir, "loc")):
                self._write_project_file()
            return
        target = project_dir_for(self.db.path)
        if os.path.exists(os.path.join(target, PROJECT_FILE)) and not messagebox.askyesno(
                "Save", f"A project folder already exists:\n{target}\n\n"
                "Replace its database with this one?", icon="warning"):
            return
        if self._save_project_to(target):
            messagebox.showinfo("Saved", (
                f"Saved everything into the folder\n{target}\n\n"
                "Database, meta XML, language files and the list of players you made are "
                "kept there. Your original file wasn't changed. Next saves go into this "
                "folder, and the editor reopens it on start.\n\n"
                f"In Frosty, import {os.path.basename(self.db.path)} from this folder."))

    def save_as(self):
        if not self.db:
            return
        self.root.focus_set()
        self.root.update_idletasks()
        folder = filedialog.askdirectory(title="Save project into folder",
                                         initialdir=os.path.dirname(self.project_dir or
                                                                    self.db.path))
        if folder:
            self._save_project_to(folder)

    def _save_project_to(self, folder):
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))
            return False
        path = os.path.join(folder, os.path.basename(self.db.path))
        if not self._write(path, os.path.join(folder, "loc")):
            return False
        self._copy_meta(path)
        self.project_dir = os.path.abspath(folder)
        self._write_project_file()
        self._remember(path)
        self.root.title(f"FIFA 17 Player Editor — {os.path.basename(path)}  "
                        f"({os.path.basename(self.project_dir)})")
        return True

    def _copy_meta(self, dbpath):
        """Put the schema next to the new file as <name>-meta.XML so it opens on its own."""
        stem = os.path.splitext(os.path.basename(dbpath))[0]
        target = os.path.join(os.path.dirname(os.path.abspath(dbpath)), stem + "-meta.XML")
        if os.path.abspath(target) == os.path.abspath(self.meta_path):
            return
        try:
            shutil.copyfile(self.meta_path, target)
        except OSError as exc:
            messagebox.showwarning("Meta XML not copied",
                                   f"The database was saved, but copying the meta XML "
                                   f"to {target} failed:\n{exc}")
            return
        self.meta_path = target
        self.status.set(self.status.get() + f"  ·  schema: {os.path.basename(target)}")

    def _write(self, path, loc_dir=None):
        """Save the database to `path`; language files go into `loc_dir` (once
        copied there they are saved in place)."""
        try:
            self.db.save(path)
            for loc in self.locs:
                inside = loc_dir and os.path.abspath(loc.path).startswith(
                    os.path.abspath(loc_dir) + os.sep)
                if loc_dir and not inside:
                    os.makedirs(loc_dir, exist_ok=True)
                    loc.save(os.path.join(loc_dir, os.path.basename(loc.path)))
                elif loc.dirty:
                    loc.save()
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
            return False
        self._snapshot()
        self.db.grown = False
        self.update_status()
        self.status.set(self.status.get() + "  ·  saved (backup: .bak)")
        return True

    def export_csv(self):
        if not self.db:
            return
        path = filedialog.asksaveasfilename(title="Export players", defaultextension=".csv",
                                            initialfile="players.csv")
        if not path:
            return
        P = self.players
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            names = [f.name for f in P.fields]
            w.writerow(["name", "team"] + names)
            for pid, r in self.pid_row.items():
                s = self.summary(pid)
                w.writerow([s["name"], s["team"]] + [P.get(r, f) for f in P.fields])
        self.status.set(f"Exported {len(self.pid_row)} players to {path}")

    def show_info(self):
        if not self.db:
            messagebox.showinfo("Database info", "No database open.")
            return
        d = self.db
        lines = [f"File: {d.path}", f"Meta: {self.meta_path}",
                 f"Project folder: {self.project_dir or 'none yet (created on first Save)'}",
                 f"Made here: {len(self.created_pids)} player(s), "
                 f"{len(self.created_tids)} team(s)",
                 f"Import in Frosty over: data/db/{self.frosty_slot() or '?'}",
                 *(f"Language file {l.path} → import over data/loc/{l.language}.db"
                   for l in self.locs),
                 f"Tables: {len(d.tables)}", f"Bit order: {d.bit_order}", ""]
        for name in ("players", "playernames", "teams", "teamplayerlinks", "nations"):
            t = d.tables.get(name)
            if t:
                lines.append(f"{name}: {t.n_rows} rows, {len(t.fields)} fields, "
                             f"record {t.record_size} B, CRC {t.crc_variant or 'NOT FOUND'}")
        messagebox.showinfo("Database info", "\n".join(lines))

    def confirm_discard(self):
        if self.db and (self.db.dirty or any(l.dirty for l in self.locs)):
            ans = messagebox.askyesnocancel("Unsaved changes", "Save changes first?")
            if ans is None:
                return False
            if ans:
                self.save()
                return not self.db.dirty and not any(l.dirty for l in self.locs)
        return True

    def quit(self):
        if self.confirm_discard():
            self.root.destroy()


class _GroupAverage:
    """Shows the average of an attribute group (not a field itself)."""
    derived = True

    def __init__(self, app, table, names, var):
        self.app, self.table, self.names, self.var = app, table, names, var
        self.field = None

    def load(self):
        r = self.app.row_for(self.table)
        if r is None:
            return
        vals = [self.table.get(r, n) for n in self.names]
        self.var.set(f"Group average: {sum(vals) / len(vals):.1f}   "
                     "(the game does not recalculate Overall automatically — "
                     "set it on the Profile tab)")


class NewPlayerDialog:
    """Asks for name, club and shirt number; attributes, looks etc. are copied from
    a template player and edited afterwards in the normal tabs."""

    ROLES = {"Reserve": fifadb.TEAM_POS_RESERVE, "Substitute": fifadb.TEAM_POS_SUB}

    def __init__(self, app):
        self.app = app
        self.win = w = tk.Toplevel(app.root)
        w.title("New player")
        w.transient(app.root)
        w.resizable(False, False)
        f = ttk.Frame(w, padding=14)
        f.pack(fill="both", expand=True)

        pids = list(app.pid_row)
        self.template_opts = {}
        if app.current_pid is not None:
            self.template_opts[f"{app.player_name(app.current_pid)} (selected)"] = \
                app.current_pid
        self.teams = {f"{name} ({tid})": tid for tid, name in
                      sorted(app.team_names.items(), key=lambda kv: fold(kv[1]))}
        cur_team = ""
        if app.current_pid is not None and app.pid_links.get(app.current_pid):
            tid = app.tpl.get(app.pid_links[app.current_pid][0], "teamid")
            cur_team = f"{app.team_names.get(tid, '')} ({tid})"

        self.vars = {k: tk.StringVar() for k in
                     ("first", "last", "common", "jersey_name", "team", "jersey", "role")}
        r = 0
        ttk.Label(f, text="Copy attributes & looks from").grid(row=r, column=0, sticky="w")
        self.template_var = tk.StringVar()
        tmpl = ttk.Combobox(f, textvariable=self.template_var, width=34,
                            values=list(self.template_opts))
        tmpl.grid(row=r, column=1, sticky="w", pady=3)
        if self.template_opts:
            tmpl.current(0)
        else:
            self.template_var.set(str(pids[0]))
        ttk.Label(f, text="(or type a player ID)", foreground="gray").grid(
            row=r, column=2, sticky="w", padx=6)
        r += 1
        for key, label, hint in (("first", "First name", "required"),
                                 ("last", "Surname", "required"),
                                 ("common", "Known as", "optional, e.g. 'Ronaldinho'"),
                                 ("jersey_name", "Name on shirt", "defaults to surname")):
            ttk.Label(f, text=label).grid(row=r, column=0, sticky="w")
            ttk.Entry(f, textvariable=self.vars[key], width=36).grid(
                row=r, column=1, sticky="w", pady=3)
            ttk.Label(f, text=hint, foreground="gray").grid(row=r, column=2, sticky="w", padx=6)
            r += 1
        ttk.Label(f, text="Club").grid(row=r, column=0, sticky="w")
        team = ttk.Combobox(f, textvariable=self.vars["team"], values=list(self.teams),
                            state="readonly", width=34)
        team.grid(row=r, column=1, sticky="w", pady=3)
        team.bind("<<ComboboxSelected>>", lambda e: self._suggest_jersey())
        self.vars["team"].set(cur_team if cur_team in self.teams else "")
        r += 1
        ttk.Label(f, text="Shirt number").grid(row=r, column=0, sticky="w")
        ttk.Spinbox(f, from_=1, to=99, textvariable=self.vars["jersey"], width=6).grid(
            row=r, column=1, sticky="w", pady=3)
        self.jersey_hint = tk.StringVar()
        ttk.Label(f, textvariable=self.jersey_hint, foreground="gray").grid(
            row=r, column=2, sticky="w", padx=6)
        r += 1
        ttk.Label(f, text="Squad role").grid(row=r, column=0, sticky="w")
        ttk.Combobox(f, textvariable=self.vars["role"], values=list(self.ROLES),
                     state="readonly", width=12).grid(row=r, column=1, sticky="w", pady=3)
        self.vars["role"].set("Reserve")
        r += 1
        self.in_game = tk.BooleanVar(value="createplayer" in app.db.tables)
        if "createplayer" in app.db.tables:
            ttk.Checkbutton(f, variable=self.in_game, text=(
                "Customise in-game (register as a Create Player player, experimental)")
            ).grid(row=r, column=0, columnspan=3, sticky="w", pady=(6, 0))
            r += 1
        ttk.Label(f, style="Sub.TLabel", justify="left", text=(
            "The new player gets a generic face and the template's attributes;\n"
            "change ratings, position, nationality etc. in the tabs afterwards.")).grid(
            row=r, column=0, columnspan=3, sticky="w", pady=(10, 0))
        r += 1
        btns = ttk.Frame(f)
        btns.grid(row=r, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel", command=w.destroy).pack(side="right")
        ttk.Button(btns, text="Create", command=self.create).pack(side="right", padx=6)
        self._suggest_jersey()
        w.bind("<Return>", lambda e: self.create())
        w.bind("<Escape>", lambda e: w.destroy())
        w.grab_set()

    def _used_numbers(self, tid):
        app = self.app
        return {app.tpl.get(r, "jerseynumber") for r in app.tpl.rows()
                if app.tpl.get(r, "teamid") == tid}

    def _suggest_jersey(self):
        tid = self.teams.get(self.vars["team"].get())
        if tid is None:
            self.jersey_hint.set("")
            return
        used = self._used_numbers(tid)
        free = next((n for n in range(2, 100) if n not in used), 99)
        if not self.vars["jersey"].get() or int(self.vars["jersey"].get() or 0) in used:
            self.vars["jersey"].set(str(free))
        self.jersey_hint.set(f"first free: {free}")

    def create(self):
        v = {k: var.get().strip() for k, var in self.vars.items()}
        tmpl = self.template_var.get().strip()
        template_pid = self.template_opts.get(tmpl)
        if template_pid is None:
            try:
                template_pid = int(tmpl)
            except ValueError:
                template_pid = None
        if template_pid not in self.app.pid_row:
            messagebox.showerror("New player", "Choose a template player (or a valid ID).",
                                 parent=self.win)
            return
        if not v["first"] or not v["last"]:
            messagebox.showerror("New player", "First name and surname are required.",
                                 parent=self.win)
            return
        tid = self.teams.get(v["team"])
        if tid is None:
            messagebox.showerror("New player", "Choose a club.", parent=self.win)
            return
        try:
            jersey = int(v["jersey"])
        except ValueError:
            jersey = 0
        if not 1 <= jersey <= 99:
            messagebox.showerror("New player", "Shirt number must be 1–99.", parent=self.win)
            return
        if jersey in self._used_numbers(tid) and not messagebox.askyesno(
                "New player", f"Number {jersey} is already taken at this club. Use it anyway?",
                parent=self.win):
            return
        pid = self.app.add_player(template_pid, tid, jersey, v["first"], v["last"],
                                  v["common"], v["jersey_name"], self.ROLES[v["role"]])
        if pid is not None:
            if self.in_game.get():
                self.app.make_in_game_editable(pid, ask=False)
            self.win.destroy()


class CopyLookDialog:
    """Copies chosen look groups from another player onto the selected one."""

    def __init__(self, app):
        if app.current_pid is None:
            return
        self.app = app
        app.root.focus_set()  # commit any half-typed entry first
        self.win = w = tk.Toplevel(app.root)
        w.title(f"Copy look to {app.player_name(app.current_pid)}")
        w.transient(app.root)
        f = ttk.Frame(w, padding=14)
        f.pack(fill="both", expand=True)
        f.columnconfigure(0, weight=1)
        f.rowconfigure(2, weight=1)

        ttk.Label(f, text="Copy from (search name or ID):").grid(row=0, column=0, sticky="w")
        self.q = tk.StringVar()
        e = ttk.Entry(f, textvariable=self.q, width=40)
        e.grid(row=1, column=0, sticky="ew", pady=3)
        self.q.trace_add("write", lambda *_: self._search())
        lb_frame = ttk.Frame(f)
        lb_frame.grid(row=2, column=0, sticky="nsew")
        self.lb = tk.Listbox(lb_frame, height=12, width=48, exportselection=False)
        sb = ttk.Scrollbar(lb_frame, orient="vertical", command=self.lb.yview)
        self.lb.configure(yscrollcommand=sb.set)
        self.lb.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.lb.bind("<<ListboxSelect>>", lambda e: self._on_pick())
        self.lb.bind("<Double-Button-1>", lambda e: self.copy())
        self.info = tk.StringVar()
        ttk.Label(f, textvariable=self.info, style="Sub.TLabel", wraplength=420,
                  justify="left").grid(row=3, column=0, sticky="w", pady=(6, 0))

        groups = ttk.LabelFrame(f, text="What to copy", padding=8)
        groups.grid(row=0, column=1, rowspan=4, sticky="n", padx=(14, 0))
        self.group_vars = {}
        for i, (g, names) in enumerate(LOOK_GROUPS):
            if any(n in app.players.by_name for n in names):
                var = tk.BooleanVar(value=g != "Body")
                ttk.Checkbutton(groups, text=g, variable=var).grid(row=i, column=0,
                                                                   sticky="w", pady=1)
                self.group_vars[g] = var
        P, tr = app.players, app.pid_row[app.current_pid]
        self.target_real = "headclasscode" in P.by_name and P.get(tr, "headclasscode") == 0
        self.make_generic = tk.BooleanVar(value=False)
        if self.target_real:
            ttk.Checkbutton(groups, text="Switch to generic face\n(this player has a real "
                            "face; needed\nfor Face/Hair to show)",
                            variable=self.make_generic).grid(
                row=len(LOOK_GROUPS), column=0, sticky="w", pady=(8, 0))

        btns = ttk.Frame(f)
        btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Close", command=w.destroy).pack(side="right")
        ttk.Button(btns, text="Copy", command=self.copy).pack(side="right", padx=6)
        w.bind("<Return>", lambda e: self.copy())
        w.bind("<Escape>", lambda e: w.destroy())
        self.matches = []
        self._search()
        e.focus_set()

    def _search(self):
        app = self.app
        q = fold(self.q.get().strip())
        P = app.players
        has_ovr = "overallrating" in P.by_name
        hits = [p for p in app.pid_row if p != app.current_pid and
                (not q or q == str(p) or q in fold(app.player_name(p)))]
        if has_ovr:
            hits.sort(key=lambda p: -P.get(app.pid_row[p], "overallrating"))
        self.matches = hits[:300]
        self.lb.delete(0, "end")
        for p in self.matches:
            s = app.summary(p)
            face = "" if "headclasscode" not in P.by_name else (
                "  [real face]" if P.get(app.pid_row[p], "headclasscode") == 0 else "")
            team = s["teams"][0] if s["teams"] else ""
            self.lb.insert("end", f"{s['name']}  ({s['ovr']}, {team}){face}")
        if self.matches:
            self.lb.selection_set(0)
        self._on_pick()

    def _source(self):
        sel = self.lb.curselection()
        return self.matches[sel[0]] if sel else None

    def _on_pick(self):
        src = self._source()
        P = self.app.players
        if src is None or "headclasscode" not in P.by_name:
            self.info.set("")
        elif P.get(self.app.pid_row[src], "headclasscode") == 0:
            self.info.set("This player has a real (scanned) face. The scan itself can't be "
                          "copied; their generic codes (close to the scan) will be.")
        else:
            self.info.set("Generic face: copying Face and Hair & beard gives the same look.")

    def copy(self):
        src = self._source()
        if src is None:
            return
        app = self.app
        groups = [g for g, v in self.group_vars.items() if v.get()]
        P, sr = app.players, app.pid_row[src]
        values = {n: P.get(sr, n) for n in app.look_fields(groups)}
        if self.target_real and self.make_generic.get():
            values.update(headclasscode=1, hashighqualityhead=0)
        if app.set_player_fields(values):
            app.status.set(f"Copied {', '.join(groups) or 'nothing'} from "
                           f"{app.player_name(src)} ({src}).")
        if (self.target_real and not self.make_generic.get() and
                {"Face", "Hair & beard"} & set(groups)):
            messagebox.showinfo("Copy look", (
                "Copied. This player still has a real (scanned) face, so the face and hair "
                "won't change in-game until Face type is set to 'Generic face'."),
                parent=self.win)
        self.win.destroy()


class ColorTriple:
    """A swatch button editing three r/g/b fields of one row together."""

    def __init__(self, owner, parent, table, prefix, gridrow, label, suffixes=("r", "g", "b")):
        self.app, self.table = owner, table
        self.fields = [table.by_name[prefix + s] for s in suffixes]
        self.field = self.fields[0]
        ttk.Label(parent, text=label).grid(row=gridrow, column=0, sticky="w",
                                           padx=(0, 10), pady=2)
        self.button = tk.Button(parent, width=10, relief="groove", command=self._pick)
        self.button.grid(row=gridrow, column=1, sticky="w", pady=2)

    def _hex(self, r):
        return "#%02x%02x%02x" % tuple(max(0, min(255, self.table.get(r, f)))
                                       for f in self.fields)

    def load(self):
        r = self.app.row_for(self.table)
        if r is None:
            return
        h = self._hex(r)
        self.button.configure(bg=h, activebackground=h, text=h)

    def _pick(self):
        r = self.app.row_for(self.table)
        if r is None:
            return
        rgb, _ = colorchooser.askcolor(self._hex(r), parent=self.button)
        if not rgb:
            return
        for f, v in zip(self.fields, rgb):
            self.table.set(r, f, int(v))
        self.app.on_edited(self)


class TeamWindow:
    """Edits one team at a time. Acts as the 'app' for its Bound controls, so it
    provides loading / row_for / on_edited / refresh_controls."""

    def __init__(self, app, team_id=None):
        self.app = app
        self.db = app.db
        self.loading = False
        self.controls = []
        self.rows = {}
        self.tid = None
        self.win = w = tk.Toplevel(app.root)
        w.title("Teams")
        w.geometry("760x720")
        T = self.db.tables["teams"]

        top = ttk.Frame(w, padding=(10, 10, 10, 0))
        top.pack(fill="x")
        ttk.Label(top, text="Team").pack(side="left")
        self.team_var = tk.StringVar()
        self.team_combo = ttk.Combobox(top, textvariable=self.team_var, width=40)
        self.team_combo.pack(side="left", padx=6)
        self.team_combo.bind("<<ComboboxSelected>>", lambda e: self._on_pick())
        self.team_combo.bind("<Return>", lambda e: self._on_pick())
        ttk.Button(top, text="New team…", command=app.new_team).pack(side="right")
        self.info = tk.StringVar()
        ttk.Label(w, textvariable=self.info, style="Sub.TLabel", padding=(10, 4)).pack(
            anchor="w")

        nb = ttk.Notebook(w)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        outer, f = scrollable(nb)
        nb.add(outer, text="Club")
        r = 0
        self.controls.append(NumberEntry(self, f, T, "teamname", r))
        r += 1
        L = self.db.tables.get("leagueteamlinks")
        if L is not None:
            self.controls.append(Choice(self, f, L, "leagueid", r, app.league_options()))
            r += 1
        for name in ("domesticprestige", "internationalprestige", "transferbudget",
                     "clubworth", "foundationyear", "teamstadiumcapacity"):
            if name in T.by_name:
                self.controls.append(NumberEntry(self, f, T, name, r))
                r += 1
        S = self.db.tables.get("teamstadiumlinks")
        if S is not None:
            self.controls.append(NumberEntry(self, f, S, "stadiumname", r))
            r += 1
        M = self.db.tables.get("manager")
        if M is not None:
            for name, label in (("firstname", "Manager first name"),
                                ("surname", "Manager surname")):
                self.controls.append(NumberEntry(self, f, M, name, r, label=label))
                r += 1
        for i in (1, 2, 3):
            self.controls.append(ColorTriple(self, f, T, f"teamcolor{i}", r, f"Team colour {i}"))
            r += 1
        lf = ttk.LabelFrame(f, text="Names on screen (language files)", padding=8)
        lf.grid(row=r, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        r += 1
        self.loc_vars = []
        for i, label in enumerate(("Full name", "15 letters", "10 letters", "3 letters",
                                   "Commentary/short")):
            ttk.Label(lf, text=label).grid(row=i, column=0, sticky="w", padx=(0, 10))
            var = tk.StringVar()
            ttk.Entry(lf, textvariable=var, width=34).grid(row=i, column=1, sticky="w", pady=1)
            self.loc_vars.append(var)
        btns = ttk.Frame(lf)
        btns.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(btns, text="Fill from team name", command=self._fill_loc_names).pack(
            side="left")
        ttk.Button(btns, text="Apply", command=self._apply_loc_names).pack(side="left", padx=6)
        self.loc_info = tk.StringVar()
        ttk.Label(lf, textvariable=self.loc_info, style="Sub.TLabel", wraplength=600,
                  justify="left").grid(row=6, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Label(f, style="Sub.TLabel", justify="left", wraplength=620, text=(
            "Team colours are used for menus, scoreboards and generic kits. Crest and "
            "shirt images are graphics in the game files, not in this database; they are "
            "found by assetid (crest) and team id (kits).")).grid(
            row=r, column=0, columnspan=3, sticky="w", pady=(10, 0))

        outer, f = scrollable(nb)
        nb.add(outer, text="Ratings")
        f.columnconfigure(1, weight=1)
        for i, name in enumerate(("overallrating", "attackrating", "midfieldrating",
                                  "defenserating")):
            self.controls.append(AttrSlider(self, f, T, name, i))

        K = self.db.tables.get("teamkits")
        if K is not None:
            outer, f = scrollable(nb)
            nb.add(outer, text="Kits")
            self.kit_frame = f
            self.kit_controls = []

        outer, f = scrollable(nb)
        nb.add(outer, text="Squad")
        self.squad = ttk.Treeview(f, columns=("id", "name", "ovr", "pos", "no"),
                                  show="headings", height=24)
        for c, h, wd in (("id", "ID", 70), ("name", "Name", 260), ("ovr", "OVR", 50),
                         ("pos", "Pos", 50), ("no", "No.", 50)):
            self.squad.heading(c, text=h)
            self.squad.column(c, width=wd, anchor="w" if c == "name" else "center")
        self.squad.pack(fill="both", expand=True)
        self.squad.bind("<Double-1>", self._open_player)
        ttk.Label(f, style="Sub.TLabel", text=(
            "Double-click a player to edit him. To move a player to another club, use the "
            "Club tab in the main window.")).pack(anchor="w", pady=6)

        outer, f = scrollable(nb)
        nb.add(outer, text="All fields")
        for i, fld in enumerate(T.fields):
            if fld.name != "teamid":
                self.controls.append(NumberEntry(self, f, T, fld.name, i, label=fld.name))

        self._fill_combo()
        self.reload(team_id if team_id is not None else
                    next(iter(app.team_options()), None))

    def _fill_combo(self):
        self.options = self.app.team_options()
        self.reverse = {v: k for k, v in self.options.items()}
        self.team_combo.configure(values=list(self.options.values()))

    def _on_pick(self):
        text = self.team_var.get().strip()
        tid = self.reverse.get(text)
        if tid is None:  # typed: accept an id or the start of a name
            tid = next((k for k, v in self.options.items()
                        if text.isdigit() and k == int(text) or fold(v).startswith(fold(text))),
                       None)
        if tid is not None:
            self.win.focus_set()
            self.reload(tid)

    def reload(self, tid):
        if tid is None:
            return
        self.tid = tid
        self.rows = {}
        for tname in ("teams", "leagueteamlinks", "teamstadiumlinks", "manager"):
            t = self.db.tables.get(tname)
            if t is not None:
                found = fifadb.rows_where(t, "teamid", tid)
                self.rows[tname] = found[0] if found else None
        self.team_var.set(self.options.get(tid, str(tid)))
        T = self.db.tables["teams"]
        tr = self.rows.get("teams")
        asset = T.get(tr, "assetid") if tr is not None else "?"
        slot = next((s for s in fifadb.KIT_SLOTS if s[0] == tid), None)
        kits = (f"kits in Frosty: {fifadb.kit_folder(tid, slot[1])}/" if slot else
                f"kits in Frosty: content/character/kit/kit_{tid // 500 * 500}/…_{tid}/")
        if asset == tid:
            crest = "its own"
        elif asset in crests.SPARE_CRESTS:
            crest = f"{crests.SPARE_CRESTS[asset]}'s (ships with the game)"
        else:
            crest = f"{self.app.team_names.get(asset, '?')}'s (borrowed)"
        self.info.set(f"Team id {tid}  ·  crest: {crest}, data/ui/imgAssets/crest*/l{asset}.dds"
                      f"\n{kits}")
        self._build_kits()
        self.refresh_controls()
        self.refresh_squad()
        self.load_loc_names()

    def load_loc_names(self):
        locs = self.app.locs
        if not locs:
            for v in self.loc_vars:
                v.set("")
            self.loc_info.set("No language files open. The game shows names from "
                              "data/loc/<language>.db when it has them for this team id, "
                              "otherwise the database name above. Export them in Frosty "
                              "(Legacy Explorer ▸ data/loc) and use File ▸ Open language "
                              "files….")
            return
        names = locs[0].team_names(self.tid)
        for v, key in zip(self.loc_vars, fifadb.LocFile.TEAM_KEYS):
            v.set(names.get(key.format(self.tid)) or "")
        have = [k.format(self.tid) for k in fifadb.LocFile.TEAM_KEYS
                if k.format(self.tid) in names]
        langs = ", ".join(l.language for l in locs)
        self.loc_info.set(
            (f"Keys in the language files: {', '.join(have)}. " if have else
             "This team id has no names in the language files, so the game uses the "
             "database name; nothing to change here. ") +
            f"Open: {langs}. Empty boxes and missing keys are left alone.")

    def _fill_loc_names(self):
        tr = self.rows.get("teams")
        if tr is None:
            return
        name = self.db.tables["teams"].get(tr, "teamname")
        a15, a10, a3 = fifadb.short_names(name)
        for v, text in zip(self.loc_vars, (name, a15, a10, a3, a10)):
            v.set(text)

    def _apply_loc_names(self):
        if not self.app.locs:
            self.app.open_locs()
            if not self.app.locs:
                return
        self.app.set_team_loc_names(self.tid, [v.get().strip() for v in self.loc_vars])
        self.load_loc_names()

    def _build_kits(self):
        if not hasattr(self, "kit_frame"):
            return
        for wdg in self.kit_frame.winfo_children():
            wdg.destroy()
        self.kit_controls = []
        K = self.db.tables["teamkits"]
        kinds = {0: "Home", 1: "Away", 2: "Goalkeeper", 3: "Third", 5: "Goalkeeper 2"}
        r = 0
        for kr in fifadb.rows_where(K, "teamtechid", self.tid):
            kind = K.get(kr, "teamkittypetechid")
            lf = ttk.LabelFrame(self.kit_frame, text=kinds.get(kind, f"Kit type {kind}"),
                                padding=8)
            lf.grid(row=r, column=0, sticky="ew", pady=4)
            r += 1
            owner = _FixedRow(self, K, kr)
            for i, (prefix, label, sfx) in enumerate((
                    ("teamcolorprim", "Primary", ("r", "g", "b")),
                    ("teamcolorsec", "Secondary", ("r", "g", "b")),
                    ("teamcolortert", "Tertiary", ("r", "g", "b")),
                    ("jerseynumbercolorprim", "Shirt numbers", ("r", "g", "b")),
                    ("jerseynamecolor", "Shirt name", ("r", "g", "b")))):
                self.kit_controls.append(ColorTriple(owner, lf, K, prefix, i, label, sfx))
            for c in self.kit_controls[-5:]:
                c.load()
        if r == 0:
            ttk.Label(self.kit_frame, text="This team has no kit rows.").grid(row=0, column=0)
        else:
            ttk.Label(self.kit_frame, style="Sub.TLabel", wraplength=620, justify="left",
                      text=("These colours drive kit details the game renders itself "
                            "(numbers, names, and generic kits). The shirt design is a "
                            "texture named after the team id, edited in Frosty.")).grid(
                row=r, column=0, sticky="w", pady=8)

    def refresh_squad(self):
        app = self.app
        self.squad.delete(*self.squad.get_children())
        tpl = app.tpl
        if tpl is None:
            return
        rows = []
        for r in fifadb.rows_where(tpl, "teamid", self.tid):
            pid = tpl.get(r, "playerid")
            if pid in app.pid_row:
                s = app.summary(pid)
                rows.append((pid, s["name"], s["ovr"], s["pos"], tpl.get(r, "jerseynumber")))
        for row in sorted(rows, key=lambda x: -x[2] if isinstance(x[2], int) else 0):
            self.squad.insert("", "end", iid=str(row[0]), values=row)
        self.win.title(f"Teams — {len(rows)} players in squad")

    def _open_player(self, _):
        sel = self.squad.selection()
        if not sel:
            return
        app = self.app
        app.search_var.set("")
        app.current_pid = int(sel[0])
        app.refresh_list()
        app.refresh_controls()
        app.root.lift()

    # -- 'app' interface for the Bound controls ------------------------------
    def row_for(self, table):
        return self.rows.get(table.name)

    def refresh_controls(self):
        self.loading = True
        try:
            for c in self.controls:
                c.load()
        finally:
            self.loading = False

    def on_edited(self, control):
        if control.field.name == "teamname" and control.table.name == "teams":
            self.app.after_teams_changed()
            self._fill_combo()
            self.team_var.set(self.options.get(self.tid, ""))
        self.refresh_controls()
        self.app.update_status()


class _FixedRow:
    """'app' stand-in that binds controls to one specific row (a kit)."""

    def __init__(self, window, table, row):
        self.window, self.table, self.row = window, table, row

    def row_for(self, table):
        return self.row if table is self.table else None

    def on_edited(self, control):
        control.load()
        self.window.app.update_status()


class NewTeamDialog:
    def __init__(self, app):
        self.app = app
        self.win = w = tk.Toplevel(app.root)
        w.title("New team")
        w.transient(app.root)
        w.resizable(False, False)
        f = ttk.Frame(w, padding=14)
        f.pack(fill="both", expand=True)
        self.teams = {v: k for k, v in app.team_options().items()}
        self.leagues = {v: k for k, v in app.league_options().items()}

        kind = {(0, 1, 2): "home, away, GK", (0, 2): "home, GK only"}
        self.slots = {f"{folder} ({tid}) — {kind.get(kits, kits)}": tid
                      for tid, folder, kits in fifadb.free_kit_slots(app.db)}
        self.slots["New id — no kits exist (shows missing textures)"] = None

        self.template = tk.StringVar()
        self.name = tk.StringVar()
        self.league = tk.StringVar()
        self.slot = tk.StringVar(value=next(iter(self.slots)))
        self.squad = tk.StringVar(value=fifadb.SQUAD_COPY)
        self.crests = {"The kit slot's own crest (replace its images in Frosty)": "own",
                       "The template team's crest": "template"}
        self.crests.update({f"{n} ({i}) — real crest in the game": i for i, n in
                            sorted(crests.SPARE_CRESTS.items(), key=lambda kv: fold(kv[1]))})
        self.crest = tk.StringVar(value=next(iter(self.crests)))
        rows = (("Copy everything from", ttk.Combobox(f, textvariable=self.template,
                                                      values=list(self.teams), width=40,
                                                      state="readonly")),
                ("Team name", ttk.Entry(f, textvariable=self.name, width=42)),
                ("League", ttk.Combobox(f, textvariable=self.league,
                                        values=list(self.leagues), width=40,
                                        state="readonly")),
                ("Kit slot", ttk.Combobox(f, textvariable=self.slot,
                                          values=list(self.slots), width=40,
                                          state="readonly")),
                ("Crest", ttk.Combobox(f, textvariable=self.crest,
                                       values=list(self.crests), width=40,
                                       state="readonly")))
        for i, (label, widget) in enumerate(rows):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w", pady=3)
            widget.grid(row=i, column=1, sticky="w", pady=3)
        cur = None
        if app.current_pid is not None and app.pid_links.get(app.current_pid):
            cur = app.tpl.get(app.pid_links[app.current_pid][0], "teamid")
        opts = app.team_options()
        self.template.set(opts.get(cur, next(iter(opts.values()), "")))
        row = next((k for k, v in self.leagues.items() if v == fifadb.LEAGUE_REST_OF_WORLD),
                   "")
        self.league.set(row)
        sq = ttk.LabelFrame(f, text="Squad", padding=8)
        sq.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        for value, text in (
                (fifadb.SQUAD_COPY, "Copy the players: new players with the same names and "
                                    "stats, but generic faces"),
                (fifadb.SQUAD_SHARE, "Use the same players: real faces, but they also stay "
                                     "at their club\n(don't play the two teams against "
                                     "each other; may confuse career mode)"),
                (fifadb.SQUAD_EMPTY, "Empty: add players yourself (needs at least 18 to "
                                     "play)")):
            ttk.Radiobutton(sq, text=text, value=value, variable=self.squad).pack(
                anchor="w", pady=1)
        ttk.Label(f, style="Sub.TLabel", justify="left", text=(
            "Rest of World is the safe league: other leagues have a fixed number of teams\n"
            "in career mode. Kit graphics only exist for team ids the game ships, so pick a\n"
            "kit slot and restyle its kits in Frosty (the Teams window shows the folder).\n"
            "Kit slots have names in the language files: open them (File menu) first so\n"
            "they get your team's name.")).grid(
            row=6, column=0, columnspan=2, sticky="w", pady=(10, 0))
        btns = ttk.Frame(f)
        btns.grid(row=7, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(btns, text="Cancel", command=w.destroy).pack(side="right")
        ttk.Button(btns, text="Create", command=self.create).pack(side="right", padx=6)
        w.bind("<Escape>", lambda e: w.destroy())
        w.grab_set()

    def create(self):
        tid = self.teams.get(self.template.get())
        name = self.name.get().strip()
        league = self.leagues.get(self.league.get())
        if tid is None or league is None:
            messagebox.showerror("New team", "Choose a template team and a league.",
                                 parent=self.win)
            return
        if not name:
            messagebox.showerror("New team", "Enter a team name.", parent=self.win)
            return
        size = self.app.db.tables["teams"].by_name["teamname"].depth // 8 - 1
        if len(name.encode("utf-8")) > size:
            messagebox.showerror("New team", f"The name can be at most {size} bytes.",
                                 parent=self.win)
            return
        crest = self.crests.get(self.crest.get(), "own")
        slot = self.slots.get(self.slot.get())
        if crest == "template" or (crest == "own" and slot is None):
            T = self.app.db.tables["teams"]
            crest = T.get(fifadb.rows_where(T, "teamid", tid)[0], "assetid")
        self.win.grab_release()
        self.win.destroy()
        self.app.add_team(tid, name, league, self.squad.get(), slot,
                          None if crest == "own" else crest)


def main():
    root = tk.Tk()
    app = EditorApp(root)
    if len(sys.argv) > 1:
        root.after(50, lambda: app.open(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
    else:
        last = read_json(SETTINGS_PATH) or {}
        db, meta = last.get("last_database"), last.get("last_meta")
        if db and os.path.isfile(db):
            root.after(50, lambda: app.open(db, meta if meta and os.path.isfile(meta)
                                            else None))
    root.mainloop()


if __name__ == "__main__":
    main()
