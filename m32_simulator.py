"""
m32_simulator.py  -  NAKLI (fake) MIDAS M32.

Mixer haath ma na hoy tyare pan AAKHU kaam kari/test kari shakay
te mate aa program tamara PC par j ek nakli M32 chalave chhe.

Aa nakli mixer kharaa M32 jevu j vartey chhe:
  * /info ane /xinfo no jawab aape
  * 32 channel na NAAM aape
  * meter data moklé -- alag alag channel par alag alag "kalakaar"
  * mute/unmute command samje, ane MUTE GROUP no asar
    fxrtn channel par pan batave (kharaa desk ni jem)
  * value vagar puchho to atyar ni halat pachhi aape

Chalavva:
    python m32_simulator.py                 (band karva Ctrl+C)
    python m32_simulator.py --start-quiet 10
    python m32_simulator.py --quiet          (kai print na kare)

Bija program ma andar thi vaparva:
    sim = m32_simulator.Simulator(); sim.start() ... sim.request_stop()
"""

import math
import socket
import struct
import sys
import threading
import time

import osc_lite

PORT = 10023
LINE = "=" * 62

# bank -> ketli value moklvi (kharaa M32 jevu j)
BANK_SIZE = {0: 70, 1: 96, 2: 49, 3: 22, 4: 82, 5: 27, 6: 4}

NUM_CHANNELS = 32
SILENCE = 0.0006                      # ~ -64 dB

# channel na naam
CH_NAMES = {
    1: "Guruji", 2: "Vocal 2", 3: "Chorus", 4: "Tabla", 5: "Flute",
    6: "Harmonium", 7: "Dholak", 8: "Manjira",
    9: "Playback L", 10: "Playback R", 11: "Talk Mic", 12: "Spare",
}

# kaya channel par kevo kalakaar
#   (channel, chalu_second, band_second, offset, nicho_db, uncho_db)
PERFORMERS = [
    (1,  3.5, 2.5, 0.0,  -18,  -8),    # Guruji -- mukhya gaayak
    (2,  2.0, 4.0, 1.0,  -22, -12),    # Vocal 2
    (3,  5.0, 5.0, 2.5,  -26, -16),    # Chorus
    (4,  0.8, 0.4, 0.0,  -20, -10),    # Tabla -- jaldi jaldi
    (5,  2.5, 3.5, 4.1,  -20, -10),    # Flute -- ulta time par
    (6,  6.0, 3.0, 1.5,  -28, -18),    # Harmonium
    (9,  999.0, 0.0, 0.0, -24, -20),   # Playback L -- haméshaa chalu
    (10, 999.0, 0.0, 0.0, -24, -20),   # Playback R
]

# nakli mute group ma kaya channel chhe
#   group 5 = FX returns (tamara kharaa desk jevu j)
MUTE_GROUP_MEMBERS = {
    1: ["/ch/01/mix/on", "/ch/02/mix/on", "/ch/03/mix/on"],
    2: ["/ch/04/mix/on", "/ch/07/mix/on"],
    5: ["/fxrtn/01/mix/on", "/fxrtn/02/mix/on",
        "/fxrtn/07/mix/on", "/fxrtn/08/mix/on"],
}


def _db_to_lin(db):
    return 10.0 ** (db / 20.0)


def performer_level(t, on_s, off_s, offset, lo_db, hi_db):
    """Ek kalakaar no atyar no level (0.0 - 1.0)."""
    cycle = on_s + off_s
    if cycle <= 0:
        return SILENCE
    pos = (t + offset) % cycle
    if pos >= on_s:
        return SILENCE
    wobble = 0.5 + 0.5 * math.sin(pos * 9.0)
    return _db_to_lin(lo_db + (hi_db - lo_db) * wobble)


def make_blob(values):
    return (struct.pack("<i", len(values)) +
            struct.pack("<%df" % len(values), *values))


