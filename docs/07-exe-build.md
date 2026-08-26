# 07 — .exe બનાવવું

## બનાવવાની રીત

```
BUILD-EXE.bat  પર ડબલ-ક્લિક        (અથવા)  python build_exe.py
```
૨-૩ મિનિટ લાગે. પરિણામ: **`dist/M32-AutoFX.exe`** (આશરે ૧૧ MB)

પહેલી વાર PyInstaller જાતે install થઈ જશે (ઇન્ટરનેટ જોઈએ).

## એક જ ફાઈલ — બીજું કંઈ નહીં

એ એક ફાઈલ ગમે ત્યાં કોપી કરો. **પહેલી વાર ચલાવો એટલે જાતે બની જાય:**

```
શરૂઆતમાં:   M32-AutoFX.exe

પછી:        M32-AutoFX.exe
            config.json              ← સેટિંગ્સ
            VAANCHO.txt              ← ટૂંકી ગાઈડ
            README-GUJARATI.txt
            JAVAB-TAMARA-SAVAL.txt
            CODING-GUIDE.txt
            automation.log           ← ચલાવ્યા પછી
```

## એ જ exe માંથી બધા ટૂલ

| કમાન્ડ | શું |
|---|---|
| (ડબલ-ક્લિક) | GUI |
| `gui --sim` | GUI + નકલી મિક્સર |
| `run` | CMD automation |
| `find` | નેટવર્કમાં મિક્સર શોધો |
| `select 1,5,9` | ચેનલ પસંદ |
| `scan` | આપોઆપ ચેનલ શોધો |
| `testfx` | ૩ વાર on/off |
| `test` | ૬૩ ટેસ્ટ |
| `sim` | ફક્ત નકલી મિક્સર |
| `tools` | આ યાદી |

## ⚠️ ટેકનિકલ — બે વસ્તુ યાદ રાખવી

### ૧. config.json exe ની બાજુમાં જ રહેવું જોઈએ

PyInstaller `--onefile` માં `__file__` એ temp ફોલ્ડર બતાવે છે.
એટલે એ ફોલ્ડરમાં લખીએ તો **સેટિંગ્સ દર વખતે ખોવાઈ જાય**.

```python
# m32_core.py
def _base_folder():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))   # exe ની બાજુમાં
    return os.path.dirname(os.path.abspath(__file__))
```

### ૨. windowed exe માં console હોતું નથી

`--windowed` વાપર્યું છે (ડબલ-ક્લિકે કાળી window ના દેખાય).
CMD ટૂલ ચલાવવા હોય ત્યારે console જાતે ખોલવું પડે:

```python
# m32_app.py → ensure_console()
kernel32.AttachConsole(-1)    # cmd માંથી ચલાવ્યું હોય તો એ જ window
   ... નહીં તો ...
kernel32.AllocConsole()       # નવી window
```

## build_exe.py માં શું છે

| વસ્તુ | કેમ |
|---|---|
| `--onefile` | એક જ ફાઈલ |
| `--windowed` | કાળી window ના દેખાય |
| `--icon icon.ico` | ટેબ પર આઇકોન |
| `--hidden-import` | અંદરથી import થતા module (PyInstaller ને દેખાતા નથી) |
| `--add-data` | guide ફાઈલો exe ની અંદર |

**નવી .py ફાઈલ ઉમેરો તો `HIDDEN` યાદીમાં પણ ઉમેરવી.**

## શું બગડી શકે

| લક્ષણ | ઉપાય |
|---|---|
| Antivirus રોકે | "Allow"/"Keep" — PyInstaller exe સાથે સામાન્ય છે |
| exe ખૂલે પણ તરત બંધ | `M32-AutoFX.exe run` થી cmd માં ચલાવો, error વાંચો |
| "No module named X" | `build_exe.py` ના `HIDDEN` માં ઉમેરો, ફરી બનાવો |
| સેટિંગ્સ યાદ ના રહે | exe ને write permission છે? Program Files માં ના મૂકો |
| exe જૂનું લાગે | `dist` અને `build` કાઢીને ફરી બનાવો |
