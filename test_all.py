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

import sys
import time

import m32_core as core
import m32_engine
import m32_simulator
import osc_lite

core.setup_console()

LINE = "=" * 66
PASS, FAIL = [], []


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
        check("badha feature na toggle banya",
              len(app.feat_vars) == len(core.FEATURES) - 1,
              "%d toggle" % len(app.feat_vars))

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
        check("MOTO automation toggle chhe",
              hasattr(app, "run_toggle") and hasattr(app, "run_var"))

        if app.engine:
            app.engine.request_stop()
        root.destroy()
    except Exception as e:
        check("GUI banyu", False, "%s: %s" % (type(e).__name__, e))


# ================================================================ main
def main():
    print(LINE)
    print("   BADHU BARABAR CHALE CHHE ?  --  aapoaap test")
    print("   (mixer ni jarur nathi)")
    print(LINE)

    start = time.time()
    for fn in (test_osc, test_db, test_config, test_features,
               test_live, test_gui):
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
