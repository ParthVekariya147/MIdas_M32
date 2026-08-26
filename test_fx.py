"""
test_fx.py  -  FX mute/unmute test.

Aa program config.json ma lakhela FX targets ne 3 var
MUTE / UNMUTE kare chhe. Tame mixer ni screen ane button ni
light jou ne confirm kari shako ke saachi jagya par kaam thay chhe.

Bijo koi path test karvo hoy to:
    python test_fx.py /ch/09/mix/on
"""

import sys
import time

import m32_core as core

core.setup_console()

LINE = "=" * 62

HELP_PATHS = [
    ("/config/mute/5",                        "Mute Group 5  (mute group vaparo tyare)"),
    ("/fxrtn/01/mix/on  +  /fxrtn/02/mix/on", "FX 1 return (stereo)"),
    ("/fxrtn/03/mix/on  +  /fxrtn/04/mix/on", "FX 2 return (stereo)"),
    ("/ch/01/mix/06/on",                      "Channel 1 no FX-1 send (bus 6)"),
    ("/bus/07/mix/on",                        "FX send bus 7"),
    ("/ch/09/mix/on",                         "Koi pan channel (dakhla: 9)"),
]


def main():
    cfg, rest = core.apply_args(core.load_config(), sys.argv[1:])
    targets = rest or list(cfg["fx_targets"])

    print(LINE)
    print("   FX MUTE / UNMUTE  TEST")
    print(LINE)
    print("  Mixer   : %s:%s" % (cfg["mixer_ip"], cfg["mixer_port"]))
    print("  Targets : %s" % ", ".join(targets))
    print(LINE)

    mixer = core.Mixer(cfg["mixer_ip"], cfg["mixer_port"], timeout=0.3)
    info = mixer.query_info(wait=1.5)
    if info:
        print("  [OK] Mixer malyu -> %s" % info.get("name", "?"))
    else:
        print("  [!!] Mixer jawab nathi aapto -- command to moklu chhu,")
        print("       pan pehla 1-FIND-MIXER.bat thi IP check karo.")
    print(LINE)
    print()
    print("  HAVE MIXER NI SCREEN JUO !")
    print("  FX return channel MUTE ane UNMUTE thata dekhavu joiye.")
    print()
    time.sleep(2.0)

    invert = cfg.get("invert", "auto")

    def apply(audible):
        sent = []
        for path in targets:
            v = core.mute_value(path, audible, invert)
            mixer.send(path, v)
            sent.append("%s=%d" % (path, v))
            time.sleep(0.002)
        return ", ".join(sent)

    for round_no in range(1, 4):
        print("  Round %d :  AWAAJ BAND (mute)    ->  %s" % (round_no, apply(False)))
        time.sleep(2.5)
        print("  Round %d :  AWAAJ CHALU (unmute) ->  %s" % (round_no, apply(True)))
        time.sleep(2.5)

    # chhelle safe state = awaaj band
    apply(False)
    print()
    print(LINE)
    print("  Test puro. Chhelle MUTE kari didhu.")
    print()
    print("  JO MIXER PAR KAI J NA BADLAYU HOY:")
    print("  -> config.json ma 'fx_targets' badlo. Options:")
    for path, desc in HELP_PATHS:
        print("     %-40s %s" % (path, desc))
    print()
    print("  -> M32 ma FX 1 no return stereo hoy to fxrtn 01 ANE 02 banne joiye.")
    print()
    print("  JO ULTU THATU HOY (bolo tyare band, chup raho tyare chalu):")
    print("  -> config.json ma  \"invert\"  ne  true  athva  false  karo")
    print("     (atyare: %s)" % cfg.get("invert", "auto"))
    print(LINE)
    mixer.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Band karyu.")
