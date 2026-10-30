# 03_standstill_csa / bench

Bench correlation for deck 03, 2026-10-30, at 12 V (approved switching scope).

**First attempt (ID_R, 0.8 A):** abandoned. The 48 mV CSA pulse at 0.8 A is the same size as the 35-65 mV switching pickup on TP20, so no CH1 trigger could separate them. Sim for that case: `03b_standstill_12V_bench.asc`.

**Run used:** I/f spin, `RUN IF_SPIN` + `REF IF 2 300` (2 A, 300 rpm, default 100 rpm/s ramp), MN601-S clamped, KA3005P 12 V / 3 A. Sent over UART by Claude with `Firmware/tools/foclink_run.py` (heartbeat on), user-approved for this session in place of the FOCLink Spin window; ARM, CSA_CAL, spin 5.4 s, STOP, DISARM; no faults. Log: `spin1_runlog.txt`.
Scope: CH1 on TP20 (SOA), 10x, 50 mV/div, 20 MHz BWL, 2 ms/div, 10 Mpts at 3.2 ns, free-running single frame 5 s into the spin.

**Sim it is compared with:** `03c_standstill_12V_2A.asc` = deck 03 with `Vbus=12`, `Iset=2` (standstill; at the phase-A peak the I/f vector lies along alpha and the back-EMF at 300 rpm is ~0.6 V, so one PWM period there matches the standstill hold).

| File | What |
|---|---|
| `spin1_ch1_raw.npz` | full record: `v`, `t0`, `dt` |
| `spin1_ia_per_period.npz` | phase-A current per PWM period from the pulse height (I = dV / (20 x 3 mOhm)) |
| `bench03_spin.png` | figure used in the deck |

**Result:** envelope 2.04 A at 70.2 Hz = 301 rpm (14 pole pairs), offset -0.12 A, ~20 Hz wobble (open-loop rotor swing). Pulse at the phase-A peak 112 mV vs 120 mV in the sim (2 A), LS window ~19 us, same ripple slope. Baseline 1.646 V = CSA_CAL offA (1646 mV); HS windows within 3.7 mV. ~1 us spike to ~1.82 V at each LS window start (edge pickup + CSA settling) that the single-pole CSA model underestimates; settled long before the mid-window sample.

Amplitude is method-dependent: averaging the top 20 / 30 / 45 % of samples per period gives 2.29 / 2.18 / 2.04 A; 45 % matches the LS window and is used. The firmware regulates on this same CSA, so 2.04 vs 2 A is a consistency check; the independent scale check is ID_R R (99-101 mOhm) vs the DC line-line measurement (98 mOhm per phase).
