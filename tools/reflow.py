"""Re-wrap left-page body paragraphs that run into photos or shapes.

Paragraphs are rebuilt from the invisible text layer (bold words detected by
glyph signature), erased and typeset again with a width that keeps GAP pt of
air before the nearest obstacle. Bullet dots move with their paragraphs.
"""
import io
import pickle

import numpy as np
import pikepdf
import pymupdf as fitz

import cat
import edit as E

S = pickle.load(open('styles.pkl', 'rb'))['style']
SIG_B = set(S['B'].values()) - set(S['R'].values())
SIG_H = set(S['H'].values())
GAP = 12.0
Z = 3


HEADS = {'инновационность', 'ключевые преимущества', 'внедрения', 'эффект от внедрения', 'запрос', 'выручка',
         'производство и штат', 'меры поддержки', 'год основания', 'год', 'основания', 'достижения'}


def _single(pdf, pi, rects=None):
    tmp = pikepdf.new()
    tmp.pages.append(pdf.pages[pi])
    if rects:
        cat.erase(tmp, 0, rects, text_layer=False, max_wh=40)
    b = io.BytesIO()
    tmp.save(b)
    return fitz.open('pdf', b.getvalue())[0]


def _arr(fp):
    pix = fp.get_pixmap(matrix=fitz.Matrix(Z, Z))
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3].astype(int)


def _render_clean(pdf, pi, rects):
    return _arr(_single(pdf, pi, rects))


def _bg(a, x, y, size):
    return tuple(int(v) for v in a[int((y - 0.4 * size) * Z), int((x + 0.5) * Z)])


def obstacle(a, x0, y, size, bg=None):
    if bg is None:
        bg = _bg(a, x0, y, size)
        x0 += 1
    """First x right of x0 where the band around baseline y differs from bg."""
    band = a[int((y - 0.85 * size) * Z):int((y + 0.3 * size) * Z), int(x0 * Z):]
    diff = (np.abs(band - np.array(bg)).sum(2) > 40).any(0)
    idx = np.nonzero(diff)[0]
    return x0 + (idx[0] / Z if len(idx) else 1e9)


def _lines(fp, area):
    out = []
    for b in fp.get_text('rawdict')['blocks']:
        for l in b.get('lines', []):
            chars = [c for s in l['spans'] for c in s['chars']]
            if not chars:
                continue
            size = l['spans'][0]['size']
            # split at large gaps (separate frames on one baseline)
            groups, cur = [], [chars[0]]
            for p, c in zip(chars, chars[1:]):
                if c['bbox'][0] - p['bbox'][2] > 2.5 * size:
                    groups.append(cur)
                    cur = []
                cur.append(c)
            groups.append(cur)
            for g in groups:
                txt = ''.join(c['c'] for c in g)
                if not txt.strip():
                    continue
                while g and not g[-1]['c'].strip():
                    g = g[:-1]
                x0, y = g[0]['origin']
                out.append(dict(text=txt, x0=x0, y=y, x1=g[-1]['bbox'][2], size=size, chars=g))
    ls = [l for l in out if area[0] <= l['x0'] <= area[2] and area[1] <= l['y'] <= area[3]
          and 11.5 <= l['size'] <= 14.5 and l['text'].strip().lower().replace('\xa0', ' ') not in HEADS]
    ls.sort(key=lambda l: (l['y'], l['x0']))
    return ls


def _ink_x1(orig, a, l, obs):
    """Right edge of the visible glyphs of line l (layer metrics differ for bold)."""
    s = l['size']
    y0, y1 = int((l['y'] - 0.8 * s) * Z), int((l['y'] + 0.2 * s) * Z)
    x0 = int(l['x0'] * Z)
    x1 = int(min(obs - 0.5, l['x1'] + 3 * s) * Z)
    if x1 <= x0:
        return l['x1']
    d = (np.abs(orig[y0:y1, x0:x1] - a[y0:y1, x0:x1]).sum(2) > 60).any(0)
    idx = np.nonzero(d)[0]
    return max(l['x1'], (x0 + idx[-1]) / Z) if len(idx) else l['x1']


