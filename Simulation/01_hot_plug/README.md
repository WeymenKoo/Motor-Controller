# 01_hot_plug

**Question:** when the XT60 is mated into a KA3005P already at 30 V, how high does +VPROT ring? Does D1 (SMCJ51CA) conduct, and what does the firmware's bus reading show?
**Analysis:** `.tran` 1.2 ms. Stepped: electrolytic ESR 0.03 / 0.3 Ω × lead inductance 0.5 / 2 µH (4 runs).

| File | What it is |
|---|---|
| `01_hot_plug.asc` | The schematic: supply → leads → board (+VPROT capacitors, D1, idle load, VBAT_SENSE divider), with the test description, HOW TO EDIT box and all directives |
| `01_hot_plug.plt` | Top: V(VBUS) and the firmware's computed bus voltage. Bottom: lead current and D1 current |
| `plot_01_hot_plug.py` | Rebuilds `results/fig01_hot_plug.png` |
| `results/01_hot_plug.log` | `.meas` results from the reference run |

Step order: 1 = ESR 0.03 Ω / 0.5 µH, 2 = 0.3 Ω / 0.5 µH, 3 = 0.03 Ω / 2 µH, 4 = 0.3 Ω / 2 µH.

**Reference results**

| | ESR 0.03, 0.5 µH | ESR 0.3, 0.5 µH | ESR 0.03, 2 µH | ESR 0.3, 2 µH |
|---|---|---|---|---|
| Vbus_pk | 30.1 V | 30.0 V | **36.3 V** | 30.1 V |
| D1 current | ~0 | ~0 | ~0 | ~0 |
| Ring | overdamped | overdamped | 5.6 kHz | overdamped |

- PASS in every case: D1 never conducts, and the FETs see ≤ 37 V.
- The electrolytics' ESR is what damps the lead LC (Z0 ≈ 0.05-0.08 Ω). Only low-ESR caps plus long leads ring.
- The firmware never sees the transient. VBAT_SENSE (12.4k/2k, 100 nF, τ = 172 µs) reaches 30 V only after about 1 ms.
- **Lead current peaks of 150-300 A are model-bound.** The supply is modelled as ideal and stiff, with no contact arc. On the bench this is the spark you see at the XT60, limited by the KA3005P's output capacitor ESR.

**Bench reproduction (no firmware needed)**
1. Board unpowered: BM235 in capacitance mode across the XT60 → C_meas. Expect about 360 µF: 300 µF of electrolytics plus the ceramics, which read their full 4.7 µF with no DC bias. So set `Cbulk = (C_meas − 12 × 4.7 µF)/3` on the sheet; `Ccer` stays at its 2.4 µF value derated for 30 V.
2. DHO804 CH1 on C34 + with the spring ground on C34 −. 10× probe, 10 V/div, 20 µs/div, single trigger rising at 33 V. Then lower it to 31 V if nothing triggers: no overshoot is the expected result with standard caps.
3. KA3005P at 30 V, output on, current limit 5 A. Plug the XT60 in. Note Vbus_pk and, if it rings, the period.
4. If it rings: `Llead = 1/((2π f_ring)² × C_meas)`. Put that on the sheet and adjust `ESRbulk` until the decay matches.
5. Compare: power up with the supply's OUTPUT button instead. The supply ramps slowly, so expect no overshoot.
