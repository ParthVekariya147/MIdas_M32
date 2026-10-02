# 00 — Everything In One File (complete system reference)

> **English version of [00-BADHU-EK-FILE-MA.md](00-BADHU-EK-FILE-MA.md)** —
> same content, both files are kept in sync.
>
> This single file covers: **every feature that is built**, **how each one
> works**, **all the logical rules** (the exact conditions each decision is
> made on), **all default numbers**, and **all limitations** (what cannot be
> done + what is still rough).
>
> Last verified: **2026-10-02** — written by reading the code, not from memory.
> Tests: **119/119 PASS**.

The other `docs/` files stay as they are — this is their combined summary.

---

## 1. At a glance — what the system does

```
  Mixer (MIDAS M32)                          This program (PC)
  -----------------                          -----------------
                      ---- meters (~50ms) --->  How loud is it?
   /meters/0  (70 values)                       Apply fader / mute
                      <--- OSC command -----    Work out the real level
   /config/mute/5                                      |
   /dca/8/fader                              +---------+---------+
   /ch/09/mix/on                             |                   |
                                        Auto FX Mute      Smart Switch
                                      (sound -> effect)  (line dies -> switch)
```

Two completely **separate** jobs in one program, each turned on/off on its own:

| | Feature | What it is for | Where in the GUI |
|---|---|---|---|
| **1** | **Auto FX Mute** | Singer stops → Reverb/Delay muted (no ringing, no feedback whistle) | Tab 1 |
| **2** | **Smart Source Switch** | Zoom's internet drops → move to the mobile line automatically | Tab 2 |

---

## 2. File map — which logic lives where

```
m32_app.py            <- everything starts here (the .exe is built from this)
  |-- m32_gui.py          on-screen UI (2 tabs, all toggles)
  |-- m32_automation.py   CMD version (prints to screen)
  |     \-- m32_engine.py      * the whole brain — GUI and CMD both use it,
  |     |                        and it also writes automation.log
  |           |-- m32_switcher.py   Smart Switch brain (runs without a mixer)
  |           \-- m32_core.py       connection, dB math, FEATURES, targets, config
  |                 \-- osc_lite.py    the mixer's language (OSC) — no library
  |-- find_mixer.py       find the mixer on the network
  |-- channel_select.py   pick channels by hand
  |-- meter_scan.py       speak into a mic and it finds the channel
  |-- test_fx.py          toggles a target on/off 3 times to verify
  |-- m32_simulator.py    fake M32 (works with no mixer at all)
  \-- test_all.py         119 automatic tests
```

**The most important rule:** logic goes **only in `m32_engine.py`**.
GUI and CMD both use it — fix it in one place, both get the fix.

---

## 3. All 15 toggles — one table

They all live in `m32_core.py` → `FEATURES`. The GUI toggles are **generated**
from it (add a new one and it appears in the UI by itself). Their state is
saved in `config.json` → `"features"`.
**They can all be changed while running — no restart.**

| # | key | Name | Default | What it does |
|---|---|---|---|---|
| 1 | `auto_fx` | Auto FX Mute | **ON** | Turn the target on/off from the sound |
| 2 | `respect_fader` | Respect fader / mute | **ON** | Ignore a mic whose fader is down or which is muted |
| 3 | `fader_boost` | Fader to 0 dB automatically | OFF | unmute → 0 dB, mute → back where it was |
| 4 | `auto_switch` | Smart Source Switch | OFF | Line dies → move to the other source |
| 5 | `switch_cross_check` | Cross-check the other line | **ON** | One silent + other talking → not a pause, the line broke |
| 6 | `switch_smart_noise` | Tell hum from speech | **ON** | Flat hum is not counted as "sound" |
| 7 | `switch_stability` | Check stability before returning | **ON** | Only go back once the higher line is steady |
| 8 | `switch_at_pause` | Switch only during a pause | **ON** | So the time offset between the two Zooms is not heard |
| 9 | `switch_watchdog` | Data stops → freeze | **ON** | No meters arriving → never switch |
| 10 | `safe_mode` | Safe Mode (test) | OFF | Send **not a single** command to the mixer |
| 11 | `start_muted` | Mute at start | **ON** | Mute the target when automation is switched on |
| 12 | `mute_on_exit` | Mute on exit | **ON** | Mute the target when the program closes |
| 13 | `auto_reconnect` | Reconnect by itself | **ON** | Re-subscribe when the data stops |
| 14 | `logging` | Write a log file | **ON** | Saves to `automation.log` — **in both GUI and CMD**. Turn it off and it is screen-only |
| 15 | `show_meter` | Show meters | **ON** | Level bars on screen |

