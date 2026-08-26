"""
channel_select.py  -  Jate channel pasand karo.

Aa tool mixer mathi BADHI 32 channel na NAAM vanchi ne batave chhe,
ane sathe atyare kaya channel ma awaaj aave chhe te pan batave chhe.
Pachhi tame fakt number lakho:  1,5,9
ane te config.json ma save thai jashe.

Chalavva:  2-CHANNEL-SELECT.bat  par double-click
Athva:     python channel_select.py
Sidhu:     python channel_select.py 1,5,9      (puchhya vagar save)
"""

import sys
import time

import m32_core as core
import osc_lite

core.setup_console()

LINE = "=" * 62
NUM_CHANNELS = 32


# ---------------------------------------------------------------- names
def read_names(mixer, count=NUM_CHANNELS, wait=2.0):
    """Mixer mathi channel na naam vanche. Return {channel_no: name}."""
    paths = {}
    for ch in range(1, count + 1):
        path = "/ch/%02d/config/name" % ch
        paths[path] = ch
        mixer.send(path)
        time.sleep(0.004)              # mixer ne bharai na jaay

    names = {}
    end = time.time() + wait
    while time.time() < end and len(names) < count:
        mixer.wait(0.05)
        for address, args in mixer.receive():
            ch = paths.get(address)
            if ch and args and isinstance(args[0], str):
                names[ch] = args[0].strip()
    return names


def read_levels(mixer, bank, seconds=3.0, count=NUM_CHANNELS):
    """Thodi var meter vanchi ne dar channel no sauthi motho awaaj shodhe."""
    mixer.subscribe_meters([bank])
    want = "/meters/%d" % bank
    peaks = [0.0] * count
    end = time.time() + seconds

    while time.time() < end:
        left = end - time.time()
        for _ in range(64):
            msgs = mixer.receive()
            if not msgs:
                break
            for address, args in msgs:
                if address != want:
                    continue
                for a in args:
                    if not isinstance(a, (bytes, bytearray)):
                        continue
                    values = osc_lite.decode_meter_blob(a)
                    for i in range(min(count, len(values))):
                        av = abs(values[i])
                        if av > peaks[i]:
                            peaks[i] = av
        mixer.keep_alive()
        if sys.stdout.isatty():          # file/pipe ma progress na lakho
            sys.stdout.write(
                "\r  Channel na awaaj sambhalu chhu ... %.0f second baaki  "
                % (left + 0.9))
            sys.stdout.flush()
        time.sleep(0.01)

    sys.stdout.write("\r" + " " * 70 + "\r")
    return [core.to_db(v) for v in peaks]


# ---------------------------------------------------------------- display
def show_table(names, levels, current):
    print()
    print("   %-4s %-16s %-10s %-6s   %-4s %-16s %-10s %s"
          % ("CH", "NAAM", "AWAAJ", "", "CH", "NAAM", "AWAAJ", ""))
    print("   " + "-" * 106)

    half = NUM_CHANNELS // 2
    for row in range(half):
        line = "   "
        for ch in (row + 1, row + 1 + half):
            name = names.get(ch, "-") or "-"
            db = levels[ch - 1] if levels and ch - 1 < len(levels) else -128.0
            db_txt = "%.0f dB" % db if db > -90 else "shant"
            mark = "<==" if (ch - 1) in current else ("  *" if db > -50 else "   ")
            line += "%-4d %-16.16s %-10s %-6s " % (ch, name, db_txt, mark)
        print(line)
    print()
    print("   <== = atyare pasand thayel      * = atyare aa ma awaaj aave chhe")


def parse_channels(text, count=NUM_CHANNELS):
    """
    "1,5,9"  athva  "1 5 9"  athva  "1-4,9"  ne  [0,4,8]  ma feravé.
    Return: (indexes, khota tukda ni list)
    """
    text = text.replace(" ", ",").replace(";", ",")
    out, bad = [], []
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            if "-" in part:                      # "1-4" = 1,2,3,4
                a, b = part.split("-", 1)
                lo, hi = int(a), int(b)
                if lo > hi:
                    lo, hi = hi, lo
                nums = list(range(lo, hi + 1))
            else:
                nums = [int(part)]
        except ValueError:
            bad.append(part)
            continue

        for ch in nums:
            if 1 <= ch <= count:
                if ch - 1 not in out:
                    out.append(ch - 1)
            else:
                bad.append(str(ch))
    return out, bad