def _lines_all(fp):
    out = []
    for b in fp.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            t = ''.join(sp['text'] for sp in l['spans']).strip()
            if t:
                out.append(dict(text=t, x0=l['bbox'][0], x1=l['bbox'][2], y=l['spans'][0]['origin'][1],
                                size=l['spans'][0]['size']))
    return out


def paragraphs(pdf, pi, area):
    fp = _single(pdf, pi)
    ls = _lines(fp, area)
    dots = cat.path_boxes(pdf, pi, (area[0], area[1] - 20, area[0] + 24, area[3]))
    dots = [b for b in dots if 3 < b[2] - b[0] < 14 and 3 < b[3] - b[1] < 14]
    paras = []
    for l in ls:
        has_dot = l['x0'] > area[0] + 10 and any(b[1] - 4 < l['y'] - 0.35 * l['size'] < b[3] + 4 for b in dots)
        prev = paras[-1]['lines'][-1] if paras else None
        if (prev is None or has_dot or abs(l['x0'] - prev['x0']) > 2 or l['y'] - prev['y'] > 1.5 * l['size']
                or abs(l['size'] - prev['size']) > 0.1):
            paras.append(dict(lines=[l], dot=has_dot))
        else:
            paras[-1]['lines'].append(l)
    orig = _arr(fp)
    ink = orig.sum(2) / 3.0
    alls = _lines_all(fp)
    for p in paras:
        p['all'] = alls
        p['words'] = _words(p, ink)
        p['orig'] = orig
    return paras, dots


def _words(p, ink):
    words = []
    for k, l in enumerate(p['lines']):
        cur = []
        for c in l['chars'] + [None]:
            if c is None or c['c'] in (' ', '\xa0', '\u2028', '\n'):
                if cur:
                    t = ''.join(ch['c'] for ch in cur)
                    x0, x1 = cur[0]['bbox'][0], cur[-1]['bbox'][2]
                    s = l['size']
                    sub = ink[int((l['y'] - 0.72 * s) * Z):int((l['y'] + 0.02 * s) * Z), int(x0 * Z):int(x1 * Z)]
                    dens = (255 - sub).sum() / max(1, sub.shape[1]) / s if sub.size else 0
                    words.append([t, dens, False])
                cur = []
            else:
                cur.append(c)
        if words and k < len(p['lines']) - 1 and words[-1][0].endswith(('-', '‑')):
            words[-1][2] = True
    letters = lambda t: sum(ch.isalnum() for ch in t)
    raw = [w[1] > 180 for w in words]
    for k, w in enumerate(words):
        if letters(w[0]) <= 1:
            b = 0 < k < len(words) - 1 and raw[k - 1] and raw[k + 1]
        else:
            b = raw[k]
        w[1] = 'B' if b else 'R'
    # a bold lead-in ends with a colon: fill gaps of thin words like «(Pay-as-you-go):»
    if words and words[0][1] == 'B':
        for k, w in enumerate(words[:10]):
            if w[0].endswith(':'):
                if sum(x[1] == 'B' for x in words[:k + 1]) >= (k + 1) / 2:
                    for x in words[:k + 1]:
                        x[1] = 'B'
                break
    return words


def runs_of(para):
    words = para['words']
    runs = []
    k = 0
    while k < len(words):
        t, st, glue = words[k]
        while glue and k + 1 < len(words):
            k += 1
            t2, st2, glue = words[k]
            t += t2
        runs.append((t + ' ', st))
        k += 1
    if runs:
        runs[-1] = (runs[-1][0].rstrip(), runs[-1][1])
    return runs


