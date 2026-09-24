# FOC Motor Controller Rev 1 — Layout & Manufacturing Review

**Reviewed from the fab package, not the schematic:** gerbers (6 layers), PTH/NPTH drill, IPC-356 netlist, BoM, and pick-and-place.
**Board is design-frozen and at fab.** Everything below is sorted by whether you can still act on it.

---

## 0. Headline

This is a good board. The layout does the things that actually matter for a 60 V inverter: both inner ground planes are solid and completely unbroken, the high-side FET drains have proper 4×4 via-in-pad fields, the stencil is windowpaned on every thermal pad, and power-in and phase-out share one board edge right next to the power stage.

More importantly, **the single biggest risk flagged in DDR-001 has been closed**: the encoder is back on the board, at (40.00, 40.00) — the exact geometric centre. That eliminates the unshielded SPI-over-moving-cable failure mode that the design record called "the most likely source of intermittent field failures in this design."

There is **one item that may still be actionable at the fab**, because it is an order option rather than a gerber change. It is in §1 and it is worth a phone call.

---

## 1. Still actionable — fab order options, not file changes

### 1.1 ⚠ Via-in-pad plugging on the high-side FET drains — URGENT

Each high-side FET (Q3, Q5, Q7) has **16 vias, 0.25 mm drill, inside its drain pad**. The top solder mask has a **single 4.41 × 3.73 mm opening** covering the whole pad, so those vias are open plated-through holes sitting in the middle of a solder joint.

```
Per high-side FET:   16 × Ø0.25 mm via, 0.55 mm pad
Drain pad:           4.41 × 3.73 mm = 16.4 mm², one mask opening
Total affected:      48 open vias in 3 solder pads
```

If the order was placed without **resin-plugged and copper-capped via-in-pad** (POFV), then during reflow solder wicks down all 48 barrels by capillary action. The consequences, in order of how much they hurt:

1. **Voiding under the thermal pad** — which destroys the exact thermal path the vias were placed to create. You lose the benefit and keep the cost.
2. **Solder balls on the bottom side**, under a board that mounts against a chassis face.
3. **Component tilt / open pins** on a 5×6 package as solder is depleted unevenly.

**Do this now:** check the order. If via-in-pad plugging was not selected, contact JLCPCB before the board enters plating. This is a process option, so it may be changeable without a new upload. If it has already gone past that point, plan on X-raying the first article at the FET pads before you power anything.

If it cannot be changed: the boards are still usable at the 10 A design point, but treat the thermal numbers as unverified and inspect the joints.

### 1.2 Confirm the copper weight

Every thermal and current-capacity number in DDR-001 assumes **2 oz outer copper**. Nothing in a gerber records copper weight — it is purely an order parameter, and 1 oz is the default.

At 1 oz, your phase conductors carry roughly half the current for the same temperature rise, and the low-side FET thermal path (§2.1) gets materially worse. Verify the order line item says 2 oz outer.

### 1.3 Confirm the stackup

Six layers, L2 and L5 as ground. What matters for the power stage is the **L1↔L2 dielectric thickness** — that spacing sets the return-path loop area for every switching edge on the top layer. JLCPCB's default 6-layer buildup is normally thin between L1 and L2, which is what you want, but it is worth confirming rather than assuming, since it is the one stackup parameter that directly affects the commutation loop.

### 1.4 Via geometry is at, not inside, the recommended minimum

You used 0.25 mm drill on a 0.55 mm pad — a **0.15 mm annular ring**. <cite index="5-1">JLCPCB advises an annular ring of at least 0.15 mm to mitigate drill breakout during fabrication</cite>, so you are exactly on the line rather than inside it. <cite index="1-1">Their capabilities page gives a preferred minimum via hole of 0.2 mm with the via diameter 0.15 mm larger</cite>.

Not a problem, but no margin for registration error on a 6-layer lamination. For Rev 2, 0.3 mm / 0.6 mm costs nothing and buys back the margin.

---

## 2. Findings you cannot change — manage these at bring-up

### 2.1 ⚠ The low-side FETs have no vertical thermal path

This is the most consequential layout finding.

```
Q3, Q5, Q7 (high-side):  16 × +VPROT via-in-pad each → inner-layer spreading
Q4, Q6, Q8 (low-side):    0 vias
Switch nodes OUT_A/B/C:   0 vias anywhere on the board
```

Keeping the switch nodes entirely on L1 is a **deliberate and defensible EMI choice** — no switching copper on inner layers, no via stubs on the noisiest nets. But it means the low-side devices dissipate only into top-layer copper, while the high-side devices get a via field into a plane.

Measured copper in each phase zone (L1, region x±7 mm, y 58.5–71.5):

```
Phase C zone: 140.6 mm² total copper
Phase B zone: 149.0 mm²
Phase A zone: 159.1 mm²
```

