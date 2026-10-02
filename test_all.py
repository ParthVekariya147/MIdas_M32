"""
test_all.py  -  BADHU BARABAR CHALE CHHE ?  (aapoaap test)

Mixer ni JARUR NATHI. Aa program nakli mixer chalavi ne aakhi
system ne jate check kare chhe ane PASS / FAIL batave chhe.

Kyare chalavvu:
  * Koi pan file ma feraf ar karo tya pachhi
  * Program ma kai vaandho lage tyare
  * Naya PC par mukyu hoy tyare

Chalavva:  9-TEST-ALL.bat  par double-click
Athva:     python test_all.py
"""

import os
import sys
import time

import m32_core as core
import m32_engine
import m32_simulator
import m32_switcher
import osc_lite

core.setup_console()

LINE = "=" * 66
PASS, FAIL = [], []

# Test vakhte kharekhar nu automation.log na bagadvu. (Log no potano
# test niche chhe -- te alag file vaapre chhe.)
core.DEFAULTS["log_file"] = ""

_real_load_config = core.load_config


def _load_config_no_log():
    cfg = _real_load_config()
    cfg["log_file"] = ""
    return cfg


core.load_config = _load_config_no_log


# ---------------------------------------------------------------- helpers
def check(name, ok, detail=""):
    if ok:
        PASS.append(name)
        print("  [PASS]  %-46s %s" % (name, detail))
    else:
        FAIL.append(name)
        print("  [FAIL]  %-46s %s" % (name, detail))
    return ok


def section(title):
    print()
    print("-" * 66)
    print("  " + title)
    print("-" * 66)


def wait_for(fn, timeout=6.0, step=0.05):
    """fn() saachu thay tya sudhi raah jue. Return True/False."""
    end = time.time() + timeout
    while time.time() < end:
        if fn():
            return True
        time.sleep(step)
    return False


# ================================================================ 1. OSC
def test_osc():
    section("1. OSC protocol (mixer ni bhasha)")

    msg = osc_lite.build_message("/ch/01/mix/on", 1)
    got = osc_lite.parse_message(msg)
    check("int moklo ane pachho vancho", got == [("/ch/01/mix/on", [1])], str(got))

    msg = osc_lite.build_message("/meters", "/meters/0")
    got = osc_lite.parse_message(msg)
    check("string moklo ane pachho vancho", got == [("/meters", ["/meters/0"])])

    msg = osc_lite.build_message("/ch/05/mix/fader", 0.75)
    addr, args = osc_lite.parse_message(msg)[0]
    check("float moklo ane pachho vancho", abs(args[0] - 0.75) < 1e-6,
          "%.4f" % args[0])

    vals = [0.1, 0.5, 0.9]
    blob = m32_simulator.make_blob(vals)
    back = osc_lite.decode_meter_blob(blob)
    check("meter blob vanchvu", len(back) == 3 and abs(back[1] - 0.5) < 1e-6,
          str([round(v, 3) for v in back]))

    check("khoto data thi crash na thay",
          osc_lite.parse_message(b"\x01\x02\x03") == [] and
          osc_lite.decode_meter_blob(b"\x00") == [])

    # lambo path ane khaali message
    msg = osc_lite.build_message("/config/mute/5")
    check("value vagar no message", osc_lite.parse_message(msg) ==
          [("/config/mute/5", [])])


# ================================================================ 2. dB
def test_db():
    section("2. dB ni ganatri")
    check("0.01 (linear) = -40 dB", abs(core.to_db(0.01) + 40.0) < 0.01)
    check("1.0 (linear) = 0 dB", abs(core.to_db(1.0)) < 0.01)
    check("0 = sav shant", core.to_db(0.0) <= -128.0)
    check("pehlethi dB hoy to jem chhe tem", core.to_db(-38.5) == -38.5)
    check("bar dekhay chhe", "#" in core.db_bar(-20) and "." in core.db_bar(-20))


# ================================================================ 3. config
def test_config():
    section("3. Channel ane target ni samajh")

    check("0 -> [0]", core.parse_indexes(0) == [0])
    check("[0,1,4] -> [0,1,4]", core.parse_indexes([0, 1, 4]) == [0, 1, 4])
    check("'0,1,4' -> [0,1,4]", core.parse_indexes("0,1,4") == [0, 1, 4])
    check("bevadu na aave", core.parse_indexes([3, 3, 1]) == [3, 1])
    check("khali hoy to CH 1", core.parse_indexes([]) == [0])
    check("naam banave", core.channel_names([0, 4]) == "CH 1, CH 5")

    cat = core.target_catalog()
    total = sum(len(items) for _g, items in cat)
    check("target ni yaadi", total >= 80, "%d target" % total)
    check("Mute Group 5 nu naam",
          core.target_label("/config/mute/5") == "Mute Group 5")
    check("Channel nu naam sathe",
          core.target_label("/ch/09/mix/on", {9: "Guruji"}) == "Channel 9 (Guruji)")

    # ---- sauthi agatya nu : ulti value ----
    check("mute group: awaaj chalu -> 0",
          core.mute_value("/config/mute/5", True) == 0)
    check("mute group: awaaj band -> 1",
          core.mute_value("/config/mute/5", False) == 1)
    check("channel: awaaj chalu -> 1",
          core.mute_value("/ch/09/mix/on", True) == 1)
    check("channel: awaaj band -> 0",
          core.mute_value("/ch/09/mix/on", False) == 0)
    check("hathe ultu karvu (invert=True)",
          core.mute_value("/ch/09/mix/on", True, True) == 0)


