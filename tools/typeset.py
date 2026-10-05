"""Typeset text with glyph outlines recovered from the catalog."""
import pickle
import pikepdf
import pymupdf as fitz
from cat import FONTS, font as rfont, FD

S = pickle.load(open('/tmp/claude-0/-home-user-small-task/01d9064f-fcc0-5c7c-99c9-dd8b7cd80bb4/scratchpad/styles.pkl', 'rb'))
STYLE, WX, OUT, KERN, SPW = S['style'], S['wx'], S['outline'], S['kern'], S['spw']
FALLBACK = {'R': FD + 'SBSansDisplay-Regular.ttf', 'B': FD + 'SBSansDisplay-Bold.ttf',
            'H': FD + 'SBSansDisplay-ExtendedSemibold.ttf'}
_ff = {}
# glyphs whose only document sample is bold-looking -> take from the font file
FORCE_FB = {'R': set('UW')}


def _fb(style):
    if style not in _ff:
        _ff[style] = fitz.Font(fontfile=FALLBACK[style])
    return _ff[style]


def _key(ch, style):
    return ch.upper() if style == 'H' else ch


def glyph_seq(text, style):
    """[(char, sig or None, advance_em)]"""
    seq = []
    for ch in text:
        if ch in (' ', '\xa0'):
            seq.append((ch, None, _fb('H').text_length(' ', 1.0) if style == 'H' else SPW[style]))
            continue
        sig = None if style == 'H' or ch in FORCE_FB.get(style, ()) else STYLE[style].get(_key(ch, style))   # headings: ExtendedSemibold file
        if sig is None:
            seq.append((ch, None, _fb(style).text_length(_key(ch, style), 1.0)))
        else:
            seq.append((ch, sig, WX[sig]))
    return seq


def width(text, style, size, tracking=0.0):
    seq = glyph_seq(text, style)
    w = 0.0
    for i, (ch, sig, adv) in enumerate(seq):
        w += adv * size
        if i + 1 < len(seq):
            w += tracking
            nxt = seq[i + 1][1]
            if sig and nxt:
                w += KERN.get((sig, nxt), 0.0) * size
    return w


def missing(text, style):
    return sorted(set(ch for ch, sig, _ in glyph_seq(text, style) if sig is None and ch not in ' \xa0'))


from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
_tt = {}


class _P(BasePen):
    def __init__(self, gs):
        super().__init__(gs)
        self.ops = []
        self.subs = []

    def _moveTo(self, p):
        self.ops = [('m', [p])]
        self.subs.append(self.ops)

    def _lineTo(self, p):
        self.ops.append(('l', [p]))

    def _curveToOne(self, a, b, c):
        self.ops.append(('c', [a, b, c]))

    def _closePath(self):
        self.ops.append(('h', []))


def fb_outline(ch, style):
    fn = FALLBACK[style] if style != 'H' else FALLBACK['H']
    if fn not in _tt:
        t = TTFont(fn)
        _tt[fn] = (t, t.getGlyphSet(), t.getBestCmap(), t['head'].unitsPerEm)
    t, gs, cm, upm = _tt[fn]
    g = cm.get(ord(ch))
    if g is None:
        return None, 0
    pen = _P(gs)
    gs[g].draw(pen)
    out = [[(op, [(px / upm, -py / upm) for px, py in pts]) for op, pts in sub] for sub in pen.subs]
    return out, t['hmtx'][g][0] / upm


def path_ops(text, style, x, y, size, height, tracking=0.0):
    """Return PDF content (bytes) drawing the text, baseline (x,y) in fitz coords."""
    seq = glyph_seq(text, style)
    parts = []
    pen = x
    fallback = []
    for i, (ch, sig, adv) in enumerate(seq):
        if sig is not None and sig in OUT:
            for sub in OUT[sig]:
                for op, pts in sub:
                    coords = []
                    for (u, v) in pts:
                        coords.append('%.3f %.3f' % (pen + u * size, height - (y + v * size)))
                    parts.append(' '.join(coords) + (' ' if coords else '') + op)
        elif ch not in ' \xa0':
            ol, _ = fb_outline(_key(ch, style), style)
            if ol is None:
                fallback.append((ch, pen))
            else:
                for sub in ol:
                    for op, pts in sub:
                        coords = ['%.3f %.3f' % (pen + u * size, height - (y + v * size)) for (u, v) in pts]
                        parts.append(' '.join(coords) + (' ' if coords else '') + op)
        pen += adv * size
        if i + 1 < len(seq):
            pen += tracking
            nxt = seq[i + 1][1]
            if sig and nxt:
                pen += KERN.get((sig, nxt), 0.0) * size
    return '\n'.join(parts), pen - x, fallback


def draw(pdf, page_index, x, y, text, style, size, color, tracking=0.0, align='left', alpha=1.0):
    pg = pdf.pages[page_index]
    h = float(pg.mediabox[3])
    w = width(text, style, size, tracking)
    if align == 'right':
        x -= w
    elif align == 'center':
        x -= w / 2
    body, w, fb = path_ops(text, style, x, y, size, h, tracking)
    if fb:
        raise ValueError('missing glyphs %r in style %s for %r' % ([c for c, _ in fb], style, text))
    if body:
        gs = ''
        if alpha < 0.999:
            from edit import alpha_gs
            gs = alpha_gs(pdf, page_index, alpha)
        content = 'q %s%.4f %.4f %.4f rg\n%s\nf\nQ\n' % (gs, color[0], color[1], color[2], body)
        pg.contents_add(pdf.make_stream(content.encode()), prepend=False)
    return w


def wrap(text, style, size, maxw, tracking=0.0):
    """Greedy wrap honouring explicit newlines; nbsp never breaks."""
    out = []
    for para in text.split('\n'):
        words = para.split(' ')
        cur = ''
        for wd in words:
            t = (cur + ' ' + wd) if cur else wd
            if width(t, style, size, tracking) <= maxw or not cur:
                cur = t
            else:
                out.append(cur)
                cur = wd
        out.append(cur)
    return out