**Old config files still work:** `get_feature()` looks in `features` first, then
at the top level of the config (so a plain `start_muted` key still works), then
falls back to the `FEATURES` default.

---

## 4. Feature 1 — AUTO FX MUTE (the main feature)

### How it works

```
meter arrives -> dB per channel -> apply fader/mute -> loudest of the selected
channels -> compare against threshold -> decide
```

### The logical rules (`m32_engine.py` → `_update()`)

| Condition | What happens |
|---|---|
| `auto_fx` is off | **Nothing is changed** (meters still shown) |
| `level_db > threshold_db` | There is sound — timer starts |
| Sound held for `attack_time` | **FX ON** (unmute) |
| Silence longer than `hold_time` | **FX OFF** (mute) |
| Any sound in between | The hold timer **restarts** |

- **Any one** selected channel with sound → effect on (OR logic)
- **All** channels quiet → off after the hold time
- A state that is already applied is **not re-sent** (no pointless commands)

### Default numbers

| Setting | Default | Meaning |
|---|---|---|
| `threshold_db` | **−40 dB** | Above this = there is sound |
| `hold_time` | **1.5 s** | Wait this long after silence, then mute |
| `attack_time` | **0.02 s** | Sound must hold this long before unmuting |
| `meter_bank` | **0** | Which meter bank |

### Limitations

- There is **only one** threshold (no hysteresis) — sound sitting right at
  −40 dB can flicker. (Smart Switch has two thresholds; this does not.)
- **One threshold for all** selected channels — not per channel.
- One rule only — there are **no separate rules** like "CH 1 → FX 1,
  CH 5 → FX 2" (F2).

---

## 5. Feature 2 — RESPECT FADER / MUTE (R10)

### Why it is needed

The mixer's **bank 0 meter is PRE-FADER** — the meter moves even with the
fader all the way down. So the effect used to switch on with the fader down
(**this bug was caught on a real mixer, on CH 10**).

### The formula

```
real level  =  meter dB  +  channel fader dB  +  its DCA fader dB
```

### The 4 conditions that drop a channel entirely (`channel_gain_db()` → `None`)

| # | Condition | OSC |
|---|---|---|
| 1 | The mixer **has not told us** about this channel yet | — (safety) |
| 2 | The channel is **muted** | `/ch/XX/mix/on` = 0 |
| 3 | Its **mute group is active** | `/ch/XX/grp/mute` + `/config/mute/N` |
| 4 | Its **DCA is off** | `/ch/XX/grp/dca` + `/dca/N/on` |

> **Rule 1 matters a lot:** until we know, **assume it is off**. It used to
> assume "unity", which could cause a false trigger in the first half second
> (a race condition). That is gone now.

### If the mixer never answers

It waits **4 seconds**, then sets `_state_gaveup = True` → carries on the old
way "without taking the fader into account" and writes a warning to the log.
(So an older firmware or a different desk still works instead of hanging.)

### Polling intervals

