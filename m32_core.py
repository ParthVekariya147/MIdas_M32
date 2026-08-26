"""
m32_core.py  -  Midas M32 / Behringer X32 connection helper.

Aa file badha tools (automation, meter_scan, test_fx) vaapre chhe.
Ek j UDP socket thi send ane receive banne thay chhe -- kem ke X32
meter data e j port par pachho moklé chhe jyanthi request aavi hoy.
"""

import json
import math
import os
import select
import socket
import sys
import time

import osc_lite

def _base_folder():
    """
    .py thi chalavo to  -> aa file je folder ma chhe te
    .exe thi chalavo to -> exe je folder ma chhe te
    (jethi config.json ane log haméshaa exe ni bajuma j rahe)
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


HERE = _base_folder()
CONFIG_PATH = os.path.join(HERE, "config.json")


def bundled_file(name):
    """
    .exe ni andar mukel file no rasto.
    (.py thi chalavo to project folder mathi)
    """
    base = getattr(sys, "_MEIPASS", None)
    return os.path.join(base or HERE, name)

# ================================================================ FEATURES
# Dareke feature ON/OFF kari shakay chhe (GUI ma toggle button thi).
#   key : (gujarati naam, tunku samjaan, default)
FEATURES = {
    "auto_fx": (
        "Auto FX Mute",
        "Awaaj aave to target chalu, shanti thay to band",
        True),
    "safe_mode": (
        "Safe Mode (test)",
        "Mixer ne KAI command na moklo -- fakt screen par batavo",
        False),
    "start_muted": (
        "Shuruaat ma mute",
        "Program chalu thay tyare target band kari devo",
        True),
    "mute_on_exit": (
        "Band karta mute",
        "Program band karo tyare target band kari devo",
        True),
    "auto_reconnect": (
        "Jate fari judo",
        "Network tuti jay to jate fari judai jay",
        True),
    "logging": (
        "Log file lakho",
        "Shu shu thayu te automation.log ma sachvo",
        True),
    "show_meter": (
        "Meter batavo",
        "Screen par level bar ane dB batavo",
        True),
}


def feature_defaults():
    return {key: item[2] for key, item in FEATURES.items()}


def get_feature(cfg, key):
    """Feature chalu chhe ke nahi (juni config sathe pan chale)."""
    feats = cfg.get("features")
    if isinstance(feats, dict) and key in feats:
        return bool(feats[key])
    if key in cfg:                       # juni config ma sidhu lakhelu hoy
        return bool(cfg[key])
    item = FEATURES.get(key)
    return bool(item[2]) if item else False


def enabled_targets(cfg):
    """
    Je target chalu chhe te j pachha aapo.
    (band karela target 'fx_targets_off' ma rahe chhe -- kaadhya vagar band)
    """
    off = set(cfg.get("fx_targets_off") or [])
    return [t for t in (cfg.get("fx_targets") or []) if t not in off]


DEFAULTS = {
    "mixer_ip": "192.168.1.15",
    "mixer_port": 10023,
    "meter_bank": 0,
    "meter_index": 0,
    "threshold_db": -40.0,
    "hold_time": 1.5,
    "attack_time": 0.02,
    "fx_targets": ["/fxrtn/01/mix/on", "/fxrtn/02/mix/on"],
    "invert": "auto",
    "start_muted": True,
    "mute_on_exit": True,
    "show_meter": True,
    "log_file": "automation.log",
    "fx_targets_off": [],
}
DEFAULTS["features"] = {key: item[2] for key, item in FEATURES.items()}


# ---------------------------------------------------------------- console
def setup_console():
    """Windows cmd ma unicode crash na thay te mate."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


# ---------------------------------------------------------------- config
def load_config():
    cfg = dict(DEFAULTS)
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for k, v in raw.items():
                if not k.startswith("_") and not k.endswith("_note"):
                    cfg[k] = v
        except Exception as e:
            print("[!] config.json vanchi na shakayu: %s" % e)
            print("[!] Default settings vaparu chhu.")
    else:
        create_default_config()
    return cfg


