# Half-Bridge Simulation Bench — User Guide

**File:** `LTspice_Inverter_Template/inverter_gate_motor_template.asc`

This bench answers two questions and deliberately nothing else:

1. **Will the inverter survive being switched at 40 kHz?** (voltage overshoot vs. the 100 V FET rating, parasitic turn-on of the off device, snubber dissipation)
2. **What should the snubber actually be?** (measured from the real ring, not guessed)

It does *not* do FOC, SVPWM, or closed-loop control. That was the right call to cut — you do not need a modulator to answer either question. Switching stress is a *per-edge* phenomenon: every edge in an SVPWM waveform is the same edge you can study one at a time, and studying it one at a time is how the industry actually does it.

---

## 1. What you are looking at

The schematic reads left to right, following the power:

```
V1 ──R1── C1/R2 ──L1── C2/L2 ──┬── M1 (high side)
battery   bulk    loop   local  │    └─L3─┐
          cap      L    ceramic │         ├── PH ──L5──R3── back to bus
                                │    ┌────┘         (load)
                                └── M2 (low side)  ── Rsn/Csn snubber
                                     └─L4─ GND
```

| Part | What it represents |
|---|---|
| `V1`, `R1` | 12S pack and its wiring resistance |
| `C1`, `R2` | your C34/C37/C39 electrolytic bank and its ESR |
| `L1` | **commutation loop stray inductance** — the single most important parasitic in this whole file |
| `C2`, `L2` | the local HF ceramic at the bridge, and its ESL |
| `M1`, `M2` | the two FETs, as a fitted VDMOS model |
| `L3`, `L4` | package/source inductance |
| `Rsn`, `Csn` | the snubber you are sizing (your R13/R14/R15 + C25/C26/C27) |
| `L5`, `R3` | motor phase load |
| `V2`/`V3` + R/D networks | the DRV8323 gate drive, with separate source and sink paths |

Two things worth internalising before you run anything:

**`L1` causes the ringing, not the FET.** The overshoot you are about to snub is energy stored in loop inductance that has nowhere to go when current stops abruptly. A snubber dissipates that energy. Shrinking the loop *prevents* it. Snubbing is always the second-best fix — if the simulation says you need a big lossy snubber, the real answer is usually layout.

**The gate drive has asymmetric paths on purpose.** `Rsrc_G` (turn-on) and `Rsnk_G` (turn-off) are derived from the DRV8323's IDRIVE source/sink settings, which are genuinely different — sink is roughly 2× source at a given code. Turn-*off* speed is what sets your overshoot, so that asymmetry matters.

---

## 2. The one knob

Near the top of the left text column:

```
.param TEST=1
```

- `TEST=1` → double-pulse test (snubber sizing, EMC)
- `TEST=2` → continuous 40 kHz (survival check)

Everything else — pulse timing, simulation length, timestep, load resistance, whether the high side is driven — derives from that one number through `if()` expressions. Change nothing else to switch tests.

**To run:** open the `.asc` in LTspice, hit the running-man icon (or Simulate → Run). To see the measurement results: **View → SPICE Error Log**.

**To plot a signal:** click on a wire for its voltage, or on a component body for its current. To plot a *differential* voltage (like V(PH,sL)), click on one node and drag to the other.

---

## 3. TEST 1 — Double-pulse test

### Why this test exists

40 kHz is 40,000 switching edges per second. Looking at all of them at once tells you nothing. The double-pulse test isolates exactly one turn-off and one turn-on so you can see the transient properly, with a 100 ps timestep that would be unaffordable over a long run.

It also creates the *worst-case* conditions on purpose: the turn-off happens at a known, controlled current, and the second turn-on happens into a freewheeling body diode (which is when reverse-recovery current adds to your peak).

### What happens when you run it

| Time | Event |
|---|---|
| 1 µs | Low-side FET turns on. Current ramps in `L5` at `VBUS/LLOAD` ≈ 3.4 A/µs |
| 6 µs | **Turn-off #1.** Current ≈ 17 A. *This is your snubber measurement.* |
| 6–8 µs | Current freewheels through M1's body diode (M1's gate is held at 0 V in this mode) |
| 8 µs | **Turn-on #2** into the conducting body diode → reverse recovery spike |
| 13 µs | Turn-off #2 |

### What to plot

Start with these four:

- **`V(PH,sL)`** — drain-source of the device under test. This is the waveform you are sizing the snubber against.
- **`Id(M2)`** — drain current. Look at the turn-on at 8 µs for the reverse-recovery spike.
- **`V(geL,sL)`** — gate-source of the DUT. You should see a clear Miller plateau around 4.6 V.
- **`V(geH,sH)`** — gate-source of the *off* device. **If this crosses ~2.8 V you have parasitic turn-on and a shoot-through path.** This is a genuine blow-up mechanism and it is worth checking every time you change gate drive settings.