# ================================================================ 3b. features
def test_features():
    section("3b. Feature toggle (chalu / band)")

    check("badha feature chhe", len(core.FEATURES) >= 7,
          "%d feature" % len(core.FEATURES))
    d = core.feature_defaults()
    check("default barabar", d["auto_fx"] and not d["safe_mode"], str(d))

    cfg = {"features": {"safe_mode": True, "logging": False}}
    check("safe_mode chalu vanchayu", core.get_feature(cfg, "safe_mode"))
    check("logging band vanchayu", not core.get_feature(cfg, "logging"))
    check("na lakhelu hoy to default", core.get_feature(cfg, "auto_fx"))
    check("juni config sathe pan chale",
          core.get_feature({"start_muted": False}, "start_muted") is False)

    cfg = {"fx_targets": ["/a", "/b", "/c"], "fx_targets_off": ["/b"]}
    check("band karel target vaparay nahi",
          core.enabled_targets(cfg) == ["/a", "/c"],
          str(core.enabled_targets(cfg)))


# ================================================================ 3c. fader
def test_fader():
    section("3c. Fader ni ganatri")
    pairs = [(1.0, 10.0), (0.75, 0.0), (0.5, -10.0), (0.25, -30.0),
             (0.0625, -60.0), (0.0, -90.0)]
    for value, want in pairs:
        got = core.fader_to_db(value)
        check("fader %-6s = %+.0f dB" % (value, want), abs(got - want) < 0.1,
              "%.1f" % got)
    check("khoto data thi crash na thay",
          core.fader_to_db(None) == -90.0 and core.fader_to_db("abc") == -90.0)
    check("fader 0 nu lakhan '-oo'", core.fader_text(0.0) == "-oo")
    check("fader unity nu lakhan '+0.0'", core.fader_text(0.75) == "+0.0")


# ================================================================ 4. live
def run_engine(sim, cfg_extra, seconds, active=True):
    """Nakli mixer sathe engine chalavi ne shu thayu te pachhu aape."""
    cfg = dict(core.DEFAULTS)
    cfg["mixer_ip"] = "127.0.0.1"
    cfg["mixer_port"] = m32_simulator.PORT
    cfg.update(cfg_extra)

    logs = []
    eng = m32_engine.Engine(cfg, on_log=logs.append)
    eng.start()
    wait_for(lambda: eng.packets > 3, 5.0)
    if active:
        eng.set_active(True)
    time.sleep(seconds)
    eng.request_stop()
    eng.join(timeout=3.0)
    return eng, logs