That total is shared between the +VPROT pour, the switch-node pour, and the phase-output run — so the low-side drain sees perhaps 80–100 mm², not the 600 mm² (6 cm²) the datasheet's 50 °C/W figure assumes, and not the ≥200 mm² per device DDR-001 §11.1 specified.

**Revised estimate for the low-side devices** (R_thJA ≈ 75 °C/W, estimated by scaling — verify on the bench):

| Phase current | P per FET | ΔT (75 °C/W) | T_j at 40 °C | DDR-001 claimed |
|---|---|---|---|---|
| 10 A (design) | 0.42 W | 32 °C | **72 °C** ✓ | 61 °C |
| 20 A (stress) | 1.44 W | 108 °C | **148 °C** | 112 °C |

**At the 10 A design point this is completely fine.** The 20 A stress claim in DDR-001 does not survive the as-built low-side thermal path — margin to the 175 °C limit drops from ~63 °C to ~27 °C, before you account for the shunt dissipating another 1.2 W right next to it.

**Action:** treat 10 A as the rated figure, and thermally characterise the **low-side** devices specifically at bring-up. Do not assume the high-side measurement represents the leg. Update DDR-001 §5 to record the asymmetry.

### 2.2 ⚠ Bulk capacitance dropped from 5 pieces to 3

```
BoM line: C34, C37, C39 — 3 × 100 µF / 100 V (C42371899)
DFD-001 froze:            5 pieces
```

C41 and C42 were reassigned to other components (1 µF and 2n2 respectively), so this is a real reduction, not a renumbering.

The earlier sizing work concluded piece count is set by **ripple-current capacity and can surface area**, not by capacitance, and that three pieces sits at roughly 96 % of the required ripple current — i.e. **overloaded**, on a 2000-hour part. Five was called the minimum defensible count.

Running an aluminium-polymer capacitor at or above its ripple rating does not fail immediately; it shortens life through self-heating. So this is a longevity issue, not a bring-up issue.

**Action:** measure actual ripple current per capacitor at your real operating point before committing to a production run. The 7.8 A figure was derived at 10 A/phase with assumptions about modulation and duty; the real number may be lower. If it holds, Rev 2 goes back to five, or to a lower-ESR part.

### 2.3 The board NTC sits at the coolest point on the board

```
R37 (10 k NTC):  (39.00, 40.25)  — board centre
FET array:       y ≈ 62.5        — 22 mm away
U1 (AS5047P):    (40.00, 40.00)  — directly underneath
```

The sheet-11 note in the annotation guide asked for the NTC to be "in the thermally interesting zone — near the FET array or the hottest expected region — NOT in a cool corner where it will read low and give false confidence." It ended up at board centre, which is about as far from the power stage as it is possible to get on this board.

It will also partly read the encoder IC's self-heating, which is a constant offset unrelated to inverter load.

**Action:** this is a calibration problem, not a defect. Characterise the offset between R37 and an actual FET-case thermocouple across load, and put that delta into the firmware's over-temperature threshold. Write the measured offset into the design record so the number doesn't get lost.

### 2.4 Encoder at board centre — verify angle error against phase current

Putting the AS5047P at the exact board centre is the right call and closes the biggest risk in DDR-001. There is one second-order effect worth measuring.

The phase conductors carry up to 10 A RMS and run ~22 mm from the sensor die. A straight conductor produces:

```
B = µ₀·I / (2πr) = (4π×10⁻⁷ × 10) / (2π × 0.022) ≈ 91 µT ≈ 0.9 gauss
```

Against a typical AS5047P working field of 300–700 gauss, that is roughly 0.15–0.3 % — an angle error on the order of 0.1–0.2°. Small, but it is **current-dependent and therefore torque-correlated**, which in an FOC loop shows up as torque ripple and a small efficiency loss rather than as random noise.

**Action:** at bring-up, log encoder angle against a known mechanical reference while sweeping Iq at fixed rotor position. If the error correlates with current, it is compensable in firmware with a simple current-proportional offset term. Cheap to check, annoying to diagnose later.

### 2.5 No fiducials on the top layer

Searched the top mask for isolated round openings 1.5–4 mm with no drill nearby: **zero found**. The bottom has four clustered openings that are DNP component pads, not fiducials.

Your finest pitch is 0.5 mm (DRV8323 WQFN-40 and STM32 LQFP64). JLCPCB will normally place their own fiducials on the panel rails, which is usually adequate at 0.5 mm pitch, so this is unlikely to cause a failure on this run. But local fiducials next to the two fine-pitch parts are standard practice and cost nothing.

**Rev 2:** three global fiducials plus locals on U5 and U6.

### 2.6 No reference designators on the silkscreen