class Simulator(threading.Thread):
    """Nakli M32. Alag thread ma chale chhe."""

    def __init__(self, port=PORT, quiet_start=0.0, verbose=True):
        threading.Thread.__init__(self, daemon=True)
        self.port = port
        self.quiet_start = float(quiet_start)
        self.verbose = verbose

        self._stop_flag = threading.Event()
        self.ready = threading.Event()
        self.error = None

        self.sock = None
        self.subs = {}                 # (ip, port) -> {bank: expiry}
        self.state = {}                # OSC path -> value
        self.received = []             # test mate: [(path, value), ...]
        self.start_time = 0.0

        # badhu chalu (1) thi shuru
        for ch in range(1, NUM_CHANNELS + 1):
            self.state["/ch/%02d/mix/on" % ch] = 1
        for fx in range(1, 9):
            self.state["/fxrtn/%02d/mix/on" % fx] = 1
        for g in range(1, 7):
            self.state["/config/mute/%d" % g] = 0

    # ------------------------------------------------------------ helpers
    def say(self, msg):
        if self.verbose:
            print(msg)

    def request_stop(self):
        self._stop_flag.set()

    def levels(self, t):
        """Badhi channel na atyar na level."""
        if t < self.quiet_start:
            return [SILENCE] * NUM_CHANNELS
        t -= self.quiet_start
        out = [SILENCE] * NUM_CHANNELS
        for ch, on_s, off_s, offset, lo, hi in PERFORMERS:
            if 1 <= ch <= NUM_CHANNELS:
                out[ch - 1] = performer_level(t, on_s, off_s, offset, lo, hi)
        return out

    def _set_state(self, path, value):
        """Value set kare, ane mute group hoy to teni asar pan lagave."""
        old = self.state.get(path)
        self.state[path] = value
        self.received.append((path, value))

        if path.startswith("/config/mute/"):
            try:
                g = int(path.rsplit("/", 1)[1])
            except ValueError:
                return
            # group CHALU (1) = teni andar na channel MUTE (0)
            for member in MUTE_GROUP_MEMBERS.get(g, []):
                self.state[member] = 0 if value in (1, True) else 1

        if old != value:
            if path.startswith("/config/mute/"):
                word = "MUTE" if value in (1, True) else "UNMUTE"
            else:
                word = "UNMUTE" if value in (1, True) else "MUTE"
            self.say("  >> COMMAND MALYO : %-22s = %s   [%s]"
                     % (path, value, word))

    # ------------------------------------------------------------ handle
    def _handle(self, address, args, src):
        if address in ("/info", "/xinfo"):
            self.sock.sendto(osc_lite.build_message(
                address, "V2.08", "M32-SIMULATOR", "M32", "4.06"), src)
            self.say("  <- %s e info puchhyu" % src[0])
            return

        if address == "/meters":
            bank = 1
            for a in args:
                if isinstance(a, str) and a.startswith("/meters/"):
                    try:
                        bank = int(a.rsplit("/", 1)[1])
                    except ValueError:
                        pass
            entry = self.subs.setdefault(src, {})
            if bank not in entry:
                self.say("  <- %s:%d e /meters/%d subscribe karyu"
                         % (src[0], src[1], bank))
            entry[bank] = time.time() + 10.0
            return

        if address == "/xremote":
            return

        if address.startswith("/ch/") and address.endswith("/config/name"):
            try:
                ch = int(address.split("/")[2])
            except (ValueError, IndexError):
                ch = 0
            self.sock.sendto(osc_lite.build_message(
                address, CH_NAMES.get(ch, "")), src)
            return

        # value sathe = set karo ; value vagar = atyar ni halat pachhi aapo
        if args:
            self._set_state(address, args[0])
        elif address in self.state:
            self.sock.sendto(osc_lite.build_message(
                address, int(self.state[address])), src)

    # ------------------------------------------------------------ run
    def run(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.sock.bind(("0.0.0.0", self.port))
        except OSError as e:
            self.error = e
            self.say("[X] Port %d par bind na thayu: %s" % (self.port, e))
            self.say("    Kadach bijo simulator pehlethi chalu chhe.")
            self.ready.set()
            return
        self.sock.settimeout(0.02)

        self.start_time = time.time()
        next_send = 0.0
        self.ready.set()

        while not self._stop_flag.is_set():
            try:
                data, src = self.sock.recvfrom(65535)
            except (socket.timeout, OSError):
                data = None

            if data:
                for address, args in osc_lite.parse_message(data):
                    try:
                        self._handle(address, args, src)
                    except Exception as e:
                        self.say("  [!] %s -> %s" % (address, e))

            now = time.time()
            if now >= next_send:
                next_send = now + 0.05                      # 20 Hz
                lv = self.levels(now - self.start_time)
                for addr, banks in list(self.subs.items()):
                    for bank, expiry in list(banks.items()):
                        if now > expiry:
                            del banks[bank]
                            continue
                        size = BANK_SIZE.get(bank, 96)
                        values = [SILENCE] * size
                        for i in range(min(size, NUM_CHANNELS)):
                            values[i] = lv[i]
                        try:
                            self.sock.sendto(osc_lite.build_message(
                                "/meters/%d" % bank, make_blob(values)), addr)
                        except OSError:
                            pass
                    if not banks:
                        self.subs.pop(addr, None)

        try:
            self.sock.close()
        except Exception:
            pass


# ---------------------------------------------------------------- CLI
def main():
    argv = sys.argv[1:]
    quiet_start = 0.0
    verbose = True
    for i, a in enumerate(argv):
        if a == "--start-quiet" and i + 1 < len(argv):
            try:
                quiet_start = float(argv[i + 1])
            except ValueError:
                pass
        elif a in ("--quiet", "-q"):
            verbose = False

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    sim = Simulator(quiet_start=quiet_start, verbose=verbose)
    sim.start()
    sim.ready.wait(2.0)
    if sim.error:
        return

    print(LINE)
    print("   NAKLI M32 SIMULATOR  --  port %d par chalu" % PORT)
    print(LINE)
    print("  Have biji window ma aa chalavo:")
    print("      python m32_gui.py --sim")
    print("      python m32_automation.py --ip 127.0.0.1")
    print()
    if quiet_start:
        print("  Pehla %.0f second sav SHANT, pachhi kalakaar shuru." % quiet_start)
    print("  Nakli kalakaar:")
    for ch, on_s, off_s, offset, lo, hi in PERFORMERS:
        kind = ("haméshaa chalu" if on_s > 100
                else "%.1fs gaay / %.1fs shant" % (on_s, off_s))
        print("     CH %-3d %-12s %s" % (ch, CH_NAMES.get(ch, "?"), kind))
    print()
    print("  Mute Group 5 = FX return 1,2,7,8  (kharaa desk jevu)")
    print("  Band karva: Ctrl + C")
    print(LINE)

    try:
        while sim.is_alive():
            time.sleep(0.3)
    except KeyboardInterrupt:
        sim.request_stop()
        print("\n  Simulator band.")


if __name__ == "__main__":
    main()
