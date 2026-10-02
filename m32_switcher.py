"""
m32_switcher.py  -  SMART SOURCE SWITCH  (auto failover) nu dimaag.

Shu kaam kare:
    Ek j katha be jagya thi aave chhe --
        Priority 1 : Zoom      (PC, WiFi)
        Priority 2 : Aux 1     (mobile, 4G/5G)
    Je upper priority ni line JIVTI hoy te j LIVE rahe.
    Line mari jay to nichli priority par jate switch thai jay,
    ane pachhi upper line sthir thay to pachha tya j.

MOTTI VAAT -- vakta katha ma sahej vishram le chhe.
    "awaaj band = switch"  evu saadu logic CHALE NAHI.
    Etle ahi TRAN halat ganiye chhiye:

        TALKING  -- bole chhe                 -> live rakho
        QUIET    -- chup, pan line jivti      -> KAI NA KARO
        DEAD     -- line mari gai             -> switch

CROSS-CHECK (aa feature nu hraday):
    Ek j vakta ek j vakhte chup pan hoy ane bolto pan hoy -- ashakya.
    Etle jo P1 chup hoy PAN P2 ma awaaj aavto hoy, to e vishram nathi --
    e chokkas internet tutyu chhe. Aa thi 6 second ni raah 2 second
    thai jay chhe.

Aa file ne mixer ni KOI jarur nathi -- fakt level (dB) aapo.
Etle test karvu sahelu chhe.
"""

import time


# ---------------------------------------------------------------- halat
TALKING = "TALKING"      # bole chhe
QUIET = "QUIET"          # chup, pan line jivti
DEAD = "DEAD"            # line mari gai

STATE_TEXT = {
    TALKING: "BOLE CHHE",
    QUIET: "ATAKYA",
    DEAD: "LINE MARI",
}


# ---------------------------------------------------------------- defaults
DEFAULTS = {
    # ---- awaaj chhe ke nahi (be threshold -- hysteresis) ----
    "open_db": -54.0,          # aa thi UPAR jay to "awaaj chhe"
    "close_db": -60.0,         # aa thi NICHE jay to "awaaj nathi"

    # ---- line mari gai ke nahi ----
    "dead_hold_s": 6.0,        # aatli var sadhang chup -> line mari
    "cross_dead_hold_s": 2.0,  # cross-check male to aatli j var
    "cross_confirm_s": 1.0,    # biji line aatli var bole to j ganvu

    # ---- pachha jata dhiraj ----
    "stable_s": 180.0,         # 3 minute sadhang jivti rahe to j pachha
    "pause_wait_s": 20.0,      # vishram ni raah -- aatli var thi vadhare nahi

    # ---- ping-pong atkavva ----
    "min_dwell_s": 5.0,        # switch pachhi aatlu tya j raho

    # ---- awaaj ane ghargharat olakhvu ----
    "var_window_s": 2.0,       # aatla second nu vadhghat jovu
    "flat_db": 3.0,            # aa thi ochhu vadhghat = ghargharat, awaaj nahi

    # ---- biju ----
    "bleed_guard_db": 6.0,     # halko bleed "awaaj" ma na ganvo
    "watchdog_s": 1.5,         # meter data band -> switch karvu j nahi
    "crossfade_ms": 250,       # fader thi smooth
    "overlap_ms": 150,         # navu chalu -> pachhi junu band (dar na pade)
}


def defaults():
    return dict(DEFAULTS)


