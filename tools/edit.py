"""High level editing helpers on top of glyphlib/typeset."""
import pikepdf
from collections import defaultdict
from glyphlib import invisible_glyphs, visible_subpaths
from cat import erase as _erase
import typeset as T

H = 870.24
LOG = []   # (page_obj, x, y, text, size) for invisible text layer


def lines(pdf, pi):
    """Visual lines: list of dict(text, x0, x1, y, size, glyphs)."""
    pg = pdf.pages[pi]
    gl = invisible_glyphs(pg, float(pg.mediabox[3]))
    d = defaultdict(list)
    for g in gl:
        d[(round(g['y'], 1), round(g['size'], 2))].append(g)
    out = []
    for (y, s), gs in d.items():
        gs.sort(key=lambda g: g['x'])
        # split on big gaps (separate frames on the same baseline)
        cur = [gs[0]]
        groups = []
        for a, b in zip(gs, gs[1:]):
            if b['x'] - (a['x'] + a['wx'] * a['size']) > 2.5 * s:
                groups.append(cur)
                cur = []
            cur.append(b)
        groups.append(cur)
        for grp in groups:
            txt = ''.join(g['u'] for g in grp).replace(' ', '')
            last = grp[-1]
            out.append(dict(text=txt, x0=grp[0]['x'], x1=last['x'] + last['wx'] * s,
                            y=grp[0]['y'], size=s, glyphs=grp))
    out.sort(key=lambda l: (l['y'], l['x0']))
    return out


def find(pdf, pi, needle, nth=0, exact=False):
    hits = [l for l in lines(pdf, pi) if (l['text'].strip() == needle if exact else needle in l['text'])]
    if len(hits) <= nth:
        raise KeyError('%r not found on page %d' % (needle, pi))
    return hits[nth]


def line_rect(l, pad=0.5):
    s = l['size']
    return (l['x0'] - pad, l['y'] - 0.95 * s, l['x1'] + pad, l['y'] + 0.3 * s)


def color_in(pdf, pi, rect):
    pg = pdf.pages[pi]
    from collections import Counter
    c = Counter()
    for sp in visible_subpaths(pg, float(pg.mediabox[3])):
        b = sp['bb']
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        if rect[0] <= cx <= rect[2] and rect[1] <= cy <= rect[3] and sp['color']:
            c[sp['color']] += 1
    if not c:
        raise ValueError('no colour in %r' % (rect,))
    col = c.most_common(1)[0][0]
    if len(col) == 1:
        col = (col[0],) * 3
    return col[:3]


def replace_line(pdf, pi, l, new, style, color=None, x=None, tracking=0.0):
    r = line_rect(l)
    if color is None:
        color = color_in(pdf, pi, r)
    erase(pdf, pi, [r])
    x = l['x0'] if x is None else x
    w = T.draw(pdf, pi, x, l['y'], new, style, l['size'], color, tracking)
    LOG.append((id(pdf), pdf.pages[pi].objgen, x, l['y'], new, l['size']))
    return w


def put(pdf, pi, x, y, text, style, size, color, tracking=0.0, align='left'):
    w = T.draw(pdf, pi, x, y, text, style, size, color, tracking, align)
    LOG.append((id(pdf), pdf.pages[pi].objgen, x if align == 'left' else x - (w if align == 'right' else w / 2), y, text, size))
    return w


def put_block(pdf, pi, x, y, lines_, style, size, color, lead, tracking=0.0):
    for i, t in enumerate(lines_):
        put(pdf, pi, x, y + i * lead, t, style, size, color, tracking)
    return y + (len(lines_) - 1) * lead


def copy_shapes(pdf, pi, rect, dx, dy, src_pi=None, src_pdf=None):
    """Copy filled subpaths whose centre is in rect (from src page) shifted by dx,dy.
    Subpaths that came from the same fill keep a common fill (holes stay holes)."""
    src_pdf = src_pdf or pdf
    src_pi = pi if src_pi is None else src_pi
    pg = src_pdf.pages[src_pi]
    h = float(pg.mediabox[3])
    groups = {}
    for sp in visible_subpaths(pg, h):
        b = sp['bb']
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        if rect[0] <= cx <= rect[2] and rect[1] <= cy <= rect[3]:
            groups.setdefault(sp.get('gid'), []).append(sp)
    parts = []
    for g, sps in groups.items():
        sp0 = sps[0]
        col = sp0['color'] or (0, 0, 0)
        if len(col) == 1:
            col = col * 3
        gs = alpha_gs(pdf, pi, sp0.get('alpha', 1.0))
        body = []
        for sp in sps:
            for op, pts in sp['ops']:
                body.append(' '.join('%.3f %.3f' % (p[0] + dx, H - (p[1] + dy)) for p in pts) + (' ' if pts else '') + op)
        fill = 'f*' if sp0.get('rule') in ('f*', 'B*', 'b*') else 'f'
        parts.append('q %s%.4f %.4f %.4f rg\n%s\n%s\nQ\n' % (gs, col[0], col[1], col[2], '\n'.join(body), fill))
    if parts:
        pdf.pages[pi].contents_add(pdf.make_stream(''.join(parts).encode()), prepend=False)
    return len(groups)


import re
SHORT = r'(?:и|а|в|с|к|о|у|на|по|за|до|от|из|не|ни|для|без|при|под|над|про|или|ее|её|их|со|во|об)'