CONFIG_TEMPLATE = {
    "_comment_1": "==== MIXER CONNECTION ====",
    "mixer_ip": "192.168.1.15",
    "mixer_port": 10023,
    "_comment_2": "==== METER (kaya channel nu awaaj sambhalvu) ====",
    "meter_bank": 0,
    "meter_index": 0,
    "meter_note": ("ek channel: 0  |  ghani channel: [0, 1, 4]  "
                   "(0=CH1, 1=CH2, 4=CH5)"),
    "_comment_3": "==== SENSITIVITY ====",
    "threshold_db": -40.0,
    "hold_time": 1.5,
    "attack_time": 0.02,
    "_comment_4": "==== SHU CHALU / BAND KARVU ====",
    "fx_targets": ["/config/mute/5"],
    "invert": "auto",
    "invert_note": "auto = /config/mute/... mate ulti value aapoaap",
    "_comment_5": "==== FEATURES (GUI na toggle button aa badle chhe) ====",
    "features": {key: item[2] for key, item in FEATURES.items()},
    "fx_targets_off": [],
    "_comment_6": "==== OTHER ====",
    "log_file": "automation.log",
}


def create_default_config():
    """config.json na hoy to navi banavi de -- exe ekli pan chale."""
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(CONFIG_TEMPLATE, f, indent=2, ensure_ascii=False)
        print("[i] navi config.json banavi: %s" % CONFIG_PATH)
        return True
    except Exception as e:
        print("[!] config.json banavi na shakayi: %s" % e)
        return False


# je file exe ni sathe joiye
EXTRA_FILES = ["VAANCHO.txt", "README-GUJARATI.txt",
               "JAVAB-TAMARA-SAVAL.txt", "CODING-GUIDE.txt",
               "REQUIREMENTS.md"]

# aakhu docs folder pan bahar nikale chhe
EXTRA_FOLDERS = ["docs"]


def first_run_setup():
    """
    Pehli var exe chalavo tyare jaruri badhi file jate banavi de,
    jethi ek j exe copy karo to pan badhu taiyar thai jay.
    """
    made = []
    if not os.path.exists(CONFIG_PATH):
        if create_default_config():
            made.append("config.json")

    for name in EXTRA_FILES:
        dest = os.path.join(HERE, name)
        if os.path.exists(dest):
            continue
        src = bundled_file(name)
        if src != dest and os.path.exists(src):
            try:
                with open(src, "rb") as fi, open(dest, "wb") as fo:
                    fo.write(fi.read())
                made.append(name)
            except Exception:
                pass

    for folder in EXTRA_FOLDERS:
        dest_dir = os.path.join(HERE, folder)
        src_dir = bundled_file(folder)
        if src_dir == dest_dir or not os.path.isdir(src_dir):
            continue
        try:
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir)
            for name in os.listdir(src_dir):
                dest = os.path.join(dest_dir, name)
                if os.path.exists(dest):
                    continue
                with open(os.path.join(src_dir, name), "rb") as fi,                         open(dest, "wb") as fo:
                    fo.write(fi.read())
                made.append("%s/%s" % (folder, name))
        except Exception:
            pass
    return made


def save_config(updates: dict):
    """config.json ma comment ane order sachvi ne value update kare."""
    data = {}
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            data = {}
    data.update(updates)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONFIG_PATH)


# ---------------------------------------------------------------- command line
ARG_MAP = {
    "--ip":        ("mixer_ip",     str),
    "--port":      ("mixer_port",   int),
    "--bank":      ("meter_bank",   int),
    "--index":     ("meter_index",  str),   # "0" athva "0,1,4"
    "--threshold": ("threshold_db", float),
    "--hold":      ("hold_time",    float),
    "--seconds":   ("run_seconds",  float),
}

ARG_HELP = ("  Options: --ip <address>  --port <n>  --bank <n>  --index <n[,n,n]>"
            "\n           --threshold <dB>  --hold <sec>  --seconds <sec>  --no-meter")


def apply_args(cfg, argv):
    """
    config.json ne badlya vagar command line thi settings badle chhe.
    Dakhla:  python m32_automation.py --ip 127.0.0.1 --threshold -35
    Return: (cfg, baaki na arguments)
    """
    rest = []
    i = 0
    while i < len(argv):
        flag = argv[i]
        if flag in ("--no-meter", "-q"):
            cfg["show_meter"] = False
            i += 1
        elif flag in ("--dry-run", "--test"):
            cfg["dry_run"] = True       # mixer ne kai command na moklo
            i += 1
        elif flag == "--sim":
            cfg["use_simulator"] = True  # PC par j nakli mixer chalavo
            cfg["mixer_ip"] = "127.0.0.1"
            i += 1
        elif flag in ARG_MAP and i + 1 < len(argv):
            key, cast = ARG_MAP[flag]
            try:
                cfg[key] = cast(argv[i + 1])
            except ValueError:
                print("[!] %s ni value khoti chhe: %s" % (flag, argv[i + 1]))
            i += 2
        else:
            rest.append(flag)
            i += 1
    return cfg, rest


