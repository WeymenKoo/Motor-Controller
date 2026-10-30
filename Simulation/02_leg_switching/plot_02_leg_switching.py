"""Reproduces results/fig02_leg_switching.png from 02_leg_switching.raw.
Run 02_leg_switching.asc in LTspice first (same folder), then:  python3 plot_02_leg_switching.py   (needs numpy + matplotlib)
Step order (LTspice runs lists ascending):  1: Iph = -2.5 A (phase B/C in an ID_R hold)   2: Iph = +5 A (phase A)
Columns: the two hard edges.  +5 A -> HS turn-on at T/4 + DT/2 (SW rising).  -2.5 A -> LS turn-on at 3T/4 + DT/2 (SW falling).
"""
import os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'common'))
from ltspice_raw import read_raw

plt.rcParams.update({'font.size': 8, 'axes.grid': True, 'grid.alpha': 0.3, 'figure.dpi': 130})
st = read_raw(os.path.join(HERE, '02_leg_switching.raw'))
OUT = os.path.join(HERE, 'results', 'fig02_leg_switching.png')
T, DT = 40e-6, 200e-9
cases = [(st[1], T / 4 + DT / 2, '+5 A: high-side turn-on (hard, SW rising)'),
         (st[0], 3 * T / 4 + DT / 2, '-2.5 A: low-side turn-on (hard, SW falling)')]

fig, ax = plt.subplots(3, 2, figsize=(8, 6.4), sharex='col')
for col, (s, t0, title) in enumerate(cases):
    t = (s['time'] - t0) * 1e9
    m = (t > -300) & (t < 500)
    a = ax[0, col]
    a.plot(t[m], s['v(sw)'][m], label='V(SW) true')
    a.plot(t[m], s['v(sw_scope)'][m], label='V(SW) on DHO804 (10x, 15 cm clip, 70 MHz)')
    a.set_title(title); a.set_ylabel('V')
    a = ax[1, col]
    a.plot(t[m], s['v(gl)'][m] - s['v(sl)'][m], label='VGS low side')
    a.plot(t[m], s['v(gh)'][m] - s['v(sw)'][m], label='VGS high side')
    a.axhline(2.3, color='r', ls=':', lw=1); a.text(-290, 2.6, 'VGS(th) min 2.3 V', fontsize=7, color='r')
    a.set_ylabel('V')
    a = ax[2, col]
    a.plot(t[m], s['v(source_a)'][m] * 1e3, color='C2')
    a.axhline(300, color='k', ls=':', lw=1); a.axhline(-300, color='k', ls=':', lw=1)
    a.set_ylabel('V(SOURCE_A) (mV)'); a.set_xlabel('time from gate command (ns)')
ax[0, 0].legend(fontsize=7, loc='lower right'); ax[1, 0].legend(fontsize=7)
ax[2, 0].text(-290, 330, 'CSA input range +-0.3 V', fontsize=7)
fig.suptitle('Fig 02 - phase A leg at 30 V, IDRIVE 1 A / 2 A, 200 ns dead time')
fig.tight_layout(); fig.savefig(OUT); print('wrote', OUT)
