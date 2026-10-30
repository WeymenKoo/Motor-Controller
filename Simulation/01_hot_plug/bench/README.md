# 01_hot_plug / bench

Bench correlation for deck 01, captured 2026-10-30 with the DHO804 over USB (pyvisa-py).

**Setup:** KA3005P at 30 V / 5 A, output on, XT60 plugged into the unpowered board by hand. DHO804 CH1 on C34+, 10x probe, spring ground on C34-, DC coupling, 5 V/div, rising single trigger at 3 V. BM235 on DC V across C37.

| Run | Timebase / sampling | Status | Files |
|---|---|---|---|
| 1 | 20 µs/div, 100 kpts | discarded: triggered mid-charge (15 V trigger), ground-spring artefacts | `hotplug_ch1_*.csv`, `hotplug_screen.png`, `hotplug_vs_sim.png` |
| 2 | 500 µs/div, 10 Mpts @ 0.8 ns | discarded: ±5 V steps from the ground spring on flux residue | `hotplug2_*` |
| 3 | 2 ms/div, 10 Mpts @ 3.2 ns | discarded: same artefacts, apparent 29 → 25 V sag | `hotplug3_*` |
| 4 | 50 ms/div, 10 Mpts @ 80 ns | **good** | `hotplug4_*` |
| 5 | 50 ms/div, 10 Mpts @ 80 ns | **good** | `hotplug5_*` |

`*_raw.npz` holds the full record: `v` (V, float32), `t0` (s, first sample), `dt` (s). `t = t0 + arange(len(v)) * dt`, t = 0 at the trigger.

**Result (runs 4 and 5):**
- Contact edge 0.12 V/µs, about 42 A into the ~360 µF bus. XT60 make-break steps during the first ~1 ms.
- 23.3 V at 1 ms (supply output capacitor sharing charge with the bus), then exponential recovery to 29.90 V with τ = 6.2 / 6.8 ms.
- Peak 30.13 / 30.15 V. No overshoot and no ringing. The two runs agree within 0.1 V after 1 ms.
- Steady-state ripple ≤ 0.37 V p-p at 5 V/div, which is mostly the scope's noise floor (not resolved at this setting).
- KA3005P and BM235 both read 30 V steady afterwards (CV).

**Against the sim:** deck 01 models the supply as an ideal source and predicts 30 V within ~50 µs, with up to 36.3 V overshoot (low-ESR bulk, 2 µH leads). The KA3005P cannot slew that fast, so the overshoot case does not arise on this bench. To do: change deck 01's `Vsup` to a current-limited source with an output capacitor and fit it to runs 4/5.

Figures: `bench01_vs_sim.png`, `bench01_detail.png`, `hotplug4_zoom.png`.
