"""Renders an LTspice .asc to PNG using LTspice's own symbol graphics (.asy files).
Not a pixel copy of the LTspice window; for documents and slides.

usage: python3 render_asc.py deck.asc out.png [--circuit-only] [--maxval N]
  --circuit-only  crop to wires + symbols (drop the sheet's text blocks)
  --maxval N      truncate component values longer than N characters (default 34)
"""
import math, os, re, sys, collections
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, Rectangle

SYMDIR = os.path.expanduser('~/Library/Application Support/LTspice/Bottles/ltspice/drive_c/users/crossover/'
                            'AppData/Local/LTspice/lib/sym')
ROT = {'R0': lambda x, y: (x, y), 'R90': lambda x, y: (-y, x),
       'R180': lambda x, y: (-x, -y), 'R270': lambda x, y: (y, -x)}
TSIZE = {0: 0.625, 1: 1.0, 2: 1.5, 3: 2.0, 4: 2.5, 5: 3.5, 6: 5.0, 7: 7.0}
C_WIRE, C_SYM, C_FLAG, C_COMMENT, C_DIR = '#1f3fbf', '#202020', '#202020', '#1f3fbf', '#202020'


def load_sym(kind, cache={}):
    if kind in cache:
        return cache[kind]
    path = None
    for f in os.listdir(SYMDIR):
        if f.lower() == kind.lower().replace('\\', '/').split('/')[-1] + '.asy':
            path = os.path.join(SYMDIR, f)
    g = dict(lines=[], rects=[], circles=[], arcs=[], win={}, pins=[])
    if path:
        for ln in open(path, encoding='latin-1'):
            p = ln.split()
            if not p:
                continue
            if p[0] == 'LINE':
                g['lines'].append(tuple(map(int, p[2:6])))
            elif p[0] == 'RECTANGLE':
                g['rects'].append(tuple(map(int, p[2:6])))
            elif p[0] == 'CIRCLE':
                g['circles'].append(tuple(map(int, p[2:6])))
            elif p[0] == 'ARC':
                g['arcs'].append(tuple(map(int, p[2:10])))
            elif p[0] == 'WINDOW':
                g['win'][int(p[1])] = (int(p[2]), int(p[3]))
            elif p[0] == 'PIN':
                g['pins'].append((int(p[1]), int(p[2])))
    cache[kind] = g
    return g


def parse(path):
    d = dict(wires=[], flags=[], syms=[], texts=[], rects=[])
    cur = None
    for ln in open(path, encoding='latin-1'):
        ln = ln.rstrip('\n')
        p = ln.split()
        if not p:
            continue
        if p[0] == 'WIRE':
            d['wires'].append(tuple(map(int, p[1:5])))
        elif p[0] == 'FLAG':
            d['flags'].append((int(p[1]), int(p[2]), p[3]))
        elif p[0] == 'SYMBOL':
            cur = dict(kind=p[1], x=int(p[2]), y=int(p[3]), rot=p[4], attr={})
            d['syms'].append(cur)
        elif p[0] == 'SYMATTR' and cur is not None:
            cur['attr'][p[1]] = ln.split(None, 2)[2] if len(p) > 2 else ''
        elif p[0] == 'TEXT':
            m = re.match(r'TEXT (-?\d+) (-?\d+) (\w+) (\d+) (.)(.*)$', ln)
            if m:
                d['texts'].append((int(m.group(1)), int(m.group(2)), int(m.group(4)), m.group(5),
                                   m.group(6).replace('\\n', '\n')))
        elif p[0] == 'RECTANGLE':
            d['rects'].append(tuple(map(int, p[2:6])))
    return d