def typo(t):
    t = re.sub(r'(?<![\w-])(' + SHORT + r') ', lambda m: m.group(1) + '\xa0', t, flags=re.I)
    t = re.sub(r'(?<![\w-])(' + SHORT + r') ', lambda m: m.group(1) + '\xa0', t, flags=re.I)
    t = t.replace(' — ', '\xa0— ').replace(' ₽', '\xa0₽')
    t = re.sub(r'(\d) (млн|млрд|тыс|человек|%)', '\\1\xa0\\2', t)
    return t


def rich_tokens(runs):
    """runs: [(text, style)] -> list of words; each word = [(piece, style)], spaces separate."""
    words = [[]]
    for text, st in runs:
        parts = text.split(' ')
        for k, p in enumerate(parts):
            if k > 0:
                words.append([])
            if p:
                words[-1].append((p, st))
    return [w for w in words if w]


def _ww(word, size):
    return sum(T.width(p, st, size) for p, st in word)


def rich_wrap(runs, size, maxw):
    words = rich_tokens(runs)
    lines_, cur, cw = [], [], 0.0
    for w in words:
        ww = _ww(w, size)
        sp = T.SPW[w[0][1]] * size
        if cur and cw + sp + ww > maxw:
            lines_.append(cur)
            cur, cw = [w], ww
        else:
            cw = cw + (sp if cur else 0) + ww
            cur.append(w)
    if cur:
        lines_.append(cur)
    return lines_


def put_rich(pdf, pi, x, y, runs, size, color, maxw, lead, colors=None):
    """Draw wrapped mixed-style paragraph; returns (n_lines, last_baseline)."""
    runs = [(typo(t), st) for t, st in runs]
    ls = rich_wrap(runs, size, maxw)
    for i, line in enumerate(ls):
        cx = x
        yy = y + i * lead
        for j, w in enumerate(line):
            if j:
                cx += T.SPW[w[0][1]] * size
            for p, st in w:
                col = (colors or {}).get(st, color)
                cx += T.draw(pdf, pi, cx, yy, p, st, size, col)
        txt = ' '.join(''.join(p for p, _ in w) for w in line)
        LOG.append((id(pdf), pdf.pages[pi].objgen, x, yy, txt, size))
    return len(ls), y + (len(ls) - 1) * lead


def put_par(pdf, pi, x, y, text, style, size, color, maxw, lead, tracking=0.0):
    return put_rich(pdf, pi, x, y, [(text, style)], size, color, maxw, lead)


def alpha_gs(pdf, pi, alpha):
    """Return 'gs' operator string for fill opacity (adds ExtGState to page)."""
    if alpha >= 0.999:
        return ''
    pg = pdf.pages[pi]
    res = pg.obj.Resources
    if '/ExtGState' not in res:
        res.ExtGState = pikepdf.Dictionary()
    name = '/GSa%d' % round(alpha * 1000)
    if name not in res.ExtGState:
        res.ExtGState[name] = pikepdf.Dictionary(Type=pikepdf.Name.ExtGState, ca=alpha)
    return '%s gs ' % name


def replace_image(pdf, ximg, pil, mode='contain', bg=None, quality=90, focus=(0.5, 0.5)):
    """Replace image XObject pixels keeping size & SMask. pil: PIL image."""
    from PIL import Image
    import io as _io
    W, Hh = int(ximg.Width), int(ximg.Height)
    src = pil.convert('RGBA')
    if mode == 'contain':
        k = min(W / src.width, Hh / src.height)
        im = src.resize((max(1, round(src.width * k)), max(1, round(src.height * k))), Image.LANCZOS)
        can = Image.new('RGBA', (W, Hh), bg or (255, 255, 255, 255))
        can.alpha_composite(im, ((W - im.width) // 2, (Hh - im.height) // 2))
    else:  # cover
        k = max(W / src.width, Hh / src.height)
        im = src.resize((max(W, round(src.width * k)), max(Hh, round(src.height * k))), Image.LANCZOS)
        x0 = int((im.width - W) * focus[0])
        y0 = int((im.height - Hh) * focus[1])
        can = Image.new('RGBA', (W, Hh), bg or (255, 255, 255, 255))
        can.alpha_composite(im.crop((x0, y0, x0 + W, y0 + Hh)))
    rgb = can.convert('RGB')
    b = _io.BytesIO()
    rgb.save(b, 'JPEG', quality=quality)
    ximg.write(b.getvalue(), filter=pikepdf.Name.DCTDecode)
    ximg.ColorSpace = pikepdf.Name.DeviceRGB
    ximg.BitsPerComponent = 8
    for k_ in ('/DecodeParms', '/Decode'):
        if k_ in ximg:
            del ximg[k_]
    return ximg


def erase(pdf, pi, rects, **kw):
    """Erase visible text/paths and drop pending invisible-text entries there."""
    og = pdf.pages[pi].objgen
    keep = []
    for ent in LOG:
        pid, o, x, y, t, s = ent
        if pid == id(pdf) and o == og and any(r[0] <= x + 1 <= r[2] and r[1] <= y - s * 0.3 <= r[3] for r in rects):
            continue
        keep.append(ent)
    LOG[:] = keep
    return _erase(pdf, pi, rects, **kw)
