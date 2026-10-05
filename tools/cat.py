"""Helpers for editing catalog spreads (Figma export, Type3 text)."""
import pikepdf
import pymupdf as fitz

FD = '/tmp/claude-0/-home-user-small-task/01d9064f-fcc0-5c7c-99c9-dd8b7cd80bb4/scratchpad/font/sbsans_2026/'
FONTS = {
    'reg': FD + 'SBSansText-Regular.ttf',
    'semi': FD + 'SBSansText-Semibold.ttf',
    'bold': FD + 'SBSansText-Bold.ttf',
    'head': FD + 'SBSansDisplay-ExtendedSemibold.ttf',
    'dreg': FD + 'SBSansDisplay-Regular.ttf',
    'dsemi': FD + 'SBSansDisplay-SemiBold.ttf',
}
_fcache = {}


def font(key):
    if key not in _fcache:
        _fcache[key] = fitz.Font(fontfile=FONTS[key])
    return _fcache[key]


def tj_items(pdf_page, height):
    """Yield (index_of_TJ, x, y_top_down) for each TJ in page content."""
    ops = pikepdf.parse_content_stream(pdf_page)
    stack = [(0.0, 0.0)]
    cur = (0.0, 0.0)
    tm = (0.0, 0.0)
    res = []
    for i, o in enumerate(ops):
        op = str(o.operator)
        if op == 'q':
            stack.append(cur)
        elif op == 'Q':
            cur = stack.pop()
        elif op == 'cm':
            a, b, c, d, e, f = [float(x) for x in o.operands]
            cur = (cur[0] + e, cur[1] + f)
        elif op == 'Tm':
            tm = (float(o.operands[4]), float(o.operands[5]))
        elif op == 'TJ' or op == 'Tj':
            x = cur[0] + tm[0]
            y = height - (cur[1] + tm[1])
            res.append((i, x, y))
    return ops, res


def remove_text_pdf(pdf, page_index, rects):
    pg = pdf.pages[page_index]
    h = float(pg.mediabox[3])
    ops, items = tj_items(pg, h)
    kill = set()
    for i, x, y in items:
        for r in rects:
            if r[0] <= x <= r[2] and r[1] <= y <= r[3]:
                kill.add(i)
    new = [o for i, o in enumerate(ops) if i not in kill]
    pg.obj.Contents = pdf.make_stream(pikepdf.unparse_content_stream(new))
    return len(kill)


def text_len(text, key, size, tracking=0.0):
    f = font(key)
    return f.text_length(text, size) + tracking * max(len(text) - 1, 0)


def draw(page, x, y, text, key, size, color, tracking=0.0, align='left'):
    """Draw text with baseline at (x,y); tracking in points per char."""
    f = font(key)
    name = 'SB' + key
    page.insert_font(fontname=name, fontfile=FONTS[key])
    w = text_len(text, key, size, tracking)
    if align == 'right':
        x -= w
    elif align == 'center':
        x -= w / 2
    if not tracking:
        page.insert_text((x, y), text, fontname=name, fontsize=size, color=color)
        return w
    cx = x
    for ch in text:
        if ch != ' ':
            page.insert_text((cx, y), ch, fontname=name, fontsize=size, color=color)
        cx += f.text_length(ch, size) + tracking
    return w


def hexc(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def _mul(m, n):
    a, b, c, d, e, f = m
    A, B, C, D, E, F = n
    return (a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D,
            e * A + f * C + E, e * B + f * D + F)


def _pt(m, x, y):
    return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])


PATH_OPS = {'m', 'l', 'c', 'v', 'y', 'h', 're'}
FILL_OPS = {'f', 'F', 'f*', 'B', 'B*', 'b', 'b*'}


