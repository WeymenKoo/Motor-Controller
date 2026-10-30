"""Reproduces results/fig01_hot_plug.png from 01_hot_plug.raw.
Run 01_hot_plug.asc in LTspice first (same folder), then:  python3 plot_01_hot_plug.py   (needs numpy + matplotlib)
Step order (LTspice runs lists ascending, ESRbulk varies fastest):
  1: ESR 0.03, Llead 0.5u   2: ESR 0.3, Llead 0.5u   3: ESR 0.03, Llead 2u   4: ESR 0.3, Llead 2u
"""
import os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'common'))
from ltspice_raw import read_raw, COL

plt.rcParams.update({'font.size': 9, 'axes.grid': True, 'grid.alpha': 0.3, 'figure.dpi': 130})
st = read_raw(os.path.join(HERE, '01_hot_plug.raw'))
OUT = os.path.join(HERE, 'results', 'fig01_hot_plug.png')
LAB = ['ESR 0.03 ohm, 0.5 uH', 'ESR 0.3 ohm, 0.5 uH', 'ESR 0.03 ohm, 2 uH', 'ESR 0.3 ohm, 2 uH']

fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.5, 5.2), sharex=True)
for s, lab, c in zip(st, LAB, COL):
    t = s['time'] * 1e6
    a1.plot(t, s['v(vbus)'], color=c, label=lab)
    a2.plot(t, -s['i(llead)'], color=c)
a1.axhline(51, color='k', ls=':', lw=1); a1.text(5, 51.5, 'D1 stand-off 51 V', fontsize=7)
a1.axhline(56.7, color='r', ls=':', lw=1); a1.text(5, 57.2, 'D1 VBR min 56.7 V', fontsize=7, color='r')
s = st[2]
a1.plot(s['time'] * 1e6, s['v(vbat_sense)'] * 14.4 / 2, 'k--', lw=1, label='firmware view (VBAT_SENSE x 7.2), ESR 0.03, 2 uH')
a1.set_ylabel('V(VBUS) (V)'); a1.set_ylim(0, 62); a1.legend(fontsize=7, loc='lower right')
a1.set_title('Fig 01 - XT60 hot-plug into a live 30 V supply')
a2.set_ylabel('lead current (A)'); a2.set_xlabel('time (us)'); a2.set_xlim(0, 400)
fig.tight_layout(); fig.savefig(OUT); print('wrote', OUT)
