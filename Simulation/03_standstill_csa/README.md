# 03_standstill_csa

**Question:** at the firmware's ID_R / hold operating point (5 A along +α at 30 V), what phase-current ripple does the MN601-S's 9.44 µH give? What does the CSA output look like on the scope, and is it settled and accurate when the ADC samples at the carrier peak?
**Analysis:** `.tran` 1 ms. Three ISC030 legs with DRV8323 gate drive, centre-aligned 25 kHz PWM with 200 ns dead time, and a PI loop on the phase-A current (like `RUN ID_R`). Motor: R 98 mΩ, L = (Ld+Lq)/2 per phase, star-connected. CSA A and B include their 56 Ω / 2.2 nF ADC filter. The run starts near steady state (`.ic` on the winding currents, feed-forward duty).

| File | What it is |
|---|---|
| `03_standstill_csa.asc` | The schematic: supply/leads/bus caps → three legs (top) → MN601-S windings (below) → CSA A/B (right); MCU carrier, PI and PWM logic (left) |
| `03_standstill_csa.plt` | Last two periods. Top: phase currents. Middle: SOA, FILTER_SOA, FILTER_SOB. Bottom: SW_A and the carrier (×30) |
| `plot_03_standstill_csa.py` | Rebuilds `results/fig03_standstill_csa.png` (with the ADC sample instants marked) |
| `results/03_standstill_csa.log` | `.meas` results |

**Reference results**
- Phase A mean **5.00 A**, ripple **1.10 A p-p**. Phase B −2.50 A.
- Duty A 52.3 %: the hold needs only about 0.8 V line-line plus about 0.3 V of dead-time loss.
- CSA at the sample instant: FILTER_SOA = 1.949 V → **4.988 A vs 4.974 A true (+0.28 %)**. Phase B: −2.494 vs −2.487 A (+0.28 %). The sample sits where the ripple crosses its mean, so the firmware reads the average current, not the peak.
- SOA = 1.650 V (VREF/2) whenever the high side conducts. On the scope the CSA output is a pulse: about 0.33 V tall, sloping with the ripple, present only in the low-side window.
- Supply: **0.140 A at 30 V (4.2 W)**, of which 3.7 W is copper (1.5 × R × I²).
- PASS on all three criteria.

**Bench reproduction (needs a 30 V, 5 A ID/hold scope, not yet approved)**
- DHO804: CH1 SOA (TP20) or FILTER_SOA (TP17), DC coupled, 100 mV/div, offset −1.65 V. CH2 PWM_PHASEA_L (TP22) as the trigger (rising). CH3 SW_A (TP38). 5 µs/div. Compare the pulse height (G × Rsh × I = 0.30 V at 5 A), the slope across the window (ripple), and the settling after the window opens.
- BM235: 10 A range in series with the supply lead → compare with 0.140 A. Or read the KA3005P display. A much higher supply current than predicted points to switching or shoot-through losses (see deck 02's Miller note).
- Firmware: the GUI's phase-current reading should match IA_csa within the CSA offset (±67 mA before CSA_CAL).
- To compare at a lower current first, set `Iset` (e.g. 3 A, the current `p_i_limit`) and re-run. Ripple barely changes.
