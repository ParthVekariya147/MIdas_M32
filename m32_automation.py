"""
m32_automation.py  -  MIDAS M32 AUTO FX MUTE  (CMD wado program)
=================================================================
Pasand karel mic ma awaaj aave  ->  target AUTOMATIC CHALU (unmute)
Badha mic shant thay           ->  hold time pachhi AUTOMATIC BAND (mute)

Screen wadu (mouse thi) joiye to :  0-START-GUI.bat
Aa CMD wadu chalavva mate       :  4-RUN-AUTOMATION.bat
Athva CMD ma                    :  python m32_automation.py
Band karva                      :  Ctrl + C

Badhi logic m32_engine.py ma chhe -- GUI ane aa, banne teni j vaapre chhe.
"""

import os
import sys
import time

import m32_core as core
import m32_engine

core.setup_console()

LINE = "=" * 64


class ConsoleRunner:
    def __init__(self, cfg):
        self.cfg = cfg
        self.show_meter = bool(cfg.get("show_meter", True))
        self.run_seconds = float(cfg.get("run_seconds", 0) or 0)
        self.last_draw = 0.0
        self.started = time.time()

        # automation.log have ENGINE pote lakhe chhe ('logging' toggle
        # pramane) -- GUI ane CMD, banne ma ek j rite.
        self.engine = m32_engine.Engine(cfg, on_log=self.log, on_status=self.draw)

    # ------------------------------------------------------------ log
    def log(self, msg):
        line = "[%s] %s" % (time.strftime("%H:%M:%S"), msg)
        sys.stdout.write("\r" + " " * 78 + "\r")
        print(line)

    # ------------------------------------------------------------ draw
    def draw(self, snap):
        now = time.time()
        if not self.show_meter or now - self.last_draw < 0.1:
            return
        self.last_draw = now
        db = snap["level_db"]
        loud = db > self.engine.threshold
        state = "FX: CHALU" if snap["fx_on"] else "FX: BAND "
        who = ""
        if len(self.engine.indexes) > 1:
            who = " %-7s" % (core.channel_names([snap["active_index"]]) if loud else "")
        sys.stdout.write("\r  %s %6.1f dB %s  %s%s  " %
                         (">>" if loud else "  ", db, core.db_bar(db), state, who))
        sys.stdout.flush()

    # ------------------------------------------------------------ run
    def run(self):
        cfg = self.cfg
        eng = self.engine
        print(LINE)
        print("   MIDAS M32  --  AUTO FX MUTE")
        print(LINE)
        print("  Mixer IP      : %s:%s" % (cfg["mixer_ip"], cfg["mixer_port"]))
        print("  Sambhale chhe : %s   (bank %d)"
              % (core.channel_names(eng.indexes), eng.bank))
        print("  Control karse : %s"
              % (", ".join(core.target_label(p) for p in eng.targets) or "(kai nahi!)"))
        print("  Threshold     : %.1f dB   |   Hold : %.2f s   |   Attack : %.2f s"
              % (eng.threshold, eng.hold, eng.attack))
        if eng.dry_run:
            print("  MODE          : DRY-RUN (mixer ne KAI command nahi jay)")
        print(LINE)

        if not eng.targets:
            print("  [X] config.json ma 'fx_targets' khali chhe.")
            print("      0-START-GUI.bat chalavi ne nakki karo ke shu control karvu.")
            print(LINE)
            return

        eng.start()
        time.sleep(2.0)                        # judai jaay tya sudhi raah juo
        eng.set_active(not eng.dry_run)
        if eng.dry_run:
            eng.active = False

        print("  Automation CHALU chhe.  Band karva mate Ctrl+C dabavo.")
        print(LINE)

        try:
            while eng.is_alive():
                time.sleep(0.2)
                if self.run_seconds and (time.time() - self.started) > self.run_seconds:
                    self.log("Time puro (--seconds %g)" % self.run_seconds)
                    break
        except KeyboardInterrupt:
            pass
        self.stop()

    def stop(self):
        self.engine.request_stop()
        self.engine.join(timeout=2.0)
        sys.stdout.write("\r" + " " * 78 + "\r")
        print(LINE)
        mins = (time.time() - self.started) / 60.0
        print("  Chalyu: %.1f minute  |  Meter packets: %d  |  Switch: %d"
              % (mins, self.engine.packets, max(0, self.engine.switches - 1)))
        print("  Automation BAND.  Aabhar!")
        print(LINE)


# ---------------------------------------------------------------- tools
# exe ma badha tool bhega hoy, jethi ek j file thi badhu thai jay.
TOOLS = {
    "gui":    ("m32_gui",         "Screen wado program"),
    "find":   ("find_mixer",      "Network ma mixer shodho"),
    "select": ("channel_select",  "Channel jate pasand karo"),
    "scan":   ("meter_scan",      "Bolo etle channel jate shodhe"),
    "testfx": ("test_fx",         "3 var on/off kari ne check karo"),
    "sim":    ("m32_simulator",   "Nakli mixer chalavo"),
}


def show_tools():
    print()
    print("  Aa exe ma aa badha tool chhe:")
    print()
    exe = os.path.basename(sys.argv[0])
    for key, (_mod, desc) in TOOLS.items():
        print("     %s %-8s %s" % (exe, key, desc))
    print()
    print("  Kai na lakho to automation chalu thai jay chhe.")
    print()


def run_tool(name):
    mod_name, _desc = TOOLS[name]
    del sys.argv[1]                       # tool nu naam kaadhi nakho
    __import__(mod_name)
    sys.modules[mod_name].main()


def main():
    if len(sys.argv) > 1:
        first = sys.argv[1].lower()
        if first in TOOLS:
            run_tool(first)
            return
        if first in ("tools", "list", "--tools"):
            show_tools()
            return

    cfg, rest = core.apply_args(core.load_config(), sys.argv[1:])
    if any(a in ("-h", "--help") for a in rest):
        print(__doc__)
        print(core.ARG_HELP)
        show_tools()
        return
    for a in rest:
        print("[!] Aa option samjayu nahi: %s" % a)
    sim = core.start_simulator_if_asked(cfg)
    try:
        ConsoleRunner(cfg).run()
    finally:
        if sim:
            sim.request_stop()


if __name__ == "__main__":
    main()