def test_live():
    section("4. Nakli mixer sathe kharekhar chalavi ne")

    sim = m32_simulator.Simulator(verbose=False)
    sim.start()
    sim.ready.wait(3.0)
    if sim.error:
        check("nakli mixer chalu thayo", False, str(sim.error))
        return
    check("nakli mixer chalu thayo", True, "port %d" % m32_simulator.PORT)

    try:
        # ---------------- judaan ane naam ----------------
        eng, logs = run_engine(sim, {"meter_index": 0,
                                     "fx_targets": ["/config/mute/5"]},
                               6.0)
        check("mixer sathe judai gayu", eng.connected,
              "%s" % eng.mixer_name)
        check("meter data aavyo", eng.packets > 40, "%d packets" % eng.packets)
        check("32 channel na naam malya", len(eng.names) >= 12,
              "%d naam, CH1=%s" % (len(eng.names), eng.names.get(1)))
        check("CH 1 no awaaj vanchayo", max(eng.levels[0], -200) > -50,
              "%.1f dB" % eng.levels[0])

        got_on = any("FX CHALU" in m for m in logs)
        got_off = any("FX BAND" in m for m in logs)
        check("awaaj aavya e FX CHALU thayu", got_on)
        check("shanti thai e FX BAND thayu", got_off)

        # ---------------- mute group ni ulti value ----------------
        sent = [v for p, v in sim.received if p == "/config/mute/5"]
        check("mute group ne 0 ane 1 banne malya",
              0 in sent and 1 in sent, "malyu: %s" % sorted(set(sent)))

        # nakli desk par fxrtn kharekhar badlayu?
        check("mute group e FX return ne asar karyu",
              sim.state["/fxrtn/01/mix/on"] in (0, 1),
              "fxrtn01 = %s" % sim.state["/fxrtn/01/mix/on"])

        # ---------------- dry-run : kai na jaay ----------------
        before = len(sim.received)
        run_engine(sim, {"meter_index": 0, "fx_targets": ["/config/mute/3"],
                         "dry_run": True}, 5.0)
        after = [p for p, _v in sim.received[before:] if p == "/config/mute/3"]
        check("dry-run ma mixer ne kai na moklyu", not after,
              "%d command" % len(after))

        # ---------------- active=False : kai na jaay ----------------
        before = len(sim.received)
        run_engine(sim, {"meter_index": 0, "fx_targets": ["/config/mute/4"]},
                   5.0, active=False)
        after = [p for p, _v in sim.received[before:] if p == "/config/mute/4"]
        check("CHALU KARO dabavya vagar kai na jaay", not after,
              "%d command" % len(after))

        # ---------------- FEATURE toggle no asar ----------------
        # safe_mode chalu -> ek pan command na jay
        before = len(sim.received)
        run_engine(sim, {"meter_index": 0, "fx_targets": ["/config/mute/1"],
                         "features": {"safe_mode": True}}, 5.0)
        after = [p for p, _v in sim.received[before:] if p == "/config/mute/1"]
        check("Safe Mode toggle: kai command na jay", not after,
              "%d command" % len(after))

        # auto_fx band -> jate kai na badlay
        before = len(sim.received)
        run_engine(sim, {"meter_index": 0, "fx_targets": ["/config/mute/2"],
                         "features": {"auto_fx": False, "start_muted": False,
                                      "mute_on_exit": False}}, 5.0)
        after = [p for p, _v in sim.received[before:] if p == "/config/mute/2"]
        check("Auto FX toggle band: jate kai na badlay", not after,
              "%d command" % len(after))

        # start_muted band -> shuruaat ma mute na kare
        eng, logs = run_engine(sim, {"meter_index": 0,
                                     "fx_targets": ["/config/mute/3"],
                                     "features": {"start_muted": False}}, 4.0)
        check("Shuruaat ma mute toggle band",
              not any("Safe start" in m for m in logs))

        # chalu haalat ma toggle badlvu
        cfg = dict(core.DEFAULTS)
        cfg.update({"mixer_ip": "127.0.0.1", "meter_index": 0,
                    "fx_targets": ["/config/mute/4"]})
        eng = m32_engine.Engine(cfg)
        eng.start()
        wait_for(lambda: eng.packets > 3, 5.0)
        eng.set_feature("safe_mode", True)
        ok1 = eng.dry_run
        eng.set_feature("safe_mode", False)
        ok2 = not eng.dry_run
        eng.request_stop(); eng.join(timeout=2.0)
        check("chalu haalat ma toggle badli shakay", ok1 and ok2)

        # mute_on_exit band -> band karta vakhte kai na moklay
        before = len(sim.received)
        run_engine(sim, {"meter_index": 0, "fx_targets": ["/config/mute/6"],
                         "features": {"auto_fx": False, "start_muted": False,
                                      "mute_on_exit": False}}, 3.0)
        after = [p for p, _v in sim.received[before:] if p == "/config/mute/6"]
        check("Band karta mute toggle band: kai na jay", not after,
              "%d command" % len(after))

        # mute_on_exit chalu -> band karta vakhte mute jay
        before = len(sim.received)
        run_engine(sim, {"meter_index": 0, "fx_targets": ["/config/mute/6"],
                         "features": {"auto_fx": False, "start_muted": False,
                                      "mute_on_exit": True}}, 3.0)
        after = [v for p, v in sim.received[before:] if p == "/config/mute/6"]
        check("Band karta mute toggle chalu: mute jay", after == [1],
              "malyu: %s" % after)

        # ---------------- FADER / MUTE dhyanma ----------------
        def set_ch1(**kw):
            for key, val in kw.items():
                sim._set_state("/ch/01/" + key.replace("_", "/"), val)

        set_ch1(mix_fader=0.75, mix_on=1, grp_dca=0, grp_mute=0)
        eng, logs = run_engine(sim, {"meter_index": 0,
                                     "fx_targets": ["/config/mute/1"]}, 8.0)
        check("Fader uncho -> chalu thay",
              any("MIC ON" in m for m in logs), eng.channel_state_text(1))

        set_ch1(mix_fader=0.0)
        eng, logs = run_engine(sim, {"meter_index": 0,
                                     "fx_targets": ["/config/mute/1"]}, 8.0)
        check("Fader SAV NICHE -> chalu na thay",
              not any("MIC ON" in m for m in logs), eng.channel_state_text(1))

        set_ch1(mix_fader=0.75, mix_on=0)
        eng, logs = run_engine(sim, {"meter_index": 0,
                                     "fx_targets": ["/config/mute/1"]}, 8.0)
        check("Channel MUTE -> chalu na thay",
              not any("MIC ON" in m for m in logs), eng.channel_state_text(1))

        set_ch1(mix_on=1, grp_dca=1)
        sim._set_state("/dca/1/on", 0)
        eng, logs = run_engine(sim, {"meter_index": 0,
                                     "fx_targets": ["/config/mute/1"]}, 8.0)
        check("DCA band -> chalu na thay",
              not any("MIC ON" in m for m in logs), eng.channel_state_text(1))
        sim._set_state("/dca/1/on", 1)

        set_ch1(grp_dca=0, grp_mute=2)
        sim._set_state("/config/mute/2", 1)
        eng, logs = run_engine(sim, {"meter_index": 0,
                                     "fx_targets": ["/config/mute/1"]}, 8.0)
        check("Mute group chalu -> chalu na thay",
              not any("MIC ON" in m for m in logs), eng.channel_state_text(1))
        sim._set_state("/config/mute/2", 0)

        # toggle band karo to juni rite chale
        set_ch1(grp_mute=0, mix_fader=0.0)
        eng, logs = run_engine(sim, {"meter_index": 0,
                                     "fx_targets": ["/config/mute/1"],
                                     "features": {"respect_fader": False}}, 8.0)
        check("toggle band -> fader dhyanma na le",
              any("MIC ON" in m for m in logs))
        set_ch1(mix_fader=0.75)

        # ---------------- ghani channel ----------------
        # CH 4 (tabla, jaldi jaldi) + CH 9 (playback, haméshaa chalu)
        eng, logs = run_engine(sim, {"meter_index": [3, 8],
                                     "fx_targets": ["/config/mute/2"],
                                     "hold_time": 1.0}, 8.0)
        offs = [m for m in logs if "SILENCE" in m and "FX BAND" in m]
        check("ghani channel: koi pan ek bole to chalu rahe",
              len(offs) <= 1, "%d var band thayu" % len(offs))

        # ---------------- threshold ----------------
        eng, logs = run_engine(sim, {"meter_index": 0,
                                     "fx_targets": ["/config/mute/6"],
                                     "threshold_db": -3.0}, 5.0)
        check("threshold uncho hoy to chalu na thay",
              not any("MIC ON" in m for m in logs))

        # ---------------- live setting badalvi ----------------
        cfg = dict(core.DEFAULTS)
        cfg.update({"mixer_ip": "127.0.0.1", "meter_index": 0,
                    "fx_targets": ["/config/mute/1"]})
        eng = m32_engine.Engine(cfg)
        eng.start()
        wait_for(lambda: eng.packets > 3, 5.0)
        eng.set_params(threshold_db=-11.0, hold_time=2.5, meter_index=[0, 4])
        time.sleep(0.5)
        ok = (abs(eng.threshold + 11.0) < 0.01 and abs(eng.hold - 2.5) < 0.01
              and eng.indexes == [0, 4])
        eng.request_stop(); eng.join(timeout=2.0)
        check("chalu haalat ma setting badli shakay", ok,
              "th=%.1f hold=%.1f idx=%s" % (eng.threshold, eng.hold, eng.indexes))

    finally:
        sim.request_stop()
        time.sleep(0.3)