def render(asc, png, circuit_only=False, maxval=34):
    d = parse(asc)
    pts = []
    for w in d['wires']:
        pts += [(w[0], w[1]), (w[2], w[3])]
    for s in d['syms']:
        g = load_sym(s['kind']); R = ROT[s['rot']]
        for (px, py) in g['pins'] or [(0, 0)]:
            X, Y = R(px, py); pts.append((s['x'] + X, s['y'] + Y))
    for (a, b, c, e) in d['rects']:
        pts += [(a, b), (c, e)]
    if not circuit_only:
        for t in d['texts']:
            pts.append((t[0], t[1]))
            nl = t[4].count('\n') + 1
            w = max(len(l) for l in t[4].split('\n')) * 9 * TSIZE[t[2]] / 1.5
            pts.append((t[0] + w, t[1] + nl * 16 * TSIZE[t[2]] / 1.5))
    x0, x1 = min(p[0] for p in pts) - 80, max(p[0] for p in pts) + 220
    y0, y1 = min(p[1] for p in pts) - 80, max(p[1] for p in pts) + 80
    S = 100.0                                    # 100 LTspice units per inch
    fig = plt.figure(figsize=((x1 - x0) / S, (y1 - y0) / S))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.axis('off')
    ax.set_aspect('equal')
    fs = 0.72 * 100 / S * 9                      # pt for a size-"1.0" text
    for w in d['wires']:
        ax.plot([w[0], w[2]], [w[1], w[3]], color=C_WIRE, lw=1.6, solid_capstyle='round')
    ends = collections.Counter()
    for w in d['wires']:
        ends[(w[0], w[1])] += 1; ends[(w[2], w[3])] += 1
    for s in d['syms']:
        g = load_sym(s['kind']); R = ROT[s['rot']]
        for (px, py) in g['pins']:
            X, Y = R(px, py); ends[(s['x'] + X, s['y'] + Y)] += 1
    for p, c in ends.items():
        if c >= 3:
            ax.add_patch(Circle(p, 5, color=C_WIRE, zorder=3))
    for s in d['syms']:
        g = load_sym(s['kind']); R = ROT[s['rot']]; ox, oy = s['x'], s['y']
        T = lambda x, y: (ox + R(x, y)[0], oy + R(x, y)[1])
        for (a, b, c, e) in g['lines']:
            (X1, Y1), (X2, Y2) = T(a, b), T(c, e)
            ax.plot([X1, X2], [Y1, Y2], color=C_SYM, lw=1.4)
        for (a, b, c, e) in g['rects']:
            (X1, Y1), (X2, Y2) = T(a, b), T(c, e)
            ax.add_patch(Rectangle((min(X1, X2), min(Y1, Y2)), abs(X2 - X1), abs(Y2 - Y1), fill=False, color=C_SYM, lw=1.4))
        for (a, b, c, e) in g['circles']:
            (X1, Y1), (X2, Y2) = T(a, b), T(c, e)
            ax.add_patch(Circle(((X1 + X2) / 2, (Y1 + Y2) / 2), abs(X2 - X1) / 2, fill=False, color=C_SYM, lw=1.4))
        for (a, b, c, e, sx, sy, ex, ey) in g['arcs']:
            (X1, Y1), (X2, Y2) = T(a, b), T(c, e)
            cx, cy = (X1 + X2) / 2, (Y1 + Y2) / 2
            (SX, SY), (EX, EY) = T(sx, sy), T(ex, ey)
            t1 = math.degrees(math.atan2(EY - cy, EX - cx)); t2 = math.degrees(math.atan2(SY - cy, SX - cx))
            ax.add_patch(Arc((cx, cy), abs(X2 - X1), abs(Y2 - Y1), theta1=t1, theta2=t2, color=C_SYM, lw=1.4))
        # labels: InstName and Value, kept horizontal
        name = s['attr'].get('InstName', ''); val = s['attr'].get('Value', '')
        if len(val) > maxval:
            val = val[:maxval - 1] + '...'
        pp = [T(px, py) for px, py in g['pins']] or [(ox, oy)]
        horiz = len(pp) == 2 and pp[0][1] == pp[1][1]
        if horiz:
            cx = sum(p[0] for p in pp) / 2; cy = pp[0][1]
            ax.text(cx, cy - 22, name, fontsize=fs, ha='center', va='bottom', color=C_SYM)
            ax.text(cx, cy + 22, val, fontsize=fs, ha='center', va='top', color=C_SYM)
        else:
            wx, wy = g['win'].get(0, (36, 40)); vx, vy = g['win'].get(3, (36, 76))
            if s['rot'] == 'R180':
                xs = max(p[0] for p in pp) + 20 if pp else ox
                ax.text(xs, (pp[0][1] + pp[-1][1]) / 2 - 8, name, fontsize=fs, ha='left', va='bottom', color=C_SYM)
                ax.text(xs, (pp[0][1] + pp[-1][1]) / 2 + 8, val, fontsize=fs, ha='left', va='top', color=C_SYM)
            else:
                X, Y = T(wx, wy); ax.text(X, Y, name, fontsize=fs, ha='left', va='center', color=C_SYM)
                X, Y = T(vx, vy); ax.text(X, Y, val, fontsize=fs, ha='left', va='center', color=C_SYM)
    for (x, y, n) in d['flags']:
        if n == '0':
            ax.plot([x - 16, x + 16, x, x - 16], [y, y, y + 16, y], color=C_FLAG, lw=1.4)
        else:
            ax.text(x, y - 6, n, fontsize=fs, ha='center', va='bottom', color=C_FLAG, fontweight='bold')
    for (a, b, c, e) in d['rects']:
        ax.add_patch(Rectangle((min(a, c), min(b, e)), abs(c - a), abs(e - b), fill=False, ls='--', color='#888888', lw=1))
    if not circuit_only:
        for (x, y, sz, kind, s) in d['texts']:
            ax.text(x, y, s, fontsize=fs * TSIZE[sz] / 1.0, va='top', ha='left', family='monospace',
                    color=C_DIR if kind == '!' else C_COMMENT)
    else:
        for (x, y, sz, kind, s) in d['texts']:
            if kind == ';' and x0 < x < x1 and y0 < y < y1 and sz <= 1 and s.count('\n') < 6:
                ax.text(x, y, s, fontsize=fs, va='top', ha='left', color=C_COMMENT)
    fig.savefig(png, dpi=200, facecolor='white'); plt.close(fig)
    # component / net positions as fractions of the image (for annotating slides)
    import json
    fr = lambda x, y: [round((x - x0) / (x1 - x0), 4), round((y - y0) / (y1 - y0), 4)]
    pos = {}
    for s in d['syms']:
        g = load_sym(s['kind']); R = ROT[s['rot']]
        pp = [(s['x'] + R(px, py)[0], s['y'] + R(px, py)[1]) for px, py in g['pins']] or [(s['x'], s['y'])]
        pos[s['attr'].get('InstName', '?')] = fr(sum(p[0] for p in pp) / len(pp), sum(p[1] for p in pp) / len(pp))
    for (x, y, n) in d['flags']:
        if n != '0':
            pos.setdefault('net:' + n, fr(x, y))
    json.dump(pos, open(os.path.splitext(png)[0] + '.json', 'w'), indent=0)


if __name__ == '__main__':
    a = sys.argv[1:]
    mv = 34
    if '--maxval' in a:
        i = a.index('--maxval'); mv = int(a[i + 1]); del a[i:i + 2]
    co = '--circuit-only' in a
    a = [x for x in a if x != '--circuit-only']
    render(a[0], a[1], co, mv)
    print('wrote', a[1])
