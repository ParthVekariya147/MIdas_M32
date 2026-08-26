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
        self.levels = [-128.0] * NUM_CHANNELS
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

            # badhi 32 channel na level (GUI ne batavva mate)
            for i in range(min(NUM_CHANNELS, len(values))):
                self.levels[i] = core.to_db(values[i])

            # pasand karel channel ma sauthi motho awaaj
            with self._lock:
                indexes = list(self.indexes)
            best_db, best_i = -128.0, None
            for i in indexes:
                if i < len(values):
                    db = core.to_db(values[i])
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