def start_simulator_if_asked(cfg):
    """
    --sim aapyu hoy to aa j program ni andar nakli M32 chalu kari de.
    Return: Simulator object athva None.
    """
    if not cfg.get("use_simulator"):
        return None
    try:
        import m32_simulator
    except ImportError:
        print("[!] m32_simulator.py malyu nahi")
        return None
    sim = m32_simulator.Simulator(verbose=False)
    sim.start()
    sim.ready.wait(2.0)
    if sim.error:
        print("[!] Nakli mixer chalu na thayo (kadach pehlethi chalu chhe)")
        print("    Vaandho nahi -- je chalu chhe teni sathe j judai jais.")
        return None
    print("[i] NAKLI MIXER chalu karyu (--sim). Kharaa mixer ni jarur nathi.")
    return sim


# ---------------------------------------------------------------- dB
def to_db(value: float) -> float:
    """
    Meter value ne dB ma convert kare.
    X32 kyarek 0.0-1.0 (linear) ape chhe, kyarek sidhu dB ape chhe --
    banne case aapoaap sambhali levay chhe.
    """
    if value is None:
        return -128.0
    if value < -1.5 or value > 1.5:      # aa pehlethi j dB chhe
        return float(value)
    if value <= 0.0:
        return -128.0
    db = 20.0 * math.log10(value)
    return db if db > -128.0 else -128.0


def db_bar(db: float, width: int = 24) -> str:
    """Terminal ma dekhata level bar."""
    lo, hi = -60.0, 0.0
    frac = (max(lo, min(hi, db)) - lo) / (hi - lo)
    filled = int(round(frac * width))
    return "[" + "#" * filled + "." * (width - filled) + "]"


# ---------------------------------------------------------------- channels
def parse_indexes(value):
    """
    meter_index ne haméshaa list ma feravé.
        0            ->  [0]
        [0, 1, 4]    ->  [0, 1, 4]
        "0,1,4"      ->  [0, 1, 4]
    """
    if isinstance(value, (list, tuple)):
        items = list(value)
    elif isinstance(value, str):
        items = [x for x in value.replace(" ", "").split(",") if x]
    else:
        items = [value]

    out = []
    for x in items:
        try:
            i = int(x)
        except (TypeError, ValueError):
            continue
        if i >= 0 and i not in out:
            out.append(i)
    return out or [0]


def channel_names(indexes):
    """[0, 1, 4]  ->  "CH 1, CH 2, CH 5" """
    return ", ".join("CH %d" % (i + 1) for i in indexes)


# ---------------------------------------------------------------- targets
# UNIVERSAL LIST -- mixer par shu shu control kari shakay.
# (naam, OSC path no format, ketla number, sharu kya thi)
TARGET_GROUPS = [
    ("Mute Group",   "/config/mute/%d",    6,  1),
    ("FX Return",    "/fxrtn/%02d/mix/on", 8,  1),
    ("Channel",      "/ch/%02d/mix/on",   32,  1),
    ("Bus",          "/bus/%02d/mix/on",  16,  1),
    ("Matrix",       "/mtx/%02d/mix/on",   6,  1),
    ("DCA",          "/dca/%d/on",         8,  1),
    ("Aux In",       "/auxin/%02d/mix/on", 8,  1),
]

# ek-ek wada (number vagar na)
TARGET_SINGLES = [
    ("Main LR",   "/main/st/mix/on"),
    ("Main Mono", "/main/m/mix/on"),
]


def target_catalog():
    """
    Badha control kari shakay eva target ni list.
    Return: [(group_naam, [(label, path), ...]), ...]
    """
    out = []
    for name, fmt, count, start in TARGET_GROUPS:
        items = [("%s %d" % (name, n), fmt % n)
                 for n in range(start, start + count)]
        out.append((name, items))
    out.append(("Main / Biju", list(TARGET_SINGLES)))
    return out


