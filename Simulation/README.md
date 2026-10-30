# FOC Motor Controller Rev 1: LTspice bench-correlation suite

Three simulations of the Rev 1 board on the bench supply (**KA3005P, 30 V / 5 A**) with the **T-Motor MN601-S**. Each one predicts a waveform you can capture on the **Rigol DHO804**, and where it helps, a number you can read on the **EEVblog BM235**. The suite deliberately leaves out anything the bench can't reproduce: IDRIVE sweeps, thermal, loop-inductance sweeps, the ISR budget. See "Not simulated" below.

Each schematic is wired as a person would draw it. Net labels are used only for ground and to name a wire for `.meas` or for a behavioural source. Every sheet carries:
- its question
- the pass criteria
- the bench probe setup
- a **HOW TO EDIT** box listing every parameter (bus voltage, motor constants, driver settings, probe)
- all `.param / .step / .meas` directives

So a screenshot of a sheet is self-contained.

Built and run with **LTspice 26.0.2 (macOS)**. The generator netlisted every `.asc` with LTspice and compared it node by node against the intended circuit before running it.

```
Simulation/
├── 01_hot_plug/         ┐  each folder:  <name>.asc          schematic
├── 02_leg_switching/    │                <name>.plt          waveform layout (loads automatically after Run)
├── 03_standstill_csa/   ┘                plot_<name>.py      rebuilds results/fig*.png from the .raw
│                                         results/            reference .log, figure, layout preview
│                                         README.md           question, numbers, bench procedure
├── lib/ISC030N10NM6_fit.lib   MOSFET model (behavioural VDMOS fit, see Models)
├── common/ltspice_raw.py      .raw reader used by the plot scripts
├── measurements_summary.txt   all .meas results in one place
└── tools/                     generator: build_decks.py (schematics), write_plots.py (.plt), ascgen.py, ltrun.sh, meas.py
```

| Folder | Question | Analysis | Runtime |
|---|---|---|---|
| `01_hot_plug/` | XT60 plugged into a live 30 V supply: bus overshoot vs D1 (SMCJ51CA) and the 100 V FETs; what the firmware sees | `.tran` 1.2 ms × 4 (ESR × lead L) | ~3 s |
| `02_leg_switching/` | Phase-A leg at 30 V, ±current: edge rate, overshoot, dead-time diode step, Miller VGS, shunt-node ringing, what a 10× probe shows | `.tran` 36 µs × 2 (Iph −2.5 / +5 A) | ~2 s |
| `03_standstill_csa/` | 5 A hold along +α (like `RUN ID_R`): phase-current ripple, CSA output, and whether it has settled at the ADC sample | `.tran` 1 ms, 3 legs + PI loop | ~15 s |

## How to run
1. Open `<folder>/<name>.asc` in LTspice and press **Run**. Keep `lib/` where it is (decks use `.include ../lib/...`).
2. The waveform window opens with the `.plt` layout. To isolate one step: right-click → *Select Steps*. **LTspice runs `.step list` values in ascending order**, so step numbers follow the sorted list (noted on each sheet).
3. Read the numbers in **View → SPICE Error Log**. Every number below comes from a `.meas`, not a cursor.
4. `python3 <folder>/plot_<name>.py` (numpy + matplotlib) rebuilds `results/fig*.png`.

To change something, edit the `.param` line on the sheet (see its HOW TO EDIT box). Or edit `tools/build_decks.py` and run `python3 tools/build_decks.py`, which regenerates and re-checks every schematic.

## Motor and board values used

