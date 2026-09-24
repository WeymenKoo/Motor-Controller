# Half-Bridge Simulation — Results, Risks, and Recommendations

Leg A of the FoC Motor Controller, ISC030N10NM6 + DRV8323, 12S bus (50.4 V nom / 56 V max), 40 kHz.
All numbers below are simulated on the netlist traced from `MOSFETs.kicad_sch`, with both snubber positions DNP as built.

---

## Headline

**The inverter will not blow up on voltage.** Peak Vds is 55 V on a 100 V part — 45 % margin, at every drive setting tested.

**The snubbers are not needed and do not help.** Leave R23/R24/C35/C36 depopulated.

**The real risk is somewhere else entirely:** shoot-through margin at the dead-time boundary is **0.06 V** at the as-built IDRIVE setting. That is the finding that matters, and it has a fix that also saves 38 % of switching loss.

---

## 1. Model validation (do not skip this)

A fitted model that is wrong in the wrong direction would have produced a confident, useless answer. Three checks:

| Quantity | Datasheet | Model | Note |
|---|---|---|---|
| RDS(on) @ Vgs=10 V, Id=25 A | 2.6 mΩ typ | 2.63 mΩ | via `mtriode=4.3` |
| RDS(on) @ Id=50 A | 2.6 mΩ typ (3.0 max) | 2.67 mΩ | |
| Qg to Vgs=10 V | 55 nC | 53.5 nC | |
| Qgd | 9.1 nC | 9.1 nC | `Cgdmax` fitted 1.5n → **1.8n** |

A single-equation MOSFET model cannot match RDS(on) *and* the Miller plateau simultaneously — the square law under-predicts gm at high current. `Kp` is fitted to the 4.6 V plateau and `mtriode` then corrects the triode conductance independently. Without that split, conduction loss would have been 2.5× too high.

The `Cgdmax` correction matters most: at the original 1.5 nF the model carried 8.0 nC of Qgd and switched too slowly, which **understates** ringing. It is now calibrated.

**Two artefacts I had to discard, flagged here so you don't trust them if you see them:**
- `V(geh,sh)` showed ±25 V to ±100 V spikes that moved erratically (25.8 → 1.55 → 95.4 → 1.69) across a *smooth* parameter sweep while Vds varied smoothly. Inspection showed three samples sharing one timestamp with `dt = 0`, during a quiet interval before any switching. Solver residue. 6 samples in 100,239.
- My first ring metric (RMS of Vds−Vbus after the edge) reported every snubber as *worse* than bare. It was measuring the freewheel diode offset — PH sits at Vbus+Vf ≈ 51.2 V, not 50.4 V — rather than any oscillation.

---

## 2. Parasitic extraction

Two-point method: ring frequency bare, then with a known 4.7 nF across the low-side device.

```
f₀ = 90.4 MHz   (bare)
f₁ = 41.7 MHz   (+4.7 nF)

C_par = 1271 pF      L_par = 2.44 nH      Z₀ = √(L/C) = 1.39 Ω
```

**The extracted 2.44 nH is not the 15 nH commutation loop, and that is the interesting part.** The local 100 n 0603 at the bridge bypasses the bulk loop at 90 MHz, so the real HF ring loop is package source inductance (2 × 0.5 nH) + shunt inductance (1.5 nH) + ceramic ESL (0.8 nH) ≈ 3.3 nH. Measured 2.44 nH. Your local decoupling is doing its job — the bulk loop never participates.

C_par = 1271 pF is consistent with Coss = 885 pF at 50 V plus the opposite device and strays.

---

## 3. Double-pulse result (as built, snubbers DNP)

```
Turn-off at 17 A, 50.4 V bus:

  Peak Vds        54.83 V      (54.8 % of BVDSS — 45 V of margin)
  Overshoot        4.43 V
  Ring            89.7 MHz
  Ring amplitude   0.64 V → 0.26 V over two cycles
  Settled         ~40 ns
  Peak Id         32.8 A       (17 A load + body-diode reverse recovery)
```

The ring is already near-critically damped by the circuit's own resistance — RDS(on), the 3 mΩ shunt, bank ESR. There is under 1 V of oscillation to suppress.

---

## 4. Snubber sweep — 32 combinations, none of them help

R ∈ {0.68 … 10 Ω} × C ∈ {1, 2.2, 3.3, 4.7 nF}, low-side position:

| Config | Vds peak | Ring amplitude (1st → 3rd extremum) |
|---|---|---|
| **Bare (as built)** | 54.83 V | 0.64 → 0.26 V @ 89.7 MHz |
| R=3.9 C=2.2n (board values) | 54.72 V | 0.97 → 0.41 V @ 88.5 MHz |
| R=1.5 C=3.3n (nearest to theory) | 55.01 V | 0.46 → 0.70 V @ 19.8 MHz |

Peak Vds moves by at most 0.7 V across the entire grid. No combination reduces ring amplitude below bare. Larger C simply drags the resonance down toward 20 MHz without damping it further.

**If EMC testing later forces the issue**, the theoretically correct values from the extraction are **R ≈ 1.4 Ω** (not 3.9 Ω — the board value is overdamped relative to Z₀) and **C ≈ 3.8–6.4 nF** (not 2.2 nF — undersized at ~1.7× C_par rather than 3–5×). But populate them only against a measured EMC failure, because lowering the ring from 90 MHz to 20 MHz is not automatically an improvement — it depends which band you are failing.

### Correction to what I told you earlier

I previously estimated snubber dissipation as `P = C·V²·f ≈ 224 mW` and called it 1.8× over the 0805 1/8 W rating. **That was wrong.** Simulated: **80 mW**.