def target_label(path, names=None):
    """
    OSC path ne manas samje evu naam ape.
      /config/mute/5    -> "Mute Group 5"
      /ch/09/mix/on     -> "Channel 9 (Guruji)"
    names = {channel_no: naam}  (marji thi)
    """
    for group, items in target_catalog():
        for label, p in items:
            if p == path:
                if names and label.startswith("Channel "):
                    try:
                        ch = int(label.split()[1])
                    except (ValueError, IndexError):
                        ch = 0
                    nm = (names or {}).get(ch, "").strip()
                    if nm:
                        return "%s (%s)" % (label, nm)
                return label
    return path


# ---------------------------------------------------------------- mute value
def mute_value(path, audible, invert="auto"):
    """
    Kaya path par kai value moklvi te nakki kare.

    audible = True  -> awaaj SAMBHALVO joiye
    audible = False -> awaaj BAND thavo joiye

    Be jaat na path hoy chhe, ane bannemaa ulti value jay chhe:
      /fxrtn/01/mix/on   ->  1 = channel ON  (awaaj sambhalay)
      /config/mute/5     ->  1 = mute group CHALU (awaaj band thai jay!)

    "auto" hoy to /config/mute/... mate aapoaap ultu kari de chhe.
    """
    if invert in (None, "auto"):
        inv = path.startswith("/config/mute/")
    else:
        inv = bool(invert)
    if inv:
        return 0 if audible else 1
    return 1 if audible else 0


# ---------------------------------------------------------------- mixer
class Mixer:
    """Ek UDP socket par M32 sathe vaat kare chhe."""

    SUBSCRIBE_INTERVAL = 4.0   # X32 nu subscription 10 second ma expire thay chhe

    def __init__(self, ip, port=10023, timeout=0.2):
        self.ip = ip
        self.port = int(port)
        self.addr = (self.ip, self.port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 262144)
        except OSError:
            pass
        # NON-BLOCKING : receive() turat pachhu aave chhe, atke nahi.
        # (Aa bahu jaruri chhe -- nahi to level check dhimu thai jay.)
        self.sock.setblocking(False)
        self._last_sub = 0.0
        self._sub_banks = []

    # -------------------------------------------------- basic io
    def send(self, address, *args):
        try:
            self.sock.sendto(osc_lite.build_message(address, *args), self.addr)
            return True
        except OSError as e:
            print("[!] Send fail: %s" % e)
            return False

    def receive(self):
        """Ek packet vanche (atkya vagar). Return list of (address, args) athva []."""
        try:
            data, _src = self.sock.recvfrom(65535)
        except (BlockingIOError, InterruptedError):
            return []
        except OSError:
            return []
        return osc_lite.parse_message(data)

    def wait(self, timeout=0.02):
        """Navo packet aave tyaa sudhi (vadhare ma vadhare timeout) raah jue."""
        try:
            ready, _, _ = select.select([self.sock], [], [], timeout)
            return bool(ready)
        except (OSError, ValueError):
            time.sleep(timeout)
            return False

    def drain(self, handler, max_packets=512):
        """Buffer ma jetla packet hoy tetla badha turat vanchi ne handler ne aape."""
        count = 0
        while count < max_packets:
            msgs = self.receive()
            if not msgs:
                break
            for address, args in msgs:
                handler(address, args)
            count += 1
        return count

    # -------------------------------------------------- meters
    def subscribe_meters(self, banks):
        """banks = [1] jeva list. Aa vaar vaar call karvu pade chhe."""
        self._sub_banks = list(banks)
        self._subscribe_now()

    def _subscribe_now(self):
        for b in self._sub_banks:
            self.send("/meters", "/meters/%d" % b)
        self.send("/xremote")
        self._last_sub = time.time()

    def keep_alive(self):
        """Main loop ma dar chakkar par call karo -- subscription renew kare."""
        if time.time() - self._last_sub >= self.SUBSCRIBE_INTERVAL:
            self._subscribe_now()

    # -------------------------------------------------- info
    def query_info(self, wait=1.0):
        """Mixer nu naam/firmware puchhe. Return dict athva None."""
        self.send("/info")
        end = time.time() + wait
        while time.time() < end:
            self.wait(0.05)
            for address, args in self.receive():
                if address == "/info":
                    vals = [a for a in args if isinstance(a, str)]
                    return {
                        "server_version": vals[0] if len(vals) > 0 else "?",
                        "name":           vals[1] if len(vals) > 1 else "?",
                        "model":          vals[2] if len(vals) > 2 else "?",
                        "firmware":       vals[3] if len(vals) > 3 else "?",
                    }
        return None

    def close(self):
        try:
            self.sock.close()
        except Exception:
            pass
