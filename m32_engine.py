"""
m32_engine.py  -  Automation nu DIMAAG (brain).

Aa file ma badhi logic chhe. CMD wado program (m32_automation.py) ane
GUI wado program (m32_gui.py) -- banne AA J file vaapre chhe.
Etle logic ek j jagya e chhe, be jagya e sudharvi na pade.

Alag thread ma chale chhe, etle GUI atakti nathi.
"""

import threading
import time

import m32_core as core
import osc_lite

NUM_CHANNELS = 32


class Engine(threading.Thread):
    """
    Mixer sathe judai ne meter vaanche ane jarur pade tyare
    mute/unmute command moklé.

    connected  -> mixer malyu ke nahi
    active     -> True hoy to j kharekhar command jaay chhe
                  (False = fakt meter joyi shakay, desk ne aday nahi)
    """

    def __init__(self, cfg, on_log=None, on_status=None):
        threading.Thread.__init__(self, daemon=True)
        self._lock = threading.Lock()
        self._stop_flag = threading.Event()
        self._want_names = threading.Event()
        self._reapply = threading.Event()

        self.on_log = on_log or (lambda msg: None)
        self.on_status = on_status or (lambda snap: None)

        self.cfg = dict(cfg)
        self.mixer = None

        # ---- settings (live badli shakay) ----
        self.bank = int(cfg.get("meter_bank", 0))
        self.indexes = core.parse_indexes(cfg.get("meter_index", 0))
        self.threshold = float(cfg.get("threshold_db", -40.0))
        self.hold = float(cfg.get("hold_time", 1.5))
        self.attack = float(cfg.get("attack_time", 0.02))
        self.targets = core.enabled_targets(cfg)
        self.invert = cfg.get("invert", "auto")

        # ---- FEATURE toggle ----
        self.features = dict(core.feature_defaults())
        self.features.update(cfg.get("features") or {})
        # --dry-run aapyu hoy to safe mode jate chalu
        if cfg.get("dry_run"):
            self.features["safe_mode"] = True

        self.active = False

        # ---- halat (state) ----
        self.connected = False
        self.mixer_name = ""
        self.mixer_fw = ""
        self.names = {}                       # {channel_no: naam}

        # ---- channel ni halat (fader / mute / DCA / mute group) ----
        self.ch_fader = {}      # ch -> 0.0-1.0
        self.ch_on = {}         # ch -> 1 chalu / 0 mute
        self.ch_dca = {}        # ch -> bitmask (kaya DCA ma chhe)
        self.ch_mgrp = {}       # ch -> bitmask (kaya mute group ma chhe)
        self.dca_on = {}        # 1-8 -> 1/0
        self.dca_fader = {}     # 1-8 -> 0.0-1.0
        self.mgrp_on = {}       # 1-6 -> 1/0
        self._last_state_poll = 0.0
        self._last_full_poll = 0.0
        # mixer e fader ni mahiti aapi ke nahi -- khabar na hoy tya sudhi
        # koi pan channel ne "sambhalay chhe" na manvu (salamati mate)
        self._state_ready = False
        self._state_asked_at = 0.0
        self._state_gaveup = False
        self.levels = [-128.0] * NUM_CHANNELS       # mic no kacho awaaj
        self.levels_eff = [-128.0] * NUM_CHANNELS   # fader lagavya pachhi no
        self.level_db = -128.0
        self.active_index = self.indexes[0]
        self.fx_on = None
        self.packets = 0
        self.last_packet = 0.0
        self.switches = 0
        self.value_count = 0

        self.last_loud = 0.0
        self.first_loud = None
        self._warned_no_data = False
        self._warned_range = False
        self._meter_address = "/meters/%d" % self.bank

    # ------------------------------------------------------------ settings
    def feature(self, key):
        """Aa feature chalu chhe ke nahi."""
        return bool(self.features.get(key, False))

    @property
    def dry_run(self):
        """Safe mode = mixer ne kai command na jay."""
        return self.feature("safe_mode")

    def set_feature(self, key, on):
        """Toggle button dabave tyare aa call thay chhe."""
        with self._lock:
            was = self.features.get(key)
            self.features[key] = bool(on)
        if was == bool(on):
            return
        name = core.FEATURES.get(key, (key,))[0]
        self.on_log("%s : %s" % (name, "CHALU" if on else "BAND"))

        if key == "safe_mode" and not on and self.active:
            self._reapply.set()          # safe mode nikalyu -> halat pachhi lagavo
        if key == "auto_fx" and not on and self.active:
            self.on_log("Auto FX band karyu -- have jate kai nahi badlay")

    def set_params(self, **kw):
        """Chalu hoy tyare pan settings badli shakay."""
        with self._lock:
            if "threshold_db" in kw:
                self.threshold = float(kw["threshold_db"])
            if "hold_time" in kw:
                self.hold = float(kw["hold_time"])
            if "attack_time" in kw:
                self.attack = float(kw["attack_time"])
            if "meter_index" in kw:
                self.indexes = core.parse_indexes(kw["meter_index"])
                self.active_index = self.indexes[0]
                self._warned_range = False
            if "fx_targets" in kw:
                self.targets = list(kw["fx_targets"])
                self._reapply.set()
            if "features" in kw:
                self.features.update(kw["features"] or {})
            if "invert" in kw:
                self.invert = kw["invert"]
                self._reapply.set()

    def set_active(self, on):
        """
        on=True  -> have kharekhar mixer ne command jashe
        on=False -> fakt meter dekhashe, desk ne kai nahi thay
        """
        with self._lock:
            was = self.active
            self.active = bool(on)
        if self.active and not was:
            if self.feature("safe_mode"):
                self.on_log("AUTOMATION CHALU (SAFE MODE -- desk ne kai nahi thay)")
            else:
                self.on_log("AUTOMATION CHALU -- have mixer par command jashe")
            self.fx_on = None                 # halat fari nakki karo
            if self.feature("start_muted"):
                self._apply(False, "Safe start")
        elif was and not self.active:
            self.on_log("AUTOMATION BAND -- desk ne have kai nahi thay")

    def request_names(self):
        self._want_names.set()

    def request_stop(self):
        self._stop_flag.set()

    # ------------------------------------------------------------ send
    def _apply(self, on, why=""):
        """on=True -> awaaj sambhalvo joiye (unmute)."""
        if self.active and not self.feature("safe_mode") and self.mixer:
            for path in self.targets:
                self.mixer.send(path, core.mute_value(path, on, self.invert))
                time.sleep(0.002)
        self.fx_on = on
        self.switches += 1
        if why:
            tag = "" if self.active else "[JOVA MATE] "
            if self.feature("safe_mode"):
                tag = "[SAFE MODE] "
            self.on_log("%s%s -> FX %s   (%s, %.1f dB)"
                        % (tag, why, "CHALU" if on else "BAND",
                           core.channel_names([self.active_index]), self.level_db))

    def send_raw(self, path, value):
        """GUI na TEST button mate."""
        if self.mixer:
            self.mixer.send(path, value)

    # ------------------------------------------------------------ fader
    def channel_gain_db(self, ch):
        """
        Aa channel no awaaj mixer ma KETLO bahar jay chhe.

        Return: dB ma vadharo/ghatado  (0 = fader unity)
                None = sav band chhe (mute / mute group / DCA off)

        Mixer meter PRE-FADER ape chhe, etle fader ni asar
        aapne jate ganvi pade chhe.
        """
        # 0) haju mixer e aa channel ni mahiti aapi j nathi?
        #    to teno bharoso na karvo -- "band chhe" evu manvu.
        #    (mixer jawab j na aape to _state_gaveup thai jay ane
        #     juni rite chale)
        if not self._state_gaveup and ch not in self.ch_fader:
            return None

        # 1) channel pote mute chhe?
        if self.ch_on.get(ch, 1) in (0, False):
            return None

        # 2) je mute group ma chhe te chalu chhe?
        mgrp = int(self.ch_mgrp.get(ch, 0) or 0)
        for n in range(1, 7):
            if mgrp & (1 << (n - 1)) and self.mgrp_on.get(n, 0) in (1, True):
                return None

        gain = core.fader_to_db(self.ch_fader.get(ch, 0.75))

        # 3) je DCA ma chhe te band chhe? nahi to teno fader umero
        dca = int(self.ch_dca.get(ch, 0) or 0)
        for n in range(1, 9):
            if dca & (1 << (n - 1)):
                if self.dca_on.get(n, 1) in (0, False):
                    return None
                gain += core.fader_to_db(self.dca_fader.get(n, 0.75))

        return gain

    def channel_state_text(self, ch):
        """GUI ne batavva mate: "+0.0" / "-10.5" / "MUTE" """
        gain = self.channel_gain_db(ch)
        if gain is None:
            return "MUTE"
        if gain <= -89.0:
            return "-oo"
        return "%+.1f" % gain

    # ------------------------------------------------------------ poll
    def _poll_channel_state(self, channels):
        """Aa channel na fader / mute / DCA puchho."""
        for ch in channels:
            for path in ("/ch/%02d/mix/fader", "/ch/%02d/mix/on",
                         "/ch/%02d/grp/dca", "/ch/%02d/grp/mute"):
                self.mixer.send(path % ch)
                time.sleep(0.002)

    def _poll_groups(self):
        """DCA ane mute group ni halat puchho."""
        for n in range(1, 9):
            self.mixer.send("/dca/%d/on" % n)
            self.mixer.send("/dca/%d/fader" % n)
            time.sleep(0.002)
        for n in range(1, 7):
            self.mixer.send("/config/mute/%d" % n)
            time.sleep(0.002)

    # ------------------------------------------------------------ packets
    def _on_packet(self, address, args):
        # ---- channel na naam ----
        if address.startswith("/ch/") and address.endswith("/config/name"):
            try:
                ch = int(address.split("/")[2])
            except (ValueError, IndexError):
                return
            if args and isinstance(args[0], str):
                self.names[ch] = args[0].strip()
            return

        # ---- fader / mute / DCA / mute group na jawab ----
        if address.startswith("/ch/") and args:
            parts = address.split("/")
            if len(parts) >= 5:
                try:
                    ch = int(parts[2])
                except ValueError:
                    return
                tail = "/".join(parts[3:])
                val = args[0]
                if tail == "mix/fader":
                    self.ch_fader[ch] = val
                    self._state_ready = True
                elif tail == "mix/on":
                    self.ch_on[ch] = val
                elif tail == "grp/dca":
                    self.ch_dca[ch] = val
                elif tail == "grp/mute":
                    self.ch_mgrp[ch] = val
            return

        if address.startswith("/dca/") and args:
            parts = address.split("/")
            try:
                n = int(parts[2])
            except (ValueError, IndexError):
                return
            if address.endswith("/on"):
                self.dca_on[n] = args[0]
            elif address.endswith("/fader"):
                self.dca_fader[n] = args[0]
            return

        if address.startswith("/config/mute/") and args:
            try:
                self.mgrp_on[int(address.rsplit("/", 1)[1])] = args[0]
            except ValueError:
                pass
            return

        if address != self._meter_address:
            return

        for a in args:
            if not isinstance(a, (bytes, bytearray)):
                continue
            values = osc_lite.decode_meter_blob(a)
            if not values:
                continue

            self.packets += 1
            self.last_packet = time.time()
            self._warned_no_data = False
            self.value_count = len(values)

            respect = self.feature("respect_fader")

            # badhi 32 channel na level (GUI ne batavva mate)
            for i in range(min(NUM_CHANNELS, len(values))):
                raw = core.to_db(values[i])
                self.levels[i] = raw
                if respect:
                    gain = self.channel_gain_db(i + 1)
                    self.levels_eff[i] = -128.0 if gain is None else raw + gain
                else:
                    self.levels_eff[i] = raw

            # pasand karel channel ma sauthi motho awaaj
            # (fader niche hoy ke mute hoy te channel ganvo j nahi)
            with self._lock:
                indexes = list(self.indexes)
            best_db, best_i = -128.0, None
            for i in indexes:
                if i < len(values):
                    db = self.levels_eff[i] if respect else core.to_db(values[i])
                    if db > best_db:
                        best_db, best_i = db, i

            if best_i is None:
                if not self._warned_range:
                    self._warned_range = True
                    self.on_log("[!] Pasand karel channel aa bank ma nathi "
                                "(bank ma fakt %d value chhe)" % len(values))
            else:
                self.level_db = best_db
                self.active_index = best_i

    # ------------------------------------------------------------ logic
    def _update(self):
        now = time.time()
        with self._lock:
            threshold, hold, attack = self.threshold, self.hold, self.attack

        # "Auto FX Mute" band hoy to jate kai badlvu nahi
        if not self.feature("auto_fx"):
            self._check_data_flow(now)
            return

        loud = self.level_db > threshold

        if loud:
            self.last_loud = now
            if self.first_loud is None:
                self.first_loud = now
            if self.fx_on is not True and (now - self.first_loud) >= attack:
                self._apply(True, "MIC ON ")
        else:
            self.first_loud = None
            if self.fx_on is not False and (now - self.last_loud) > hold:
                self._apply(False, "SILENCE")

        if self._reapply.is_set():
            self._reapply.clear()
            if self.fx_on is not None:
                self._apply(self.fx_on)

        self._check_data_flow(now)

    def _check_data_flow(self, now):
        """Data aavto band thai jay to warning ane (chalu hoy to) fari judo."""
        if not self.connected or self.last_packet <= 0:
            return
        if now - self.last_packet <= 3.0:
            return
        if self._warned_no_data:
            return
        self._warned_no_data = True
        if self.feature("auto_reconnect"):
            self.on_log("[!] Mixer parthi data band -- fari judva prayatna karu chhu")
            self.mixer.subscribe_meters([self.bank])
        else:
            self.on_log("[!] Mixer parthi data band ('Jate fari judo' band chhe)")

    # ------------------------------------------------------------ names
    def _fetch_names(self):
        for ch in range(1, NUM_CHANNELS + 1):
            self.mixer.send("/ch/%02d/config/name" % ch)
            time.sleep(0.004)

    # ------------------------------------------------------------ snapshot
    def snapshot(self):
        return {
            "connected": self.connected,
            "mixer_name": self.mixer_name,
            "mixer_fw": self.mixer_fw,
            "active": self.active,
            "features": dict(self.features),
            "levels": list(self.levels),
            "levels_eff": list(self.levels_eff),
            "state_ready": self._state_ready or self._state_gaveup,
            "ch_state": {ch: self.channel_state_text(ch)
                         for ch in range(1, NUM_CHANNELS + 1)},
            "level_db": self.level_db,
            "active_index": self.active_index,
            "fx_on": self.fx_on,
            "packets": self.packets,
            "names": dict(self.names),
            "data_age": time.time() - self.last_packet if self.last_packet else 999.0,
        }

    # ------------------------------------------------------------ run
    def run(self):
        self.mixer = core.Mixer(self.cfg["mixer_ip"], self.cfg["mixer_port"])
        info = self.mixer.query_info(wait=1.5)
        if info:
            self.connected = True
            self.mixer_name = info.get("name", "?")
            self.mixer_fw = info.get("firmware", "?")
            self.on_log("Mixer malyu: %s  (firmware %s)"
                        % (self.mixer_name, self.mixer_fw))
        else:
            self.on_log("[!] Mixer jawab nathi aapto -- IP/cable check karo")

        self._fetch_names()
        self._state_asked_at = time.time()
        self._poll_channel_state(range(1, NUM_CHANNELS + 1))
        self._poll_groups()
        self._last_full_poll = time.time()
        self._last_state_poll = time.time()
        self.mixer.subscribe_meters([self.bank])
        self.last_packet = time.time()

        last_status = 0.0
        while not self._stop_flag.is_set():
            self.mixer.drain(self._on_packet)
            self._update()
            self.mixer.keep_alive()

            if self._want_names.is_set():
                self._want_names.clear()
                self._fetch_names()

            now = time.time()

            # mixer fader ni mahiti aapto j nathi? (juno firmware / bijo desk)
            # to 4 second raah joi ne juni rite chalu rakho.
            if (self.feature("respect_fader") and not self._state_ready
                    and not self._state_gaveup and self._state_asked_at
                    and now - self._state_asked_at > 4.0):
                self._state_gaveup = True
                self.on_log("[!] Mixer fader ni mahiti aapto nathi -- "
                            "fader dhyanma lidha vagar chalu rakhu chhu")

            # fader/mute badlaya hoy to khabar pade te mate vaar vaar puchho
            # (/xremote thi mixer jate pan moklé chhe, aa safety net chhe)
            if self.feature("respect_fader"):
                if now - self._last_state_poll >= 2.0:
                    self._last_state_poll = now
                    with self._lock:
                        sel = [i + 1 for i in self.indexes]
                    self._poll_channel_state(sel)
                    self._poll_groups()
                if now - self._last_full_poll >= 15.0:
                    self._last_full_poll = now
                    self._poll_channel_state(range(1, NUM_CHANNELS + 1))
            if now - last_status >= 0.1:
                last_status = now
                if not self.connected and self.packets > 0:
                    self.connected = True
                try:
                    self.on_status(self.snapshot())
                except Exception:
                    pass

            self.mixer.wait(0.02)

        if self.active and self.feature("mute_on_exit"):
            self._apply(False, "Band karu chhu")
        self.mixer.close()
        self.on_log("Engine band thai gayu.")
