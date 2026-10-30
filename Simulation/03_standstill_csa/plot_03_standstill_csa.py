"""Reproduces results/fig03_standstill_csa.png from 03_standstill_csa.raw.
Run 03_standstill_csa.asc in LTspice first (same folder), then:  python3 plot_03_standstill_csa.py   (needs numpy + matplotlib)
Single run (no .step). Shows the last two PWM periods; dashed lines = ADC sample instants (carrier peak).
"""
import os, sys
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'common'))
from ltspice_raw import read_raw

plt.rcParams.update({'font.size': 8, 'axes.grid': True, 'grid.alpha': 0.3, 'figure.dpi': 130})
s = read_raw(os.path.join(HERE, '03_standstill_csa.raw'))[0]
OUT = os.path.join(HERE, 'results', 'fig03_standstill_csa.png')
fsw, G, Rsh, VREF = 25e3, 20, 3e-3, 3.3
t = s['time']
m = t > 23 / fsw
tu = t[m] * 1e6
samples = [23.5 / fsw * 1e6, 24.5 / fsw * 1e6]

fig, ax = plt.subplots(3, 1, figsize=(7, 6.4), sharex=True)
ax[0].plot(tu, s['i(la)'][m], label='I phase A (true)')
ax[0].plot(tu, s['i(lb)'][m], label='I phase B (true)')
ax[0].set_ylabel('A'); ax[0].legend(fontsize=7)
ax[0].set_title('Fig 03 - 5 A hold along +alpha at 30 V: ripple and what the CSA shows')
ax[1].plot(tu, s['v(soa)'][m], label='SOA (DRV8323 pin, TP20)')
ax[1].plot(tu, s['v(filter_soa)'][m], label='FILTER_SOA (MCU ADC, TP17)')
ax[1].plot(tu, VREF / 2 + G * Rsh * s['i(la)'][m], 'k:', lw=1, label='VREF/2 + G*Rsh*I_A (ideal)')
ax[1].set_ylabel('V'); ax[1].legend(fontsize=7)
ax[2].plot(tu, s['v(sw_a)'][m], label='SW_A')
ax[2].plot(tu, s['v(inla)'][m] * 10, label='PWM_PHASEA_L x10 (TP22, scope trigger)')
ax[2].set_ylabel('V'); ax[2].set_xlabel('time (us)'); ax[2].legend(fontsize=7)
for a in ax:
    for x in samples:
        a.axvline(x, color='r', ls='--', lw=0.8)
ax[1].text(samples[0] + 0.5, ax[1].get_ylim()[0] + 0.02, 'ADC sample', color='r', fontsize=7)
fig.tight_layout(); fig.savefig(OUT); print('wrote', OUT)