| What | How often |
|---|---|
| fader/mute/DCA of the selected channels | every **2 s** |
| DCA + mute group state | every **2 s** |
| All 32 channels | every **15 s** |
| `/meters` re-subscribe | every **4 s** (X32's subscription expires in 10 s) |

(`/xremote` also makes the mixer push changes by itself — this polling is the
**safety net**.)

### Fader → dB (the mixer's own curve, `fader_to_db()`)

| fader | dB | | fader | dB |
|---|---|---|---|---|
| 1.00 | +10 | | 0.25 | −30 |
| 0.75 | **0 (unity)** | | 0.0625 | −60 |
| 0.50 | −10 | | 0.00 | −90 (−inf) |

`db_to_fader()` is the inverse (needed by R12). The `+0.0` / `−10.5` / `-oo` /
`MUTE` box shown per channel in the GUI comes from this same math.

### Limitations

- There are three lists: `all_levels` = raw level of the whole bank (70),
  `levels` = raw for the 32 channels, `levels_eff` = after fader/mute.
  **Auto FX uses `levels_eff`, Smart Switch uses `all_levels` (raw)** — why,
  see §6.
- It **does not look at bus/aux send levels** — there is no way to tell
  whether the channel actually feeds the FX bus (F6, still open).
- Only **channel** (`/ch/`) fader/mute/DCA state is tracked. Aux In /
  FX Return / Bus fader-and-mute state is not.

---

## 6. Feature 3 — SMART SOURCE SWITCH (R11, two Zooms)

### The setup

| | Channel | Device | Internet |
|---|---|---|---|
| **Priority 1** | Zoom | PC | WiFi |
| **Priority 2** | Aux 1 | Mobile | Mobile data (4G/5G) |

The **order of the list is the priority** (top one first). Both carry the same
meeting, the same katha — only the device differs.

> ⚠️ The mobile **must be on its own 4G/5G**. On the same WiFi, **both die
> together** when the internet drops and the whole backup is pointless.

### The foundation — three states (pause vs dead line)

A speaker naturally pauses. So **"no sound = switch" does not work** — Aux
would cut in on every breath.

| State | In code | Meaning | What to do |
|---|---|---|---|
| 🟢 Talking | `TALKING` | There is sound | Keep it live |
| 🟡 Paused | `QUIET` | Silent, but the line is alive | **Do nothing at all** |
| 🔴 Line dead | `DEAD` | Silent this long without a break | **Switch** |

### How "there is sound" is decided — two locks

**1) Two thresholds (hysteresis)**

```
      −54 dB  --------  only above this does sound turn ON   (open_db)
                 ^  anything inside these 6 dB -> state does not change
      −60 dB  --------  only below this does sound turn OFF  (close_db)
```

**2) Variance — `switch_smart_noise`**

> This is what solves the "there's 1-2 dB of signal but nobody is talking"
> problem.

How much did the level move up and down in the last **2 seconds** (`wiggle`)?

| Movement | Meaning |
|---|---|
| < **3 dB** (flat) | Hum / rumble → **not sound** (even at a high level) |
| 10-20 dB | Real speech (words, pauses) → sound |

- With fewer than **3 samples**, or less than **0.5 s** of history, `wiggle`
  returns **99** ("don't know") — so no wrong call is made on the first two or
  three samples.
- The rule also applies **while sound is on**: a high but flat level (hum left
  behind after Zoom dies) → "sound off".

### ⭐ CROSS-CHECK — the heart of this feature

One speaker cannot be silent and talking at the same instant — **impossible**.
PC-Zoom silent **but** mobile-Zoom talking → not a pause, **the internet broke**.

| | Wait |
|---|---|
| On its own (no cross-check) | **6 s** (`dead_hold_s`) |
| **Cross-check available** | **2 s** (`cross_dead_hold_s`) |

A cross-check counts only when:
1. The other source is **on** and its `alive` is true
2. Its level is above `open_db + 6 dB` — faint bleed does not count
   (`bleed_guard_db`)
3. It has been talking continuously for **1 s** (`cross_confirm_s`)

### Patience when going back — `switch_stability`

- Only return once the higher priority has been **alive continuously for
  `stable_s`** — default **180 s = 3 minutes**
