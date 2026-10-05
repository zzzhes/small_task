"""Renumber pages and rebuild the table of contents."""
import edit as E
import typeset as T
from edit import erase
from glyphlib import visible_subpaths

NAVY = (0.047059, 0.090196, 0.160784)


def number_glyphs(pdf, pi, rect):
    out = []
    for sp in visible_subpaths(pdf.pages[pi], 870.24):
        b = sp['bb']
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        if rect[0] <= cx <= rect[2] and rect[1] <= cy <= rect[3] and (b[2] - b[0]) < 12 and (b[3] - b[1]) < 12 \
                and sp.get('alpha', 1) < 0.99:
            out.append(sp)
    return out


def renumber(parts):
    k = 0
    changed = 0
    for p in sorted(parts):
        pdf = parts[p]
        for pi in range(len(pdf.pages)):
            k += 1
            left, right = 2 * k - 4, 2 * k - 3
            for side, rect, val in (('L', (40, 812, 100, 830), left), ('R', (1150, 812, 1210, 830), right)):
                gl = number_glyphs(pdf, pi, rect)
                if not gl:
                    continue
                x0 = min(s['bb'][0] for s in gl)
                x1 = max(s['bb'][2] for s in gl)
                col = gl[0]['color'][:3]
                a = gl[0]['alpha']
                erase(pdf, pi, [rect])
                txt = str(val)
                if side == 'L':
                    T.draw(pdf, pi, 44.4, 826.0, txt, 'R', 14, col, alpha=a)
                else:
                    T.draw(pdf, pi, 1203.6, 826.0, txt, 'R', 14, col, alpha=a, align='right')
                E.LOG.append((id(pdf), pdf.pages[pi].objgen, 44.4 if side == 'L' else 1203.6 - T.width(txt, 'R', 14), 826.0, txt, 14))
                changed += 1
    return k, changed


# ------------------------------------------------------------------ TOC
SEP = (0.883654, 0.883654, 0.883654)


def rect_fill(pdf, pi, r, color):
    x0, y0, x1, y1 = r
    s = 'q %.4f %.4f %.4f rg %.3f %.3f %.3f %.3f re f Q\n' % (color[0], color[1], color[2], x0, 870.24 - y1, x1 - x0, y1 - y0)
    pdf.pages[pi].contents_add(pdf.make_stream(s.encode()), prepend=False)


def build_column(pdf, pi, spdf, spi, col, blocks, pitch):
    """col: dict(label=(x0,x1), bar=(x0,x1), x=, right=); blocks: list of dict(
       label_src_top=, color=, rows=[(title, num)])"""
    y = 109.5
    for b in blocks:
        top = y - 15.5
        # label shapes moved from source
        lx0, lx1 = col['label']
        dy = top - b['label_src_top']
        E.copy_shapes(pdf, pi, (lx0, b['label_src_top'] - 2, lx1, b['label_src_top'] + 60), 0, dy,
                      src_pi=spi, src_pdf=spdf)
        if b.get('suffix'):
            E.add_suffix(pdf, pi, (lx0, top - 4, lx1, top + 60))
        for j, lt in enumerate(b.get('label', [])):
            E.LOG.append((id(pdf), pdf.pages[pi].objgen, lx0 + 6, top + 20 + 24 * j, lt, 20))
        for i, (title, num) in enumerate(b['rows']):
            yy = y + i * pitch
            E.put(pdf, pi, col['x'], yy, title, 'R', 12, NAVY)
            T.draw(pdf, pi, col['right'], yy, str(num), 'R', 12, NAVY, alpha=0.5, align='right')
            E.LOG.append((id(pdf), pdf.pages[pi].objgen, col['right'] - T.width(str(num), 'R', 12), yy, str(num), 12))
            rect_fill(pdf, pi, (col['x'], yy + 7, col['right'], yy + 8), SEP)
        last = y + (len(b['rows']) - 1) * pitch
        rect_fill(pdf, pi, (col['bar'][0], top, col['bar'][1], last + 7.5), b['color'])
        y = last + pitch + 20
    return y - pitch - 20