# ================================================================ 5. gui
def test_gui():
    section("5. Screen wado program (GUI)")
    try:
        import tkinter as tk
    except ImportError:
        check("tkinter chhe", False, "Python ma tkinter nathi")
        return

    try:
        import m32_gui
        root = tk.Tk()
        root.withdraw()
        app = m32_gui.App(root)
        root.update()

        check("GUI banyu", True, "32 channel row")
        check("badhi channel row banni", len(app.ch_vars) == 32)

        app.cat_var.set("Channel")
        app._fill_catalog()
        check("catalog badli shakay", len(app._cat_paths) == 32,
              "%d channel" % len(app._cat_paths))

        n = len(app._target_paths)
        app.cat_list.selection_set(8)
        app.add_target()
        check("target umeri shakay", len(app._target_paths) == n + 1,
              str(app._target_paths))

        app.remove_target(app._target_paths[-1])
        check("target kaadhi shakay", len(app._target_paths) == n)

        app.ch_vars[1].set(True)
        app.ch_vars[5].set(True)
        check("channel toggle chale", app._selected_indexes() == [0, 4],
              core.channel_names(app._selected_indexes()))

        # ---- toggle button ----
        # auto_fx = niche nu MOTU toggle, etle feat_vars ma nathi.
        # switch_* wala biji tab (Smart Switch) ma chhe -- pan feat_vars
        # ma to hova j joiye, nahi to save thay nahi.
        want = set(core.FEATURES) - {"auto_fx"}
        missing = sorted(want - set(app.feat_vars))
        check("badha feature na toggle banya", not missing,
              "%d toggle%s" % (len(app.feat_vars),
                               ("  KHUTE CHHE: " + ", ".join(missing))
                               if missing else ""))
        check("Smart Switch nu toggle chhe", "auto_switch" in app.feat_vars)

        v = tk.BooleanVar(value=False)
        tog = m32_gui.Toggle(root, variable=v)
        tog._clicked()
        on_after = v.get()
        tog._clicked()
        check("toggle dabave etle badlay", on_after and not v.get())

        app.feat_vars["safe_mode"].set(True)
        check("Safe Mode toggle vanchay chhe",
              app.features_dict()["safe_mode"] is True)
        app.feat_vars["safe_mode"].set(False)

        # target no potano toggle
        if app._target_paths:
            p0 = app._target_paths[0]
            app._target_toggled(p0, False)
            off_ok = p0 not in app._enabled_targets()
            app._target_toggled(p0, True)
            on_ok = p0 in app._enabled_targets()
            check("target no toggle chale", off_ok and on_ok)

        app.run_var.set(False)
        app._update_run_label()
        check("dareki channel no FADER khano chhe",
              len(app.ch_faders) == 32)

        check("MOTO automation toggle chhe",
              hasattr(app, "run_toggle") and hasattr(app, "run_var"))

        if app.engine:
            app.engine.request_stop()
        root.destroy()
    except Exception as e:
        check("GUI banyu", False, "%s: %s" % (type(e).__name__, e))