- If it dies **even once** in between, the timer **restarts from 0:00**
  (`stable_since = None`)
- The countdown is shown in the GUI, and **"switch now"** skips it
- The time is picked as **minutes + seconds**

### Switch only in a pause — `switch_at_pause` (the SYNC fix)

The PC and the mobile Zoom run **0.5-3 s** apart. Switching while both are
silent means the offset is never heard.

- After it is stable, it **waits for a pause**
- But no longer than **20 s** (`pause_wait_s`) — after that it switches even
  mid-sentence

### The **order of decisions** in `tick()` (checked in exactly this order)

```
1.  Settle every source's state            <- always, even when the toggle is off
2.  auto_switch off?                       -> do nothing
3.  Fewer than 2 live sources / same index? -> do nothing + log a warning
4.  Meter data stopped for 1.5 s?          -> FREEZE, do nothing
5.  Engineer pressed HOLD?                 -> do nothing
6.  Nothing live yet?                      -> open the highest line that is alive
7.  Live line DEAD?                        -> straight to the next priority
                                              (min_dwell drops to 1 s)
8.  Higher priority came back?             -> stability (3 min) -> min_dwell (5 s)
                                              -> pause -> switch
9.  Anything else                          -> do nothing
```

### All the other rules

| Rule | Why / detail |
|---|---|
| **Both silent → do nothing** | Whatever is live stays live. **Never mute everything** |
| **Fewer than 2 sources → the toggle will not run** | Greyed out in the GUI with the reason |
| **Two sources on the same index → refused** | Catches the mistake |
| **Data stops → freeze** | No meters means leave everything as it is (no wrong switch) |
| **Never fight the human** | HOLD → automation stands still |
| **MAKE-BEFORE-BREAK** | **New one on first, old one off 150 ms later** — not one instant of silence in between |
| **250 ms crossfade** | Done on the fader, so there is no click |
| **Use the raw level** | `levels`/`all_levels`, **not `levels_eff`** — otherwise the backup we muted ourselves looks "dead" (this was a real bug) |
| **`time.monotonic()`** | In a 3-hour katha, a Windows clock jump must not break the 3-minute timer |
| **min_dwell 5 s** | Stops ping-pong. But in an emergency it is **1 s** |
| **Sources can change any time** | CH 9 today, Aux 3 tomorrow — all editable, saved once |
| **Changing settings must not break the timers** | `configure()` keeps the old state (history, timers) when the name and index are unchanged |
| **Stereo pairs** | One source can listen on several indexes (loudest wins) and control several targets (both get muted) |

### All default numbers (`m32_switcher.DEFAULTS`)

| key | Default | What |
|---|---|---|
| `open_db` | **−54.0** | Above this = sound on |
| `close_db` | **−60.0** | Below this = sound off |
| `dead_hold_s` | **6.0** | Silent this long without a break → line dead |
| `cross_dead_hold_s` | **2.0** | Only this long when cross-checked |
| `cross_confirm_s` | **1.0** | The other line must talk this long to count |
| `stable_s` | **180.0** | Steady this long before going back (3 minutes) |
| `pause_wait_s` | **20.0** | Wait for a pause — never longer than this |
| `min_dwell_s` | **5.0** | Stay put this long after a switch |
| `var_window_s` | **2.0** | Window of movement to look at |
| `flat_db` | **3.0** | Less movement than this = rumble |
| `bleed_guard_db` | **6.0** | Faint bleed does not count as sound |
| `watchdog_s` | **1.5** | Data stops → freeze |
| `crossfade_ms` | **250** | Smoothed on the fader |
| `overlap_ms` | **150** | New one on → then the old one off |

### Limitations

- **A source can sit on any meter index** — CH 1-32, Aux In, FX Return, Bus,
  Matrix (index 0-69). Only as many indexes as the mixer actually sends are
  considered; the rest stay "unknown", so no wrong switch happens.
  *(✅ fixed 2026-10-02 — before this only CH 1-32 ever received a level.)*