# ---------------------------------------------------------------- main
def main():
    cfg, rest = core.apply_args(core.load_config(), sys.argv[1:])
    bank = int(cfg.get("meter_bank", 0))
    current = core.parse_indexes(cfg.get("meter_index", 0))

    print(LINE)
    print("   CHANNEL PASAND KARO")
    print(LINE)
    print("  Mixer : %s:%s" % (cfg["mixer_ip"], cfg["mixer_port"]))

    mixer = core.Mixer(cfg["mixer_ip"], cfg["mixer_port"])
    info = mixer.query_info(wait=1.5)

    names, levels = {}, []
    if info:
        print("  [OK] Mixer malyu -> %s (firmware %s)"
              % (info.get("name", "?"), info.get("firmware", "?")))
        print(LINE)
        print("  Channel na naam vanchu chhu...")
        names = read_names(mixer)
        print("  [OK] %d channel na naam malya" % len(names))
        levels = read_levels(mixer, bank, 3.0)
    else:
        print("  [!!] Mixer jawab nathi aapto -- naam ane awaaj batavi nahi shaku.")
        print("       Channel number to tame have pan lakhi shako chho.")
        print(LINE)

    # -------------------------------------------------- sidhu argument
    direct = ",".join(rest).strip()
    if direct:
        indexes, bad = parse_channels(direct)
        if bad:
            print("  [!] Aa samjayu nahi: %s" % ", ".join(bad))
        if indexes:
            core.save_config({"meter_index":
                              indexes if len(indexes) > 1 else indexes[0]})
            print("  [OK] Save thayu -> %s" % core.channel_names(indexes))
        else:
            print("  [X] Ek pan valid channel na malyu. Kai save karyu nathi.")
        print(LINE)
        mixer.close()
        return

    # -------------------------------------------------- table + puchho
    if names or levels:
        show_table(names, levels, current)

    print()
    print(LINE)
    print("  Atyare pasand thayel : %s" % core.channel_names(current))
    print(LINE)
    print()
    print("  Kaya channel na mic sambhalva chhe te CHANNEL NUMBER lakho.")
    print("  Dakhla :   1          (fakt channel 1)")
    print("             1,5,9      (channel 1, 5 ane 9)")
    print("             1-4        (channel 1 thi 4)")
    print("             1-4,9,12   (bane rite bhega)")
    print()
    print("  (koi PAN ek ma awaaj aave -> FX chalu, badha shant thay -> FX band)")
    print()

    while True:
        try:
            text = input("  Channel number lakho (khali rakhi ne ENTER = na badlo): ")
        except EOFError:
            text = ""
        text = text.strip()

        if not text:
            print("  Kai badlyu nathi.")
            print(LINE)
            mixer.close()
            return

        indexes, bad = parse_channels(text)
        if bad:
            print("  [!] Aa samjayu nahi: %s   (1 thi %d vachche j lakho)"
                  % (", ".join(bad), NUM_CHANNELS))
        if indexes:
            break
        print("  [X] Fari lakho.")

    print()
    print("  Pasand thayu : %s" % core.channel_names(indexes))
    if names:
        for i in indexes:
            nm = names.get(i + 1, "")
            if nm:
                print("      CH %-3d = %s" % (i + 1, nm))
    print()

    try:
        ans = input("  Save karu? (y/n, Enter = y): ").strip().lower()
    except EOFError:
        ans = "y"

    if ans in ("", "y", "yes"):
        core.save_config({"meter_index":
                          indexes if len(indexes) > 1 else indexes[0]})
        print("  [OK] config.json ma save thai gayu!")
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
