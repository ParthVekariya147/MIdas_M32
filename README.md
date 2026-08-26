# MIDAS M32 — Auto FX Mute

લાઈવ પ્રોગ્રામમાં **માઈકમાં અવાજ આવે ત્યારે ઇફેક્ટ આપોઆપ ચાલુ**, અને
**ગાવાનું બંધ થાય એટલે આપોઆપ બંધ** — જેથી પાછળથી અવાજ ગુંજે નહીં
અને વ્હીસલ (feedback) વાગે નહીં.

> Automatic reverb/delay muting for MIDAS M32 / Behringer X32 digital
> mixers, driven by live channel meters over OSC. Pure Python, no
> dependencies, ships as a single Windows .exe.

---

## શું કરે છે

```
માઈકમાં અવાજ આવે        →  Mute Group / FX return  આપોઆપ CHALU
બધા માઈક શાંત થાય       →  1.5 સેકન્ડ પછી આપોઆપ BAND
```

- એક કરતાં **વધારે માઈક** — કોઈ પણ એકમાં અવાજ આવે તો ચાલુ
- **૮૬ વસ્તુ** કંટ્રોલ કરી શકાય — Mute Group, Channel, FX Return,
  Bus, Matrix, DCA, Aux, Main
- **બધું toggle બટનથી** ચાલુ/બંધ
- **મિક્સર વગર પણ ચાલે** — અંદર નકલી M32 છે

---

## ચલાવવાની રીત

### સૌથી સહેલી — એક જ ફાઈલ

`BUILD-EXE.bat` ચલાવો → **`dist/M32-AutoFX.exe`** બને છે.
એ એક જ ફાઈલ ગમે ત્યાં કોપી કરો. Python ની જરૂર નથી.
પહેલી વાર ચલાવો એટલે config અને બધી ગાઈડ **જાતે બની જાય**.

### Python થી

```bash
python m32_app.py              # GUI
python m32_app.py gui --sim    # મિક્સર વગર પ્રેક્ટિસ
python m32_app.py test         # ૬૩ ટેસ્ટ
python m32_app.py tools        # બધા ટૂલ
```

| કમાન્ડ | શું કરે |
|---|---|
| `gui` | સ્ક્રીન વાળું UI |
| `run` | CMD માં automation |
| `find` | નેટવર્કમાં મિક્સર શોધો |
| `select 1,5,9` | ચેનલ પસંદ કરો |
| `scan` | બોલો એટલે ચેનલ જાતે શોધે |
| `testfx` | ૩ વાર on/off ટેસ્ટ |
| `sim` | નકલી મિક્સર |
| `test` | બધા ટેસ્ટ |

---

## UI

```
┌──────────────────────────────┬──────────────────────────────┐
│ 1) કયા મિક સાંભળવા ?          │ 2) શું ચાલુ/બંધ કરવું ?        │
│ (◯━) 1  Guruji  ▓▓▓▓  -12    │  [Mute Group ▾]  [UMERO]     │
│ (━◯) 2  Vocal 2 ▓     -58    │  પસંદ: (━◯) Mute Group 5 [x] │
├──────────────────────────────┴──────────────────────────────┤
│ 3) FEATURES  (◯━)Safe Mode  (━◯)શરૂઆતમાં mute  (━◯)Log...   │
│    Sensitivity ──●──  Hold ──●──  Attack ──●──              │
├─────────────────────────────────────────────────────────────┤
│ (━━◯)  AUTOMATION CHALU    [SAVE]     FX: CHALU    -12 dB   │
└─────────────────────────────────────────────────────────────┘
```

**સલામતી:** GUI ખોલો એટલે તરત મીટર દેખાય, પણ મોટું toggle ચાલુ કરો
ત્યાં સુધી **મિક્સર પર કંઈ જ થતું નથી** — લાઈવ પ્રોગ્રામ વખતે પણ
સલામત રીતે ખોલી શકાય.

---

## ડોક્યુમેન્ટ

