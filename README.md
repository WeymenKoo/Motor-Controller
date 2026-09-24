# Building a FOC Motor Controller for a Cat-Scale Robot Leg

Technical notes from a full design cycle: idea → theory → schematic → simulation → layout → fab → bring-up plan. Written as a knowledge refresher as much as a build log, so each section starts with the background needed to follow the decision.

**Status:** Rev 1 design-frozen and fabricated. Not yet bench-validated. Everything below is analytical or derived from the fabrication files.


## Repository layout

| Path | Contents |
|---|---|
| `FoC Motor Controller.kicad_pro` / `.kicad_sch` / `.kicad_pcb` | KiCad 10 project, root sheet and board |
| `Schematics/` | Hierarchical sheets (power, MCU, gate driver, MOSFETs, sensing, CAN-FD, interconnects, ...) |
| `Libraries/` | Project-local symbols, footprints and 3D models (referenced via `${KIPRJMOD}/Libraries/`) |
| `Documentation/` | Design rationale, layout/manufacturing review, board renders, RevC action summary |
| `Simulation/` | LTspice inrush and inverter/gate-drive benches |
| `Project Outputs/` | BOM, pick-and-place, netlist, fabrication package (Rev 1), schematic PDF |

Open `FoC Motor Controller.kicad_pro` in KiCad 10. Vendor datasheets and the KiCad worksheet templates are not included in this repo; without the templates KiCad falls back to its default title block.

---

## 1. What and why

A single-axis field-oriented-control motor controller for one joint of a cat-scale bipedal robot. Six boards, one per joint, sharing a 12S bus, coordinated over CAN-FD.

The actuator architecture is **quasi-direct drive** — a low gear ratio (roughly 6:1 to 10:1) between a large-diameter pancake outrunner and the joint, rather than the 100:1+ of a conventional servo.

Why that matters, because it drives everything downstream:

| QDD property | Consequence for the electronics |
|---|---|
| Backdrivable, low reflected inertia | Torque control fidelity matters more than peak power. Current-sense accuracy becomes a first-class requirement, not an afterthought. |
| Joint torque ∝ motor current, almost directly | Current sense error *is* torque error. No gearbox to hide it behind. |
| Impacts transmit straight back to the motor | Regeneration is routine, not exceptional. Bus transient behaviour is a safety question. |
| It hangs on a limb | Board mass is a real constraint. An over-specified power stage is a defect, not free margin. |

Reference motor: ODrive M8325s, 100 KV, 92 mm pancake outrunner, **20 pole pairs**. That pole count comes back repeatedly.

---

## 2. Theory refresher: why FOC at all

### 2.1 The problem with six-step commutation

Trapezoidal (six-step) BLDC control energises two phases at a time and commutates on Hall transitions. It's simple, and for a fan or a drill it's fine. It has two properties that kill it for a leg joint:

- **Torque ripple.** Torque varies by roughly 13% across each 60° electrical sector because the current vector jumps in discrete steps rather than rotating smoothly.
- **No control of the current *angle*.** You can only control magnitude.

### 2.2 What FOC actually does

FOC transforms the three phase currents into a rotating reference frame locked to the rotor, so that a spinning three-phase AC problem becomes two DC quantities you can put a PI loop around.

```
Clarke:  3-phase (a,b,c)  →  2-axis stationary (α,β)
Park:    stationary (α,β) →  rotor-synchronous (d,q)   [needs rotor angle θ]

  i_d  = flux-producing current   → command 0 for a surface-PM motor
  i_q  = torque-producing current → this is your torque command
```

Two consequences worth internalising:

1. **Park needs θ.** The whole scheme collapses without an accurate rotor angle. This is why position sensing is not a peripheral feature — it is load-bearing.
2. **Commanding `i_d = 0`** means all current produces torque and none produces useless flux. That's the efficiency win over six-step, alongside the smoothness win.

The inverse path (inverse Park → SVM → gate signals) synthesises the voltage vector. **Space Vector Modulation** is worth knowing as the standard choice: it uses the two adjacent active vectors plus zero vectors, and by injecting a common-mode third harmonic it gets ~15% more bus utilisation than sinusoidal PWM for the same DC link.

### 2.3 Why sensorless was ruled out immediately

Sensorless FOC estimates θ from back-EMF. Back-EMF is proportional to speed, so at zero speed there is nothing to observe. A leg joint's primary duty is **holding position and torque at or near zero speed** — exactly where the observer has no signal.

Not a close call. Absolute magnetic encoder, AS5047P, 14-bit, over SPI.

**Refresher — magnetic encoder basics:** a diametrically-magnetised magnet on the shaft end, Hall array on the IC, sensing field *direction* not strength. Field strength only has to be in range (typically 30–70 mT). Absolute means it knows the angle at power-up with no homing move — essential when powering up a leg that is already loaded.

---

## 3. Requirements, and one I got wrong in my own documentation

```
Bus:              12S LiPo — 50.4 V full charge, 44.4 V nominal, 56 V max
Phase current:    10 A RMS continuous
Control:          sensored FOC, three-shunt low-side sensing
Comms:            CAN-FD, 6 nodes on a shared bus
Switching:        inaudible
```

### The f_sw story — worth reading as a lesson in post-hoc rationalisation

**The actual requirement was "inaudible."** 40 kHz was chosen as arbitrary headroom above the ~20 kHz audibility limit. That's it.

Later documentation in this project (including my own design record) presented a derivation:

```
f_electrical = rpm/60 × pole_pairs = 3500/60 × 20 ≈ 1167 Hz
20 PWM cycles per electrical cycle → ~23 kHz floor
∴ 40 kHz
```

That derivation is *correct arithmetic* and a genuinely useful sanity check — it confirms 40 kHz is comfortably above the control-bandwidth floor. But it is **not why the number was chosen**, and writing it up as though it were makes the design look more derived than it was.

Worth flagging because this is a common failure mode in engineering documentation: a number picked by judgement acquires a derivation after the fact, and three revisions later nobody remembers which constraint is real. If f_sw ever needs to move, the binding constraint is audibility and the charge-pump budget — not the pole-pair math.

