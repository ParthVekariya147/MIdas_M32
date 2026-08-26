"""
m32_gui.py  -  MIDAS M32 AUTO FX  --  screen wado (front-end) program.

Badhu TOGGLE BUTTON thi chalu/band thay chhe:
  * Upar     : mixer sathe judaan
  * Dabi     : 32 channel -- dareki no potano toggle
  * Jamni    : shu control karvu -- dareka target no potano toggle
  * Niche    : FEATURE toggle (Safe Mode, Auto FX, log ...) ane slider
  * Chhelle  : MOTO toggle -- aakhu automation chalu / band

Chalavva:  0-START-GUI.bat  athva  python m32_app.py
"""

import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

import m32_core as core
import m32_engine

NUM_CHANNELS = 32

BG = "#1b1b1b"
PANEL = "#232323"
FG = "#eaeaea"
DIM = "#8d8d8d"
GREEN = "#3fbf5f"
RED = "#e05252"
BLUE = "#4a9eff"
TRACK = "#3a3a3a"


# ====================================================================== toggle
class Toggle(tk.Canvas):
    """
    Chalu/Band karva no toggle button (mobile ma hoy chhe tevo).
    Dabavo etle sarki jay: lilo = CHALU, kaalo = BAND.
    """

    def __init__(self, master, variable=None, command=None,
                 width=46, height=24, bg=BG):
        tk.Canvas.__init__(self, master, width=width, height=height,
                           bg=bg, highlightthickness=0, cursor="hand2")
        self.w, self.h = width, height
        self.var = variable if variable is not None else tk.BooleanVar(value=False)
        self.command = command
        self._enabled = True

        r = height
        self.track_l = self.create_oval(0, 0, r, r, width=0)
        self.track_r = self.create_oval(width - r, 0, width, r, width=0)
        self.track_m = self.create_rectangle(r / 2, 0, width - r / 2, r, width=0)
        pad = 3
        self.knob = self.create_oval(pad, pad, r - pad, r - pad,
                                     fill="#d8d8d8", width=0)

        self.bind("<Button-1>", self._clicked)
        self.var.trace_add("write", lambda *_: self._redraw())
        self._redraw()

    def _clicked(self, _event=None):
        if not self._enabled:
            return
        self.var.set(not self.var.get())
        if self.command:
            self.command(self.var.get())

    def set_enabled(self, on):
        self._enabled = bool(on)
        self.configure(cursor="hand2" if on else "arrow")
        self._redraw()

    def _redraw(self):
        on = bool(self.var.get())
        if not self._enabled:
            colour, knob = "#2c2c2c", "#5a5a5a"
        else:
            colour = GREEN if on else TRACK
            knob = "#ffffff" if on else "#9a9a9a"
        for item in (self.track_l, self.track_r, self.track_m):
            self.itemconfig(item, fill=colour)
        self.itemconfig(self.knob, fill=knob)

        pad = 3
        r = self.h
        x = (self.w - r + pad) if on else pad
        self.coords(self.knob, x, pad, x + r - 2 * pad, r - pad)


class LevelBar(tk.Canvas):
    """Nano level meter (lilo -> pilo -> laal)."""

    def __init__(self, master, width=104, height=11, bg=BG):
        tk.Canvas.__init__(self, master, width=width, height=height,
                           bg="#2c2c2c", highlightthickness=0)
        self.w, self.h = width, height
        self.bar = self.create_rectangle(0, 0, 0, height, fill=GREEN, width=0)
        self.mark = self.create_line(0, 0, 0, height, fill="#ffffff", width=1)

    def set(self, db, threshold=None):
        lo, hi = -70.0, 0.0
        frac = (max(lo, min(hi, db)) - lo) / (hi - lo)
        colour = GREEN if db < -18 else ("#e0c040" if db < -6 else RED)
        self.coords(self.bar, 0, 0, int(frac * self.w), self.h)
        self.itemconfig(self.bar, fill=colour)
        if threshold is not None:
            tx = int(((max(lo, min(hi, threshold)) - lo) / (hi - lo)) * self.w)
            self.coords(self.mark, tx, 0, tx, self.h)


