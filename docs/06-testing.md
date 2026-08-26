# 06 — આપોઆપ ટેસ્ટ

## ચલાવવાની રીત

```
M32-AutoFX.exe test        (અથવા)  python test_all.py
```
**મિક્સરની જરૂર નથી.** આશરે ૫૫ સેકન્ડ લાગે.

## શું ચકાસે છે (૬૩ ટેસ્ટ)

| વિભાગ | શું |
|---|---|
| 1. OSC | encode/decode, meter blob, ખોટા ડેટાથી crash ના થાય |
| 2. dB | linear → dB, પહેલેથી dB હોય તે, બાર |
| 3. Channel/Target | index સમજવું, ૮૬ target, **ઊંધી value** |
| 3b. Features | toggle વાંચવું, જૂની config, બંધ કરેલા target |
| 4. Live | નકલી મિક્સર સાથે ખરેખર ચલાવીને |
| 5. GUI | બધા widget, toggle, target ઉમેરવું/કાઢવું |

## સૌથી અગત્યના ટેસ્ટ (સલામતી)

આ ત્રણ **લાઈવ પ્રોગ્રામની સલામતી** માટે છે:

| ટેસ્ટ | શું ખાતરી કરે |
|---|---|
| `CHALU KARO dabavya vagar kai na jaay` | મોટું toggle બંધ હોય તો ડેસ્ક પર કંઈ ના જાય |
| `Safe Mode toggle: kai command na jay` | safe_mode ચાલુ હોય તો કંઈ ના જાય |
| `Auto FX toggle band: jate kai na badlay` | auto_fx બંધ હોય તો જાતે કંઈ ના બદલાય |

આમાંથી કોઈ FAIL થાય તો **સાચા મિક્સર પર ચલાવવું નહીં.**

## નવો ટેસ્ટ ઉમેરવો

```python
def test_navu():
    section("7. Navu feature")
    check("shu chakasvu chhe", saachu_chhe, "vigat")
```
પછી નીચે `main()` માં `for fn in (...)` યાદીમાં ઉમેરો.

નકલી મિક્સર સાથે ચલાવવું હોય તો:
```python
eng, logs = run_engine(sim, {"meter_index": 0,
                             "fx_targets": ["/config/mute/1"],
                             "features": {"safe_mode": True}}, 5.0)
```

## ક્યારે ચલાવવો

- **કંઈ પણ કોડ બદલો પછી** — હંમેશા
- .exe બનાવતાં પહેલાં
- નવા PC પર મૂક્યા પછી
- કંઈ વાંધો લાગે ત્યારે

## શું બગડી શકે

| લક્ષણ | કારણ |
|---|---|
| "Port bind na thayu" | બીજો simulator/exe ચાલુ છે |
| GUI ટેસ્ટ FAIL | tkinter નથી, અથવા GUI માં નામ બદલાયું |
| Live ટેસ્ટ ધીમા | PC પર બીજું ભારે કામ ચાલુ છે |
| વારંવાર બદલાતું પરિણામ | timing — `wait_for()` નો timeout વધારો |