def filter_paths(ops, base, height, test):
    """Drop filled subpaths for which test(bbox_fitz) is True.

    base: CTM of the stream (page space). Returns (new_ops, n_removed)."""
    out = []
    stack = []
    ctm = base
    sub = []      # current subpath ops (in order)
    subs = []     # list of (ops, bbox)
    removed = 0

    def flush_sub():
        nonlocal sub
        if sub:
            xs, ys = [], []
            for o in sub:
                nums = [float(v) for v in o.operands]
                if str(o.operator) == 're':
                    x, y, w, h = nums
                    pts = [(x, y), (x + w, y + h)]
                else:
                    pts = list(zip(nums[0::2], nums[1::2]))
                for (px, py) in pts:
                    X, Y = _pt(ctm, px, py)
                    xs.append(X)
                    ys.append(height - Y)
            bb = (min(xs), min(ys), max(xs), max(ys)) if xs else None
            subs.append((sub, bb))
            sub = []

    for o in ops:
        op = str(o.operator)
        if op in PATH_OPS:
            if op in ('m', 're'):
                flush_sub()
            sub.append(o)
            if op == 're':
                flush_sub()
            continue
        if op in FILL_OPS or op in ('S', 's', 'n', 'W', 'W*'):
            flush_sub()
            if op in ('W', 'W*'):
                # clip: keep everything; W is followed by n or paint
                for s, bb in subs:
                    out.extend(s)
                subs = []
                out.append(o)
                continue
            kept = []
            for s, bb in subs:
                if op in FILL_OPS and bb and test(bb):
                    removed += 1
                else:
                    kept.extend(s)
            subs = []
            if kept or op == 'n':
                out.extend(kept)
                out.append(o)
            continue
        if op == 'q':
            stack.append(ctm)
        elif op == 'Q':
            ctm = stack.pop()
        elif op == 'cm':
            ctm = _mul(tuple(float(v) for v in o.operands), ctm)
        out.append(o)
    return out, removed


def in_rects(rects, max_wh=None):
    def t(bb):
        if max_wh and (bb[2] - bb[0] > max_wh or bb[3] - bb[1] > max_wh):
            return False
        cx, cy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
        return any(r[0] <= cx <= r[2] and r[1] <= cy <= r[3] for r in rects)
    return t


def _erase_form(xo, base, h, rects, max_wh, depth=0):
    xops = pikepdf.parse_content_stream(xo)
    new, n = filter_paths(xops, base, h, in_rects(rects, max_wh))
    if n:
        xo.write(pikepdf.unparse_content_stream(new))
    if depth > 4:
        return n
    res = xo.get('/Resources', {})
    xd = res.get('/XObject', {}) if res else {}
    stack, ctm = [], base
    for o in new:
        op = str(o.operator)
        if op == 'q':
            stack.append(ctm)
        elif op == 'Q':
            ctm = stack.pop()
        elif op == 'cm':
            ctm = _mul(tuple(float(v) for v in o.operands), ctm)
        elif op == 'Do' and o.operands[0] in xd:
            sub = xd[o.operands[0]]
            if sub.get('/Subtype') == '/Form':
                m = tuple(float(v) for v in sub.get('/Matrix', [1, 0, 0, 1, 0, 0]))
                n += _erase_form(sub, _mul(m, ctm), h, rects, max_wh, depth + 1)
    return n


def erase(pdf, page_index, rects, text_layer=True, max_wh=None):
    """Erase visible outline-text (paths in page forms) + invisible Type3 text."""
    pg = pdf.pages[page_index]
    h = float(pg.mediabox[3])
    total = 0
    pops = pikepdf.parse_content_stream(pg)
    # find CTM at each Do
    stack, ctm = [], (1, 0, 0, 1, 0, 0)
    for o in pops:
        op = str(o.operator)
        if op == 'q':
            stack.append(ctm)
        elif op == 'Q':
            ctm = stack.pop()
        elif op == 'cm':
            ctm = _mul(tuple(float(v) for v in o.operands), ctm)
        elif op == 'Do':
            name = o.operands[0]
            xo = pg.Resources.XObject[name]
            if xo.Subtype != '/Form':
                continue
            m = tuple(float(v) for v in xo.get('/Matrix', [1, 0, 0, 1, 0, 0]))
            total += _erase_form(xo, _mul(m, ctm), h, rects, max_wh)
    # page-level paths (glyphs drawn by earlier edits)
    new, n = filter_paths(pops, (1, 0, 0, 1, 0, 0), h, in_rects(rects, max_wh))
    if n:
        pg.obj.Contents = pdf.make_stream(pikepdf.unparse_content_stream(new))
        total += n
    if text_layer:
        remove_text_pdf(pdf, page_index, rects)
    return total


