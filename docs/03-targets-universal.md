# 03 — Universal Target (શું કંટ્રોલ કરવું)

## શું કરે છે

મિક્સર પર **કંઈ પણ** ચાલુ/બંધ કરી શકાય — કુલ ૮૬ વસ્તુ.
આજે Mute Group 5 છે, કાલે ચેનલ 9 જોઈએ તો ફક્ત ડ્રોપડાઉનમાંથી બદલો.

## યાદી

| પ્રકાર | કેટલા | OSC path |
|---|---|---|
| Mute Group | 6 | `/config/mute/1` … `/config/mute/6` |
| FX Return | 8 | `/fxrtn/01/mix/on` … `/fxrtn/08/mix/on` |
| Channel | 32 | `/ch/01/mix/on` … `/ch/32/mix/on` |
| Bus | 16 | `/bus/01/mix/on` … |
| Matrix | 6 | `/mtx/01/mix/on` … |
| DCA | 8 | `/dca/1/on` … |
| Aux In | 8 | `/auxin/01/mix/on` … |
| Main | 2 | `/main/st/mix/on`, `/main/m/mix/on` |

યાદીમાં ના હોય તો GUI માં **Custom OSC** ખાનામાં સીધો path લખો.

## ⭐ સૌથી અગત્યનું — ઊંધી value

આ **બહુ સહેલાઈથી ભુલાય** એવી વસ્તુ છે:

| path | value 1 નો અર્થ | value 0 નો અર્થ |
|---|---|---|
| `/config/mute/5` | **મ્યુટ** (અવાજ બંધ) | અનમ્યુટ (અવાજ ચાલુ) |
| `/ch/09/mix/on` | ચાલુ (અવાજ સંભળાય) | મ્યુટ |
| `/fxrtn/01/mix/on` | ચાલુ | મ્યુટ |

એટલે **mute group માં બધું ઊંધું** છે.

કોડ આ જાતે સંભાળે છે:

```python
core.mute_value("/config/mute/5", audible=True)   # → 0
core.mute_value("/ch/09/mix/on",  audible=True)   # → 1
```

`config.json` માં `"invert": "auto"` રાખો. જો ક્યારેક ઊંધું થાય તો
`true` કે `false` લખીને હાથે નક્કી કરી શકાય.

## તમારા ડેસ્ક પર ચકાસાયેલું

```
/config/mute/5 = 1  →  Fx 1L, Fx 1R, Fx 4L, Fx 4R  મ્યુટ
/config/mute/5 = 0  →  એ ચારેય  અનમ્યુટ
```
(ડેસ્ક પરથી `/fxrtn/01/mix/on` વાંચીને ખાતરી કરેલી)

## એક કરતાં વધારે target

એકસાથે ઘણા પસંદ કરી શકાય. દા.ત. stereo FX return માટે
`/fxrtn/01/mix/on` **અને** `/fxrtn/02/mix/on` બન્ને જોઈએ.

દરેક target ને **પોતાનું toggle** છે — બંધ કરો તો યાદીમાં રહે
પણ વપરાય નહીં. (`x` દબાવો તો કાયમ કાઢી નાખે.)

`config.json` માં:
```json
"fx_targets":     ["/config/mute/5", "/ch/09/mix/on"],
"fx_targets_off": ["/ch/09/mix/on"]
```
અહીં ફક્ત `/config/mute/5` વપરાશે.

## કોડ ક્યાં છે

| શું | ફાઈલ |
|---|---|
| ૮૬ ની યાદી | `m32_core.py` → `TARGET_GROUPS`, `target_catalog()` |
| ઊંધી value | `m32_core.py` → `mute_value()` |
| નામ બતાવવું | `m32_core.py` → `target_label()` |
| ચાલુ કરેલા જ પસંદ કરવા | `m32_core.py` → `enabled_targets()` |
| GUI ની પસંદગી | `m32_gui.py` → `_build_targets()` |

## નવો પ્રકાર ઉમેરવો હોય તો

`m32_core.py` માં `TARGET_GROUPS` માં એક લીટી:
```python
("Naam", "/osc/path/%02d/on", કેટલા, ક્યાંથી_શરૂ),
```
પછી `python m32_app.py test` ચલાવો.

⚠️ **નવો path સાચા મિક્સર પર એક વાર ચકાસવો** — GUI નું TEST બટન વાપરો.

## શું બગડી શકે

| લક્ષણ | ઉપાય |
|---|---|
| TEST દબાવો પણ કંઈ ના થાય | path ખોટો — બીજો પસંદ કરો |
| ઊંધું થાય | `"invert"` ને `true`/`false` કરો |
| stereo FX માં એક જ બાજુ બંધ થાય | બન્ને (01 અને 02) ઉમેરો |