**The 20-cycles-per-electrical-cycle rule** is still worth knowing: it's a sampling-rate argument. Your current loop runs at f_sw, and it has to track a sinusoid at f_electrical. Fewer than ~10–20 samples per cycle and the loop can't keep up with the rotating vector.

---

## 4. Design workflow

Fixed order, applied per subsystem:

```
1. First principles      → napkin numbers, identify the BINDING constraint
                           (no optimisation — the goal is order of magnitude)
2. SPICE                 → build from the napkin result, optimise here
3. Component search      → real parts, availability checked before committing
4. Power & thermal       → hot Rds(on), not the 25 °C headline
5. BoM consolidation     → once the design is stable, never during
6. Schematic review      → verify earlier action items actually landed
7. Layout
```

### Why LTspice is not used for the control loop

Tried it, abandoned it. The timescale separation is fatal:

```
Device switching:      ~5 ns edges
Mechanical settling:   ~500 ms
Ratio:                 10^8
```

A transient solver forced to resolve nanosecond edges across a mechanical settling time isn't just slow — it accumulates numerical error that swamps the result. **Control loops belong in discrete-time simulation. SPICE is for the power stage only.**

Three benches that were useful:

- `dpt_halfbridge.cir` — double-pulse test, one half-bridge
- `input_stage_transients.cir` — hot-plug and inductive transient
- `bus_regen_cascade.cir` — multi-board shared-bus regeneration

**Refresher — the double-pulse test (DPT)** is the standard method for characterising switching loss and overshoot. Two gate pulses: the first builds current in an inductive load, the gap measures turn-off, the second measures turn-on with the current already established. It isolates switching behaviour from conduction behaviour.

The single most useful result from the whole simulation effort:

```
Commutation loop inductance → V_GS undershoot
   2 nH  →  ~0 V
  80 nH  →  −4.9 V
```

Gate-oxide stress and false turn-off appear **well before** drain overshoot looks alarming on a scope. That reframed loop area as the number one layout variable, not one of several.

---

## 5. Power stage

### 5.1 Refresher: where the losses come from

```
Conduction:   P = I²_rms × R_DS(on, hot)
Switching:    P = ½ × V_bus × I × (t_r + t_f) × f_sw
```

Two things that trip people up:

**R_DS(on) roughly doubles from 25 °C to 150 °C.** The datasheet headline is at 25 °C. Using it for thermal work underestimates conduction loss by 2×.

**t_r and t_f are set by gate charge, not by the FET's "speed".** Specifically by **Q_gd**, the gate-to-drain (Miller) charge. During the Miller plateau, all your gate current goes into discharging C_gd while V_DS swings — that's the transition, and that's where switching loss happens.

```
t_r ≈ Q_gd / I_drive
```

So a "faster" FET is one with lower Q_gd, and drive current is a lever you control.

### 5.2 The 40 V mistake

Rev A used CSD18540Q5B — **40 V V_DS rating on a bus whose full-charge voltage is 50.4 V**.

Not a margin question. The device is outside its absolute maximum at rest, before anything switches.

How it happened: component selection was anchored on R_DS(on) and package, with no explicit voltage-margin gate. The rule adopted afterwards:

> **Voltage rating is checked first, against worst-case bus transient, before any other parameter is considered.**

### 5.3 The loss inversion — the most instructive result in the project

Having fixed the voltage rating, the obvious next move is the lowest R_DS(on) 100 V part available. That's how IPT015N10N5 (1.5 mΩ) entered the design.

Running the numbers at the actual operating point:

```
40 A RMS, 40 kHz, 50 V bus, I_drive = 1 A

R_DS(on)   P_cond    P_sw     P_total
1.50 mΩ    1.80 W    3.85 W   5.65 W   ← lowest Rds(on), WORST total
2.24 mΩ    2.69 W    1.58 W   4.27 W   ← best
2.70 mΩ    3.24 W    1.36 W   4.60 W
```

The 1.5 mΩ part loses because its Q_gd is 2–3× higher. **At this current and frequency, switching loss dominates conduction loss**, so the parameter everyone markets on is the wrong one to optimise.

Selection metric changed to **figure of merit**:

```
FOM = R_DS(on) × Q_g     (lower is better)
```

This is the standard metric for exactly this reason — it captures the fundamental process trade-off. A die that's bigger has lower resistance and more gate capacitance. FOM measures how good the silicon is, independent of how you sized the die.

### 5.4 Final selection

**Infineon ISC030N10NM6** (OptiMOS 6), 100 V, 3.0 mΩ max, Q_g 55 nC, Q_gd 14 nC, **PG-TDSON-8 (5 × 6 mm)**.

Note on package: earlier project notes say TOLL. The **fabricated board uses TDSON-8, the 5 × 6 mm package** — that change was made deliberately. Six TOLL packages would occupy roughly 700 mm² for a stage dissipating under a watt at the design point. On a limb, board area is mass, and mass is what the whole machine is fighting. Margin that costs nothing is worth keeping; margin that costs the primary system constraint is a defect wearing a reassuring disguise.

Sourcing note: **JLCPCB's entire 100 V TOLL inventory is optimised for 200–360 A battery/BMS applications.** Those parts buy R_DS(on) this design doesn't need by paying gate charge it can't afford (165–252 nC vs 55 nC). This is a case where local-assembly convenience had to lose to the electrical requirement, and the part became an extended/consigned line.

### 5.5 Thermal

Using hot R_DS(on) ≈ 6 mΩ, datasheet t_r/t_f of 4.5/5.3 ns, R_thJA = 50 °C/W (datasheet figure for ~6 cm² copper, no heatsinking), T_a = 40 °C:

| Phase current | P_cond (3 legs) | P_sw (6 FETs) | P per FET | T_j |
|---|---|---|---|---|
| 10 A | 1.80 W | 0.71 W | 0.42 W | 61 °C |
| 20 A | 7.20 W | 1.41 W | 1.44 W | 112 °C |