# ================================================================ Source
class Source:
    """
    Ek source (dakhla: "Zoom (PC)").

    SAMBHALVU  ane  CONTROL KARVU  -- be alag vastu:
        index    = meter ma kayo index sambhalvo
        targets  = kaya OSC path mute/unmute karva
    Etle Channel, Aux In, FX Return -- badhu source bani shake.
    """

    def __init__(self, cfg, opts=None):
        cfg = dict(cfg or {})
        o = opts or DEFAULTS

        self.name = str(cfg.get("name") or "Source")
        self.on = bool(cfg.get("on", True))

        # SAMBHALVU : ek karta vadhare index pan hoi shake.
        # (dakhla: stereo pair -- CH 31 ane CH 32 banne sambhalo,
        #  jema motho awaaj hoy te ganvo)
        raw = cfg.get("indexes")
        if raw is None:
            raw = cfg.get("index", 0)
        if isinstance(raw, (list, tuple)):
            self.indexes = [int(x) for x in raw] or [0]
        else:
            self.indexes = [int(raw)]
        self.index = self.indexes[0]                   # juni config sathe chale

        # CONTROL KARVU : ahi pan ghana hoi shake
        # (stereo pair mate CH 31 ane CH 32 -- banne mute thavа joiye)
        self.targets = list(cfg.get("targets") or [])
        # fader pan ghana (crossfade mate)
        f = cfg.get("faders")
        if f:
            self.faders = list(f)
        else:
            one = cfg.get("fader")
            self.faders = [one] if one else []
        self.fader = self.faders[0] if self.faders else None
        self.on_level = cfg.get("on_level")            # yaad rakhel fader

        # per-source threshold (None = badha mate no vaparo)
        self.open_db = cfg.get("open_db")
        self.close_db = cfg.get("close_db")
        self._o = o

        # ---- halat ----
        self.db = -128.0
        self.alive = False               # atyare awaaj chhe ke nahi
        self.state = QUIET
        self.hist = []                   # [(time, db)] -- vadhghat ganva
        self.last_alive = 0.0            # chhelli var kyare awaaj hato
        self.stable_since = None         # kyar thi sadhang jivti chhe
        self.started = False
        self.first_seen = None           # kyar thi aa source ne sambhaliye chhiye

    # ------------------------------------------------------------ helpers
    def thr_open(self):
        v = self.open_db
        return float(self._o["open_db"] if v is None else v)

    def thr_close(self):
        v = self.close_db
        return float(self._o["close_db"] if v is None else v)

    def wiggle(self):
        """
        Chhella thoda second ma level ketlu upar-niche thayu (dB).
            ghargharat / hum  ->  nanu  (sapat)
            kharekhar bolvu   ->  motu  (shabdo, viram)
        """
        # haju puratu sambhalyu j nathi -> "khabar nathi" (99) kaho.
        # (nahi to shuruaat na be-tran sample par j khoto nirnay thai jay)
        if len(self.hist) < 3 or (self.hist[-1][0] - self.hist[0][0]) < 0.5:
            return 99.0
        vals = [d for _t, d in self.hist]
        return max(vals) - min(vals)

    def is_flat(self):
        return self.wiggle() < float(self._o["flat_db"])

    def quiet_for(self, now):
        """Ketli var thi awaaj nathi aavto."""
        if self.alive:
            return 0.0
        if self.last_alive:
            return now - self.last_alive
        # ek pan var awaaj aavyo j nathi -- jyar thi sambhaliye chhiye tyar thi.
        # (hist ni baari fakt 2 second ni chhe, etle teno bharoso na karay --
        #  aa bug kharaa mixer par pakadayo hato: program chalu karo tyare
        #  Zoom pehlethi band hoy to KYAREY "line mari" thatu j nahi)
        if self.first_seen is not None:
            return now - self.first_seen
        return 0.0

    def talk_for(self, now):
        """Ketli var thi sadhang bole chhe (vishram vagar)."""
        if not self.alive:
            return 0.0
        start = None
        for t, db in reversed(self.hist):
            if db <= self.thr_close():
                break
            start = t
        return 0.0 if start is None else (now - start)

    def stable_for(self, now):
        if self.stable_since is None:
            return 0.0
        return now - self.stable_since

    # ------------------------------------------------------------ feed
    def feed(self, db, now, smart_noise=True):
        """Navo level aapo. Halat jate nakki thai jashe."""
        self.db = float(db)
        self.started = True
        if self.first_seen is None:
            self.first_seen = now

        # ---- vadhghat ganva mate itihas ----
        self.hist.append((now, self.db))
        cut = now - float(self._o["var_window_s"])
        while self.hist and self.hist[0][0] < cut:
            self.hist.pop(0)

        # ---- awaaj chhe ke nahi (be threshold) ----
        if self.alive:
            # chalu chhe -> close_db thi NICHE jay to j band
            if self.db < self.thr_close():
                self.alive = False
            elif smart_noise and self.is_flat():
                # level to uncho chhe, PAN sav sapat chhe --
                # etle e bolvu nathi, e ghargharat/hum chhe.
                # (Zoom ni line mari jay pachhi hum chalu rahe te case)
                self.alive = False
        else:
            # band chhe -> open_db thi UPAR jay to j chalu.
            # ane smart_noise chalu hoy to sapat awaaj ne ganvo j nahi
            # (aa "1-2 dB nu awaaj" walo prashn ahi j pate chhe)
            if self.db > self.thr_open() and not (smart_noise and self.is_flat()):
                self.alive = True

        if self.alive:
            self.last_alive = now

    # ------------------------------------------------------------ state
    def settle(self, now, dead_hold):
        """Halat nakki karo. dead_hold baharthi aave chhe (cross-check)."""
        was = self.state
        if self.alive:
            self.state = TALKING
        elif self.quiet_for(now) >= dead_hold:
            self.state = DEAD
        else:
            self.state = QUIET

        # ---- sthirta no timer ----
        if self.state == DEAD:
            self.stable_since = None          # mari gai -> timer 0 thi
        elif was == DEAD or self.stable_since is None:
            self.stable_since = now
        return self.state

    def snapshot(self, now):
        return {
            "name": self.name,
            "on": self.on,
            "index": self.index,
            "indexes": list(self.indexes),
            "db": self.db,
            "state": self.state,
            "state_text": STATE_TEXT.get(self.state, self.state),
            "wiggle": self.wiggle(),
            "quiet_for": self.quiet_for(now),
            "stable_for": self.stable_for(now),
            "targets": list(self.targets),
        }