- **Not yet verified on a real mixer** — the 14 tests pass against the simulator.
- It **does not correct** the time offset between the two Zooms — it only hides
  it by switching during a pause.
- If both lines share one internet connection the whole feature is pointless
  (see the ⚠️ above).
- If the speaker really is silent for more than **6 s** and the other line is
  not talking, that counts as "line dead" → a wrong switch is possible.
  (Raise `dead_hold_s` if needed.)

---

## 7. Feature 4 — FADER TO 0 dB AND BACK AGAIN (R12)

```
   fader −20 dB
        |
        |-- unmuted  ->  fader   0 dB     (the old −20 is remembered)
        |
        \-- muted    ->  fader −20 dB     (back where it was)
```

### The logic

| When | Condition | What happens |
|---|---|---|
| **Unmute** | Fader is **above** `to_db − tolerance` | **Do nothing** (don't even remember it) |
| **Unmute** | It is below | **Remember** the current value, then ramp to `to_db` |
| **Mute** | Nothing was remembered | Nothing |
| **Mute** | The engineer **moved it by hand** (difference > 0.02) | **Do not put it back** + log it |
| **Mute** | Otherwise | Ramp back to the remembered value |

### Settings

| Name | Default | What it does |
|---|---|---|
| `target` | `/dca/8/fader` | Which fader |
| `to_db` | **0.0** | Where to take it |
| `tolerance_db` | **1.0** | Inside this, **do not touch it at all** |
| `ramp_ms` | **250** | Move gradually (so there is no click) |

**`_note_fader()` — a small but necessary part:** whatever fader value we send,
we also write into our own table. Otherwise we send 0 dB while our table still
says −20 dB, and later it **wrongly** looks like "the engineer moved it by
hand". (That was a real bug, caught by a test.)

### Limitations

- `target` only works for **`/dca/N/fader`** or **`/ch/NN/mix/fader`**. Give it
  a Bus, Matrix or Main fader and `_fader_now()` has no value for it, so
  **nothing happens silently** (not even an error). The GUI dropdown offers
  only these two kinds.
- **One** fader only — not several at once.
- Nothing happens unless `active` is on **and** `safe_mode` is off.
- Nothing happens if the mixer never reported that fader's value.

---

## 8. Feature 5 — WHAT TO CONTROL (universal targets)

### 86 targets in total

| Group | OSC | Count |
|---|---|---|
| Mute Group | `/config/mute/N` | 6 |
| FX Return | `/fxrtn/NN/mix/on` | 8 |
| Channel | `/ch/NN/mix/on` | 32 |
| Bus | `/bus/NN/mix/on` | 16 |
| Matrix | `/mtx/NN/mix/on` | 6 |
| DCA | `/dca/N/on` | 8 |
| Aux In | `/auxin/NN/mix/on` | 8 |
| Main LR / Mono | `/main/st/mix/on`, `/main/m/mix/on` | 2 |

- **More than one** can be selected together
- Anything not in the list can be typed as a **custom OSC path**
- A disabled target **stays in the list** (`fx_targets_off`), it is just not used

### ⭐ Inverted values handled automatically (`mute_value()`)

| path | What `1` means | Send this for "audible" |
|---|---|---|
| `/config/mute/5` | mute group **active** = sound **off** | **0** |
| Everything else (`/ch/`, `/fxrtn/`, `/dca/`…) | **on** = sound on | **1** |

With `invert: "auto"` (the default) every `/config/mute/` path is inverted
**automatically**. The user never has to think about it. `true`/`false` can be
set to force it either way.

---

## 9. Feature 6 — WHICH CHANNEL TO LISTEN TO

### Meter map (70 values in bank 0 — measured on a real M32, firmware 4.13)

| index | What |
|---|---|
| 0-31 | CH 1-32 |
| 32-39 | Aux In 1-8 |
| 40-47 | FX Return 1-8 |
| 48-63 | Bus 1-16 |
| 64-69 | Matrix 1-6 |

### Two ways to choose

1. **By hand** — type the channel number / tick it in the GUI
2. **Automatically** — `scan`: speak into the mic and it finds the channel

`meter_index` accepts all three forms: `0` / `[0, 1, 4]` / `"0,1,4"` —
`parse_indexes()` turns everything into a list (`[0]` if it is nonsense).

### Limitations

- **For Auto FX the GUI only offers CH 1-32.** A larger index can be written
  into `meter_index` in `config.json` and it does work — but there the **raw
  level** is used (its fader/mute state is not known).
- If a selected index is not in the bank, a warning is logged and no decision
  is made.
- Channel names are read from the mixer — they stay blank if it does not answer.

---

## 10. Feature 7 — SAFETY DURING A LIVE SHOW

| Protection | How |
|---|---|
| **Open the GUI → nothing happens on the mixer** | `active = False`. Meters show, no commands go out |
| **Only when the big toggle is switched on** | Commands start after `set_active(True)` |
| **Safe Mode** | `_can_send()` false → **not a single** command goes out, log shows `[SAFE MODE]` |
| **Mute at start** | The target is muted the moment it is switched on (`start_muted`) |
| **Mute on exit** | The target is muted when the program closes (`mute_on_exit`) |
| **Manual override** | The engineer can change anything on the mixer at any time |
| **`--dry-run`** | Turns `safe_mode` on by itself |

**`_can_send()` is the one rule** used everywhere:
```
a command goes out   <=>   active is on  AND  safe_mode is off  AND  mixer connected
```

---

## 11. Feature 8 — CONNECTION (OSC) AND STAYING ALIVE

| | |
|---|---|
| protocol | **UDP OSC**, port **10023** |
| library | **no pip library** — only what ships with Python (`osc_lite.py`) |
| socket | **one** for both send and receive (the X32 replies to the same port) |
| discovery | broadcast `/info` finds it on the network |
| subscription | `/meters/0` + `/xremote`, renewed every **4 s** (expires in 10) |
| data stops | nothing for **3 s** → warning + re-subscribe (if `auto_reconnect`) |
| socket | **non-blocking** — level checks never slow down |
| meter → dB | `to_db()` handles **both** 0.0-1.0 (linear) and plain dB |
| loop | up to 20 ms wait per pass; a snapshot to the GUI every **0.1 s** |
| thread | the engine runs in **its own thread** — the GUI never freezes |

### Limitations

- **Not real-time.** A lost UDP packet means that pass is skipped (the next
  meter fixes it).
- Meters arrive about every 50 ms, so the real delay is **one meter cycle**
  even with `attack_time` at 0.02.
- **One mixer** at a time.
- If Windows/the PC goes down, automation stops — **the mixer stays exactly as
  it was left**.

---

## 12. ⚠️ KNOWN LIMITATIONS AND ROUGH EDGES (all in one place)

### (a) Missing in the code

> ✅ **Two bugs were fixed on 2026-10-02:**
> (1) Smart Switch sources now work past CH 32 — Aux In / FX Return / Bus /
> Matrix, all of them. (2) The `logging` toggle actually does something now —
> and **the GUI writes `automation.log` too** (before, only CMD did).

| # | What | Effect |
|---|---|---|
| 1 | **`show_meter` is only read at startup in CMD** | Changing it while CMD is running has no effect (the GUI applies it immediately) |
| 2 | **`fader_boost` target only takes `/dca/` or `/ch/`** | Any other path silently does nothing |
| 3 | **Auto FX has a single threshold** | No hysteresis — it can flicker right at the threshold |

### (b) Still to verify / decide

| # | What | Status |
|---|---|---|
| 4 | **R11 Smart Switch on a real mixer** | 14 tests pass on the simulator, real desk still pending |
| 5 | **The new UI (toggles + fader) on a real mixer** | Pending (F5) |
| 6 | **R13 — vMix master level (AGC)** | 🚧 **Do not build it until the target dB is settled** — AGC on a live desk with a wrong number is dangerous |

### (c) What can **never** be done (R9)

| Question | Answer |
|---|---|
| Can the program be installed inside the M32? | ❌ No — the firmware is locked |
| From a pen drive? | ❌ No — USB is only for recording/scenes/firmware |
| Can a plugin be written? | ❌ No — Behringer never released an SDK |
| So? | Keep a box running outside it (laptop / Raspberry Pi) |

### (d) To add later

| # | What | Why |
|---|---|---|
| F1 | Raspberry Pi setup guide | So a PC need not stay on |
| F2 | Several rules (CH1 → FX1, CH5 → FX2) | Different effects for different singers |
| F3 | Ride the fader instead of muting | Sounds more natural |
| F4 | Scenes / presets | No re-dialling settings every time |
| F6 | Watch bus/aux send levels too | More accuracy |

---

## 13. Working without a mixer + tests

| | |
|---|---|
| **Fake M32** | `m32_simulator.py` — behaves like the real thing |
| **How** | `--sim` → the program runs the fake mixer inside itself |
| **Fake performers** | CH 1 Guruji, CH 2 Vocal 2, CH 4 Tabla, CH 5 Flute |
| **Tests** | `python m32_app.py test` → **119 tests, ~120 seconds** |
| **The switcher needs no mixer** | Just feed it dB — which makes it easy to test |
| **The log-file test** | Uses its own separate file — it never touches the real `automation.log` |

---

## 14. One single .exe

| | |
|---|---|
| Files | **just one** — no need to install Python |
| First run | `config.json`, every guide and the whole `docs/` folder appear next to it **by themselves** |
| All CMD tools | From the same exe — `M32-AutoFX.exe tools` |
| Watch out | Antivirus sometimes blocks a fresh PyInstaller exe → "Allow"/"Keep" |

---

## 15. Every number — one table (quick reference)

| What | Default | Where |
|---|---|---|
| Threshold (Auto FX) | **−40 dB** | `threshold_db` |
| Hold time | **1.5 s** | `hold_time` |
| Attack time | **0.02 s** | `attack_time` |
| Switch: sound on | **−54 dB** | `open_db` |
| Switch: sound off | **−60 dB** | `close_db` |
| Line dead (on its own) | **6 s** | `dead_hold_s` |
| Line dead (cross-checked) | **2 s** | `cross_dead_hold_s` |
| Stability before going back | **180 s (3 min)** | `stable_s` |
| Waiting for a pause | **20 s** | `pause_wait_s` |
| Stay put after a switch | **5 s** | `min_dwell_s` |
| Flat = rumble | **< 3 dB** | `flat_db` |
| Crossfade | **250 ms** | `crossfade_ms` |
| Overlap (make-before-break) | **150 ms** | `overlap_ms` |
| Fader boost | **0 dB, ±1 dB, 250 ms** | `fader_boost` |
| Meter re-subscribe | **4 s** | `Mixer.SUBSCRIBE_INTERVAL` |
| Data stops → warning | **3 s** | `_check_data_flow` |
| Data stops → switch freeze | **1.5 s** | `watchdog_s` |
| No fader info → give up | **4 s** | `_state_gaveup` |
| Poll channel state | **2 s** / all **15 s** | engine loop |
| Snapshot to the GUI | **0.1 s** | engine loop |
| Port | **10023** | `mixer_port` |

---

## 16. How to add a new feature

```
1. Write it in REQUIREMENTS.md (give it an R number)
2. Add the toggle to m32_core.py -> FEATURES (if it needs on/off)
3. Write the logic in m32_engine.py   (GUI and CMD both get it for free)
4. Show the toggle in m32_gui.py      (generated from FEATURES)
5. Add its test to test_all.py
6. Create its .md file in docs/  +  update this file (00) and its
   Gujarati twin 00-BADHU-EK-FILE-MA.md
7. Run python m32_app.py test -- everything must PASS
```