**At 10 A the inverter is thermally uncritical.** That's what makes the package downsize a real trade rather than a risk. See §11.2 for how the as-built layout changes the 20 A number.

---

## 6. Gate drive

### 6.1 Refresher: what a gate driver actually has to do

A high-side N-channel MOSFET's source sits at the switch node, which swings to the full bus voltage. To hold it on, V_GS must be ~10 V **above** the switch node — i.e. above the bus. That voltage has to come from somewhere.

Two standard approaches:

- **Bootstrap** — a capacitor charged through a diode while the low side is on. Cheap. Fails at 100% duty cycle because the cap never gets recharged.
- **Charge pump** — an on-chip doubler generating a rail above V_M continuously. Works at any duty cycle.

The DRV8323 has an integrated charge pump. That matters for FOC because SVM does spend time at very high duty on individual phases.

### 6.2 The charge pump budget — and a correction to my own analysis

The charge pump supplies the **high-side** gates only (low-side gates are driven from an internal linear regulator off V_M). TI's datasheet gives:

```
I_VCP ≥ 3 × Q_g × f_PWM        [3 high-side gates]
```

At 55 nC and 40 kHz:

```
I_required = 3 × 55 nC × 40 kHz = 6.6 mA
I_available = 25 mA
Margin = 3.8×                                 ✓ comfortable

Q_g ceiling at 2× margin = 25 mA / (2 × 3 × 40 kHz) ≈ 104 nC
```

**Correction to earlier project documentation.** A design record I wrote during this project claimed the correct 2×-margin ceiling was ~52 nC, derived from `6 × Q_g × f_sw` — counting all six devices. That is wrong: the low-side gates are not a charge-pump load. The original project note (~100 nC at 2× margin) was right and my "correction" introduced an error.

The lesson generalises: **when you re-derive someone's number and get a different answer, check whether you changed the model before concluding they were wrong.** A factor-of-two disagreement is usually a definition disagreement, not an arithmetic one.

Separately, the capability figure itself was corrected in the other direction: an early note said the charge pump supplies 10–15 mA. That's the low-V_M figure where the doubler is strained. At a 44–50 V bus it's **25 mA**.

### 6.3 Slew rate control: gate side, not drain side

**Refresher on the trade.** Fast switching = low switching loss, but high dv/dt and di/dt, which means more overshoot (`V = L·di/dt` across the commutation loop inductance) and more EMI. Slow switching is the opposite. You need a knob.

Three ways to get one:

| Approach | How it works | Verdict here |
|---|---|---|
| Drain-source RC snubber | Damps the loop-L / C_oss resonance | Rejected — costs board area, burns power continuously, and needs resistor power-rating work |
| Asymmetric gate network (R + parallel diode) | Slow turn-on, fast turn-off | Rejected — this is a workaround for drivers with a single fixed drive current |
| Programmable I_DRIVE | Driver sources/sinks a configured current | **Selected** |

The DRV8323's Smart Gate Drive provides independently programmable source and sink currents over SPI — the same asymmetry the diode network provides, implemented internally. TI's own app note recommends a single small or 0 Ω external series resistor when it's in use.

Sizing:

```
I_DRIVE = Q_gd / t_r_target = 14 nC / 50 ns = 280 mA
```

Shipped configuration: **0 Ω series gate resistors populated** (so I_DRIVE has sole control), with the gate-source RC network (3.9 Ω + 2.2 nF per FET) **fitted as DNP footprints**. That's deliberate insurance — ship with the simplest arrangement, add damping only if the real waveforms demand it.

One thing to know if you populate them: a 2.2 nF gate-source cap adds ~22 nC per device to the charge-pump demand (`Q = C·V`). Re-check the budget before doing it.

**Honest caveat:** this replaced a *sized* snubber with a *removed* snubber. That converts a sizing task into a validation task, and it raises rather than lowers the priority of the DPT work. The board has no drain-side snubber footprints, which in hindsight should have been added as DNP.

### 6.4 Dead time

**Refresher:** both FETs in a leg on simultaneously = shoot-through = a direct short across the bus through two devices. Dead time is the deliberate gap where both are off.

```
t_dead > t_r + t_f + driver propagation delay mismatch
```

Start conservative (200–300 ns), measure, reduce. It's SPI-programmable, so it's a bench task, not a design-time commitment. Note that the datasheet's 4.5/5.3 ns figures are quoted at R_g = 1.6 Ω, which is *not* this gate network.

---

## 7. Current sensing

### 7.1 Refresher: the three topologies

| Topology | Pros | Cons |
|---|---|---|
| **Low-side shunt** | Ground-referenced, cheap, simple amplifier | Blind at very high duty cycle; measures leg current not phase current |
| **In-line phase** | True phase current at any duty | Needs high-common-mode or isolated amps; expensive |
| **High-side** | Sees bus current | Common mode at bus voltage |

Chose **three low-side shunts** into the DRV8323's integrated CSAs. Three rather than two: the third gives redundancy and a consistency check (`i_a + i_b + i_c = 0`) rather than requiring reconstruction.

### 7.2 The thing that actually determines whether it works

Not the filter. **Sample timing.**

Low-side shunt current is only valid while the low-side FET is on. During switching transients it's garbage. The fix is to sample at the **centre of the PWM period**, where all three low sides are on and the transients have settled:

```
Centre-aligned PWM → TIM1_TRGO2 at the counter peak → triggers ADC
```

The RC filter on the sense lines (56 Ω + 2.2 nF, f_c ≈ 1.29 MHz, τ ≈ 123 ns) is **edge damping and ADC input protection, not switching-noise rejection**. At 40 kHz it attenuates nothing. Its job is to be settled by the time the sample fires — 10τ ≈ 1.23 µs of margin.

> Filtering cannot substitute for correct sample timing. If your currents are noisy proportional to duty cycle, move the trigger; don't add capacitance.

### 7.3 Shunt and gain are one decision

```
Full scale = (V_ref / 2) / (G × R_shunt)

3 mΩ, G=20  →  ±27.5 A    ✓ selected
3 mΩ, G=40  →  ±13.75 A   ✗ below peak current
5 mΩ, G=20  →  ±16.5 A    ✗ only 1.17× over the 14.1 A peak
5 mΩ, G=10  →  ±33 A      — the earlier frozen value
```

