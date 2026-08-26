# 05 — નકલી મિક્સર (Simulator)

## શેના માટે

મિક્સર હાથમાં ના હોય તો પણ **બધું જ** કામ થઈ શકે — કોડિંગ,
ટેસ્ટિંગ, નવા ફીચર, GUI ની પ્રેક્ટિસ.

## વાપરવાની રીત

```
M32-AutoFX.exe gui --sim     GUI + નકલી મિક્સર (એક જ કમાન્ડ)
M32-AutoFX.exe run --sim     CMD + નકલી મિક્સર
M32-AutoFX.exe sim           ફક્ત નકલી મિક્સર (અલગ window માં)
```

`--sim` લખવાથી પ્રોગ્રામ **પોતાની અંદર** નકલી M32 ચલાવે છે અને
`127.0.0.1` સાથે જોડાય છે.

## નકલી કલાકારો

| CH | નામ | કેવું વગાડે |
|---|---|---|
| 1 | Guruji | 3.5 s ગાય / 2.5 s શાંત |
| 2 | Vocal 2 | 2.0 / 4.0 |
| 3 | Chorus | 5.0 / 5.0 |
| 4 | Tabla | 0.8 / 0.4 (જલદી જલદી) |
| 5 | Flute | 2.5 / 3.5 (ઊંધા ટાઈમે) |
| 6 | Harmonium | 6.0 / 3.0 |
| 9, 10 | Playback L/R | હંમેશા ચાલુ |
| બાકી | — | શાંત (−64 dB) |

જુદા જુદા ટાઈમે વગાડે છે એટલે **multi-channel લોજિક ખરેખર ચકાસાય** —
CH 1 + CH 5 પસંદ કરો તો FX સળંગ ચાલુ રહેવું જોઈએ.

## સાચા M32 જેવું શું શું કરે છે

- `/info`, `/xinfo` નો જવાબ (M32-SIMULATOR, FW 4.06)
- 32 ચેનલનાં નામ
- મીટર ડેટા 20 વાર/સેકન્ડ, સાચા જેવા bank size
  (0=70, 1=96, 2=49, 3=22, 4=82, 5=27, 6=4)
- mute/unmute કમાન્ડ સમજે
- **Mute Group 5 = FX return 1, 2, 7, 8** — તમારા સાચા ડેસ્ક જેવું જ.
  `/config/mute/5 = 1` મોકલો તો `fxrtn` પણ ખરેખર બંધ થાય.
- value વગર પૂછો તો અત્યારની હાલત પાછી આપે

## બદલવું હોય તો

`m32_simulator.py` માં:

```python
PERFORMERS = [
    # (channel, ચાલુ_સેકન્ડ, બંધ_સેકન્ડ, offset, નીચો_dB, ઊંચો_dB)
    (1, 3.5, 2.5, 0.0, -18, -8),
]

MUTE_GROUP_MEMBERS = {
    5: ["/fxrtn/01/mix/on", "/fxrtn/02/mix/on", ...],
}

CH_NAMES = {1: "Guruji", ...}
```

શરૂઆતમાં થોડી વાર સાવ શાંતિ જોઈએ (scan ટેસ્ટ કરવા):
```
python m32_simulator.py --start-quiet 12
```

## કોડમાં વાપરવું

```python
import m32_simulator
sim = m32_simulator.Simulator(verbose=False)
sim.start()
sim.ready.wait(2.0)
...
print(sim.received)   # [(path, value), ...] — શું શું મળ્યું
print(sim.state)      # અત્યારની હાલત
sim.request_stop()
```

## શું બગડી શકે

| લક્ષણ | ઉપાય |
|---|---|
| "Port 10023 par bind na thayu" | બીજો simulator ચાલુ છે — બંધ કરો |
| `--sim` છતાં જોડાય નહીં | Firewall — Python/exe ને allow કરો |
| સાચું મિક્સર જોડાયેલું હોય | `--sim` વાપરો ત્યારે કેબલ કાઢી નાખો, નહીં તો ગૂંચવાડો |