`C·V²·f` assumes a step transition. Here RC = 3.9 × 2.2n = 8.6 ns against a ~60 ns edge, so the cap tracks the node quasi-statically instead of being hard-switched. The correct form in this regime is `2C²V²R·f / t_transition` ≈ 64 mW, which matches. The C·V²·f figure is an upper bound that only applies when RC ≫ transition time.

So the snubbers would be thermally *fine* if populated. They are just pointless.

---

## 5. Continuous 40 kHz — thermal

At the **10 A rms design point**, no snubber:

| IDRIVE (src/snk) | Vds peak | P(M2) low side | P(M1) high side | P(shunt) |
|---|---|---|---|---|
| **0.33 / 0.66 A (as built)** | 54.8 V | 1.23 W | 0.19 W | 0.26 W |
| 0.57 / 1.14 A | 56.1 V | 0.92 W | 0.20 W | 0.26 W |
| 1.00 / 2.00 A | 57.3 V | 0.74 W | 0.20 W | 0.26 W |

Shunt dissipation 0.26 W against a 3 W 2512 — comfortable.

At 15.5 A rms the IDRIVE sensitivity becomes dramatic:

| IDRIVE | P per leg |
|---|---|
| 0.06 / 0.12 A | **16.9 W** |
| 0.12 / 0.24 A | 5.75 W |
| 0.19 / 0.38 A | 3.76 W |
| 0.33 / 0.66 A (as built) | 2.82 W |
| 0.57 / 1.14 A | 2.36 W |
| 1.00 / 2.00 A | 2.08 W |

**Switching loss dominates: 1.66 W of M2's 1.98 W at as-built settings.** If you ever configure IDRIVE near the bottom of the table by mistake, the leg dissipates 17 W and the board dies. Worth a firmware assertion on the SPI register value.

---

## 6. The actual risk: shoot-through margin

Measured at the instant the low-side FET turns on, with the high-side driver commanding off:

| IDRIVE | Vgs(HS) at LS turn-on | Peak Vgs(HS) during the edge | Headroom to Vth |
|---|---|---|---|
| **0.33 / 0.66 A (as built)** | 1.25 V | **2.74 V** | **0.06 V** |
| 1.00 / 2.00 A | 0.41 V | 2.17 V | 0.63 V |

Vth = **2.8 V typical**. The as-built configuration clears it by 60 millivolts.

That is not a real margin, for three compounding reasons:

1. **Datasheet Vgs(th) minimum is 2.3 V**, not 2.8 V. On a min-threshold part, 2.74 V is already *above* threshold.
2. **Vth has a negative tempco** (≈ −6 mV/°C). At 125 °C junction, typical Vth falls to roughly 2.2 V and minimum to ~1.7 V. The 2.74 V excursion is then well into conduction.
3. The 200 ns dead time is not enough for the gate to discharge. With Rsnk = 15.15 Ω and Ciss = 4 nF, τ = 61 ns, so after 200 ns the gate is still at 1.25 V — and the low-side turn-on edge then Miller-couples another 1.5 V on top.

**Mechanism:** this is dead-time inadequacy compounded by Miller coupling, not a layout problem.

### Important caveat in your favour

The model uses a **fixed** 200 ns dead time. The real DRV8323's TDRIVE state machine uses **adaptive, Vgs-sensed** dead time — it waits for the gate to actually fall before switching the other device. If that is enabled, hardware has materially more margin than this model shows. **Confirm it is enabled before acting on this.** The model identifies the mechanism and the sensitivity; it does not model the mitigation that may already be present.

---

## 7. Recommendations

**Do not populate the snubbers.** R23/R24/C35/C36 stay DNP. The ring is under 1 V and damps in 40 ns; no R/C combination tested improves it. The DNP decision was correct.

**Raise IDRIVE to 0.57/1.14 A or 1.00/2.00 A.** This is the one change worth making and it wins on both axes:
- Shoot-through headroom: 0.06 V → 0.63 V
- Switching loss: −25 % to −38 %
- Cost: 1.5–2.5 V more overshoot, against 45 V of margin

**Do not add external gate resistance.** My earlier guide suggested sweeping RG_EXT upward to reduce overshoot. Given this result that trade is backwards — slower turn-off directly erodes the shoot-through margin, and you have voltage margin to spare. The 0 Ω resistors that were flagged as a layout risk are, on this evidence, the right call. Keep the footprints for flexibility.

**Verify the DRV8323 TDRIVE adaptive dead-time configuration** before trusting the 200 ns figure either way. If adaptive dead time is off, turn it on; if it cannot be, raise the fixed dead time to ≥ 300 ns (≈5τ).

**Add a firmware guard on the IDRIVE SPI register.** A mis-write to a low code costs 17 W per leg. Read the register back after configuration and refuse to enable TIM1 if it does not match.

**At bring-up, measure Vgs on the off device directly.** This is the one prediction here most worth confirming on hardware, because it is where the model is both least certain and most consequential. A differential probe across GHx–SHx during a low-side turn-on edge settles it.

---

## 8. What this does not cover

- No thermal feedback. RDS(on) roughly doubles at 125 °C; conduction loss above is a cold-board number. Switching loss dominates, so the totals move less than you'd fear.
- `LLOAD = 15 µH` is still a placeholder — replace with odrivetool calibration output. It sets di/dt and ripple, not the ring.
- One leg. Three legs share the bulk bank; bus ripple is worse than modelled.
- Stray inductances are estimates, but note the extraction in §2 is self-consistent and can be re-run against hardware to get the real numbers.
- Gate driver is idealised apart from IDRIVE source/sink impedance and the IHOLD path.