Resolution at the shipped config: **~13.4 mA/LSB**. Dissipation: 0.3 W each at 10 A, 1.2 W at 20 A, in a 3 W part.

**Refresher — Kelvin sensing.** A 3 mΩ shunt develops 30 mV at 10 A. A few mΩ of trace or solder-joint resistance in the sense path is a large fraction of that. Kelvin (4-wire) connection taps the sense voltage at the resistor body itself, carrying no power current. Implemented here with net ties on the sense pads.

### 7.4 A retracted instruction worth recording

An action item carried forward for several revisions said: **change the shunts from 5 mΩ to 1 mΩ, critical.**

It was generated during a MOSFET-selection exercise at a **40 A RMS** operating point, where 5 mΩ would dissipate 8 W in a 3 W part. Entirely correct there.

At the frozen 10 A design point it's unnecessary and actively harmful — it throws away a factor of five in sense resolution for no thermal benefit.

> **An action item carried forward without its operating-point context is worse than no action item.** Every carried item should state the assumption it depends on.

### 7.5 Overcurrent protection: know what's actually protecting you

Two mechanisms exist on the DRV8323:

- **SEN_OCP** — threshold across the sense resistor. At 3 mΩ this implies a trip current in the hundreds of amps. **Unusable.**
- **VDS_OCP** — measures V_DS across the conducting FET.

```
VDS_LVL = I_trip × R_DS(on, hot)
        = 20 A × 6 mΩ = 120 mV
```

Even configured well, hardware OCP sits far above the working range (on the order of 80 A+ against ~10 A operation). The practical consequence:

> **In normal operation, firmware current limiting is the only real protection.** Hardware OCP is a catastrophe backstop — shorted phase, shorted FET — not a current limit. The firmware limit must be robust, because nothing underneath it will catch a 15 A overcurrent.

---

## 8. Power tree, and a scope decision

### 8.1 The cut that mattered most

Early revisions carried a full input-protection front end on the controller board: LM5069 hot-swap controller, back-to-back SOA-rated pass FETs, inrush limiting, UVLO/OVLO, current limit, latch-off.

**That was removed.** Input protection and hot-swap are delegated to a dedicated upstream **Power Distribution Board (PDB)**, shared across all six joints.

This is the right architectural call and it's worth stating why:

- Hot-swap protection is a **bus-level** function. Six copies of it is six times the mass and cost for a job that only needs doing once, at the point where the bus meets the battery.
- The hardest constraints (SOA-rated pass FETs, inrush energy into 500 µF, latch-reset access) get easier when there's one of them in an accessible place instead of six buried in limb segments.
- It removed roughly a dozen line items and a significant chunk of board area from every joint.

Alongside it, the board also runs **bench-powered** during lab work — which is the correct way to bring up a prototype anyway.

What stayed on-board: a local TVS clamp (SMCJ51CA). Local transient clamping is still a board-level responsibility.

### 8.2 The remaining power tree

```
+VPROT (36–56 V) → LMR36520 buck (400 kHz) → +5 V
                                            → TLV75733 LDO → +3V3
```

Two converters. Simple, and defensible: a single-stage 50 V → 3.3 V buck runs at a tiny duty cycle with poor transient behaviour, and the 5 V rail is needed anyway for the CAN transceiver and connector supply pins.

### 8.3 The pre-boot window

**Refresher on why this matters more than power-up ordering.** No sequence of rails coming up will destroy anything here. What sequencing actually buys you is the guarantee that **the gate driver is never live and armed while the MCU's PWM state is undefined**.

+VPROT is live for tens of milliseconds before the MCU boots. During that window:

```
REQUIRED: external 10 kΩ pulldowns on DRV_ENABLE, DRV_CAL,
          and all six INHx/INLx.
```

The driver's internal 100 kΩ pulldowns are too weak to rely on against flux residue, probing, or partial population. A floating CAL pin can put the amplifiers into calibration mode at power-up.

Also: `nFAULT` and `nSCS` pull-ups must go to the **main 3.3 V rail**, never to the driver's own generated DVDD — which dies whenever the driver is disabled, exactly when you most want to read the fault line.

### 8.4 Power-down ordering works in your favour

```
DRV8323 V_M UVLO ≈ 6 V
Buck operates down to a much lower input
```

On bus collapse, **gate drive dies before logic does**. That window is what lets the MCU log the fault and emit a CAN frame. Put fault reporting early in the brown-out handler and you get a free post-mortem.

### 8.5 An open finding: no separate analog rail

In the fabricated Rev 1, **VDDA, VREF+ and the DRV8323 VREF all sit on the raw +3V3 digital rail.**

**Refresher on why that's not ideal.** The ADC reference sets the absolute scale of every measurement. A 12-bit converter on a 3.3 V reference has 1 LSB = 806 µV. An LDO gives maybe 40 dB of rejection at 100 kHz and only 10–20 dB by 1 MHz, so switching ripple reaching the rail translates directly into reference wander — ~10 mV of ripple is ~12 LSB, more than the converter's own unadjusted error budget.

Rev 2 fix: ferrite bead plus local caps to create a separate `+3V3A` node.

Partial mitigation that already exists: **current sense is ratiometric** through the DRV8323's own VREF, so CSA gain error largely cancels. Bus voltage and temperature sensing are *not* ratiometric and inherit the LDO's absolute accuracy directly.

---

## 9. Communications

### 9.1 CAN-FD

Convergent choice across every comparable open-source design (ODrive, moteus). Deterministic multi-drop on a six-node bus, enough payload for command + telemetry, two-wire harness that suits a limb.

**Refresher — split termination.** Standard CAN termination is 120 Ω across the pair at each end of the bus. *Split* termination divides it into 2 × 60.4 Ω with a capacitor (47 nF here) from the midpoint to ground. The differential impedance is unchanged; the capacitor gives common-mode energy somewhere to go.