Zoom hard into the 6 µs edge. That is where all the information is.

---

## 4. Sizing the snubber properly

Do not guess and iterate. There is a measurement procedure that gets you the right answer in three runs, because the ring frequency tells you what the parasitics actually are.

### Step 1 — measure the undamped ring

Set `CSNUB=1p` (effectively no snubber). Run `TEST=1`. Zoom into the turn-off edge of `V(PH,sL)`.

Put cursors on two adjacent ring peaks. Read Δt. Then **f₀ = 1/Δt**. Also note the peak voltage.

### Step 2 — add a known capacitor and re-measure

Set `CSNUB` to something that visibly slows the ring — try `4.7n` — and set `RSNUB=0.001` so it is a pure capacitor, not yet damped. Run again, measure the new ring frequency **f₁**.

### Step 3 — solve for the real parasitics

You now have two equations and two unknowns:

```
C_par = C_added / ( (f₀/f₁)² − 1 )

L_par = 1 / ( (2π·f₀)² · C_par )
```

`C_par` is the effective output capacitance of the node; `L_par` is the effective loop inductance. **These are the numbers you actually wanted** — and notice you just measured your own layout's parasitic inductance without a VNA.

### Step 4 — pick R and C

```
R_snub ≈ √( L_par / C_par )        (the characteristic impedance — this is what critically damps it)

C_snub ≈ 3 to 5 × C_par             (bigger = more damping, more loss)
```

### Step 5 — verify, then check what it costs you

Re-run with your new values. Confirm the overshoot is where you want it, then look at the dissipation:

```
P_snub ≈ C_snub · V_bus² · f_sw
```

The `Psnub` measurement in the error log gives you the simulated number to check that against.

### A result you should brace for

Run the numbers on the values currently on your board — 2.2 nF at 50.4 V and 40 kHz:

```
P = 2.2n × 50.4² × 40k ≈ 0.22 W per snubber
```

Your R13/R14/R15 are 0402 parts rated 1/16 W (62.5 mW). That is roughly **3.5× over rating**. Verify it yourself with `Psnub` in TEST=2 rather than taking my arithmetic on faith — but if it holds, this is a real Rev 2 item, and it is exactly the thing your earlier review flagged as unverifiable because the switching frequency was never stated on the schematic. Now it is verifiable.

Your options if it confirms: larger resistor package, smaller `CSNUB` (costs damping), lower `f_sw`, or a different damping strategy entirely (e.g. improving the loop so you need less snubber). Worth thinking through which of those you actually want before deciding.

---

## 5. TEST 2 — Continuous 40 kHz

### Why

TEST 1 tells you about one edge. TEST 2 tells you whether the thing runs — steady-state currents, whether the transients repeat identically or build on each other, and what the snubber and FETs dissipate over many cycles.

### What changes

Set `TEST=2`. Both FETs now switch complementary at 40 kHz, 50 % duty, with 200 ns dead time. `RLOAD` switches to 1.7 Ω, giving roughly 15 A of DC load current. Simulation runs 400 µs (16 switching cycles) at a 2 ns timestep.

**This run is slow** — expect minutes, not seconds. That is the price of resolving nanosecond edges over hundreds of microseconds, and it is why TEST 1 exists.

### What to check

- **`Vds_pct`** in the error log — peak drain-source as a percentage of the 100 V rating. Under 80 % is the usual comfort threshold. Remember your SMCJ51CA TVS clamps around 82 V under surge, so the bus itself can transiently sit higher than 50.4 V before switching overshoot is even added.
- **`Vgs_hs_offpk`** — must stay well below `VTO` (2.8 V). This is your shoot-through margin.
- **`Psnub`** — the thermal question from Section 4.
- **`Id_ls_pk`** — peak current including recovery spikes, against the FET's pulsed rating.
- Plot `V(PH,sL)` across several cycles and confirm every edge looks the same. If overshoot grows cycle-on-cycle, something is not settling.

Useful addition if you want device loss: add a directive

```
.meas TRAN Pm2 AVG Id(M2)*V(PH,sL)
```

which gives average dissipation in the low-side FET (conduction + switching together).

---

## 6. Swapping in a different MOSFET

Change the eleven `.param` lines in the left column. Here is where each comes from on a datasheet:

| Param | Source |
|---|---|
| `VTO` | Vgs(th), typical |
| `KP` | `2·Id / (V_plateau − Vto)²` using the gate-charge test conditions |
| `RDON` | RDS(on) at the Vgs you actually drive |
| `RG_INT` | internal gate resistance Rg |
| `CGS_M` | Ciss − Crss, at the datasheet's Vds test point |
| `CGDMAX` | fit to Qgd — start around 100× `CGDMIN` and adjust until the plateau length matches |
| `CGDMIN` | Crss at the datasheet Vds |
| `CJO` | `(Coss − Crss) · √(1 + Vds_test/0.8)` |
| `RB` | from the body diode forward drop at rated current |
| `TT` | from Qrr |
| `BVDSS` | V(BR)DSS |

The `CJO` formula is worth understanding rather than just applying: LTspice models the body-diode junction capacitance as `Cjo/√(1+V/0.8)`, so you are back-solving the zero-bias value from the datasheet's value at its test voltage. For the ISC030N10NM6 that gives `(900p−15p)·√(1+50/0.8) ≈ 7.0 n`, which is what is in the file.

**Sanity-check after swapping:** run TEST=1 and confirm the gate plateau in `V(geL,sL)` sits at the datasheet's plateau voltage and lasts roughly `Qgd/I_drive`. If it does, your capacitance fit is good enough to trust the switching waveforms.

---

## 7. Swapping the motor

`LLOAD` is currently a **placeholder** (15 µH). ODrive does not publish phase inductance or resistance for the M8325s anywhere — I checked their shop pages and the community threads. The authoritative numbers come from your own hardware: ODrive's motor calibration measures phase resistance and inductance directly and reports them. Use those.

For this bench, `LLOAD` only sets the di/dt during the double pulse and the ripple in TEST 2. It is not critical to get exactly right for snubber sizing (the ring is set by `L1` and the FET capacitance, not the load), but it matters for realistic current levels.

---

## 8. What this model will not tell you

Be clear-eyed about the boundaries:

- **The gate driver is idealised.** No propagation delay, no adaptive dead time (the real DRV8323 senses Vgs and adjusts), no ISTRONG 2 A pulldown, no 150k/480k hold-off resistors. Your real parasitic-turn-on margin is *better* than this model suggests, not worse — so treat a `Vgs_hs_offpk` pass here as necessary, not sufficient.
- **Stray inductances are lumped guesses.** `LLOOP=15n` is a plausible value for a decent layout, not a measurement. The Step 3 procedure above lets you *extract* the real one once you have hardware — and then this model becomes genuinely predictive.
- **The VDMOS model is fitted, not vendor-validated.** Relative comparisons (snubber A vs. snubber B, gate resistor 0 Ω vs. 2.2 Ω) are trustworthy. Absolute loss numbers are indicative only.
- **No thermal model.** Nothing here heats up, and RDS(on) roughly doubles at 125 °C.
- **One leg only.** The real board has three legs sharing one bulk cap. Bus ripple current and sag are worse than this file shows.

---

## 9. Further reading

You already have several of these in the project:

- `sicmos_snubber_circuit_design_ane.pdf` — snubber design procedure, same method as Section 4
- `Mosfet optimization slvaf66.pdf` (TI SLVAF66) — §3.1.2 is the source of the gate-drive topology used here
- `MOSFET literature sbaa698a.pdf` — switching loss mechanisms
- `infineonisc030n10nm6datasheeten 1.pdf` — every model parameter traces back here

Worth adding:

- TI **SLUA618** — *Fundamentals of MOSFET and IGBT Gate Driver Circuits*, the standard reference for Miller plateau and parasitic turn-on
- LTspice's own help page for **VDMOS** — documents every parameter in the `.model` line
- Infineon's application notes on **double-pulse testing** — for how this is done on real hardware, which you will want when you get to bring-up

---

## 10. Suggested order of work

1. Run TEST=1 as shipped. Look at the turn-off edge. Get a feel for what the ring looks like.
2. Do the Section 4 extraction properly. Write down your `L_par` and `C_par`.
3. Pick R and C from the formulas, re-run, confirm.
4. Check `Psnub` against the resistor rating. Decide what to do about it.
5. Run TEST=2 once as a survival check and to get steady-state dissipation.
6. Sweep `RG_EXT` (0 Ω → 2.2 Ω → 4.7 Ω) in TEST=1 and watch overshoot vs. switching loss trade off. This is the argument for whether your current 0 Ω gate resistors are the right call.
7. Set `LS_PKG=0.1n` and re-run to see what a proper Kelvin gate connection buys you.

Steps 6 and 7 are where this file earns its keep — both are decisions you will otherwise be making on intuition.
