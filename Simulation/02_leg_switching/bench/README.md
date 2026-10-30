# 02_leg_switching / bench

Bench correlation for deck 02, 2026-10-30. **Run at 12 V, not 30 V:** every approved switching scope in Firmware/CLAUDE.md is a 12 V bench supply (motor modes are refused above 15 V).

**Setup:** KA3005P 12 V / 2 A, MN601-S connected and clamped. `RUN ID_R` from FOCLink (ARM, CSA_CAL, ID_R; `p_id_current` 0.8 A, so phase A +0.8 A, B/C -0.4 A in the first step). DHO804 CH1 on TP38 (SHA, phase-A switch node), 10x probe, spring ground, 2 V/div, 20 ns/div, 1.25 GSa/s, rising trigger.

**Sim it is compared with:** `02b_leg_12V_bench.asc` = deck 02 with `Vbus=12`, `Iph = -0.4 / +0.8 A` (nothing else changed).

| File | What |
|---|---|
| `edge3_*` | HS turn-on in the 0.8 A step (watcher froze the scope 0.5 s after the first edge) - **the comparison capture** |
| `edge_last_*` | last edge of ID_R run 1 (current unknown, probably the 0.16 A step) |
| `edge1_*`, `edge2_*` | watcher false starts (no switching in the record) |
| `bench02_vs_sim.png` | overlay used in the deck |

**Result (edge3 vs 02b, +0.8 A):** rise 8.8 ns / 1.09 V/ns (sim 7.0 ns true; 9.0 ns through the 10x + 70 MHz model; sqrt(7.0^2 + 5^2) = 8.6 ns), peak 13.87 V / +1.87 V (sim +2.61 V true, +3.33 V via probe model), dead time 200 ns at -0.71 V (sim -0.66 V), ring decays in ~150 ns, plus a ~20 MHz wobble not in the sim (bulk-cap / lead loop lumped as 10 nH). ID_R: 99.27 and 100.89 mOhm, no faults.

To do: fit `Lpar` to the measured ring, and use a spring-tip probe model (`Lgnd` ~10 nH) for this setup.