```
Common-mode path: 30.2 Ω × 47 nF → f_c ≈ 112 kHz
```

**Termination topology is a system-level property, not a board property:**

```
6 nodes, each with 120 Ω fitted  →  20 Ω bus  →  does not work
Correct: exactly 2 terminators, at the two PHYSICAL ends
```

So termination must be selectable per board while keeping every board identical. On this layout the split network (R45/R46/C68) sits clustered with **SW1**, a DPDT slide switch — a DPDT being exactly what you need to bring both lines into termination.

### 9.2 Oscillator tolerance — the constraint people miss

**Refresher.** CAN has no separate clock line. Receivers resynchronise on edges, and the tolerance budget has to accommodate *both* nodes' clock error. CAN-FD's data phase is faster and the budget is correspondingly tighter.

```
Ceramic resonator:  ±0.5%  = ±5000 ppm
Quartz crystal:     ±30 ppm typical
Ratio:              ~170×
```

A ceramic resonator is marginal for classical CAN and generally insufficient for CAN-FD data-phase bit timing. Swapped to quartz. Cost: about 35 cents and two load capacitors.

There was no competing constraint because native USB was dropped (see §10), so the crystal only serves the timer and CAN clock trees.

### 9.3 Node addressing — an idea that came and went

Six physically identical boards need to be distinguishable **without reflashing**, and a board swapped in the field should take on the identity of the joint it's installed in. So the ID must be in hardware.

**Approach 1 — binary-weighted resistor ladder into one ADC pin.** Four jumpers, 16 addresses, one pin instead of four GPIO.

```
V_node = 3.3 / (1 + n)      where n = binary sum of closed jumpers

code 0  → 3.300 V
code 1  → 1.650 V
code 7  → 0.413 V
code 15 → 0.206 V
```

Two engineering notes on this that are generally useful:

- **The response compresses at high codes.** Gap between codes 14 and 15 is ~13.75 mV. That forces 1% resistors, oversampling, and a boot-time-only read — all required, not optional.
- **Source impedance hits 100 kΩ at code 0**, which demands the maximum ADC sampling time. Fine, because it's read once before PWM is active, so switching noise is absent entirely.

The ladder was built from **parallel combinations of values already on the board** (2 × 100 kΩ = 50 kΩ for the 49.9 kΩ leg; 2 × 24.9 kΩ = 12.45 kΩ for the 12.4 kΩ leg) — a BoM consolidation trick that trades two extra placements for two whole line items, with a 0.2–0.4% shift that is invisible against 16-level quantisation.

> Worth recording: when I first reviewed this network I misread the parallel pairs as a broken ladder and flagged it as an error. It wasn't. **Parallel/series synthesis from existing values is a legitimate and underused consolidation technique**, and a reviewer who doesn't recognise the pattern will call it a mistake.

**Approach 2 — GPIO solder bridges.** Simpler, no analogue decode, at the cost of pins.

**What actually shipped: neither.** Rev 1 has no node addressing mechanism. It's a Rev 2 item. Noting it honestly because the design record spent real effort on a feature that didn't make the board.

---

## 10. Scope discipline: what got deleted

Roughly as much engineering went into removing things as adding them. The pattern worth extracting: **re-check why a part is there, not just whether it works.**

| Removed | Why it existed | Why it went |
|---|---|---|
| LM5069 hot-swap front end | Inrush, UVLO/OVLO, fault current limit | Bus-level function → moved to the PDB |
| USB-C + CH340X UART bridge | Config and console access | SWD/RTT does the same job with no extra silicon, no connector, and no boot-select pin conflict |
| Gate network diode (R + parallel D) | Asymmetric turn-on/turn-off | DRV8323 IDRIVEP/IDRIVEN does it internally |
| LED buffer MOSFETs | 5 V / 3.3 V level mismatch | Mismatch disappeared when LEDs moved to the 3V3 rail; 3.9 mA is well inside a 20 mA GPIO |
| Encoder UVW output | Commutation fallback | ABI retained; UVW added pins for a mode not used |
| Qwiic connector | Expansion | Lost to MCU pin constraints |
| Node ID resistor ladder | Hardware addressing | Deferred to Rev 2 |

Two of these — the gate diode and the LED buffers — were **not wrong when added**. They both outlived their justification. Neither would have been caught by "does this work?"; both were caught by "why is this here?"

---

## 11. Layout

### 11.1 Refresher: the three things that matter

**1. Commutation loop area.** The loop is `bulk cap → high-side FET → switch node → low-side FET → ground → back to cap`. Its inductance rings against the FETs' C_oss at every switching edge. Per the DPT result in §4, gate ringing gets dangerous before drain overshoot gets visible.

**2. Return current paths.** High-frequency return current does **not** take the shortest path — it takes the path of lowest impedance, which means it flows directly under the signal trace on the nearest plane. A slot or split in that plane forces it to detour, which increases loop area and radiates. This is why an unbroken plane beats a carefully-drawn split almost every time.

**3. Ground domain separation where the silicon asks for it.** The DRV8323 provides separate AGND (pin 32) and PGND (pin 40). Honouring that in copper — joined at **one star point at the shunts** — is mandatory. Merging them anywhere else injects CSA offset error, which corrupts current feedback and therefore torque control directly.

> These last two look contradictory until you see the distinction: **a split defined by the silicon at a defined star point is a different operation from a split the designer invented.** Don't slot a plane; do honour a device's documented ground pin separation.

### 11.2 What the fabricated board actually shows

Verified from the gerbers, drill files and IPC-356 netlist.

**Board:** 70.1 × 70.1 mm, 6 layer. Stackup `Sig/Pwr · GND · Sig/Pwr · Sig/Pwr · GND · Sig/Pwr`.

**What's right:**

