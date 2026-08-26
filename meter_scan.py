"""
meter_scan.py  -  Kai channel sambhalvi te aapoaap shodhe chhe.

M32 meter data ne "bank" ane "index" thi olakhvu pade chhe.
Aa tool tamne kahe chhe: pehla shant raho, pachhi MIC ma bolo --
ane jate j nakki kare chhe ke kaya index ma tamaro awaaj aavyo.

EK KARTA VADHARE MIC pan umeri shakay chhe (dakhla: singer + tabla + flute).
Koi pan ek ma awaaj aave to FX chalu thai jashe.

Pachhi badhu config.json ma save kari de chhe.
"""

import sys
import time

import m32_core as core
import osc_lite

core.setup_console()

LINE = "=" * 62
PROBE_BANKS = [0, 1, 2, 3, 4, 5]
MIN_DIFF = 6.0          # aatla dB no farak hoy to j "male gayu" ganvu
MAX_CHANNEL = 32        # fakt input channel 1-32 ma j shodhvu (bus/aux nahi)


# ---------------------------------------------------------------- capture
def collect(mixer, bank, seconds, label):
    """
    'seconds' sudi meter data vanche.
    Return: (peaks list, packet count)   peaks[i] = te index nu sauthi motu value
    """
    mixer.subscribe_meters([bank])
    want = "/meters/%d" % bank
    peaks = []
    packets = 0
    end = time.time() + seconds

    while time.time() < end:
        left = end - time.time()
        for _ in range(64):
            msgs = mixer.receive()
            if not msgs:
                break
            for address, args in msgs:
                if address != want:          # biji bank ignore karo
                    continue
                for a in args:
                    if not isinstance(a, (bytes, bytearray)):
                        continue
                    values = osc_lite.decode_meter_blob(a)
                    if not values:
                        continue
                    packets += 1
                    if len(peaks) < len(values):
                        peaks.extend([0.0] * (len(values) - len(peaks)))
                    for i, v in enumerate(values):
                        av = abs(v)
                        if av > peaks[i]:
                            peaks[i] = av
        mixer.keep_alive()
        if sys.stdout.isatty():          # file/pipe ma progress na lakho
            sys.stdout.write("\r  %s ... %.0f second baaki   "
                             % (label, left + 0.9))
            sys.stdout.flush()
        time.sleep(0.01)

    sys.stdout.write("\r" + " " * 70 + "\r")
    return peaks, packets


def probe_banks(mixer):
    """Kaya bank ma ketli value aave chhe te check kare."""
    print("  Mixer na meter banks check karu chhu...")
    result = {}
    for bank in PROBE_BANKS:
        mixer.subscribe_meters([bank])
        want = "/meters/%d" % bank
        count = 0
        end = time.time() + 0.8
        while time.time() < end:
            mixer.wait(0.02)
            for address, args in mixer.receive():
                if address != want:
                    continue
                for a in args:
                    if isinstance(a, (bytes, bytearray)):
                        vals = osc_lite.decode_meter_blob(a)
                        if vals:
                            count = max(count, len(vals))
        result[bank] = count
        print("    /meters/%d  ->  %s"
              % (bank, ("%d value" % count) if count else "koi data nahi"))
    return result


# ---------------------------------------------------------------- compare
def rank(quiet, loud):
    """
    Shanti ane awaaj sarkhavi ne sauthi saari index shodhe.
    Sort: (1) sauthi vadhare farak, (2) sauthi motho awaaj, (3) nano index
    """
    size = max(len(loud), len(quiet))
    quiet = list(quiet) + [0.0] * (size - len(quiet))
    loud = list(loud) + [0.0] * (size - len(loud))

    scored = []
    for i in range(size):
        q_db = core.to_db(quiet[i])
        l_db = core.to_db(loud[i])
        scored.append((round(l_db - q_db, 1), round(l_db, 1), -i, i, q_db, l_db))
    scored.sort(reverse=True)
    # bus / aux / matrix na meter na levay -- fakt channel 1-32
    return [row for row in scored if row[3] < MAX_CHANNEL]


def show_table(scored, chosen):
    print()
    print("   %-8s %-12s %-12s %-10s" % ("index", "shanti", "awaaj", "farak"))
    print("   " + "-" * 50)
    for diff, _l, _ni, i, q_db, l_db in scored[:5]:
        mark = "  <== AA"if i == chosen else ""
        print("   %-8d %-12s %-12s %+.1f dB%s"
              % (i, "%.1f dB" % q_db, "%.1f dB" % l_db, diff, mark))
    print()


def ask(prompt, default="y"):
    try:
        ans = input(prompt).strip().lower()
    except EOFError:
        return default
    return ans or default