# ================================================================ 6. Switch
def _katha(seed=11):
    """Nakli katha: vakta bole chhe, vachche vishram le chhe."""
    import random
    rnd = random.Random(seed)

    def speech(t, quiet=None):
        if quiet and quiet[0] <= t < quiet[1]:
            return -70.0 + rnd.uniform(-1, 1)      # vishram, line jivti
        return -40.0 + rnd.uniform(-12, 6)         # bole chhe
    return speech


def _run(ctl, t0, t1, zoom, aux, step=0.05):
    t = t0
    while t < t1:
        ctl.feed({8: zoom(t), 12: aux(t)}, now=t)
        ctl.tick(now=t)
        t += step
    return t


def _ctl(**over):
    cfg = {"stable_s": 5.0, "min_dwell_s": 2.0, "pause_wait_s": 4.0,
           "sources": [
               {"name": "Zoom (PC)", "index": 8, "targets": ["/ch/09/mix/on"]},
               {"name": "Aux 1", "index": 12, "targets": ["/auxin/01/mix/on"]}]}
    cfg.update(over)
    c = m32_switcher.SwitchController()
    c.configure(cfg)
    c.set_features({"auto_switch": True})
    return c


DEAD_LINE = -95.0


def test_switch():
    section("6. Smart Source Switch (be Zoom)")
    sp = _katha()

    # ---- vakta atke to switch NA thavo joiye (sauthi agatya no test) ----
    c = _ctl()
    _run(c, 0, 3, lambda t: sp(t), lambda t: sp(t))
    first = c.live.name
    _run(c, 3, 9, lambda t: sp(t, (3, 8)), lambda t: sp(t, (3, 8)))
    check("vakta 5 sec atke to switch NA thay", c.live.name == first,
          "live = %s" % c.live.name)

    # ---- line mari jay to switch thavo joiye ----
    c = _ctl()
    _run(c, 0, 3, lambda t: sp(t), lambda t: sp(t))
    _run(c, 3, 12, lambda t: DEAD_LINE, lambda t: sp(t))
    check("line mari jay to Aux par switch thay", c.live.name == "Aux 1",
          "live = %s" % c.live.name)

    # ---- cross-check thi jaldi switch thay ----
    c = _ctl()
    _run(c, 0, 3, lambda t: sp(t), lambda t: sp(t))
    _run(c, 3, 12, lambda t: DEAD_LINE, lambda t: sp(t))
    took = c.last_switch - 3.0
    check("cross-check thi jaldi (5 sec ni ander)", took < 5.0,
          "%.1f second ma switch thayu" % took)

    # ---- cross-check band hoy to dhime, pan thay to khari ----
    c = _ctl()
    c.set_features({"auto_switch": True, "switch_cross_check": False})
    _run(c, 0, 3, lambda t: sp(t), lambda t: sp(t))
    _run(c, 3, 18, lambda t: DEAD_LINE, lambda t: sp(t))
    check("cross-check band: dhime pan switch thay", c.live.name == "Aux 1",
          "%.1f second" % (c.last_switch - 3.0))

    # ---- sthir thay pachhi j pachha javu ----
    c = _ctl()
    _run(c, 0, 3, lambda t: sp(t), lambda t: sp(t))
    _run(c, 3, 12, lambda t: DEAD_LINE, lambda t: sp(t))
    _run(c, 12, 15, lambda t: sp(t), lambda t: sp(t))
    early = c.live.name
    _run(c, 15, 26, lambda t: sp(t), lambda t: sp(t, (20, 22)))
    check("3 sec ma pachha NA jay (sthirta baaki)", early == "Aux 1", early)
    check("sthir thay pachhi Zoom par pachha", c.live.name == "Zoom (PC)",
          "live = %s" % c.live.name)

    # ---- vachche fari tute to timer 0 thi ----
    c = _ctl()
    _run(c, 0, 3, lambda t: sp(t), lambda t: sp(t))
    _run(c, 3, 12, lambda t: DEAD_LINE, lambda t: sp(t))
    _run(c, 12, 15, lambda t: sp(t), lambda t: sp(t))
    _run(c, 15, 24, lambda t: DEAD_LINE, lambda t: sp(t))
    _run(c, 24, 28, lambda t: sp(t), lambda t: sp(t))
    check("vachche fari tute to timer 0 thi", c.live.name == "Aux 1",
          "haju Aux par j chhe (sacchu)")

    # ---- banne mari jay to KAI na thay ----
    c = _ctl()
    _run(c, 0, 3, lambda t: sp(t), lambda t: sp(t))
    n0 = c.switch_count
    _run(c, 3, 20, lambda t: DEAD_LINE, lambda t: DEAD_LINE)
    check("banne mari jay to kai na thay", c.switch_count == n0,
          "switch = %d" % (c.switch_count - n0))

    # ---- 1 j source hoy to chale j nahi ----
    c = _ctl(sources=[{"name": "Zoom", "index": 8,
                       "targets": ["/ch/09/mix/on"]}])
    ok, why = c.ready()
    check("1 j source hoy to chalu na thay", not ok, why)

    # ---- sapat hum ne awaaj na ganvo (1-2 dB walo prashn) ----
    s1 = m32_switcher.Source({"name": "x", "index": 0},
                             m32_switcher.defaults())
    t = 0.0
    while t < 3.0:                       # -50 dB, pan sav sapat
        s1.feed(-50.0 + (0.5 if int(t * 10) % 2 else -0.5), t, True)
        t += 0.05
    check("sapat hum ne awaaj na ganyo", not s1.alive,
          "wiggle = %.1f dB" % s1.wiggle())

    s2 = m32_switcher.Source({"name": "y", "index": 0},
                             m32_switcher.defaults())
    t = 0.0
    while t < 3.0:                       # e j level, pan vadhghat sathe
        s2.feed(-50.0 + (12.0 if int(t * 4) % 2 else -8.0), t, True)
        t += 0.05
    check("vadhghat wala ne awaaj ganyo", s2.alive,
          "wiggle = %.1f dB" % s2.wiggle())

    # ---- data band thay to freeze ----
    c = _ctl()
    _run(c, 0, 3, lambda t: sp(t), lambda t: sp(t))
    n0 = c.switch_count
    for i in range(20):
        c.tick(now=3.0 + i * 0.5)        # feed() nathi -- data band
    check("data band thay to switch na kare",
          c.switch_count == n0 and c.frozen, "frozen = %s" % c.frozen)

    # ---- HOLD dabave to kai na thay ----
    c = _ctl()
    _run(c, 0, 3, lambda t: sp(t), lambda t: sp(t))
    c.set_hold(True)
    n0 = c.switch_count
    _run(c, 3, 14, lambda t: DEAD_LINE, lambda t: sp(t))
    check("HOLD dabave to switch na thay", c.switch_count == n0)

    # ---- shuruaat thi j line mareli hoy to pan pakdai javi joiye ----
    # (aa bug kharaa M32 par pakadayo hato -- 2 second ni itihas baari
    #  ne lidhe "line mari" kyarey thatu j nahi)
    c = _ctl()
    _run(c, 0, 12, lambda t: DEAD_LINE, lambda t: sp(t))
    zoom = c.sources[0]
    check("shuruaat thi j mareli line pakdai", zoom.state == "DEAD",
          "halat = %s, chup = %.1f s" % (zoom.state, zoom.quiet_for(12.0)))
    check("shuruaat thi mareli hoy to Aux par jay", c.live.name == "Aux 1",
          "live = %s" % c.live.name)

    # ---- STEREO PAIR : ek source ma be channel (L ane R) ----
    c = m32_switcher.SwitchController()
    c.configure({"stable_s": 5.0, "min_dwell_s": 2.0, "sources": [
        {"name": "Zoom", "indexes": [13], "targets": ["/ch/14/mix/on"]},
        {"name": "Photo Video", "indexes": [30, 31],
         "targets": ["/ch/31/mix/on", "/ch/32/mix/on"],
         "faders": ["/ch/31/mix/fader", "/ch/32/mix/fader"]}]})
    c.set_features({"auto_switch": True})
    pv = c.sources[1]
    check("stereo pair: be index sambhalay", pv.indexes == [30, 31],
          str(pv.indexes))
    check("stereo pair: be target mute thashe", len(pv.targets) == 2,
          ", ".join(pv.targets))
    check("stereo pair: be fader ramp thashe", len(pv.faders) == 2,
          ", ".join(pv.faders))

    # L chup pan R ma awaaj -> source "bole chhe" ganvi joiye
    t = 0.0
    while t < 3.0:
        c.feed({13: DEAD_LINE, 30: -120.0, 31: sp(t)}, now=t)
        c.tick(now=t)
        t += 0.05
    check("be ma thi ek ma awaaj hoy to pan pakdai jay",
          pv.state == "TALKING", "halat = %s, %.1f dB" % (pv.state, pv.db))

    # ---- juni config (index) pan chalvi joiye ----
    c2 = m32_switcher.SwitchController()
    c2.configure({"sources": [{"name": "a", "index": 7, "targets": ["/x"]},
                              {"name": "b", "index": 9, "targets": ["/y"]}]})
    check("juni config ('index') pan chale", c2.sources[0].indexes == [7],
          str(c2.sources[0].indexes))

    # ---- be source ek j channel na sambhale ----
    c3 = m32_switcher.SwitchController()
    c3.configure({"sources": [
        {"name": "a", "indexes": [30, 31], "targets": ["/x"]},
        {"name": "b", "indexes": [31], "targets": ["/y"]}]})
    ok3, why3 = c3.ready()
    check("be source ek j channel na sambhale", not ok3, why3)

    # ---- hathe switch kari shakay ----
    c = _ctl()
    _run(c, 0, 3, lambda t: sp(t), lambda t: sp(t))
    c.force_switch("Aux 1", now=3.0)
    check("hathe switch kari shakay", c.live.name == "Aux 1")