- **L2 and L5 are perfect** — solid, unbroken ground planes across the whole board, nothing but via antipads. No splits, no routing, no slots. Under the power stage specifically.
- **High-side FET drains have 16 via-in-pad each** (4×4 grid, 0.25 mm) against the ≥9 specified.
- **Every thermal pad is windowpaned on the stencil** — 15 apertures on the FET drains, none over 3 mm². This is the difference between a flat joint and a floating part.
- **Power in and phases out share one board edge**, immediately adjacent to the FET row.
- **Single-point chassis bond implemented correctly**: four mounting holes each with a 0 Ω and a 1 nF/1 kV footprint; only **one** 0 Ω populated, three 1 nF fitted. One DC bond defines chassis potential; a second would create a ground loop through the cable shields.

**The one real finding:**

```
High-side FETs (Q3/Q5/Q7):  16 thermal vias each → inner-layer spreading
Low-side FETs  (Q4/Q6/Q8):   0 vias
Switch nodes OUT_A/B/C:      0 vias anywhere
```

Keeping the switch nodes entirely on L1 is a **defensible EMI choice** — no switching copper on inner layers, no via stubs on the noisiest nets. But it means the low-side devices dissipate into roughly 80–100 mm² of top copper, against the ~600 mm² the 50 °C/W datasheet figure assumes.

Revised estimate (R_thJA ≈ 75 °C/W, scaled — needs bench verification):

| Phase current | P per FET | T_j estimated | Earlier claim |
|---|---|---|---|
| 10 A | 0.42 W | **72 °C** ✓ | 61 °C |
| 20 A | 1.44 W | **148 °C** | 112 °C |

**At 10 A this is fine. The 20 A claim does not survive the as-built thermal path** — margin to the 175 °C limit drops from ~63 °C to ~27 °C, before counting the shunt's 1.2 W right next to it. Treat 10 A as the rating until measured.

**Other findings:**

- **Board NTC sits at board centre** — 22 mm from the FET array, directly above the encoder whose self-heating it partly reads. It's the coolest point on the board. A calibration problem rather than a defect: characterise the offset against a FET-case thermocouple and bake it into the trip threshold.
- **No fiducials on the top layer.** Finest pitch is 0.5 mm (DRV8323 WQFN-40, STM32 LQFP64). Assembly houses normally add panel fiducials, which is usually adequate at that pitch, but locals are standard practice.
- **No reference designators on silkscreen** — functional labels only. Fine for machine assembly, awkward for hand rework, and it matters more for a board other people will build.

### 11.3 On bulk capacitor placement, and a number worth checking before "fixing" it

Two of the bulk capacitors sit 20–45 mm from the furthest half-bridge. That looks alarming until you check the frequency:

```
At 40 kHz:  X_L of 40 nH ≈ 10 mΩ
            Capacitor ESR ≈ 35 mΩ
```

The interconnect inductance barely affects ripple sharing. The **high-frequency commutation loop is closed by the MLCCs 6 mm from the FETs**, not by the bulk bank. The placement is correct.

Recording it because it's exactly the kind of thing a later revision "fixes" by someone who didn't run the numbers.

### 11.4 Bulk capacitance: sized by ripple current, not capacitance

**Refresher.** The DC link capacitor's job in an inverter isn't primarily energy storage — it's supplying the high-frequency component of inverter current so the battery and its wiring don't have to. The binding spec is usually **RMS ripple current capability**, which is a thermal limit (self-heating via ESR), and which scales with the can's surface area.

```
Capacitance requirement:      met by 3 pieces (~322 µF effective)
Ripple current requirement:   ~7.8 A
  3 × polymer → 7.5 A capacity  → ~96%, overloaded
  5 × polymer → 12.5 A          → the minimum defensible count
```

The design was frozen at five. **Three were built.** A longevity issue rather than a bring-up one — running at or above the ripple rating shortens life through self-heating rather than failing immediately. Measure actual ripple per capacitor before any production run.

Also worth knowing: **MLCC effective capacitance collapses under DC bias.** A 4.7 µF X7R at 50 V may deliver ~40% of nameplate. The MLCC bank here contributes only ~7–10% of ripple current after derating — its job is **ESL reduction at the half-bridge inputs**, and it must not be counted toward reducing the polymer count.

---

## 12. Manufacturing notes

### 12.1 Via-in-pad — the item most worth checking

Each high-side FET drain has **16 open 0.25 mm vias inside a 4.41 × 3.73 mm solder pad**, with a single mask opening covering the whole pad.

**Refresher on why that's a problem.** During reflow, molten solder wicks down open via barrels by capillary action. Consequences in order of severity:

1. **Voiding under the thermal pad** — destroying the exact thermal path the vias exist to create
2. Solder balls on the bottom side
3. Component tilt or opens as solder depletes unevenly

The fix is a fab option, not a gerber change: **resin-plugged and copper-capped via-in-pad (POFV)**. Verify it was ordered. If not, X-ray a first article at the FET pads before powering anything.

### 12.2 Things gerbers don't tell you

- **Copper weight is an order parameter.** Nothing in a gerber records it. Every thermal and current figure assumes 2 oz outer; at 1 oz the phase conductors carry roughly half the current for the same rise.
- **L1↔L2 dielectric thickness** sets the return-path loop area for every switching edge on the top layer. Worth confirming rather than assuming.

### 12.3 Via geometry

Used 0.25 mm drill on 0.55 mm pad = **0.15 mm annular ring**. JLCPCB advises ≥0.15 mm to mitigate drill breakout — so exactly on the line, with no margin for registration error on a 6-layer lamination. 0.3/0.6 mm costs nothing and buys the margin back.

### 12.4 BoM consolidation techniques

Done **once the design was stable**, never during. Early consolidation biases component choices for the wrong reason.

| Technique | Example |
|---|---|
| Merge duplicate rows | Same part number split across two BoM rows |
| Parallel synthesis | 49.9 kΩ from 2 × 100 kΩ already on the board |
| Series synthesis | 37.3 kΩ from two existing values — which also fixed a working-voltage violation |
| Footprint substitution | Zero-ohm links moved to a size already in use |
| Dielectric upgrade | X5R → X7R (X5R is only characterised to 85 °C — a real derating risk next to a six-FET bridge) |

