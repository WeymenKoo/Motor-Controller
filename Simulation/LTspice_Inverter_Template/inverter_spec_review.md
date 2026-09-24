# Design Review — Switching Frequency, and What This Drive Actually Is

Reviewer's assessment from the simulated hardware alone. Part 2 deliberately ignores any stated design target and derives the capability envelope from the components and the sim.

---

# Part 1 — Is 40 kHz needed?

**No. Not for the reason you chose it, and it is not free.**

## Your stated goal is met at 25 kHz with margin

Adult hearing rolls off at 15–17 kHz; 20 kHz is the textbook ceiling and only some children reach it. PWM acoustic energy sits at f_sw and its sidebands at f_sw ± k·f_e. With f_e up to ~1 kHz, 25 kHz puts the lowest sideband at ~24 kHz — inaudible to everyone. 20 kHz would be borderline (lower sideband lands at ~19 kHz); **25 kHz is a sound choice and 40 kHz buys nothing acoustically.**

Three audible mechanisms that f_sw does *not* fix, so don't expect silence from frequency alone:

- Torque ripple at 6× electrical frequency — at 1 kHz electrical that's 6 kHz, loudly audible. This is a FOC quality problem.
- Sub-harmonic limit cycling at f_sw/2 = 12.5 kHz, which is very audible. Runs the risk of appearing if the current loop executes every other PWM cycle. **Keep the current loop at f_sw, not f_sw/2.**
- Mechanical/structural resonance excited by current ripple.

## What 25 kHz actually buys you: about 30 % of your inverter loss

Simulated, IDRIVE 0.57/1.14 A, no snubber, 50.4 V bus, per leg:

| I_rms | 25 kHz | 40 kHz | saving |
|---|---|---|---|
| ~10.6 A | 0.95 W | 1.38 W | **31 %** |
| ~15 A | 1.67 W | 2.36 W | **29 %** |
| ~20 A | 2.61 W | 3.64 W | **28 %** |

Across three legs at 15 A rms that is 5.0 W vs 7.1 W. Switching loss dominates this design, so f_sw is the single biggest lever you have on thermal performance — and thermal is what caps your continuous current rating. **Dropping to 25 kHz directly buys continuous current capability.**

Secondary wins at 25 kHz: the three-shunt sampling window gets easier (min low-side on-time ~1.1 µs is 2.8 % of a 40 µs period vs 4.4 % of 25 µs), and raising dead time to fix the shoot-through margin costs less duty range (300 ns = 0.75 % of period vs 1.2 %).

## What 40 kHz buys: ripple and top-speed control quality

**Current ripple**, single-leg 50 % duty worst case at ~10 A rms:

| L_phase | 25 kHz | 40 kHz |
|---|---|---|
| 15 µH | 18.5 A pp | 15.5 A pp |
| 30 µH | 13.6 A pp | 9.6 A pp |
| 60 µH | 7.9 A pp | 5.1 A pp |
| 120 µH | 4.1 A pp | 2.6 A pp |

A wye 3-phase load sees roughly 1.5× the effective inductance and SVPWM applies fewer volt-seconds, so real ripple is about 0.5–0.7× these figures.

**Top speed.** 20 pole pairs is a lot. At the 5040 RPM no-load point, f_e = 1680 Hz. Good FOC wants f_sw/f_e ≥ 20:

- 25 kHz → f_e ≤ 1250 Hz → **~3750 RPM** usable
- 40 kHz → f_e ≤ 2000 Hz → 6000 RPM (above the motor's no-load speed, so not limiting)

For a QDD leg through any reduction at all, 3750 RPM is far more than you need. This constraint is almost certainly irrelevant to you — but it is the honest answer to "what does 40 kHz buy".

## The decision actually hinges on a number you have not measured

Everything above is secondary to **phase inductance**, which ODrive does not publish for the M8325s and which I could not find anywhere. The 15 µH in the model is a placeholder. Run `odrivetool` calibration — it applies a square wave and measures ripple directly — and use the **phase-neutral** value (most manufacturers quote phase-phase, which is exactly 2×).

Then:

| Measured L_phase | Call |
|---|---|
| **≥ 50 µH** | 25 kHz comfortably. Take the thermal win. |
| **20–50 µH** | 25 kHz, verify ripple is tolerable in current sensing and iron loss. |
| **≤ 20 µH** | Neither frequency fixes it — at 15 µH even 40 kHz leaves ~100 % ripple. The answer is series inductors, or accepting the ripple with eyes open. Do not reach for 40 kHz thinking it solves this. |

**Recommendation: design for 25 kHz, confirm against measured inductance.** If it turns out you need 40 kHz for ripple, you will also need the IDRIVE increase from the previous review to afford it thermally.

---

# Part 2 — What this drive actually is

Written as if I had never seen a requirement for it.

## Headline

**A 48 V-class, ~10–12 A rms continuous, 3-phase FOC servo drive with high-bandwidth torque control and no regenerative energy path.**

The interesting thing about this board is that its *stated* component ratings and its *actual* capability disagree in two places, both worth knowing before anyone writes it on a datasheet.

## Bus voltage — the binding limit is 51 V, not 100 V

| Element | Rating |
|---|---|
| MOSFETs | 100 V |
| Bulk + ceramic caps | 100 V |
| **SMCJ51CA TVS standoff (VRWM)** | **51.0 V** |
| TVS breakdown (VBR) | 56.7 V min, 62.7 V max |
| TVS clamping (VC @ 18.2 A) | 82.4 V |
| Measured peak Vds, switching | 55–59 V |

The 100 V silicon suggests a 60 V-capable drive. It is not. **The TVS standoff caps working bus voltage at 51 V**, and a fully charged 12S LiPo sits at 4.2 × 12 = **50.4 V — that is 1.2 % of margin.** Above 51 V the TVS enters its knee and leakage climbs; above 56.7 V it conducts hard.

So:

- **Max continuous bus: 51 V. Recommended: ≤ 48 V.**
- This is a 12S drive with no headroom at full charge, not a "56 V" drive.
- If anyone ever wants 13S or 14S, the TVS is the first thing that has to change — not the FETs.

Switching overshoot is a non-issue by comparison: 55–59 V peak against 100 V silicon is 45 % margin, confirmed across every drive setting simulated.

## Current

| Limit | Value | Set by |
|---|---|---|
| Measurement ceiling | ±27.5 A (CSA gain 20) / ±55 A (gain 10) | CSA range, 3 mΩ shunt, 3.3 V ref |
| Hardware OCP trip | ~83 A | Far above working range — firmware is the real protection |
| Shunt thermal | 0.71 W measured at 19.6 A rms vs 3 W rating | Ample |
| MOSFET pulsed | 179 A | Not limiting |
| **Continuous** | **thermal — see below** | The actual constraint |

## Thermal — the real rating, and the number nobody has yet

Simulated inverter dissipation (3 legs, 25 kHz, IDRIVE 0.57/1.14, no snubber):

| I_rms per phase | Inverter loss | + shunts |
|---|---|---|
| 10.6 A | 2.0 W | 2.9 W |
| 15.0 A | 3.6 W | 5.0 W |
| 19.6 A | 5.7 W | 7.8 W |

These are *cold-board* numbers; RDS(on) roughly doubles by 125 °C, so conduction loss (a minority of the total here) rises accordingly.

Converting this to a current rating needs **RθJA, which has not been measured.** Your bring-up plan already includes extracting it via RDS(on)-as-thermometer per JESD51-1 — that is the missing number, and until you have it any continuous current spec is a guess.

My estimate, for a compact multilayer board with no heatsink in still air (θ ≈ 15–25 °C/W board-to-ambient): **~10–12 A rms continuous.** With forced air or a heatsink, 20 A+ is plausible. Treat these as hypotheses to be tested, not specifications.

## Torque and speed, with the M8325s

Kt = 0.0827 Nm/A:

| Operating point | Phase current | Torque |
|---|---|---|
| Continuous (thermal est.) | ~10–12 A rms → 14–17 A pk | **1.2–1.4 Nm** |
| CSA ceiling, gain 20 | 27.5 A pk | 2.3 Nm |
| Motor continuous (free air) | 40 A | 3.3 Nm |
| Motor peak | 80 A | 6.6 Nm |

**The drive, not the motor, is the limiting element** — it accesses roughly a third of the motor's continuous torque. That is a legitimate design point for a legged robot (which lives at low duty), but it should be a conscious one.

Speed: 5040 RPM no-load at 50.4 V; ~3750 RPM with good current control at 25 kHz.

## Regenerative braking — the significant gap

There is no brake chopper and no regen clamp. Bus energy headroom before the TVS conducts hard:

```
E = ½C(V_BR² − V_bus²) = ½ × 300 µF × (56.7² − 50.4²) ≈ 0.10 J
```

To the 51 V standoff it is **9 mJ**.

With a healthy battery connected this is mostly fine — regen flows back into the pack through ~20 mΩ, and 10 A of regen lifts the bus only 0.2 V. The exposure is single-fault:

- **A BMS disconnect during deceleration** leaves regen energy with nowhere to go. Rotor kinetic energy for an 840 g pancake at speed is on the order of joules — one to two orders of magnitude above the 0.1 J the bus can absorb. The TVS is a 1500 W transient part, not a brake resistor.
- A full pack at 50.4 V has essentially zero regen headroom before the TVS starts leaking.

For a legged robot, which does substantial negative work every step, this deserves a decision rather than an omission: firmware regen current limiting, a brake chopper on the PDB, or an explicit "never run on a full pack" constraint. ODrive sells a separate regen clamp for exactly this reason.

## Control

| Parameter | Value |
|---|---|
| Current loop rate | f_sw (25 kHz recommended) |
| Current loop bandwidth | ~1.5–2.5 kHz typical |
| Position feedback | AS5047P, 14-bit on-board, ABI + SPI |
| Comms | CAN FD |
| Sensing | 3-shunt low-side, 3 mΩ, CSA gain 5/10/20/40 SPI-selectable |

Adequate for impedance control on a leg.

## Known open items carried forward

- **Shoot-through margin 0.06 V at as-built IDRIVE** (previous review). Unchanged by frequency — it is a per-edge phenomenon. Raise IDRIVE to 0.57/1.14 A; verify DRV8323 adaptive TDRIVE is enabled. 25 kHz makes a longer dead time cheaper if you need one.
- Snubbers stay DNP.
- Phase inductance unmeasured — gates the frequency decision.
- RθJA unmeasured — gates the current rating.
- VDDA/VREF on the raw digital 3V3 rail; DRV_CS pull-up missing; chassis bond resistors creating ground loops; E-stop lacking RC + ESD. All Rev 2.

## Summary spec, as I would write it today

```
Bus voltage         12S LiPo, 36–50.4 V     (hard ceiling 51 V, TVS-limited)
Continuous current  ~10–12 A rms/phase      (thermal, UNVERIFIED — needs RθJA)
Peak current        27.5 A                  (CSA gain 20; 55 A at gain 10)
Continuous torque   1.2–1.4 Nm              (with M8325s, Kt = 0.0827)
Max useful speed    ~3750 RPM @ 25 kHz
Switching           25 kHz recommended      (40 kHz only if ripple demands it)
Regen               none — battery sink only, ~0.1 J transient headroom
Feedback            AS5047P 14-bit absolute, on-board
Comms               CAN FD
Protection          OCP ~83 A, TVS 51 V standoff, E-stop → TIM1_BKIN2
```

The two numbers most worth measuring before anyone commits to this sheet are **phase inductance** and **RθJA**. Everything soft in the spec above traces back to one of them.
