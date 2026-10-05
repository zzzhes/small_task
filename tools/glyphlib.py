"""Glyph library built from the catalog itself.

Figma exported text twice: visible outlines (filled paths inside page Form
XObjects) and an invisible Type3 layer whose glyph procs only carry d1
metrics (advance + ink bbox). We match the two to recover per-glyph outlines
for every typeface used in the layout, then draw new text with them.
"""
import pickle
import re
import statistics
from collections import defaultdict

import pikepdf

from cat import _mul, _pt, PATH_OPS, FILL_OPS


# ---------------------------------------------------------------- type3 font
_fcache = {}


def type3_info(font):
    key = font.objgen
    if key in _fcache:
        return _fcache[key]
    enc = font.Encoding.Differences
    names = {}
    code = 0
    for v in enc:
        if isinstance(v, (int, pikepdf.Object)) and not isinstance(v, pikepdf.Name):
            try:
                code = int(v)
                continue
            except Exception:
                pass
        names[code] = str(v)[1:]
        code += 1
    uni = {}
    cm = font.ToUnicode.read_bytes().decode('latin1')
    for a, b in re.findall(r'<([0-9A-Fa-f]{2})>\s*<([0-9A-Fa-f]+)>', cm):
        hx = b
        s = ''.join(chr(int(hx[i:i + 4], 16)) for i in range(0, len(hx), 4))
        uni[int(a, 16)] = s
    info = {}
    for code, nm in names.items():
        proc = font.CharProcs.get('/' + nm)
        if proc is None:
            continue
        nums = proc.read_bytes().split()
        try:
            i = nums.index(b'd1')
            wx, wy, llx, lly, urx, ury = [float(x) for x in nums[i - 6:i]]
        except ValueError:
            i = nums.index(b'd0')
            wx = float(nums[i - 2])
            llx = lly = urx = ury = 0.0
        info[code] = (uni.get(code, ''), wx, (llx, lly, urx, ury))
    _fcache[key] = info
    return info


def sig_of(u, wx, bb):
    return (u, round(wx, 3), tuple(round(v, 3) for v in bb))


# ---------------------------------------------------------------- invisible
def invisible_glyphs(pg, height):
    """List of dicts: u, sig, x, y (baseline, fitz), size, adj_after, word."""
    ops = pikepdf.parse_content_stream(pg)
    fonts = pg.Resources.get('/Font', {})
    stack, ctm = [], (1, 0, 0, 1, 0, 0)
    tm = (1, 0, 0, 1, 0, 0)
    font = None
    res = []
    line_id = 0
    for o in ops:
        op = str(o.operator)
        if op == 'q':
            stack.append(ctm)
        elif op == 'Q':
            ctm = stack.pop()
        elif op == 'cm':
            ctm = _mul(tuple(float(v) for v in o.operands), ctm)
        elif op == 'Tf':
            font = fonts[o.operands[0]]
        elif op == 'Tm':
            tm = tuple(float(v) for v in o.operands)
        elif op == 'TJ':
            line_id += 1
            if font is None or font.get('/Subtype') != '/Type3':
                continue
            info = type3_info(font)
            m = _mul(tm, ctm)
            size = m[0]
            pen = 0.0  # text space units (em)
            arr = list(o.operands[0])
            last = None
            for el in arr:
                if isinstance(el, pikepdf.String):
                    for code in bytes(el):
                        u, wx, bb = info.get(code, ('', 0, (0, 0, 0, 0)))
                        X, Y = _pt(m, pen, 0)
                        g = dict(u=u, sig=sig_of(u, wx, bb), wx=wx, bb=bb,
                                 x=X, y=height - Y, size=size, adj=0.0,
                                 line=line_id)
                        res.append(g)
                        last = g
                        pen += wx
                else:
                    n = float(el)
                    pen -= n / 1000.0
                    if last is not None:
                        last['adj'] += -n / 1000.0
    return res