Equally important, what was **declined**: trip-point dividers (synthesis lands 2.5% off, directly on a threshold), USB-C CC pull-downs (value mandated by spec), gate resistors (value set by dv/dt work, not economics), and high-voltage divider legs kept as series pairs specifically so no single 0402 exceeds its ~50 V working-voltage limit.

> **Consolidation stops where the reason the part was chosen begins.**

### 12.5 A consequence that must propagate

Two accepted changes altered divider ratios, which changes **firmware scaling constants**. The bus-sense lower leg moved from 2.2 kΩ to 2 kΩ.

This is exactly the class of change made for BoM reasons that silently breaks a calibration constant nobody re-derived. Recalibrate against a measured bus voltage at bring-up — 1% resistor tolerance alone gives ~32 LSB of absolute error.

---

## 13. Firmware constraints baked into the hardware

Three that will cost days if discovered at bring-up rather than read here first.

### 13.1 UCPD dead-battery pulldowns

PB6 and PB4 carry internal 5.1 kΩ pulldowns associated with the USB-C controller. Those pulldowns are **enabled by a high level on PA9/PA10** — which on this board are two of the high-side PWM outputs.

```
Consequence: starting TIM1 pulls down a UART line and an LED line.
REQUIRED:    set PWR_CR3.UCPD1_DBDIS = 1 BEFORE enabling TIM1.
```

Symptom if you miss it: an LED that glows faintly and permanently once the motor timer starts.

This one was found, fixed by pin reassignment, and then **reappeared after a later pin shuffle** — which is the argument for putting constraints on the schematic rather than in a changelog.

### 13.2 ADC channel pairing

```
FILTER_SOA → PB11 (ADC1 and ADC2 — shared)
FILTER_SOB → PB12 (ADC1 only)
FILTER_SOC → PB14 (ADC1 only)
```

Dual-simultaneous sampling must always pair SOA on ADC2 with SOB *or* SOC on ADC1. **Phases B and C can never be sampled together.** Reconstruct the third from `i_a + i_b + i_c = 0`.

Permanent, and created by a layout-convenience pin assignment. Worth documenting now rather than discovering during commissioning.

### 13.3 Timer break input

`DRV_nFAULT` lands on PA15 = TIM1_BKIN. Configure it as a **timer break input**, not an EXTI.

**Refresher:** break gives hardware output disable, independent of interrupt latency — the timer drops the outputs in silicon. An EXTI handler is at the mercy of whatever else is running. For a leg joint, automatic output enable (AOE) should be **off**: require an explicit re-arm after a fault.

---

## 14. Safety architecture

### 14.1 Fault state is coast, not brake

**Refresher on why.** Shorting all three low sides brakes the motor by dissipating back-EMF in the phase resistance:

```
At speed: ~19 V back-EMF into ~100 mΩ phase resistance
        ≈ 180 A
```

That exceeds both device and motor ratings. Braking by shorting **must** be current-limited and PWM-modulated, which requires firmware to be alive — so it cannot serve as a hardware backstop.

Fault state is therefore high-impedance: the limb free-falls. If uncontrolled drop is a hazard, that needs a mechanical fail-safe brake, which is outside this board.

### 14.2 Two mechanisms, two timescales

Every open-source reference surveyed (ODrive, moteus, ODRI, OpenPodcar) kept a physical stop independent of the compute path. None used a software stop as the sole mechanism.

The reason is precise: **a level signal tells the board what the controller wants right now, but has no opinion about whether the controller is still alive.** That's the gap a heartbeat closes, and the gap a physical contactor closes when the heartbeat itself can't be trusted.

```
t=0      Signal-level disable → inverter safe in microseconds
t≈500ms  Contactor opens → power removed
```

The 500 ms gap gives every node time to emit a CAN fault frame.

**A tempting wrong answer worth naming:** wiring the e-stop into a hot-swap controller's UVLO pin. It's the pin manufacturers advertise for remote shutdown, and it's wrong here — it removes bus power instantly, dropping the motor to coast in the worst possible way and killing the MCU before it can report anything.

Rev 1 has a 2-pin e-stop connector with proper conditioning (1 kΩ series, RC filter, clamp) routed to a hardware break path. **Verify empirically that an unplugged cable leaves the driver disabled** — that's the fail-safe property, and it's the kind of polarity question that gets flipped for bench convenience and then forgotten.

---

## 15. Bring-up plan

Not yet executed. Staged so each step gates the next.

```
0. Inspect      X-ray a FET drain for wicking voids. Confirm 2 oz copper.
                Visual: FET orientation, cap polarity, connector pin 1.
                Continuity: bus+ to bus− is not a short.

1. Dead board   Current-limited bench supply, 24 V @ 100 mA. NOT a battery.
                Rails: +5 V, +3V3. Draw settles < 50 mA.
                SWD connects, correct device ID.
                E-STOP UNPLUGGED → confirm driver disabled. Record it.

2. Gate driver  UCPD_DBDIS first. Then enable, wait t_WAKE 1 ms.
                SPI read-back of every register you write — never assume.
                CSA offset calibration, motor disconnected.
                Scope one gate pair DIFFERENTIALLY at low duty.

3. IDRIVE sweep BEFORE any high current. 0 Ω gate resistors mean IDRIVE is
                the only slew knob — find the setting before loading it.

4. Double pulse Characterise V_DS overshoot and V_GS undershoot for real.
                This is the measurement the removed snubber owes.

5. Encoder      Field strength in range. Monotonic sweep, one wrap per rev.
                Two wraps = magnet diametric misalignment (mechanical).
                Zero parity errors over thousands of reads.

6. First motion Open-loop current at fixed angle (~1 A) → rotor aligns.
                Confirm i_a + i_b + i_c ≈ 0.
                Encoder-to-phase alignment, repeatable across runs.
                Closed-loop torque at low i_q.

7. Characterise Low-side FET case temp at 10 A — NOT high-side.
                R37 offset vs that thermocouple → NTC calibration constant.
                Encoder angle vs i_q → current-correlated error check.
                Ripple current on one bulk cap.
```

### Measurement technique notes