| Quantity | Value | Source |
|---|---|---|
| Phase R | 98 mΩ (motor + leads) | firmware `ID_R`, 2026-09-27; matches DC line-line 195 mΩ |
| Ld / Lq | 7.9 / 11.0 µH (decks use the mean 9.44 µH, as the firmware does) | firmware `ID_L` |
| λ, Kt, pole pairs, J | 1.389 mV·s, 0.0292 N·m/A, 14, ~8e-5 kg·m² | firmware tier-2 recordings (listed on deck 03; not used at standstill) |
| f_sw, dead time | 25 kHz centre-aligned, 200 ns | `APP_PWM_FREQ_HZ`, TIM1 DTG = 34 |
| IDRIVE | 1.0 A source / 2.0 A sink (code 15, both sides) | `p_drv_idrive` default |
| CSA | G = 20, VREF/2 bias, 600 ns settling to 1 % | `p_csa_gain`, DRV8323 datasheet |
| Shunt, CSA filter | 3 mΩ; 56 Ω + 2.2 nF to the ADC | R22/R27/R32; R13-15, C25-27 |
| Snubbers | 3.9 Ω + 2.2 nF across each FET | R23/C35, C36/R24 (per leg) |
| Bus capacitance | 3 × 100 µF electrolytic, 12 × 4.7 µF/100 V X7R, 5 × 100 nF, SMCJ51CA | +VPROT net |

## Reference results (LTspice 26.0.2)

| # | Result | Value | Figure |
|---|---|---|---|
| 01 | Hot-plug peak, general-purpose electrolytics (ESR 0.3 Ω) | **30.1 V**: no overshoot (ESR overdamps the lead LC) | Fig 01 |
| 01 | Hot-plug peak, low-ESR electrolytics (0.03 Ω) + 2 µH leads | **36.3 V** (+21 %), ring 5.6 kHz; D1 never conducts | Fig 01 |
| 01 | Firmware's view of the bus during the hot-plug | VBAT_SENSE filter (172 µs) hides the transient entirely | Fig 01 |
| 02 | Hard edge, +5 A (HS turn-on) | 5.5 ns, **4.4 V/ns**, V(SW) peak 32.8 V, LS Vds peak 38.6 V | Fig 02 |
| 02 | Hard edge, −2.5 A (LS turn-on) | 4.3 ns, **5.6 V/ns**, V(SW) min −2.5 V true, **−6.2 V on a 10× probe with a 15 cm clip** | Fig 02 |
| 02 | Miller VGS on the off low-side FET at the +5 A edge | **2.36 V** vs VGS(th) min 2.3 V (typ 2.8 V). Marginal; see derived requirements | Fig 02 |
| 02 | Ring frequency at the switch node | ~500 MHz (layout estimate). **Above the DHO804's 70 MHz**: the scope shows the probe's ~100 MHz ring instead | Fig 02 |
| 03 | Phase-A current ripple at the 5 A hold | **1.10 A p-p** (mean 5.00 A) | Fig 03 |
| 03 | CSA-derived current at the carrier-peak sample vs true | 4.988 vs 4.974 A: **+0.28 %** (A and B) | Fig 03 |
| 03 | SOA while the high side conducts | 1.650 V (= VREF/2: low-side shunts see nothing then) | Fig 03 |
| 03 | Supply current / power at the 5 A hold | **0.140 A / 4.2 W** (copper 3.7 W) | log |

All three decks pass their criteria. The one marginal number is the low-side Miller spike at the +5 A edge.

## Bench procedure (summary; details in each folder's README)

| Deck | DHO804 | BM235 | Firmware needed |
|---|---|---|---|
| 01 | CH1 on VBUS (C34 +), spring ground, 10 V/div, 20 µs/div, single trigger rising 33 V | Bus capacitance at the XT60, board unpowered (sets `Cbulk`); bus DC voltage at the board vs the supply display | **None.** Can be done today |
| 02 | CH1 SW_A (TP38), CH2 GLA (TP39), CH3 GHA (TP37); 5 ns/div; spring ground tips | Nothing on SW (it averages a 25 kHz square). Gate drive DC level with the bridge static | PWM at 30 V with the motor (ID_R hold) |
| 03 | CH1 SOA (TP20) or FILTER_SOA (TP17), CH2 PWM_PHASEA_L (TP22) as trigger, CH3 SW_A; 5 µs/div | **In series with the supply, 10 A range: compare with 0.140 A.** K-type probe on a shunt or FET, for a sanity check | ID_R / hold at 5 A, 30 V |