# ---------------------------------------------------------------- visible
def visible_subpaths(pg, height):
    """Filled subpaths in page Form XObjects: dict(pts ops, bbox, color)."""
    out = []
    gid = [0]

    def walk(xo, base):
        ops = pikepdf.parse_content_stream(xo)
        st, c = [], base
        color = None
        alpha = 1.0
        res = xo.Resources if hasattr(xo, 'Resources') else xo.obj.Resources
        egs = res.get('/ExtGState', {})
        cst = []
        cur, subs = [], []

        def flush():
            nonlocal cur
            if cur:
                subs.append(cur)
                cur = []
        for o in ops:
            op = str(o.operator)
            if op in PATH_OPS:
                if op in ('m', 're'):
                    flush()
                nums = [float(v) for v in o.operands]
                if op == 're':
                    x, y, w, h = nums
                    pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
                    cur.append(('m', [_tp(c, pts[0], height)]))
                    for p in pts[1:]:
                        cur.append(('l', [_tp(c, p, height)]))
                    cur.append(('h', []))
                    flush()
                    continue
                pts = [_tp(c, p, height) for p in zip(nums[0::2], nums[1::2])]
                cur.append((op, pts))
                continue
            if op in FILL_OPS or op in ('S', 's', 'n', 'W', 'W*'):
                flush()
                if op in FILL_OPS:
                    gid[0] += 1
                    for s in subs:
                        xs = [p[0] for _, pts in s for p in pts]
                        ys = [p[1] for _, pts in s for p in pts]
                        if xs:
                            out.append(dict(ops=s, bb=(min(xs), min(ys), max(xs), max(ys)),
                                            color=color, rule=op, alpha=alpha, gid=gid[0]))
                if op not in ('W', 'W*'):
                    subs = []
                continue
            if op == 'q':
                st.append((c, color, alpha))
            elif op == 'Q':
                c, color, alpha = st.pop()
            elif op == 'gs':
                e = egs.get(o.operands[0])
                if e is not None and '/ca' in e:
                    alpha = float(e.ca)
            elif op == 'cm':
                c = _mul(tuple(float(v) for v in o.operands), c)
            elif op in ('scn', 'sc', 'rg'):
                color = tuple(float(v) for v in o.operands if not isinstance(v, pikepdf.Name))
            elif op == 'g':
                v = float(o.operands[0])
                color = (v, v, v)
            elif op == 'Do':
                sub = xo.Resources.XObject[o.operands[0]] if hasattr(xo, 'Resources') else xo.obj.Resources.XObject[o.operands[0]]
                if sub.Subtype == '/Form':
                    m = tuple(float(v) for v in sub.get('/Matrix', [1, 0, 0, 1, 0, 0]))
                    walk(sub, _mul(m, c))
    walk(pg, (1, 0, 0, 1, 0, 0))
    return out


def _tp(m, p, height):
    X, Y = _pt(m, p[0], p[1])
    return (X, height - Y)


# ---------------------------------------------------------------- matching
def ink_rect(g):
    s = g['size']
    llx, lly, urx, ury = g['bb']
    return (g['x'] + llx * s, g['y'] - 1.0 * s, g['x'] + urx * s, g['y'] + 0.32 * s)