The silkscreen carries **functional** labels — and does it well (see §3). What it does not carry is `R47`, `C25`, `U6`-style designators. That is fine for machine assembly, which uses the position file, but it makes hand rework and bench debugging harder: you cannot look at the physical board and identify a part without the fab drawing open beside you.

For a board you intend to open-source, where other people will hand-assemble and probe it, this matters more than usual.

**Rev 2:** designators on silk at 0.5–0.6 mm where space allows, at minimum on the ICs, connectors, and anything you expect to swap.

### 2.7 Verify the E-stop polarity is fail-safe

The e-stop input is well built. `DRV_ENABLE` reaches J11 at (70.50, 19.00) through a proper conditioning network:

```
R41 (1 k)    series limiting at (65.00, 19.50)
C42 (2n2)    filter at (66.50, 19.00)
DZ3          clamp at (66.00, 25.50)
R19 (100 k)  pulldown near the driver at (28.75, 29.75)
```

Series resistance also means the external switch and the MCU GPIO cannot fight each other destructively if both drive the net — which was the failure mode I would otherwise have flagged.

**The one thing to confirm on the bench:** with the e-stop cable **unplugged**, does the driver end up disabled? The 100 k pulldown suggests yes (open = disabled = fail-safe), which is the correct behaviour. But the project record notes a polarity flip made at some point for bench convenience, which would make a cut cable read as "run". Verify empirically, and write the answer into DDR-001 D-19 — this is a safety property, not a detail.

### 2.8 Small things

- **CAN termination:** R45/R46 (60R4) are fitted but J2 (the select header) is DNP, so boards ship unterminated. Correct default for a 6-node bus. Just make sure you can actually enable it on the two end nodes — solder a header or bridge the pads.
- **SWD header J7 is DNP.** You will need to hand-solder one for bring-up. The pin-by-pin silkscreen makes this painless.
- **LED3 and LED4 are both silkscreened "MCU".** Cosmetic, but give them distinct labels in Rev 2.
- **`DZ1` is absent from the BoM.** If that was the bus-sense clamp, the VBAT_SENSE node now has no zener backstop. At 65 V bus the divider (24.9k + 12.4k / 2k) outputs ~3.31 V against a 3.3 V rail — the MCU's internal clamp will handle the microamps through a ~1.9 kΩ source, but confirm this was intentional.
- **Designator gaps** (LED2, and several R/C numbers) are from parts removed during the redesign. Harmless, but a reviewer will ask.

---

## 3. What's notably good

Worth recording, because a review that only lists problems gives a false impression.

**L2 and L5 are perfect.** Solid, unbroken ground planes across the entire board with nothing but via antipads — no splits, no slots, no routing. Under the power stage specifically, which is where DDR-001 §11.2 said it mattered most. This is the single most important thing to get right on a board like this and it is right.

**High-side via-in-pad is generous.** 16 vias per drain against the ≥9 specified. Assuming §1.1 gets resolved, the high-side thermal path is better than the design record assumed.

**Every thermal pad is windowpaned.** FET drains: 15 apertures, none larger than 3 mm². DRV8323 and STM32 pads likewise. This is the difference between a flat joint and a floating part, and it is easy to forget.

**The encoder decision was reversed correctly.** On-board, dead centre, coaxial. This closes the highest-rated risk in the entire design record, and the AUX connector (J6, 7-pin GH with 100 R series damping) is retained so an external encoder is still an option.

**Single-point chassis bond, implemented exactly as intended.** Four mounting holes each have a 0 Ω and a 1 nF/1 kV footprint. In the BoM: only **R58** is populated; R56, R57, R59 are DNP; all four capacitors fitted. One DC bond defines chassis potential, three HF-only couplings, no ground loop through the harness. This was the ambiguity flagged in the sheet-15 annotation and it was resolved the right way.

**Package downsize.** ISC030N10NM6 in PG-TDSON-8 (5×6 mm) rather than TOLL. DDR-001 D-06 flagged six TOLL packages as ~700 mm² of board bought for a stage dissipating under a watt — "margin that costs the primary system constraint." That got fixed. Board came in at **70.1 × 70.1 mm**, inside the 80 × 80 ceiling.

**Slew-control insurance is in place.** The gate-source RC networks (R23/R24/R28/R29/R33/R34 + C35/C36/C45/C46/C56/C57) are all **DNP with footprints reserved**. So you ship with pure IDRIVE control and can add damping after you see real waveforms, without a respin. That is precisely the recommendation from the annotation guide.

> **This also corrects a concern I raised earlier.** In the sheet annotations I calculated that the 2n2 gate-source caps would add 22 nC per device to the charge-pump budget, cutting margin to 1.35×. As built they are unpopulated, so the budget is back to the DDR-001 figure: **6 × 55 nC × 40 kHz = 13.2 mA against 25 mA, 1.9× margin.** If you later populate those caps to tame ringing, the budget tightens and you should re-check it at your final f_sw.