# ================================================================ 7. R12
def test_fader_boost():
    section("7. Fader jate 0 dB par ane pachho (R12)")
    check("0 dB no fader value 0.75 chhe",
          abs(core.db_to_fader(0.0) - 0.75) < 1e-9,
          "%.4f" % core.db_to_fader(0.0))
    ok = all(abs(core.fader_to_db(core.db_to_fader(d)) - d) < 0.01
             for d in (10, 0, -5, -20, -30, -60, -90))
    check("dB -> fader -> dB pachhu e j aave", ok)

    sim = m32_simulator.Simulator(verbose=False)
    sim.start()
    sim.ready.wait(2.0)
    if sim.error:
        check("nakli mixer chalu thayo", False, str(sim.error))
        return
    try:
        sim.state["/dca/8/fader"] = core.db_to_fader(-20.0)
        cfg = dict(core.DEFAULTS)
        # CH 1 = Guruji (3.5 s gaay / 2.5 s shant) -- hold 0.8 s karta
        # shanti lambi chhe, etle MUTE chokkas thashe (test bharoso patra)
        cfg.update({"mixer_ip": "127.0.0.1", "mixer_port": 10023,
                    "meter_index": 0, "fx_targets": ["/config/mute/1"],
                    "threshold_db": -40.0, "hold_time": 0.8,
                    "attack_time": 0.02})
        cfg["features"] = dict(core.feature_defaults())
        cfg["features"].update({"fader_boost": True, "respect_fader": False,
                                "auto_fx": True, "start_muted": False})
        cfg["fader_boost"] = {"target": "/dca/8/fader", "to_db": 0.0,
                              "tolerance_db": 1.0, "ramp_ms": 100}
        eng = m32_engine.Engine(cfg)
        eng.start()
        time.sleep(1.5)
        eng.set_active(True)

        up = wait_for(lambda: core.fader_to_db(
            sim.state.get("/dca/8/fader")) > -1.0, 10.0)
        check("unmute thay to fader 0 dB par gayo", up,
              "%.1f dB" % core.fader_to_db(sim.state.get("/dca/8/fader")))

        back = wait_for(lambda: core.fader_to_db(
            sim.state.get("/dca/8/fader")) < -19.0, 10.0)
        check("mute thay to fader -20 dB par pachho", back,
              "%.1f dB" % core.fader_to_db(sim.state.get("/dca/8/fader")))

        eng.request_stop()
        eng.join(timeout=2.0)
    finally:
        sim.request_stop()
        time.sleep(0.3)


