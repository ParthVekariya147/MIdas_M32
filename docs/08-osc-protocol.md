# 08 — OSC (મિક્સરની ભાષા)

## પાયાની વાત

M32 **OSC over UDP, પોર્ટ 10023** પર વાત કરે છે.
કોઈ library વાપરી નથી — `osc_lite.py` માં જાતે લખેલું છે (100 લીટી).
એટલે `pip install` ની જરૂર નથી.

## Message નું બંધારણ

```
[address]  [typetag]  [arguments]
/ch/01/mix/on   ,i        1
```
દરેક ભાગ ૪ બાઈટના ગુણાંકમાં padding સાથે.

| typetag | શું |
|---|---|
| `i` | int (4 બાઈટ, big-endian) |
| `f` | float |
| `s` | string |
| `b` | blob (મીટર ડેટા) |

## વાપરવાની રીત

```python
import osc_lite
msg = osc_lite.build_message("/ch/01/mix/on", 1)
osc_lite.parse_message(msg)      # [("/ch/01/mix/on", [1])]
```

## ⭐ ૪ અગત્યની વાતો (ભૂલવા જેવી નહીં)

### ૧. મીટર એ જ પોર્ટ પર પાછું આવે છે

M32 મીટર ડેટા **જે પોર્ટ પરથી request આવી** તેના પર જ મોકલે છે.
એટલે **એક જ socket** થી મોકલવું અને વાંચવું પડે.

```python
# m32_core.py → class Mixer  — એક જ socket
```

### ૨. Subscription ૧૦ સેકન્ડમાં પૂરું થાય

દર ૪ સેકન્ડે ફરી `/meters` મોકલવું પડે:
```python
Mixer.SUBSCRIBE_INTERVAL = 4.0
Mixer.keep_alive()    # મુખ્ય લૂપમાં દર વખતે
```
ના મોકલો તો ડેટા ચૂપચાપ બંધ થઈ જાય.

### ૩. Socket non-blocking હોવું જ જોઈએ

**આ એક અસલી બગ હતો.** પહેલા socket timeout 0.2 s હતો, અને
packet દર 0.05 s આવતા — એટલે drain loop ક્યારેય ખાલી ના થાય,
૬૪ packet વાંચીને જ બહાર નીકળે → **`update()` દર ~3 સેકન્ડે જ ચાલતું**.

```python
self.sock.setblocking(False)     # ફિક્સ
```
હવે `select()` થી રાહ જુએ છે — સેકન્ડમાં ~50 વાર નિર્ણય લે છે.

### ૪. Meter blob નું બંધારણ

```
[int32 count (little-endian)] + [count × float32 (little-endian)]
```
⚠️ બહાર big-endian, **blob ની અંદર little-endian** — ગૂંચવાય એવું છે.

value 0.0-1.0 હોય → `dB = 20 × log10(value)`
(ક્યારેક સીધું dB પણ આવે — `to_db()` બન્ને સંભાળે છે)

## વપરાતા path

| કામ | path |
|---|---|
| મિક્સર ઓળખવું | `/info`, `/xinfo` |
| મીટર માંગવું | `/meters` + `"/meters/0"` |
| જીવતું રાખવું | `/xremote` |
| ચેનલનું નામ | `/ch/01/config/name` |
| Mute group | `/config/mute/5` |
| ચેનલ on/off | `/ch/01/mix/on` |

**value વગર મોકલો = "અત્યારે શું છે?" પૂછવું.** મિક્સર જવાબ આપે છે.
આ રીતે જ ડેસ્ક પરથી ખાતરી કરી હતી કે `/config/mute/5 = 1` એટલે mute.

## તમારા M32 ની વિગત

```
નામ      : M32-0A-8D-19
IP       : 192.168.45.100  (બદલાઈ શકે)
Firmware : 4.13
Port     : 10023

Meter banks : 0=70, 1=96, 2=49, 3=22, 4=82, 5=27, 6=4
              bank 0 ની પહેલી 32 = ચેનલ 1-32
```

## શું બગડી શકે

| લક્ષણ | ઉપાય |
|---|---|
| જવાબ ના આવે | IP, કેબલ, Firewall ચકાસો |
| થોડી વાર પછી ડેટા બંધ | `keep_alive()` ચાલતું નથી |
| ખોટી ચેનલ વંચાય | address exact match કરો (docs/02 જુઓ) |
| dB ખોટા લાગે | blob little-endian છે તે ચકાસો |
