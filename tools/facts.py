"""Round 6: drop staff and revenue, put the founding year (from the table) on every startup spread."""
import csv
import re

import numpy as np
import pikepdf

import cat
import edit as E
import reflow as R
import typeset as T

SKIP = {1, 2, 3, 4, 26, 48, 72, 89, 106}          # cover, TOC, section dividers, summit page
NAVY = (0.047059, 0.090196, 0.160784)


def years():
    rows = list(csv.reader(open('years.csv', encoding='utf-8-sig', newline='')))[1:]
    return [(r[1].strip(), r[2].strip()) for r in rows]


def page_lines(pdf, pi):
    """Text lines of the page: remaining text layer + pending invisible entries (our own text)."""
    fp = R._single(pdf, pi)
    out = []
    for b in fp.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            t = ''.join(s['text'] for s in l['spans']).strip()
            if t:
                out.append(dict(t=t, x0=l['bbox'][0], x1=l['bbox'][2], y=l['spans'][0]['origin'][1],
                                s=l['spans'][0]['size']))
    og = pdf.pages[pi].objgen
    for pid, o, x, y, t, s in E.LOG:
        if pid == id(pdf) and o == og and t.strip():
            w = max(T.width(t, 'R', s), T.width(t, 'H', s)) if not T.missing(t, 'H') else T.width(t, 'R', s)
            out.append(dict(t=t.strip(), x0=x, x1=x + w, y=y, s=s))
    out.sort(key=lambda l: (l['y'], l['x0']))
    return out, fp


def _col(pdf, pi, rects, default):
    for r in rects:
        try:
            return E.color_in(pdf, pi, r)
        except ValueError:
            pass
    return default


def rect_of(l, pad=1.0):
    return (l['x0'] - pad, l['y'] - 0.95 * l['s'], l['x1'] + pad, l['y'] + 0.3 * l['s'])


def trim_header(pdf, pi, L, fp):
    """'ПРОИЗВОДСТВО И ШТАТ' -> 'ПРОИЗВОДСТВО' (keep the original glyphs, cut the tail)."""
    h = [l for l in L if 'штат' in l['t'].lower() and 130 < l['y'] < 148 and 680 < l['x0'] < 700]
    if not h:
        return False
    h = h[0]
    a = R._arr(fp)
    Z = R.Z
    band = a[int((h['y'] - 11) * Z):int((h['y'] + 1) * Z), int(685 * Z):int(965 * Z)]
    bg = np.median(band.reshape(-1, 3), 0)
    ink = (np.abs(band - bg).sum(2) > 80).any(0)
    xs = np.nonzero(ink)[0] / Z + 685
    end1 = None
    for p, q in zip(xs, xs[1:]):
        if q - p > 4.0:
            end1 = p
            break
    tail_end = xs[xs < 965].max()
    if end1 is None or end1 > 860:
        print('  header gap not found', end1)
        return False
    cat.erase(pdf, pi, [(end1 + 1.5, h['y'] - 12, min(tail_end + 1.5, 968), h['y'] + 3)], text_layer=False, max_wh=30)
    cat.remove_text_pdf(pdf, pi, [rect_of(h)])
    E.LOG[:] = [e for e in E.LOG if not (e[0] == id(pdf) and e[1] == pdf.pages[pi].objgen and 'штат' in e[4].lower())]
    E.LOG.append((id(pdf), pdf.pages[pi].objgen, 685.0, h['y'], 'ПРОИЗВОДСТВО', 14))
    return True


def drop_staff(pdf, pi, L):
    st = [l for l in L if re.search(r'\d\s*человек', l['t']) and 150 < l['y'] < 175 and l['x0'] > 683]
    for l in st:
        right = [m for m in L if abs(m['y'] - l['y']) < 2 and m['x0'] > l['x1'] + 2 and m['x0'] < 965]
        if right:
            print('  WARN item right of staff:', right[0]['t'])
        E.erase(pdf, pi, [rect_of(l), (l['x0'] - 27, l['y'] - 16, l['x0'] - 1, l['y'] + 6)], max_wh=26)
    return len(st)