# ================================================================ 8. meter
def test_meter_all():
    section("8. Aakha bank na meter (Aux In / Bus pan source bani shake)")

    check("METER_COUNT = 70", core.METER_COUNT == 70,
          "bank 0 ni badhi value (CH+Aux+FX+Bus+Mtx)")

    cfg = dict(core.DEFAULTS)
    cfg["meter_index"] = 32                     # Aux In 1 -- CH 32 pachhi
    cfg["features"] = dict(core.feature_defaults(), auto_switch=True)
    cfg["auto_switch"] = dict(core.switch_defaults(), sources=[
        {"name": "Aux In 1", "on": True, "index": 32,
         "targets": ["/auxin/01/mix/on"]},
        {"name": "CH 1", "on": True, "index": 0,
         "targets": ["/ch/01/mix/on"]},
    ])

    # mixer ni jarur nathi -- engine ne sidho nakli meter packet aapiye
    eng = m32_engine.Engine(cfg)
    check("all_levels 70 lamba chhe", len(eng.all_levels) == core.METER_COUNT,
          "%d" % len(eng.all_levels))

    vals = [-90.0] * core.METER_COUNT
    vals[32] = -12.0                            # Aux In 1 ma motho awaaj
    eng._on_packet("/meters/0", [m32_simulator.make_blob(vals)])

    check("Aux In 1 (index 32) no level engine ne malyo",
          abs(eng.all_levels[32] + 12.0) < 0.5,
          "%.1f dB" % eng.all_levels[32])

    aux = eng.switcher.sources[0]
    check("Smart Switch ne CH 32 pachhi no level malyo",
          abs(aux.db + 12.0) < 0.5, "%s = %.1f dB" % (aux.name, aux.db))
    check("etli source 'jivti' ganai", aux.alive is True,
          "state %s" % aux.state)

    check("Auto FX e pan te level vaapryo (crash nahi)",
          eng.active_index == 32 and abs(eng.level_db + 12.0) < 0.5,
          "index %d, %.1f dB" % (eng.active_index, eng.level_db))

    # mixer ochhi value aape to jena meter j nathi aavta te index ne
    # "mari gai" na manvu -- fakt "khabar nathi"
    eng2 = m32_engine.Engine(cfg)
    eng2._on_packet("/meters/0", [m32_simulator.make_blob([-90.0] * 32)])
    a2 = eng2.switcher.sources[0]
    check("fakt 32 value aave to CH 32 pachhi nu 'khabar nathi' rahe",
          not a2.started and a2.db == -128.0, "db %.1f" % a2.db)


