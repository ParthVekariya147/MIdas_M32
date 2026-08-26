# ડોક્યુમેન્ટ — MIDAS M32 Auto FX

દરેક ફીચરની અલગ ફાઈલ છે. કંઈ પ્રોબ્લેમ આવે તો સંબંધિત ફાઈલ ખોલો —
તેમાં **શું કરે છે, ક્યાં કોડ છે, અને શું બગડી શકે** તે લખેલું છે.

| # | ફાઈલ | શેના વિશે |
|---|---|---|
| — | [../REQUIREMENTS.md](../REQUIREMENTS.md) | **શું બનાવવાનું છે** — પહેલા આ વાંચો |
| 01 | [01-auto-fx-mute.md](01-auto-fx-mute.md) | મુખ્ય ફીચર — અવાજ પ્રમાણે mute/unmute |
| 02 | [02-channel-selection.md](02-channel-selection.md) | કઈ ચેનલ સાંભળવી |
| 03 | [03-targets-universal.md](03-targets-universal.md) | શું કંટ્રોલ કરવું (૮૬ target) |
| 04 | [04-ui-toggle.md](04-ui-toggle.md) | સ્ક્રીન વાળું UI અને toggle બટન |
| 05 | [05-simulator.md](05-simulator.md) | નકલી મિક્સર (મિક્સર વગર કામ) |
| 06 | [06-testing.md](06-testing.md) | આપોઆપ ટેસ્ટ |
| 07 | [07-exe-build.md](07-exe-build.md) | .exe બનાવવું |
| 08 | [08-osc-protocol.md](08-osc-protocol.md) | મિક્સરની ભાષા (OSC) |
| 09 | [09-troubleshooting.md](09-troubleshooting.md) | **પ્રોબ્લેમ આવે તો** |
| 10 | [10-fader-aware.md](10-fader-aware.md) | **Fader / Mute ધ્યાનમાં લેવું** |

## ફાઈલોનો નકશો

```
m32_app.py         ← બધું અહીંથી ચાલુ થાય (exe આમાંથી બને)
   ├── m32_gui.py        સ્ક્રીન વાળું UI
   ├── m32_automation.py CMD વાળું
   │      └── m32_engine.py   ★ આખું મગજ — બન્ને આ જ વાપરે
   │             └── m32_core.py   જોડાણ, dB, features, targets
   │                    └── osc_lite.py   મિક્સરની ભાષા
   ├── find_mixer.py     નેટવર્કમાં શોધવું
   ├── channel_select.py ચેનલ જાતે પસંદ
   ├── meter_scan.py     ચેનલ આપોઆપ શોધવી
   ├── test_fx.py        target ટેસ્ટ
   ├── m32_simulator.py  નકલી M32
   └── test_all.py       ૬૩ આપોઆપ ટેસ્ટ
```

**સૌથી અગત્યનો નિયમ:** લોજિક `m32_engine.py` માં જ લખવું.
GUI અને CMD બન્ને એ જ વાપરે છે — એટલે એક જગ્યાએ સુધારો, બન્નેમાં અસર.