| ફાઈલ | શેના વિશે |
|---|---|
| [REQUIREMENTS.md](REQUIREMENTS.md) | **શું બનાવવાનું છે** — પહેલા આ વાંચો |
| [docs/](docs/) | દરેક ફીચરની અલગ .md (૧૦ ફાઈલ) |
| [docs/09-troubleshooting.md](docs/09-troubleshooting.md) | **પ્રોબ્લેમ આવે તો** |
| [JAVAB-TAMARA-SAVAL.txt](JAVAB-TAMARA-SAVAL.txt) | મિક્સરમાં નાખી શકાય? PC બંધ થાય તો? |
| [CODING-GUIDE.txt](CODING-GUIDE.txt) | મિક્સર વગર કોડિંગ કરવા |
| [README-GUJARATI.txt](README-GUJARATI.txt) | વિગતવાર ગુજરાતી ગાઈડ |

---

## કોડનો નકશો

```
m32_app.py              ← બધું અહીંથી ચાલુ (exe આમાંથી બને)
   ├── m32_gui.py            સ્ક્રીન વાળું UI (toggle બટન)
   ├── m32_automation.py     CMD વાળું
   │      └── m32_engine.py       ★ આખું મગજ — બન્ને આ જ વાપરે
   │             └── m32_core.py       જોડાણ, dB, features, targets
   │                    └── osc_lite.py    OSC (કોઈ library નહીં)
   ├── find_mixer.py         નેટવર્કમાં શોધવું
   ├── channel_select.py     ચેનલ જાતે પસંદ
   ├── meter_scan.py         ચેનલ આપોઆપ શોધવી
   ├── test_fx.py            target ટેસ્ટ
   ├── m32_simulator.py      નકલી M32
   └── test_all.py           ૬૩ આપોઆપ ટેસ્ટ
```

**નિયમ:** લોજિક `m32_engine.py` માં જ લખવું — GUI અને CMD બન્ને એ જ
વાપરે છે, એટલે એક જગ્યાએ સુધારો બન્નેમાં આવે.

---

## ટેકનિકલ વિગત

| | |
|---|---|
| પ્રોટોકોલ | OSC over UDP, પોર્ટ 10023 |
| Dependency | **કોઈ નહીં** — ફક્ત Python standard library |
| Python | 3.8+ (3.14 પર ચકાસાયેલું) |
| GUI | Tkinter (Python સાથે જ આવે છે) |
| ટેસ્ટ | ૬૩ — મિક્સર વગર ચાલે |
| ચકાસાયેલું | M32-0A-8D-19, firmware 4.13 |

### Meter banks (M32 firmware 4.13)

| bank | values | |
|---|---|---|
| **0** | 70 | પહેલી 32 = ચેનલ 1-32 ← વપરાય છે |
| 1 | 96 | |
| 2 | 49 | |
| 3 | 22 | |
| 4 | 82 | |
| 5 | 27 | |
| 6 | 4 | |

### ⚠️ ધ્યાનમાં રાખવા જેવું

- **Mute group ની value ઊંધી છે** — `/config/mute/5 = 1` એટલે **મ્યુટ**,
  જ્યારે `/ch/01/mix/on = 1` એટલે **ચાલુ**. કોડ આ જાતે સંભાળે છે.
- Meter subscription ૧૦ સેકન્ડમાં પૂરું થાય — દર ૪ સેકન્ડે ફરી મોકલવું
- M32 એકસાથે ઘણા bank મોકલી શકે — address exact match કરવો
- Socket **non-blocking** હોવું જ જોઈએ, નહીં તો નિર્ણય ધીમા પડે

વિગત: [docs/08-osc-protocol.md](docs/08-osc-protocol.md)

---

## મિક્સરની અંદર નાખી શકાય?

**ના.** M32 નું firmware locked છે, USB ફક્ત recording/scene/firmware
માટે છે, અને Behringer એ plugin SDK આપી નથી. બહાર એક ડબ્બો ચાલુ રાખવો
પડે — લેપટોપ, અથવા Raspberry Pi (આ જ કોડ ત્યાં એક પણ લીટી બદલ્યા
વગર ચાલશે).

વિગત: [JAVAB-TAMARA-SAVAL.txt](JAVAB-TAMARA-SAVAL.txt)