# ====================================================================== app
class App:
    def __init__(self, root):
        self.root = root
        self.cfg = core.load_config()
        self.engine = None
        self.events = queue.Queue()
        self.names = {}
        self._target_paths = []
        self._target_off = set()

        root.title("MIDAS M32  --  Auto FX Mute")
        root.configure(bg=BG)
        root.geometry("1100x780")
        root.minsize(960, 700)

        self._init_style()
        self._build()
        self._load_into_widgets()

        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(100, self._pump)
        self.connect()

    # ------------------------------------------------------------ style
    def _init_style(self):
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure(".", background=BG, foreground=FG, fieldbackground="#2c2c2c")
        st.configure("TFrame", background=BG)
        st.configure("Panel.TFrame", background=PANEL)
        st.configure("TLabel", background=BG, foreground=FG)
        st.configure("Panel.TLabel", background=PANEL, foreground=FG)
        st.configure("Dim.TLabel", background=BG, foreground=DIM)
        st.configure("PanelDim.TLabel", background=PANEL, foreground=DIM)
        st.configure("Head.TLabel", font=("Segoe UI", 10, "bold"), foreground=BLUE)
        st.configure("Big.TLabel", font=("Consolas", 14, "bold"))
        st.configure("TButton", padding=4)
        st.configure("TLabelframe", background=BG, foreground=BLUE)
        st.configure("TLabelframe.Label", background=BG, foreground=BLUE,
                     font=("Segoe UI", 10, "bold"))

    # ------------------------------------------------------------ layout
    def _build(self):
        root = self.root
        self._build_top(root)

        mid = ttk.Frame(root, padding=(10, 0))
        mid.pack(fill="both", expand=True)
        mid.columnconfigure(0, weight=3)
        mid.columnconfigure(1, weight=2)
        mid.rowconfigure(0, weight=1)
        self._build_channels(mid)
        self._build_targets(mid)

        self._build_features(root)
        self._build_bottom(root)

    # ---------------------------------------------- top
    def _build_top(self, root):
        top = ttk.Frame(root, padding=(10, 8))
        top.pack(fill="x")

        ttk.Label(top, text="Mixer IP:").pack(side="left")
        self.ip_var = tk.StringVar(value=self.cfg.get("mixer_ip", ""))
        ttk.Entry(top, textvariable=self.ip_var, width=15).pack(side="left", padx=6)
        ttk.Button(top, text="Judo", command=self.connect).pack(side="left")
        ttk.Button(top, text="Network ma shodho",
                   command=self.find_mixer).pack(side="left", padx=6)

        self.conn_dot = tk.Canvas(top, width=14, height=14, bg=BG,
                                  highlightthickness=0)
        self.conn_dot.pack(side="left", padx=(14, 4))
        self.dot = self.conn_dot.create_oval(2, 2, 12, 12, fill=RED, width=0)
        self.conn_var = tk.StringVar(value="judai nathi")
        ttk.Label(top, textvariable=self.conn_var).pack(side="left")

    # ---------------------------------------------- channels
    def _build_channels(self, parent):
        box = ttk.Labelframe(parent, text=" 1)  KAYA MIC SAMBHALVA ? ", padding=6)
        box.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=6)

        bar = ttk.Frame(box)
        bar.pack(fill="x", pady=(0, 4))
        ttk.Button(bar, text="Badha band",
                   command=lambda: self._set_all_channels(False)).pack(side="left")
        ttk.Button(bar, text="Naam fari vancho",
                   command=self.refresh_names).pack(side="left", padx=6)
        ttk.Label(bar, text="toggle CHALU = te mic sambhalse",
                  style="Dim.TLabel").pack(side="left", padx=6)

        canvas = tk.Canvas(box, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(box, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        hdr = ttk.Frame(inner)
        hdr.grid(row=0, column=0, sticky="w", pady=(0, 2))
        for text, w in (("ON/OFF", 9), ("CH", 4), ("NAAM", 15),
                        ("LEVEL", 14), ("dB", 7)):
            ttk.Label(hdr, text=text, width=w, style="Dim.TLabel").pack(side="left")

        self.ch_vars, self.ch_names, self.ch_bars, self.ch_dbs = {}, {}, {}, {}
        for ch in range(1, NUM_CHANNELS + 1):
            row = ttk.Frame(inner)
            row.grid(row=ch, column=0, sticky="w", pady=1)

            var = tk.BooleanVar(value=False)
            self.ch_vars[ch] = var
            Toggle(row, variable=var, command=lambda _v: self._channels_changed(),
                   width=38, height=19).pack(side="left", padx=(4, 12))

            ttk.Label(row, text="%d" % ch, width=4).pack(side="left")
            nm = ttk.Label(row, text="-", width=15, anchor="w", style="Dim.TLabel")
            nm.pack(side="left")
            self.ch_names[ch] = nm

            b = LevelBar(row)
            b.pack(side="left", padx=4)
            self.ch_bars[ch] = b

            db = ttk.Label(row, text="", width=8, anchor="e", style="Dim.TLabel")
            db.pack(side="left")
            self.ch_dbs[ch] = db

    # ---------------------------------------------- targets
    def _build_targets(self, parent):
        box = ttk.Labelframe(parent, text=" 2)  SHU CHALU / BAND KARVU ? ", padding=6)
        box.grid(row=0, column=1, sticky="nsew", pady=6)

        pick = ttk.Frame(box)
        pick.pack(fill="x")
        self.cat_var = tk.StringVar(value="Mute Group")
        cb = ttk.Combobox(pick, textvariable=self.cat_var, state="readonly",
                          values=[g for g, _ in core.target_catalog()])
        cb.pack(side="left", fill="x", expand=True)
        cb.bind("<<ComboboxSelected>>", lambda e: self._fill_catalog())
        ttk.Button(pick, text="UMERO", command=self.add_target).pack(side="left",
                                                                    padx=(6, 0))

        self.cat_list = tk.Listbox(box, height=7, selectmode="extended",
                                   bg="#2c2c2c", fg=FG, highlightthickness=0,
                                   selectbackground=BLUE, activestyle="none",
                                   borderwidth=0)
        self.cat_list.pack(fill="both", expand=True, pady=(4, 8))
        self.cat_list.bind("<Double-Button-1>", lambda e: self.add_target())

        ttk.Label(box, text="Pasand thayela  (toggle thi chalu/band):",
                  style="Head.TLabel").pack(anchor="w")

        self.tgt_holder = ttk.Frame(box, style="Panel.TFrame", padding=4)
        self.tgt_holder.pack(fill="both", expand=True, pady=(3, 6))

        row = ttk.Frame(box)
        row.pack(fill="x")
        ttk.Button(row, text="TEST (3 var on/off)",
                   command=self.test_targets).pack(side="left")
        ttk.Label(row, text="mixer ni screen juo",
                  style="Dim.TLabel").pack(side="left", padx=6)

        row2 = ttk.Frame(box)
        row2.pack(fill="x", pady=(6, 0))
        ttk.Label(row2, text="Custom OSC:", style="Dim.TLabel").pack(side="left")
        self.custom_var = tk.StringVar()
        ttk.Entry(row2, textvariable=self.custom_var).pack(
            side="left", fill="x", expand=True, padx=4)
        ttk.Button(row2, text="+", width=3, command=self.add_custom).pack(side="left")

        self._fill_catalog()

    # ---------------------------------------------- features + sliders
    def _build_features(self, root):
        box = ttk.Labelframe(root, text=" 3)  FEATURES  ane  SETTINGS ", padding=8)
        box.pack(fill="x", padx=10, pady=(2, 4))

        # ---- feature toggle ----
        feats = ttk.Frame(box)
        feats.pack(fill="x")
        self.feat_vars = {}
        saved = self.cfg.get("features") or {}

        keys = [k for k in core.FEATURES if k != "auto_fx"]
        per_col = (len(keys) + 2) // 3
        for i, key in enumerate(keys):
            name, hint, default = core.FEATURES[key]
            col, rowi = divmod(i, per_col)
            cell = ttk.Frame(feats)
            cell.grid(row=rowi, column=col, sticky="w", padx=(0, 24), pady=3)

            var = tk.BooleanVar(value=bool(saved.get(key, default)))
            self.feat_vars[key] = var
            Toggle(cell, variable=var, width=40, height=20,
                   command=lambda v, k=key: self._feature_changed(k, v)
                   ).pack(side="left", padx=(0, 8))
            text = ttk.Frame(cell)
            text.pack(side="left")
            ttk.Label(text, text=name).pack(anchor="w")
            ttk.Label(text, text=hint, style="Dim.TLabel",
                      font=("Segoe UI", 8)).pack(anchor="w")
        for c in range(3):
            feats.columnconfigure(c, weight=1)

        ttk.Separator(box, orient="horizontal").pack(fill="x", pady=8)

        # ---- slider ----
        sl = ttk.Frame(box)
        sl.pack(fill="x")
        self.th_var = tk.DoubleVar(value=self.cfg.get("threshold_db", -40.0))
        self.hold_var = tk.DoubleVar(value=self.cfg.get("hold_time", 1.5))
        self.atk_var = tk.DoubleVar(value=self.cfg.get("attack_time", 0.02))

        def slider(col, text, var, lo, hi, fmt, hint):
            f = ttk.Frame(sl)
            f.grid(row=0, column=col, sticky="ew", padx=(0, 18))
            sl.columnconfigure(col, weight=1)
            head = ttk.Frame(f)
            head.pack(fill="x")
            ttk.Label(head, text=text).pack(side="left")
            lbl = ttk.Label(head, text=fmt % var.get(), style="Big.TLabel")
            lbl.pack(side="right")
            ttk.Scale(f, from_=lo, to=hi, variable=var, orient="horizontal",
                      command=lambda v: self._slider_moved(lbl, fmt, var)
                      ).pack(fill="x")
            ttk.Label(f, text=hint, style="Dim.TLabel",
                      font=("Segoe UI", 8)).pack(anchor="w")
            return lbl

        self.th_lbl = slider(0, "Sensitivity", self.th_var, -70, -10, "%.1f dB",
                             "dabu = vadhare sensitive")
        self.hold_lbl = slider(1, "Hold time", self.hold_var, 0.2, 6.0, "%.2f s",
                               "band thaya pachhi ketlu chalu rakhvu")
        self.atk_lbl = slider(2, "Attack", self.atk_var, 0.0, 0.5, "%.2f s",
                              "khaasi thi chalu na thay te mate vadharo")

    # ---------------------------------------------- bottom
    def _build_bottom(self, root):
        bar = ttk.Frame(root, padding=(10, 4))
        bar.pack(fill="x")

        run_box = ttk.Frame(bar)
        run_box.pack(side="left")
        self.run_var = tk.BooleanVar(value=False)
        self.run_toggle = Toggle(run_box, variable=self.run_var, width=70,
                                 height=34, command=self._run_toggled)
        self.run_toggle.pack(side="left")
        txt = ttk.Frame(run_box)
        txt.pack(side="left", padx=10)
        self.run_lbl = ttk.Label(txt, text="AUTOMATION  BAND",
                                 font=("Segoe UI", 12, "bold"))
        self.run_lbl.pack(anchor="w")
        ttk.Label(txt, text="chalu karo etle mixer par command jashe",
                  style="Dim.TLabel").pack(anchor="w")

        ttk.Button(bar, text="SAVE settings",
                   command=self.save_settings).pack(side="left", padx=20)

        self.fx_lbl = ttk.Label(bar, text="FX: --", style="Big.TLabel")
        self.fx_lbl.pack(side="right", padx=10)
        self.lvl_lbl = ttk.Label(bar, text="-- dB", style="Big.TLabel")
        self.lvl_lbl.pack(side="right")

        logbox = ttk.Labelframe(root, text=" Shu shu thayu ", padding=4)
        logbox.pack(fill="both", expand=False, padx=10, pady=(2, 8))
        self.log = tk.Text(logbox, height=7, bg="#121212", fg="#c8c8c8",
                           relief="flat", font=("Consolas", 9), wrap="none")
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

    # ------------------------------------------------------------ helpers
    def _slider_moved(self, lbl, fmt, var):
        lbl.configure(text=fmt % var.get())
        if self.engine:
            self.engine.set_params(threshold_db=self.th_var.get(),
                                   hold_time=self.hold_var.get(),
                                   attack_time=self.atk_var.get())

    def _feature_changed(self, key, value):
        if self.engine:
            self.engine.set_feature(key, value)
        else:
            self.logline("%s : %s" % (core.FEATURES[key][0],
                                      "CHALU" if value else "BAND"))

    def features_dict(self):
        d = {k: bool(v.get()) for k, v in self.feat_vars.items()}
        d["auto_fx"] = True
        return d

    def _fill_catalog(self):
        self.cat_list.delete(0, "end")
        self._cat_paths = []
        for group, items in core.target_catalog():
            if group == self.cat_var.get():
                for _label, path in items:
                    self.cat_list.insert("end", core.target_label(path, self.names))
                    self._cat_paths.append(path)

    def _refresh_targets(self):
        for w in self.tgt_holder.winfo_children():
            w.destroy()
        if not self._target_paths:
            ttk.Label(self.tgt_holder, text="  (kai pasand karyu nathi)",
                      style="PanelDim.TLabel").pack(anchor="w")
            return
        for path in list(self._target_paths):
            row = ttk.Frame(self.tgt_holder, style="Panel.TFrame")
            row.pack(fill="x", pady=1)
            var = tk.BooleanVar(value=path not in self._target_off)
            Toggle(row, variable=var, width=38, height=19, bg=PANEL,
                   command=lambda v, p=path: self._target_toggled(p, v)
                   ).pack(side="left", padx=(2, 8))
            ttk.Label(row, text=core.target_label(path, self.names),
                      style="Panel.TLabel").pack(side="left")
            ttk.Button(row, text="x", width=2,
                       command=lambda p=path: self.remove_target(p)).pack(side="right")

    def _target_toggled(self, path, on):
        if on:
            self._target_off.discard(path)
        else:
            self._target_off.add(path)
        self.logline("%s : %s" % (core.target_label(path, self.names),
                                  "chalu" if on else "band"))
        self._push_targets()

    def _enabled_targets(self):
        return [p for p in self._target_paths if p not in self._target_off]

    def _set_all_channels(self, on):
        for var in self.ch_vars.values():
            var.set(on)
        self._channels_changed()

    def _channels_changed(self):
        if self.engine:
            self.engine.set_params(meter_index=self._selected_indexes())

    def _selected_indexes(self):
        idx = [ch - 1 for ch in range(1, NUM_CHANNELS + 1) if self.ch_vars[ch].get()]
        return idx or [0]

    def _load_into_widgets(self):
        for i in core.parse_indexes(self.cfg.get("meter_index", 0)):
            if 0 <= i < NUM_CHANNELS:
                self.ch_vars[i + 1].set(True)
        self._target_paths = list(self.cfg.get("fx_targets") or [])
        self._target_off = set(self.cfg.get("fx_targets_off") or [])
        self._refresh_targets()

    def logline(self, msg):
        self.log.configure(state="normal")
        self.log.insert("end", "%s  %s\n" % (time.strftime("%H:%M:%S"), msg))
        if int(self.log.index("end-1c").split(".")[0]) > 300:
            self.log.delete("1.0", "50.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ------------------------------------------------------------ targets
    def add_target(self):
        for i in self.cat_list.curselection():
            path = self._cat_paths[i]
            if path not in self._target_paths:
                self._target_paths.append(path)
                self._target_off.discard(path)
        self._refresh_targets()
        self._push_targets()

    def add_custom(self):
        path = self.custom_var.get().strip()
        if not path.startswith("/"):
            messagebox.showwarning("Khoto path",
                                   "OSC path '/' thi shuru thavo joiye.\n"
                                   "Dakhla: /config/mute/5")
            return
        if path not in self._target_paths:
            self._target_paths.append(path)
        self.custom_var.set("")
        self._refresh_targets()
        self._push_targets()

    def remove_target(self, path=None):
        if path is None:
            return
        if path in self._target_paths:
            self._target_paths.remove(path)
        self._target_off.discard(path)
        self._refresh_targets()
        self._push_targets()

    def _push_targets(self):
        if self.engine:
            self.engine.set_params(fx_targets=self._enabled_targets())

    def test_targets(self):
        targets = self._enabled_targets()
        if not targets:
            messagebox.showinfo("Kai pasand nathi",
                                "Pehla jamni baju thi kaik UMERO ane"
                                " teno toggle CHALU rakho.")
            return
        if not self.engine:
            return
        self.logline("TEST shuru -- mixer ni screen juo (3 var on/off)")
        threading.Thread(target=self._test_worker, args=(targets,),
                         daemon=True).start()

    def _test_worker(self, targets):
        inv = self.cfg.get("invert", "auto")
        for _ in range(3):
            for audible in (False, True):
                for p in targets:
                    self.engine.send_raw(p, core.mute_value(p, audible, inv))
                self.events.put(("log", "  TEST -> %s"
                                 % ("CHALU (unmute)" if audible else "BAND (mute)")))
                time.sleep(1.5)
        for p in targets:
            self.engine.send_raw(p, core.mute_value(p, False, inv))
        self.events.put(("log", "TEST puro (chhelle BAND kari didhu)"))

    # ------------------------------------------------------------ connect
    def refresh_names(self):
        if self.engine:
            self.engine.request_names()
            self.logline("Channel na naam fari vanchu chhu...")

    def find_mixer(self):
        self.logline("Network ma mixer shodhu chhu... (5 second)")
        threading.Thread(target=self._find_worker, daemon=True).start()

    def _find_worker(self):
        try:
            import find_mixer
            found = find_mixer.scan(5.0)
        except Exception as e:
            self.events.put(("log", "[!] Shodhi na shakayu: %s" % e))
            return
        if not found:
            self.events.put(("log", "[X] Koi mixer na malyu -- LAN cable check karo"))
            return
        self.events.put(("found", sorted(found)[0]))

    def connect(self):
        if self.engine:
            self.engine.request_stop()
            self.engine = None
        cfg = dict(self.cfg)
        cfg["mixer_ip"] = self.ip_var.get().strip()
        cfg["meter_index"] = self._selected_indexes()
        cfg["fx_targets"] = self._enabled_targets()
        cfg["features"] = self.features_dict()
        if hasattr(self, "th_var"):
            cfg["threshold_db"] = self.th_var.get()
            cfg["hold_time"] = self.hold_var.get()
            cfg["attack_time"] = self.atk_var.get()

        self.conn_var.set("judai rahyo chhu...")
        self.conn_dot.itemconfig(self.dot, fill="#c0a020")
        self.engine = m32_engine.Engine(
            cfg,
            on_log=lambda m: self.events.put(("log", m)),
            on_status=lambda s: self.events.put(("status", s)))
        self.engine.start()

        if self.run_var.get():
            self.engine.set_active(True)

    # ------------------------------------------------------------ run
    def _run_toggled(self, on):
        if not self.engine:
            self.run_var.set(False)
            return
        if on and not self._enabled_targets():
            self.run_var.set(False)
            messagebox.showinfo("Kai pasand nathi",
                                "Jamni baju thi nakki karo ke SHU chalu/band karvu.")
            return
        if on:
            self.engine.set_params(meter_index=self._selected_indexes(),
                                   fx_targets=self._enabled_targets(),
                                   threshold_db=self.th_var.get(),
                                   hold_time=self.hold_var.get(),
                                   attack_time=self.atk_var.get(),
                                   features=self.features_dict())
        self.engine.set_active(on)
        self._update_run_label()

    def _update_run_label(self):
        on = bool(self.run_var.get())
        safe = self.feat_vars["safe_mode"].get() if "safe_mode" in self.feat_vars else False
        if not on:
            self.run_lbl.configure(text="AUTOMATION  BAND", foreground=DIM)
        elif safe:
            self.run_lbl.configure(text="AUTOMATION  CHALU  (SAFE MODE)",
                                   foreground="#e0c040")
        else:
            self.run_lbl.configure(text="AUTOMATION  CHALU", foreground=GREEN)

    def save_settings(self):
        idx = self._selected_indexes()
        core.save_config({
            "mixer_ip": self.ip_var.get().strip(),
            "meter_index": idx if len(idx) > 1 else idx[0],
            "threshold_db": round(self.th_var.get(), 1),
            "hold_time": round(self.hold_var.get(), 2),
            "attack_time": round(self.atk_var.get(), 3),
            "fx_targets": self._target_paths,
            "fx_targets_off": sorted(self._target_off),
            "features": self.features_dict(),
        })
        self.logline("config.json ma save thai gayu")

    # ------------------------------------------------------------ pump
    def _pump(self):
        snap = None
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "log":
                    self.logline(data)
                elif kind == "status":
                    snap = data
                elif kind == "found":
                    self.ip_var.set(data)
                    self.logline("Mixer malyu: %s -- judai rahyo chhu" % data)
                    self.connect()
        except queue.Empty:
            pass
        if snap:
            self._apply_status(snap)
        self.root.after(80, self._pump)

    def _apply_status(self, s):
        live = s["connected"] and s["data_age"] < 2.0
        self.conn_dot.itemconfig(self.dot, fill=GREEN if live else RED)
        self.conn_var.set("%s  (FW %s)" % (s["mixer_name"], s["mixer_fw"])
                          if live else "judai nathi")

        if s["names"] and s["names"] != self.names:
            self.names = s["names"]
            for ch, lbl in self.ch_names.items():
                nm = self.names.get(ch, "").strip()
                lbl.configure(text=nm or "-", foreground=FG if nm else DIM)
            self._fill_catalog()
            self._refresh_targets()

        th = self.th_var.get()
        show = self.feat_vars.get("show_meter")
        if show is None or show.get():
            for ch in range(1, NUM_CHANNELS + 1):
                db = s["levels"][ch - 1]
                self.ch_bars[ch].set(db, th)
                self.ch_dbs[ch].configure(text="%.0f" % db if db > -90 else "--",
                                          foreground=GREEN if db > th else DIM)
            self.lvl_lbl.configure(
                text="%6.1f dB  %s" % (s["level_db"],
                                       core.channel_names([s["active_index"]])))
        else:
            self.lvl_lbl.configure(text="meter band")

        if not s["active"]:
            self.fx_lbl.configure(text="FX: (jova mate)", foreground=DIM)
        elif s["fx_on"]:
            self.fx_lbl.configure(text="FX: CHALU", foreground=GREEN)
        else:
            self.fx_lbl.configure(text="FX: BAND", foreground=RED)
        self._update_run_label()

    # ------------------------------------------------------------ close
    def on_close(self):
        if self.engine and self.engine.active:
            if not messagebox.askokcancel(
                    "Band karvu?",
                    "Automation chalu chhe. Band karsho to FX mute thai jashe.\n"
                    "Kharekhar band karvu chhe?"):
                return
        if self.engine:
            self.engine.request_stop()
        self.root.after(300, self.root.destroy)


def main():
    core.setup_console()
    cfg, _rest = core.apply_args(core.load_config(), sys.argv[1:])
    sim = core.start_simulator_if_asked(cfg)

    root = tk.Tk()
    app = App(root)
    if cfg.get("use_simulator"):
        app.ip_var.set("127.0.0.1")
        app.logline("NAKLI MIXER mode (--sim) -- kharaa mixer ni jarur nathi")
        app.connect()
    try:
        root.mainloop()
    finally:
        if sim:
            sim.request_stop()


if __name__ == "__main__":
    main()