def reflow(pdf, pi, area, need=14.0, bg=None, force=None, log=''):
    """Rewrap paragraphs in area whose lines come within `need` pt of an obstacle."""
    paras, dots = paragraphs(pdf, pi, area)
    if not paras:
        return 0
    rects = [E.line_rect(l, 1.0) for p in paras for l in p['lines']]
    a = _render_clean(pdf, pi, rects + [(b[0] - 1, b[1] - 1, b[2] + 1, b[3] + 1) for b in dots])
    bad = []
    for n, p in enumerate(paras):
        p['obs'] = [obstacle(a, l['x0'], l['y'], l['size'], bg) for l in p['lines']]
        tight = min(o - _ink_x1(p['orig'], a, l, o) for o, l in zip(p['obs'], p['lines']))
        if tight < need or (force and n in force):
            bad.append(n)
    if not bad:
        return 0
    snap = pikepdf.new()
    snap.pages.append(pdf.pages[pi])
    plan = []
    shift = 0.0
    prev_end = None
    for n in range(bad[0], len(paras)):
        p = paras[n]
        l0 = p['lines'][0]
        size = l0['size']
        if prev_end is not None and l0['y'] - prev_end > 2.2 * size:
            if shift > 0 and prev_end + shift > l0['y'] - 1.6 * size:
                print('  WARN reflow', log, 'block grew into next element at', round(l0['y']))
            shift = 0.0
        prev_end = p['lines'][-1]['y']
        if n not in bad and abs(shift) < 0.01:
            continue
        lead = (p['lines'][1]['y'] - l0['y']) if len(p['lines']) > 1 else size * 1.215
        x0 = l0['x0']
        oldw = max(l['x1'] - l['x0'] for l in p['lines'])
        if n in bad:
            def mw(yy, x0=x0, size=size, oldw=oldw):
                return min(oldw + 1.0, obstacle(a, x0, yy, size, bg) - x0 - GAP)
        else:
            mw = oldw + 1.0
        runs = runs_of(p)
        cnt = len(E.rich_wrap([(E.typo(t), st) for t, st in runs], size,
                              (lambda i, mw=mw, y0=l0['y'] + shift, lead=lead: mw(y0 + i * lead)) if callable(mw) else mw))
        if cnt > len(p['lines']):
            last_new = l0['y'] + shift + (cnt - 1) * lead
            below = [l for l in p['all'] if l['y'] > p['lines'][-1]['y'] + 1 and l['x0'] < x0 + oldw and l['x1'] > x0
                     and not any(l['y'] == q['y'] and abs(l['x0'] - q['x0']) < 1 for pp in paras for q in pp['lines'])]
            if below:
                nb = min(below, key=lambda l: l['y'])
                if last_new + 0.3 * size > nb['y'] - 0.8 * nb['size'] - 3 and nb['size'] > 14.5:
                    print('  SKIP reflow', log, 'would hit', nb['text'][:20])
                    continue
        dr = [b for b in dots if b[1] - 4 < l0['y'] - 0.35 * size < b[3] + 4] if p['dot'] else []
        plan.append(dict(p=p, x0=x0, y0=l0['y'] + shift, size=size, lead=lead, mw=mw, runs=runs, dr=dr, shift=shift,
                         col=E.color_in(pdf, pi, E.line_rect(l0))))
        shift += (cnt - len(p['lines'])) * lead
    rects = [E.line_rect(l, 1.0) for it in plan for l in it['p']['lines']]
    E.erase(pdf, pi, rects)
    moved = [it for it in plan if it['dr'] and abs(it['shift']) > 0.01]
    dot_rects = [(b[0] - 0.5, b[1] - 0.5, b[2] + 0.5, b[3] + 0.5) for it in moved for b in it['dr']]
    if dot_rects:
        cat.erase(pdf, pi, dot_rects, text_layer=False)
    for it in moved:
        for b in it['dr']:
            E.copy_shapes(pdf, pi, (b[0] - 0.5, b[1] - 0.5, b[2] + 0.5, b[3] + 0.5), 0, it['shift'],
                          src_pi=0, src_pdf=snap)
    for it in plan:
        E.put_rich(pdf, pi, it['x0'], it['y0'], it['runs'], it['size'], it['col'], it['mw'], it['lead'])
    print('reflow', log, 'paras', bad, [paras[n]['lines'][0]['text'][:25] for n in bad])
    return True


def limits(pdf, pi):
    """Width limiter for new text: LIM(x, size, default) -> callable(baseline)."""
    a = _render_clean(pdf, pi, [])

    def lim(x, size, default):
        def f(yy):
            bg = tuple(int(v) for v in a[int((yy - 0.4 * size) * Z), int((x + 0.5) * Z)])
            return min(default, obstacle(a, x + 1, yy, size, bg) - x - GAP)
        return f
    return lim