def year_block(pdf, pi, x, y, year, col, hdr_src):
    spdf, spi = hdr_src
    E.copy_shapes(pdf, pi, (683, 292, 800, 330), x - 685, y - 308, src_pi=spi, src_pdf=spdf, color=col)
    og = pdf.pages[pi].objgen
    E.LOG.append((id(pdf), og, x, y, 'ГОД', 14))
    E.LOG.append((id(pdf), og, x, y + 17, 'ОСНОВАНИЯ', 14))
    E.put(pdf, pi, x, y + 43, year, 'H', 16, col)


def facts_pass(parts, hdr_src):
    ys = years()
    pages = [(p, i) for p in sorted(parts) for i in range(len(parts[p].pages))]
    starts = [pi for g, pi in enumerate(pages, 1) if g not in SKIP]
    assert len(starts) == len(ys) == 97, (len(starts), len(ys))
    report = []
    for (p, i), (name, year) in zip(starts, ys):
        pdf = parts[p]
        L, fp = page_lines(pdf, i)
        n_staff = drop_staff(pdf, i, L)
        hdr = trim_header(pdf, i, L, fp)
        ask = [l for l in L if l['t'].lower().startswith('запрос') and 680 < l['x0'] < 700]
        ask_y = ask[0]['y'] if ask else 543
        rev = [l for l in L if l['t'].lower().startswith('выручка') and 680 < l['x0'] < 700]
        yr = [l for l in L if 'основания' in l['t'].lower() and l['x0'] > 680]
        act = ''
        if rev:
            ry = rev[0]['y']
            col = _col(pdf, i, [rect_of(rev[0])], None)
            body = [l for l in L if ry - 1 <= l['y'] < ask_y - 12 and 683 <= l['x0'] < 860
                    and not l['t'].lower().startswith(('год', 'запрос'))]
            # second speaker block (x 755) is not revenue
            body = [l for l in body if l['x0'] < 700 or (l['t'].lower() in ('млн', 'тыс.', 'млрд') or l['t'][:1].isdigit() or 'кв' in l['t'])]
            last = max(l['y'] for l in body)
            x1 = max(l['x1'] for l in body)
            if col is None:
                col = _col(pdf, i, [rect_of(a) for a in ask], NAVY)
            E.erase(pdf, i, [(683, ry - 15, x1 + 12, last + 6)], max_wh=40)
            act = 'revenue removed'
            if year:
                year_block(pdf, i, 685.0, ry, year, col, hdr_src)
                act += ', year ' + year
        elif yr:
            h = yr[0]
            dig = [l for l in L if re.fullmatch(r'\d{4}', l['t']) and h['y'] < l['y'] < h['y'] + 45 and abs(l['x0'] - h['x0']) < 6]
            if dig and year and dig[0]['t'] != year:
                d = dig[0]
                col = _col(pdf, i, [rect_of(d)], NAVY)
                E.erase(pdf, i, [rect_of(d)])
                E.put(pdf, i, d['x0'], d['y'], year, 'H', d['s'], col)
                act = 'year %s -> %s' % (dig[0]['t'], year)
            else:
                act = 'year kept %s' % (dig[0]['t'] if dig else '?')
        elif year:
            busy = [l for l in L if 290 < l['y'] < 370 and 683 <= l['x0'] < 860]
            if busy:
                act = 'NO SPACE for year (%s)' % busy[0]['t']
            else:
                a = R._arr(fp)
                bg = a[int(300 * R.Z), int(690 * R.Z)]
                bga = a[int((ask_y - 20) * R.Z), int(690 * R.Z)]
                if np.abs(bg - bga).sum() < 30:
                    col = _col(pdf, i, [rect_of(x) for x in ask], NAVY)
                else:
                    ph = [l for l in L if l['t'].lower().startswith('производство')]
                    col = _col(pdf, i, [(684, 125, 800, 143)] + [rect_of(x) for x in ph], NAVY)
                year_block(pdf, i, 685.0, 308.0, year, col, hdr_src)
                act = 'year added ' + year
        else:
            act = 'no year in table'
        report.append((name, n_staff, hdr, act))
        print('facts', name, '| staff', n_staff, '| header', hdr, '|', act)
    return report