# ---------------------------------------------------------------- main
def main():
    cfg, rest = core.apply_args(core.load_config(), sys.argv[1:])
    bank = int(cfg.get("meter_bank", 0))
    for a in rest:                       # "python meter_scan.py 0" pan chale
        try:
            bank = int(a)
        except ValueError:
            pass

    print(LINE)
    print("   METER SCAN  --  kai channel sambhalvi te shodho")
    print(LINE)
    print("  Mixer : %s:%s" % (cfg["mixer_ip"], cfg["mixer_port"]))

    mixer = core.Mixer(cfg["mixer_ip"], cfg["mixer_port"])
    info = mixer.query_info(wait=1.5)
    if info:
        print("  [OK] Mixer malyu -> %s (firmware %s)"
              % (info.get("name", "?"), info.get("firmware", "?")))
    else:
        print("  [!!] Mixer jawab nathi aapto. Pehla 1-FIND-MIXER.bat chalavo.")
        print(LINE)
        mixer.close()
        return
    print(LINE)

    banks = probe_banks(mixer)
    live = [b for b, c in banks.items() if c > 0]
    if not live:
        print()
        print("  [X] Mixer parthi meter data aavtu j nathi.")
        print("      Windows Firewall ma aa python program ne allow karo.")
        print(LINE)
        mixer.close()
        return
    if bank not in live:
        bank = live[0]
    print()
    print("  Vaaparu chhu: /meters/%d  (%d value)" % (bank, banks[bank]))
    print(LINE)

    # ------------------------------------------------------ shanti (ek j var)
    print()
    print("  STEP 1 :  BADHI MIC BAND / SHANT RAHO")
    print("            (aa ek j var karvanu chhe)")
    ask("            taiyar hoy to ENTER dabavo... ", "")
    quiet, n1 = collect(mixer, bank, 4.0, "Shanti record karu chhu")
    print("  [OK] shanti record thai (%d packets)" % n1)
    if not quiet:
        print("  [X] Data na malyo. Fari prayatna karo.")
        mixer.close()
        return

    # ------------------------------------------------------ ek pachhi ek mic
    chosen = []          # [(index, quiet_db, loud_db), ...]
    mic_no = 0

    while True:
        mic_no += 1
        print()
        print(LINE)
        print("  STEP 2.%d :  MIC ma MOTHE THI BOLO / GAO  (6 second)" % mic_no)
        if chosen:
            print("              (ali sudhi umeryu: %s)"
                  % core.channel_names([c[0] for c in chosen]))
            print("              have BIJI mic ma bolo -- pehli vaali chup rakho")
        ask("              taiyar hoy to ENTER dabavi ne bolvanu shuru karo... ", "")

        loud, n2 = collect(mixer, bank, 6.0, "Awaaj record karu chhu -- BOLO")
        print("  [OK] awaaj record thayo (%d packets)" % n2)

        scored = rank(quiet, loud)
        # jeni pasandgi thai gai hoy te fari na levay
        already = {c[0] for c in chosen}
        pick = None
        for diff, _l, _ni, i, q_db, l_db in scored:
            if i not in already:
                pick = (diff, i, q_db, l_db)
                break

        if pick is None or pick[0] < MIN_DIFF:
            show_table(scored, -1)
            print("  [!] Aa mic no awaaj bharoso patra rite na malyo"
                  " (farak %.1f dB)." % (pick[0] if pick else 0.0))
            print("      -> mic no gain vadharo athva vadhare mothe bolo.")
            if ask("      Fari prayatna karvo chhe? (y/n, Enter = y): ") not in ("y", "yes"):
                mic_no -= 1
                break
            mic_no -= 1
            continue

        diff, i, q_db, l_db = pick
        show_table(scored, i)
        print("  ===> MIC %d  =  index %d  (%s)   farak %+.1f dB"
              % (mic_no, i, core.channel_names([i]), diff))
        chosen.append((i, q_db, l_db))

        print()
        if ask("  Biji koi mic pan umervi chhe? (y/n, Enter = n): ", "n") \
                not in ("y", "yes"):
            break

    if not chosen:
        print()
        print("  [X] Ek pan channel na malyu. Kai save karyu nathi.")
        print(LINE)
        mixer.close()
        return

    # ------------------------------------------------------ threshold
    indexes = [c[0] for c in chosen]
    # badhi pasand karel channel ni SHANTI ma sauthi uncho awaaj
    floor_db = max(c[1] for c in chosen)
    # ane teni AWAAJ ma sauthi dheemo awaaj
    ceil_db = min(c[2] for c in chosen)

    if ceil_db - floor_db < MIN_DIFF:
        suggested = floor_db + 6.0
        print()
        print("  [!] Channel o vachche awaaj no farak ghano chhe.")
        print("      Threshold %.1f dB rakhu chhu, pan jarur pade to"
              " config.json ma badlo." % suggested)
    else:
        suggested = floor_db + (ceil_db - floor_db) * 0.35
    suggested = max(-60.0, min(-12.0, round(suggested, 1)))

    print()
    print(LINE)
    print("  PARINAAM")
    print(LINE)
    print("  Channel   : %s" % core.channel_names(indexes))
    print("  index     : %s" % ", ".join(str(i) for i in indexes))
    print("  bank      : %d" % bank)
    print("  Threshold : %.1f dB" % suggested)
    print()
    print("  (shanti sauthi uncha %.1f dB, awaaj sauthi dheemo %.1f dB)"
          % (floor_db, ceil_db))
    if len(indexes) > 1:
        print("  Koi PAN ek channel ma awaaj aave -> FX chalu.")
        print("  BADHI channel shant thay -> FX band.")
    print(LINE)

    if ask("  Aa settings config.json ma save karu? (y/n, Enter = y): ") \
            in ("y", "yes", ""):
        core.save_config({
            "meter_bank": bank,
            "meter_index": indexes if len(indexes) > 1 else indexes[0],
            "threshold_db": suggested,
        })
        print("  [OK] Save thai gayu!")
        print("  Have  4-RUN-AUTOMATION.bat  thi automation chalu karo.")
    else:
        print("  Kai save karyu nathi.")
    print(LINE)
    mixer.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Band karyu.")