> **Scope gate:** decks 02 and 03 at 30 V / 5 A are **outside every approved bench scope**. The approved scopes are 12 V, a 3 A cap, and ID/spin modes refused above 15 V. The saved OV protection is 14 V. The simulations are done; running them on the bench needs that scope raised as a separate, reviewed firmware change. Deck 01 needs no firmware.

## Derived requirements and observations
1. **Regen at 30 V is the real hazard, not hot-plug.** Hand calculation, using the bus's ~356 µF and J = 8e-5 kg·m²:

   | Braked from | Rotor energy | Bus voltage if all of it lands on the bus |
   |---|---|---|
   | 500 rpm | 0.11 J | 39 V |
   | 1000 rpm | 0.44 J | 58 V (D1 starts conducting) |
   | 2700 rpm | 3.2 J | 137 V (past the 100 V FETs) |

   The KA3005P cannot sink. At 30 V, keep stops by coasting (as the firmware does at 12 V), or keep the regen guard active, above roughly 800 rpm.
2. **Miller margin at IDRIVE code 15.** The LS gate reaches 2.36 V at the +5 A hard edge, at VGS(th) min. A worst-case FET could see a brief partial turn-on. If the bench shows shoot-through signs (bus current rising with dV/dt, or warm FETs at light load), lower IDRIVEP (e.g. code 12 = 570 mA). That halves the dV/dt; the sink current stays at 2 A.
3. **CSA timing budget.** About 1.5 µs after a low-side turn-on before the ADC sample: 0.6 µs CSA settling, 0.12 µs RC, and about 0.5 µs for the shunt-node ring to fall back inside ±0.3 V (Fig 02). At 25 kHz that caps the low-side window at ≥ 1.5 µs, i.e. **duty ≤ ~96 %** on the phase being sampled. At standstill the window is 19 µs.
4. **Ripple is set by the motor, not the bus.** 1.1 A p-p at the hold, roughly V_applied × T / L. The 9.44 µH winding is small. At speed the active vectors lengthen and ripple grows, so re-check it before closed-loop FOC.
5. **Use spring ground tips.** The 15 cm clip turns a −2.5 V undershoot into −6.2 V on screen and adds a ~100 MHz ring. That is probably also why the switch node "read 75 V" on a DMM earlier: a DMM on a 25 kHz edge is not a measurement.

## Models (`lib/`)
- `ISC030N10NM6_fit.lib`: behavioural VDMOS fit of the Infineon ISC030N10NM6 from datasheet Rev 2.2. **Not the vendor model.** Checked in LTspice against the datasheet: Rds(on) 2.55 mΩ at 10 V (typ 2.6), plateau 4.59 V (4.6), Qg 55 nC (55), Qgd 9.6 nC (9.1). Diode recovery comes from `tt=8n` only. Edge and overshoot numbers are therefore model-dependent.
- DRV8323 gate drive is modelled as behavioural current sources: IDRIVEP until VGSH/VGSL = 11 V, IDRIVEN/ISTRONG when off, plus the 150 kΩ passive pull-downs. TDRIVE and the VGS-handshake delay are not modelled.
- DRV8323 CSA: ideal gain plus one pole set from t_SET, output clipped to its 0.25 V … VREF−0.25 V linear range. Offset is not modelled; the firmware calibrates it out.
- Layout parasitics in deck 02 (0.5 nH per FET lead, 0.6 nH shunt, 0.3 nH ceramics, 10 nH to the bulk) are estimates. Correct `Lpar` from the measured ring frequency.

## Not simulated (and why)
IDRIVE / dead-time sweeps, shoot-through margin maps, loop-inductance sweeps: design-space exploration the bench can't check one-to-one. Thermal: the 5 A supply limit keeps the board far from it. ISR budget and voltage-limited speed: not SPICE problems; the firmware measures them. LMR36520 buck: TI ships no LTspice model, and it already works on the bench. Regen: a hand calculation answers it (above), and reproducing it at 30 V would be destructive.
