# 02_leg_switching

**Question:** at 30 V and the firmware's IDRIVE (1 A / 2 A), what does the phase-A switch node do? That means edge rate, overshoot and undershoot, the body-diode step in the 200 ns dead time, Miller-induced VGS on the off FET, and ringing at the shunt (CSA input). And what does a 10× probe on the DHO804 actually show?
**Analysis:** `.tran` 36 µs (one 25 kHz period, 50 % duty). Stepped: phase current Iph = −2.5 A (step 1) and +5 A (step 2), the two currents in an ID_R hold along +α.

| File | What it is |
|---|---|
| `02_leg_switching.asc` | The schematic: bus, ceramics, C38, HS/LS ISC030 with lead inductances, DRV8323 gate drive, RC snubbers, 3 mΩ shunt, phase current, two probe models (SW, GL) |
| `02_leg_switching.plt` | Zoomed on 9.8-10.6 µs (the first edge). Top: V(SW) true and as the scope shows it. Middle: VGS low/high, GL on the scope. Bottom: shunt node, phase current. For the second edge, zoom to 29.8-30.6 µs |
| `plot_02_leg_switching.py` | Rebuilds `results/fig02_leg_switching.png` (the two hard edges side by side) |
| `results/02_leg_switching.log` | `.meas` results |

**Reference results**

| | Step 1: −2.5 A (phase B/C) | Step 2: +5 A (phase A) |
|---|---|---|
| Hard edge | LS turn-on, SW falling: 4.3 ns, **5.6 V/ns** | HS turn-on, SW rising: 5.5 ns, **4.4 V/ns** |
| Soft edge | SW rising in the dead time: 83 ns (0.29 V/ns) | SW falling in the dead time: 40 ns (0.6 V/ns) |
| V(SW) max / min, true | 31.7 / −2.5 V | 32.8 / −1.0 V |
| V(SW) max / min, on the scope (15 cm clip) | 31.1 / **−6.2 V** | **35.9** / −1.1 V |
| Vds peak HS / LS | 35.7 / 31.3 V | 31.0 / 38.6 V |
| SW in the dead time | Vbus + 0.95 V (HS diode) | −0.76 V (LS diode) |
| Miller VGS on the off FET | 0.07 V (HS) | **2.36 V (LS)**, 3.6 V on the scope (probe ring) |
| Shunt node during edges | −0.97 … +1.21 V | −1.37 … +1.42 V |

- PASS: Vds ≤ 38.6 V against the 80 V criterion. The shunt node is back inside ±0.3 V about 0.5 µs after an edge (Fig 02), well before the sample, which is at least 9 µs away at standstill.
- **Marginal:** the LS Miller spike at +5 A (2.36 V) is at VGS(th) min (2.3 V). Typical parts (2.8 V) stay off. If you see shoot-through signs, drop IDRIVEP (`Isrc` here) to 0.57 A (code 12) and re-run.
- The true ring is about 500 MHz with these layout guesses, far above the 70 MHz scope. **What you will see is the probe:** about 100 MHz from the ground clip and tip capacitance. Fig 02 shows how much that exaggerates the undershoot.

**Bench reproduction (needs a 30 V PWM scope, not yet approved)**
- Probes: CH1 SW_A (TP38), CH2 GLA (TP39), CH3 GHA (TP37). Spring ground tips on the nearest GND (the shunt's GND end), 10×, full 70 MHz bandwidth (BW limit off).
- Timebase 5 ns/div, trigger CH1 rising at 15 V for the +5 A edge (phase A in a hold along +α). For the −2.5 A edge, probe phase B (TP41) and trigger falling.
- High-side VGS = CH3 − CH1 (math). Trust it only away from the edges.
- Compare: edge time (10-90 %), the dead-time plateau (−0.8 V or Vbus + 0.9 V), the ring frequency, and the low-side gate bump.
- If the measured ring is slower than predicted, raise `Lpar` until the sim matches. That gives you the real loop inductance.
- BM235: not on SW. With the bridge static (outputs off, then the LS held on), the DC level on GLA should read about 11 V (VGSL).