def _inter(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return w * h if w > 0 and h > 0 else 0.0


def match_page(pg, height):
    gl = [g for g in invisible_glyphs(pg, height) if g['u'].strip() and g['bb'][2] > g['bb'][0]]
    sps = visible_subpaths(pg, height)
    # grid index of glyphs
    grid = defaultdict(list)
    for i, g in enumerate(gl):
        r = ink_rect(g)
        for gx in range(int(r[0] // 20), int(r[2] // 20) + 1):
            for gy in range(int(r[1] // 20), int(r[3] // 20) + 1):
                grid[(gx, gy)].append(i)
    owner = defaultdict(list)
    for sp in sps:
        b = sp['bb']
        area = max((b[2] - b[0]) * (b[3] - b[1]), 1e-6)
        if area > 2000:
            continue
        cand = set()
        for gx in range(int(b[0] // 20), int(b[2] // 20) + 1):
            for gy in range(int(b[1] // 20), int(b[3] // 20) + 1):
                cand.update(grid.get((gx, gy), ()))
        best, bi = 0, None
        for i in cand:
            r = ink_rect(gl[i])
            # loosen the rect a bit for kerning shifts
            rr = (r[0] - 0.6, r[1] - 0.6, r[2] + 0.6, r[3] + 0.6)
            f = _inter(b, rr) / area
            if f > best:
                best, bi = f, i
        if bi is not None and best > 0.6:
            owner[bi].append(sp)
    samples = []
    for i, sp_list in owner.items():
        g = gl[i]
        r = ink_rect(g)
        xs0 = min(s['bb'][0] for s in sp_list)
        ys0 = min(s['bb'][1] for s in sp_list)
        xs1 = max(s['bb'][2] for s in sp_list)
        ys1 = max(s['bb'][3] for s in sp_list)
        w = r[2] - r[0]
        if abs((xs1 - xs0) - w) > 0.08 * w + 0.15:
            continue
        dx, dy = xs0 - r[0], 0.0
        s = g['size']
        ox, oy = g['x'] + dx, g['y'] + dy
        norm = []
        for sp in sp_list:
            norm.append([(op, [((p[0] - ox) / s, (p[1] - oy) / s) for p in pts]) for op, pts in sp['ops']])
        samples.append(dict(sig=g['sig'], u=g['u'], wx=g['wx'], outline=norm,
                            color=sp_list[0]['color'], size=s, line=g['line'],
                            x=g['x'], y=g['y']))
    return gl, samples


# ---------------------------------------------------------------- library
class Lib:
    def __init__(self):
        self.outline = {}          # sig -> outline
        self.parent = {}           # union-find over sigs
        self.adj = defaultdict(list)    # sig -> list of adjustments after it
        self.pair = defaultdict(list)   # (sigA,sigB) -> adjustments
        self.wx = {}

    def find(self, a):
        self.parent.setdefault(a, a)
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb

    def add_page(self, pg, height):
        gl, samples = match_page(pg, height)
        for s in samples:
            if s['sig'] not in self.outline:
                self.outline[s['sig']] = s['outline']
        allg = invisible_glyphs(pg, height)
        for a, b in zip(allg, allg[1:]):
            self.wx[a['sig']] = a['wx']
            if a['line'] != b['line'] or abs(a['size'] - b['size']) > 0.01:
                continue
            if a['u'] in (' ', '\xa0', ' ') or b['u'] in (' ', '\xa0', ' '):
                continue
            # same word -> same typeface
            self.union(a['sig'], b['sig'])
            self.adj[a['sig']].append(a['adj'])
            self.pair[(a['sig'], b['sig'])].append(a['adj'])
        for a in allg:
            self.wx[a['sig']] = a['wx']
            if a['u'] in (' ', '\xa0'):
                self.adj[a['sig']].append(a['adj'])

    def families(self):
        fam = defaultdict(set)
        for s in self.parent:
            fam[self.find(s)].add(s)
        return fam

    def save(self, fn):
        with open(fn, 'wb') as f:
            pickle.dump(dict(outline=self.outline, parent=self.parent, adj=dict(self.adj),
                             pair=dict(self.pair), wx=self.wx), f)

    @classmethod
    def load(cls, fn):
        lib = cls()
        with open(fn, 'rb') as f:
            d = pickle.load(f)
        lib.outline = d['outline']
        lib.parent = d['parent']
        lib.adj = defaultdict(list, d['adj'])
        lib.pair = defaultdict(list, d['pair'])
        lib.wx = d['wx']
        return lib


def median(v, default=0.0):
    return statistics.median(v) if v else default