def path_boxes(pdf, page_index, rect):
    """Return bboxes (fitz coords) of filled subpaths whose centre is in rect."""
    pg = pdf.pages[page_index]
    h = float(pg.mediabox[3])
    found = []

    def t(bb):
        if in_rects([rect])(bb):
            found.append(bb)
        return False
    pops = pikepdf.parse_content_stream(pg)
    stack, ctm = [], (1, 0, 0, 1, 0, 0)
    for o in pops:
        op = str(o.operator)
        if op == 'q':
            stack.append(ctm)
        elif op == 'Q':
            ctm = stack.pop()
        elif op == 'cm':
            ctm = _mul(tuple(float(v) for v in o.operands), ctm)
        elif op == 'Do':
            xo = pg.Resources.XObject[o.operands[0]]
            if xo.Subtype != '/Form':
                continue
            m = tuple(float(v) for v in xo.get('/Matrix', [1, 0, 0, 1, 0, 0]))
            filter_paths(pikepdf.parse_content_stream(xo), _mul(m, ctm), h, t)
    return found


def image_placements(pdf, page_index):
    """List (form_name, img_name, img_obj, placed_rect_fitz, clip_bbox_fitz)."""
    pg = pdf.pages[page_index]
    h = float(pg.mediabox[3])
    out = []
    pops = pikepdf.parse_content_stream(pg)

    def walk(xo, base, fname):
        ops = pikepdf.parse_content_stream(xo)
        st, c = [], base
        clip = None
        pts = []
        for o in ops:
            op = str(o.operator)
            if op in ('m', 'l', 'c', 're'):
                nums = [float(v) for v in o.operands]
                if op == 're':
                    x, y, w, hh = nums
                    nums = [x, y, x + w, y + hh]
                for px, py in zip(nums[0::2], nums[1::2]):
                    X, Y = _pt(c, px, py)
                    pts.append((X, h - Y))
            elif op in ('W', 'W*'):
                if pts:
                    clip = (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))
            elif op in ('n', 'f', 'f*', 'S', 'B', 'b'):
                pts = []
            elif op == 'q':
                st.append((c, clip))
            elif op == 'Q':
                c, clip = st.pop()
            elif op == 'cm':
                c = _mul(tuple(float(v) for v in o.operands), c)
            elif op == 'Do':
                nm = o.operands[0]
                x = xo.Resources.XObject[nm]
                if x.Subtype == '/Image':
                    p0 = _pt(c, 0, 0)
                    p1 = _pt(c, 1, 1)
                    r = (min(p0[0], p1[0]), h - max(p0[1], p1[1]), max(p0[0], p1[0]), h - min(p0[1], p1[1]))
                    out.append((fname, str(nm), x, r, clip))
                elif x.Subtype == '/Form':
                    m = tuple(float(v) for v in x.get('/Matrix', [1, 0, 0, 1, 0, 0]))
                    walk(x, _mul(m, c), fname + '/' + str(nm))
    stack, ctm = [], (1, 0, 0, 1, 0, 0)
    for o in pops:
        op = str(o.operator)
        if op == 'q':
            stack.append(ctm)
        elif op == 'Q':
            ctm = stack.pop()
        elif op == 'cm':
            ctm = _mul(tuple(float(v) for v in o.operands), ctm)
        elif op == 'Do':
            xo = pg.Resources.XObject[o.operands[0]]
            if xo.Subtype == '/Form':
                m = tuple(float(v) for v in xo.get('/Matrix', [1, 0, 0, 1, 0, 0]))
                walk(xo, _mul(m, ctm), str(o.operands[0]))
            elif xo.Subtype == '/Image':
                p0 = _pt(ctm, 0, 0)
                p1 = _pt(ctm, 1, 1)
                r = (min(p0[0], p1[0]), h - max(p0[1], p1[1]), max(p0[0], p1[0]), h - min(p0[1], p1[1]))
                out.append(('page', str(o.operands[0]), xo, r, None))
    return out