**Silkscreen is genuinely well done.** Title block populated (board name, Rev 01, date, your name), phase A/B/C labelled at the terminals, bulk cap polarity marked, power +/− marked, and the SWD header labelled pin-by-pin (3V3 / NRST / SWCLK / SWDIO / GND). Every connector named by function: I2C, UART, CAN ×2, MOTOR TEMP, ESTOP, AS5047 (AUX), 10k NTC. Someone picking this board up cold can find their way around it. This is the part of the schematic package that was weakest at review time and it is now the strongest part of the physical board.

**38 test points.** Good DFT coverage for a board this size.

**Power topology is clean.** Power in at (54, 71) and (63, 71), phases out at (18.5, 71), (30.0, 71), (41.5, 71) — all on the top edge, immediately adjacent to the FET row at y ≈ 62.5, with the bulk bank at x = 57–68 in between. Short, wide, and no power current crossing the signal side of the board.

**On bulk capacitor distance:** C34 and C37 sit 20–45 mm from the phase-C half-bridge, which looks alarming until you check the frequency. At 40 kHz, 40 nH of interconnect is about 10 mΩ of reactance against ~35 mΩ of capacitor ESR — so it barely affects ripple sharing. The high-frequency commutation loop is closed by the nine 4.7 µF MLCCs at y = 56.25, which are 6 mm from the FETs. **The placement is correct and the layout gets this right**; I am recording it because it is the kind of thing that gets "fixed" in a later revision by someone who didn't check the numbers.

---

## 4. Rev 2 list

Ordered by value.

| # | Change | Why |
|---|---|---|
| 1 | Thermal vias in the low-side drain pads, or a bottom-side switch-node pour | §2.1 — the only finding with a real performance consequence |
| 2 | Move R37 (NTC) into the FET zone, or add a second NTC there | §2.3 — you cannot control a temperature you measure 22 mm away |
| 3 | Bulk back to 5 pieces, or a higher-ripple part | §2.2 — capacitor longevity |
| 4 | Fiducials: 3 global + locals on U5/U6 | §2.5 |
| 5 | Reference designators on silkscreen | §2.6 — matters for an open-source board |
| 6 | Vias to 0.3 mm / 0.6 mm | §1.4 — free registration margin |
| 7 | Resolve DDR-001 blockers B1 (TVS clamp above two 65 V abs-max ICs) and B3 (generator mode) | Carried forward, still open |
| 8 | Distinct LED labels; close the designator gaps | Cosmetic |

---

## 5. Updates to make in DDR-001

The design record is now behind the hardware. To keep it useful:

- **D-21 (off-board encoder):** status changes from CONFIRMED-but-flagged to **REVERSED**. Record why, and record the new second-order risk (§2.4) in its place. This is the most interesting entry in the whole document now — a flagged risk that got designed out.
- **D-06 (MOSFET package):** the TOLL over-provisioning trade-off was resolved in favour of the 5×6 package. Mark it closed and note the resulting board size.
- **§5 thermal tables:** add the high-side / low-side asymmetry. The single "P per FET → T_j" table no longer describes the board.
- **D-08 (bulk capacitance):** frozen at 5, built at 3. Record the deviation and the ripple-current consequence rather than silently editing the number.
- **D-19 (safety):** an e-stop input now exists in hardware. Update, and add the measured fail-safe polarity once verified.
- **D-31 / §14 B1:** the buck is LMR36520 at **65 V** absolute maximum, not the 80 V part the document names. The TVS clamps at 82.4 V, so it now exceeds the absolute maximum of two ICs rather than one. B1 got worse, not better.
- **§13 Corrections:** add an entry for the charge-pump budget — the 2n2 gate-source cap concern was raised, then rendered moot by those caps shipping DNP. That is the same pattern as the 1N4148 gate diode: a concern that evaporated when its premise changed.

---

## 6. Bring-up sequence given the above

1. **Inspect before powering.** X-ray or cross-section one board at a high-side FET drain to check for wicking voids (§1.1). Verify copper weight against the order.
2. **Power the logic only**, driver disabled. Confirm rails, confirm the e-stop polarity is fail-safe with the cable unplugged (§2.7).
3. **Encoder characterisation, no motor current.** Baseline angle accuracy.
4. **Low current, motor spinning.** Sweep Iq at fixed rotor position and check for current-correlated angle error (§2.4).
5. **Thermal run at 10 A.** Thermocouple on a **low-side** FET case and on R37 simultaneously. Record the delta — that is your NTC calibration constant (§2.1, §2.3).
6. **Ripple current on one bulk capacitor** with a current probe, at the real operating point (§2.2).
7. Only then push toward 20 A, and stop at whatever the low-side thermal measurement says rather than at the number in the design document.
