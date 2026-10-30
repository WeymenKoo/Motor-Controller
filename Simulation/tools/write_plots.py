"""Writes <deck>.plt (LTspice waveform-viewer layout) for every sim folder."""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # the Simulation folder
V, A = 524290, 34603010            # LTspice trace codes: volts / amps; + n selects colour n


def pane(traces, x, y, unit='V'):
    """traces: list of (expr, unit); x/y: (prefix, decimals, min, tick, max)."""
    tr = ' '.join('{%d,0,"%s"}' % ((V if u == 'V' else A) + i, e) for i, (e, u) in enumerate(traces))
    return '\n'.join(['   {', '      traces: %d %s' % (len(traces), tr),
                      "      X: ('%s',%d,%g,%g,%g)" % x,
                      "      Y[0]: ('%s',%d,%g,%g,%g)" % y,
                      "      Y[1]: ('_',0,1e+308,0,-1e+308)",
                      "      %s: ('%s',0,0,%d,%g,%g,%g)" % ('Volts' if unit == 'V' else 'Amps', y[0], y[1], y[2], y[3], y[4]),
                      '      Log: 0 0 0', '      GridStyle: 1', '   }'])


def plt_file(panes):
    return '[Transient Analysis]\n{\n   Npanes: %d\n   Active Pane: 1\n%s\n}\n' % (len(panes), ',\n'.join(panes))


X01 = ('u', 0, 0, 5e-05, 0.0004)
X02 = ('n', 0, 9.8e-06, 1e-07, 1.06e-05)
X03 = ('u', 0, 0.00092, 1e-05, 0.001)
PLT = {
    '01_hot_plug': plt_file([
        pane([('V(VBUS)', 'V'), ('V(VBAT_SENSE)*(12.4k+2k)/2k', 'V')], X01, (' ', 0, 0, 5, 40)),
        pane([('-I(Llead)', 'A'), ('-I(D1)', 'A')], X01, (' ', 0, -50, 50, 350), 'A')]),
    '02_leg_switching': plt_file([
        pane([('V(SW)', 'V'), ('V(SW_SCOPE)', 'V')], X02, (' ', 0, -8, 4, 40)),
        pane([('V(GL,SL)', 'V'), ('V(GH,SW)', 'V'), ('V(GL_SCOPE)', 'V')], X02, (' ', 0, -2, 2, 12)),
        pane([('V(SOURCE_A)', 'V'), ('I(Iph)', 'A')], X02, (' ', 1, -1.5, 0.5, 1.5))]),
    '03_standstill_csa': plt_file([
        pane([('I(LA)', 'A'), ('I(LB)', 'A'), ('I(LC)', 'A')], X03, (' ', 0, -4, 1, 6), 'A'),
        pane([('V(SOA)', 'V'), ('V(FILTER_SOA)', 'V'), ('V(FILTER_SOB)', 'V')], X03, (' ', 1, 1.3, 0.1, 2.1)),
        pane([('V(SW_A)', 'V'), ('V(TRI)*30', 'V')], X03, (' ', 0, -2, 5, 32))]),
}

if __name__ == '__main__':
    for name, txt in PLT.items():
        p = os.path.join(ROOT, name, name + '.plt')
        open(p, 'w').write(txt)
        print('wrote', p)