**Probing.** Use a ground spring, not the alligator lead, for anything above 1 MHz. A 15 cm ground lead adds ~150 nH, which rings with the probe capacitance and produces overshoot *on the screen* that doesn't exist on the board. That will send you hunting a snubber problem you don't have.

**Never ground-reference a high-side gate measurement.** GHx is referenced to SHx, which swings the full bus. Measure V_GS differentially or you'll read the switch node and conclude the gate drive is broken.

**Thermal.** Thermocouple placement plus IR camera with emissivity correction (bare copper and solder mask have wildly different emissivity — IR without correction reads nonsense on a PCB). For R_thJA extraction, the standard method uses **R_DS(on) as the temperature sensor** per JESD51-1: calibrate resistance against temperature in an oven, then infer junction temperature from measured resistance under load. Also watch shunt TCR drift — the current reading itself moves with temperature.

**Encoder angle vs current.** Phase conductors pass ~22 mm from the sensor:

```
B = µ₀I / 2πr = (4π×10⁻⁷ × 10) / (2π × 0.022) ≈ 91 µT ≈ 0.9 gauss
```

Against a 300–700 gauss working field that's 0.15–0.3%, i.e. ~0.1–0.2° of angle error. Small — but **current-dependent and therefore torque-correlated**, so it appears as torque ripple rather than random noise. Compensable in firmware with a current-proportional offset term if it shows up.

---

## 16. Rev 2 list

| Priority | Change | Driver |
|---|---|---|
| 1 | Thermal vias in low-side drain pads, or a bottom-side switch-node pour | §11.2 — the only finding with a real performance consequence |
| 2 | Move the board NTC into the FET zone, or add a second one there | §11.2 — you can't control a temperature measured 22 mm away |
| 3 | Separate `+3V3A` via ferrite + local caps for VDDA/VREF+ | §8.5 |
| 4 | Bulk back to 5 pieces, or a lower-ESR part | §11.4 |
| 5 | Hardware CAN node addressing | §9.3 — never shipped |
| 6 | DNP drain-side snubber footprints | §6.3 — insurance the current board lacks |
| 7 | Fiducials (3 global + locals on the fine-pitch parts) | §11.2 |
| 8 | Reference designators on silkscreen | §11.2 — matters for an open board |
| 9 | Vias to 0.3/0.6 mm | §12.3 |
| 10 | Resolve the TVS clamp vs 65 V abs-max question | Carried open |

---

## 17. Lessons

Generalisable, in rough order of how much they cost to learn.

**Select on the metric that binds, not the metric that's famous.** R_DS(on) is what every MOSFET is marketed on and it was the wrong parameter here. Identifying which constraint actually binds *is* the first-principles stage.

**When you re-derive a number and disagree, check whether you changed the model.** The charge-pump correction in §6.2 was my own error, from counting six gates where the charge pump drives three. A factor-of-two disagreement is usually a definition disagreement.

**An action item without its operating point is a hazard.** The 1 mΩ shunt instruction was right at 40 A and harmful at 10 A. Carried items should state the assumption they depend on.

**Check the note against the symbol.** A gate driver ordering code was wrong in written guidance for several revisions while the schematic symbol was correct throughout. Any fact stored in two places will eventually disagree in two places.

**When the reason for a part evaporates, delete the part.** The gate diode and the LED buffers were both correct when added and both outlived their justification. "Why is this here?" is a different review pass from "does this work?", and worth running explicitly.

**Removing a component is not the same as sizing it.** Deleting the snubber closed a requirement by deletion rather than analysis. That converts a sizing task into a validation task — requirements closed by removal deserve *more* scrutiny, not less.

**Over-provisioning is a cost, not free margin.** Six oversized packages for a stage dissipating under a watt is board area bought to solve a problem that doesn't exist — and on a limb, board area is mass. Margin that costs the primary system constraint is a defect wearing a reassuring disguise.

**The failure that gets you is the connector, not the silicon.** The highest-rated risk in this design was never a semiconductor at 1.2× voltage margin. It was a synchronous serial bus running over an unshielded cable through a moving joint. (Which is why the encoder came back on-board.)

**A number picked by judgement will acquire a derivation.** 40 kHz was chosen because it's inaudible. The pole-pair math came later and is a fine sanity check — but three revisions on, nobody remembers which constraint is real. Write down *why* at the moment you choose, not afterwards.

---

## Appendix: references worth reading

**Gate drive and power stage**
- TI SLVSDJ3D — DRV8323 datasheet (charge-pump equation, generator mode §10.1, layout §12.2.1)
- TI SLVA714 — understanding IDRIVE and TDRIVE
- TI SLVAF66 — motor driver system design; brake vs coast topology
- Infineon OptiMOS 6 / ISC030N10NM6 datasheet

**MCU**
- ST DS12589 — STM32G431 datasheet (I/O structure table; the UCPD dead-battery note)
- ST RM0440 — reference manual (PWR_CR3, timer break, ADC dual injected mode)
- ST AN2867 — oscillator design guide (crystal CL and gain margin)
- ST AN4013 — timer overview (complementary PWM, dead time, break)
- ST AN2834 — getting the best ADC accuracy, including a PCB layout section

**Layout and EMC**
- Henry Ott, *Electromagnetic Compatibility Engineering* — return current paths, mixed-signal layout
- Analog Devices MT-031 — grounding data converters, and the case against splitting planes
- Rick Hartley, *How to Achieve Proper Grounding* — why plane cuts cause more problems than they solve

**Control theory**
- TI BPRA048 — Clarke and Park transforms
- SimpleFOC documentation — FOC theory section, and a practical bring-up reference

**Reference designs**
- ODrive (ODriveHardware, ODrive S1) — closest architectural match
- mjbots moteus — Apache-licensed full KiCad source, CAN-FD servo across several revisions
- ODRI (Open Dynamic Robot Initiative) — distributed actuator architecture, e-stop in the power board

**Standards**
- ISO 11898 — CAN bit timing and oscillator tolerance budget
- IEC 60204-1 — stop categories
- IEC 61800-5-2 — safe torque off terminology
- JESD51-1 — thermal test method (R_DS(on) as temperature sensor)