# ================================================================ controller
class SwitchController:
    """
    Badhi source ma thi kai LIVE rakhvi te nakki kare chhe.

    Vaparvani rit (engine ma):
        sw.feed(index_thi_db_no_dict, now)
        act = sw.tick(now)
        if act: ... mixer par lagavo ...
    """

    def __init__(self, cfg=None, on_log=None):
        self.on_log = on_log or (lambda m: None)
        self.opts = defaults()
        self.sources = []
        self.enabled = False

        # feature toggle (engine baharthi bharé chhe)
        self.cross_check = True
        self.smart_noise = True
        self.stability = True
        self.at_pause = True
        self.watchdog = True

        self.live = None                 # atyare kai source live chhe
        self.last_switch = 0.0
        self.hold = False                # engineer e HOLD dabavyu
        self.frozen = False              # data band -> freeze
        self.waiting_pause_since = None
        self.pending = None              # kai source par javanu chhe
        self.switch_count = 0
        self.history = []                # [(time, thi, sudhi, karan)]
        self._last_data = 0.0
        self._warned = ""

        if cfg:
            self.configure(cfg)

    # ------------------------------------------------------------ config
    def configure(self, cfg):
        cfg = dict(cfg or {})
        for k in DEFAULTS:
            if k in cfg and cfg[k] is not None:
                try:
                    self.opts[k] = type(DEFAULTS[k])(cfg[k])
                except (TypeError, ValueError):
                    pass
        raw = cfg.get("sources") or []
        old = {s.name: s for s in self.sources}
        self.sources = []
        for item in raw:
            s = Source(item, self.opts)
            prev = old.get(s.name)
            if prev is not None and prev.indexes == s.indexes:
                # juni halat sachvo -- settings badlo tyare timer na tute
                s.db, s.alive, s.state = prev.db, prev.alive, prev.state
                s.hist, s.last_alive = prev.hist, prev.last_alive
                s.stable_since, s.started = prev.stable_since, prev.started
                s.first_seen = prev.first_seen
            self.sources.append(s)
        if self.live and self.live not in self.sources:
            match = [s for s in self.sources if s.name == self.live.name]
            self.live = match[0] if match else None

    def set_features(self, feats):
        f = feats or {}
        self.enabled = bool(f.get("auto_switch", False))
        self.cross_check = bool(f.get("switch_cross_check", True))
        self.smart_noise = bool(f.get("switch_smart_noise", True))
        self.stability = bool(f.get("switch_stability", True))
        self.at_pause = bool(f.get("switch_at_pause", True))
        self.watchdog = bool(f.get("switch_watchdog", True))

    # ------------------------------------------------------------ list
    def active_sources(self):
        """Fakt chalu karel source (toggle on) ane jena target hoy."""
        return [s for s in self.sources if s.on and s.targets]

    def ready(self):
        """
        Feature chalavva layak chhe ke nahi.
        Return: (True/False, karan)
        """
        act = self.active_sources()
        if len(act) < 2:
            return False, ("Ochha ma ochha 2 source joiye "
                           "(atyare %d chhe)" % len(act))
        seen = set()
        for s in act:
            same = seen.intersection(s.indexes)
            if same:
                return False, ("Be source ek j channel sambhale chhe "
                               "(index %d)" % sorted(same)[0])
            seen.update(s.indexes)
        return True, ""

    # ------------------------------------------------------------ feed
    def feed(self, levels, now=None):
        """
        levels = list athva dict -- meter index thi dB.
        Engine e KACHO level (levels) aapvo, levels_eff NAHI --
        nahi to aapne j mute karel backup "mari gai" lagshe.
        """
        now = time.monotonic() if now is None else now
        self._last_data = now
        for s in self.sources:
            best = None
            for i in s.indexes:
                try:
                    v = levels[i]
                except (IndexError, KeyError, TypeError):
                    continue
                if best is None or v > best:
                    best = v            # ghani hoy to sauthi motho ganvo
            if best is not None:
                s.feed(best, now, self.smart_noise)

    # ------------------------------------------------------------ dead hold
    def _dead_hold_for(self, src, now):
        """
        Aa source ne "mari gai" kehta pehla ketli var raah jovi.
        Cross-check male to bahu ochhi.
        """
        slow = float(self.opts["dead_hold_s"])
        if not self.cross_check:
            return slow
        fast = float(self.opts["cross_dead_hold_s"])
        need = float(self.opts["cross_confirm_s"])
        guard = float(self.opts["bleed_guard_db"])

        for other in self.active_sources():
            if other is src or not other.alive:
                continue
            # halko bleed "awaaj" ma na ganvo
            if other.db < other.thr_open() + guard:
                continue
            # biji line aatli var thi sadhang bole chhe?
            if other.talk_for(now) >= need:
                return fast
        return slow

    # ------------------------------------------------------------ tick
    def tick(self, now=None):
        """
        Dar chakkar par call karo.
        Return: None  athva  dict {"to": Source, "from": Source, "why": str}
        """
        now = time.monotonic() if now is None else now

        # ---- badhi source ni halat nakki karo ----
        for s in self.sources:
            s.settle(now, self._dead_hold_for(s, now))

        if not self.enabled:
            return None

        ok, why = self.ready()
        if not ok:
            if self._warned != why:
                self._warned = why
                self.on_log("[!] Smart Switch: %s" % why)
            return None
        self._warned = ""

        # ---- data band thai gayo? to KAI J na karo ----
        if self.watchdog and self._last_data:
            stale = now - self._last_data
            if stale > float(self.opts["watchdog_s"]):
                if not self.frozen:
                    self.frozen = True
                    self.on_log("[!] Meter data band -- Smart Switch FREEZE "
                                "(halat jem chhe tem rahi)")
                return None
        if self.frozen:
            self.frozen = False
            self.on_log("Meter data pachhu aavyu -- Smart Switch fari chalu")

        if self.hold:
            return None

        act = self.active_sources()

        # ---- pehli var: je upper priority ma line jivti hoy te kholo ----
        if self.live is None or self.live not in act:
            pick = next((s for s in act if s.state != DEAD), act[0])
            return self._go(pick, now, "Shuruaat", force=True)

        live = self.live

        # ---- 1) live line mari gai? -> turat nichli priority par ----
        if live.state == DEAD:
            cand = next((s for s in act if s is not live and s.state != DEAD),
                        None)
            if cand is not None:
                self.waiting_pause_since = None
                self.pending = None
                # emergency chhe -- min_dwell ne bahu na pakdo
                if (now - self.last_switch) >= min(1.0,
                                                   float(self.opts["min_dwell_s"])):
                    return self._go(cand, now, "LINE MARI GAI")
            return None

        # ---- 2) upper priority pachhi aavi gai? ----
        idx = act.index(live)
        better = [s for s in act[:idx] if s.state != DEAD]
        if not better:
            self.waiting_pause_since = None
            self.pending = None
            return None

        cand = better[0]

        # sthirta ni raah (3 minute)
        if self.stability:
            need = float(self.opts["stable_s"])
            if cand.stable_for(now) < need:
                return None

        if (now - self.last_switch) < float(self.opts["min_dwell_s"]):
            return None

        # ---- vishram ma j switch karo (sync no jhatko na sambhalay) ----
        if self.at_pause:
            if self.waiting_pause_since is None:
                self.waiting_pause_since = now
                self.pending = cand
                self.on_log("%s sthir thai gayi -- vishram ni raah joi rahyo chhu"
                            % cand.name)
            waited = now - self.waiting_pause_since
            if live.state == TALKING and waited < float(self.opts["pause_wait_s"]):
                return None

        self.waiting_pause_since = None
        self.pending = None
        return self._go(cand, now, "PACHHU AAVYU (sthir)")

    # ------------------------------------------------------------ switch
    def _go(self, src, now, why, force=False):
        if src is self.live and not force:
            return None
        old = self.live
        self.live = src
        self.last_switch = now
        self.switch_count += 1
        self.history.append((now, old.name if old else "-", src.name, why))
        if len(self.history) > 200:
            del self.history[:100]
        self.on_log("SWITCH: %s -> %s   (%s, %.1f dB)"
                    % (old.name if old else "-", src.name, why, src.db))
        return {"to": src, "from": old, "why": why}

    def force_switch(self, name, now=None):
        """GUI nu 'hamna j switch karo' button."""
        now = time.monotonic() if now is None else now
        for s in self.active_sources():
            if s.name == name:
                self.waiting_pause_since = None
                self.pending = None
                return self._go(s, now, "Hathe switch karyu", force=True)
        return None

    def set_hold(self, on):
        self.hold = bool(on)
        self.on_log("Smart Switch: %s"
                    % ("HOLD -- jem chhe tem pakdi rakhyu" if on else "fari chalu"))

    # ------------------------------------------------------------ snapshot
    def snapshot(self, now=None):
        now = time.monotonic() if now is None else now
        ok, why = self.ready()
        wait_left = 0.0
        if self.pending is not None and self.waiting_pause_since is not None:
            wait_left = max(0.0, float(self.opts["pause_wait_s"])
                            - (now - self.waiting_pause_since))
        # pachha jata ketlu baaki chhe
        countdown = None
        if self.live is not None and self.enabled and ok:
            act = self.active_sources()
            if self.live in act:
                idx = act.index(self.live)
                better = [s for s in act[:idx] if s.state != DEAD]
                if better and self.stability:
                    need = float(self.opts["stable_s"])
                    countdown = max(0.0, need - better[0].stable_for(now))
        return {
            "enabled": self.enabled,
            "ready": ok,
            "why_not": why,
            "hold": self.hold,
            "frozen": self.frozen,
            "live": self.live.name if self.live else "",
            "pending": self.pending.name if self.pending else "",
            "countdown": countdown,
            "pause_wait_left": wait_left,
            "switch_count": self.switch_count,
            "sources": [s.snapshot(now) for s in self.sources],
        }