# ================================================================ 9. log
def test_logging():
    section("9. Log file lakhvu ('logging' toggle)")

    name = "test-log-check.log"
    path = os.path.join(core.HERE, name)
    if os.path.exists(path):
        os.remove(path)

    def txt():
        if not os.path.exists(path):
            return ""
        with open(path, encoding="utf-8") as f:
            return f.read()

    cfg = dict(core.DEFAULTS)
    cfg["log_file"] = name
    seen = []
    eng = m32_engine.Engine(cfg, on_log=seen.append)
    try:
        eng.on_log("pehli line")
        check("log file jate bani ane lakhai", "pehli line" in txt(), name)
        check("sathe screen par pan gayu", seen == ["pehli line"])

        eng.set_feature("logging", False)
        eng.on_log("aa na lakhavi joiye")
        check("'logging' BAND karo to file ma na jay",
              "aa na lakhavi joiye" not in txt())
        check("pan screen par to dekhay", "aa na lakhavi joiye" in seen)

        eng.set_feature("logging", True)
        eng.on_log("fari chalu")
        check("fari CHALU karo to pachhu lakhay (restart vagar)",
              "fari chalu" in txt())
    finally:
        eng._close_log()
        try:
            os.remove(path)
        except OSError:
            pass

    # log_file khali hoy to kai file na banavvi
    cfg2 = dict(core.DEFAULTS)
    cfg2["log_file"] = ""
    eng2 = m32_engine.Engine(cfg2)
    eng2.on_log("kai file nathi")
    check("log_file khali hoy to kai na lakhay", eng2.log_path == "")


# ================================================================ main
def main():
    print(LINE)
    print("   BADHU BARABAR CHALE CHHE ?  --  aapoaap test")
    print("   (mixer ni jarur nathi)")
    print(LINE)

    start = time.time()
    for fn in (test_osc, test_db, test_config, test_features, test_fader,
               test_live, test_switch, test_fader_boost, test_meter_all,
               test_logging, test_gui):
        try:
            fn()
        except Exception as e:
            check("%s ma bhool" % fn.__name__, False,
                  "%s: %s" % (type(e).__name__, e))

    print()
    print(LINE)
    total = len(PASS) + len(FAIL)
    if FAIL:
        print("   %d/%d PASS   --   %d FAIL" % (len(PASS), total, len(FAIL)))
        print()
        print("   Aa vaandha chhe:")
        for name in FAIL:
            print("     X  %s" % name)
    else:
        print("   BADHA %d TEST PASS !   Badhu barabar chale chhe." % total)
    print("   Time: %.1f second" % (time.time() - start))
    print(LINE)
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
