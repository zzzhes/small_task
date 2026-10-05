"""Build new catalog spreads from template spreads."""
import io
from PIL import Image, ImageDraw, ImageFont
import edit as E
import typeset as T
from cat import image_placements, FD
from edit import erase

ASI = ['Участник инвестиционного Демо-', 'дня конкурса брендов «Знай\xa0наших»']


def placeholder(w, h, label, bg=(226, 230, 237), fg=(150, 158, 172)):
    im = Image.new('RGBA', (w, h), bg + (255,))
    if label:
        d = ImageDraw.Draw(im)
        size = max(14, int(min(w, h) * 0.06))
        f = ImageFont.truetype(FD + 'SBSansDisplay-Regular.ttf', size)
        lines = label.split('\n')
        tot = len(lines) * size * 1.3
        y = (h - tot) / 2
        for ln in lines:
            tw = d.textlength(ln, font=f)
            d.text(((w - tw) / 2, y), ln, font=f, fill=fg + (255,))
            y += size * 1.3
    return im


def build(pdf, pi, spdf, spi, D):
    """D: dict with content + template geometry (see run.py)."""
    L = {l['text'].strip(): l for l in E.lines(spdf, spi)}
    col = {}
    for k, key in D['colors'].items():
        col[k] = E.color_in(spdf, spi, E.line_rect(L[key]))
    erase(pdf, pi, D['erase'])
    nav, tcol, rcol = col['body'], col['title'], col['right']
    # ---- left page
    nt, _ = E.put_par(pdf, pi, 44.4, 56.0, D['title'], 'H', 18, tcol, 545, 22)
    assert nt <= 2, ('title > 2 lines', D['title'])
    E.put_rich(pdf, pi, 44.0, 116.0, D['desc'], 14, nav, 255, 17)
    y = 305.0
    for runs in D['innov']:
        E.copy_shapes(pdf, pi, (42, 292, 62, 310), 0, y - 305.0, src_pi=spi, src_pdf=spdf)
        n, last = E.put_rich(pdf, pi, 66.0, y, runs, 14, nav, 234, 17)
        y = last + 22
    assert y < 540, ('innovation too long', y)
    for x, t in zip((77.0, 252.3, 427.7), D['adv']):
        n, last = E.put_par(pdf, pi, x, 566.0, t, 'R', 12, nav, 142, 14)
        assert last < 640, ('advantage too long', t)
    # implementations
    w = E.put(pdf, pi, 44.0, 696.0, D['impl_num'], 'H', 24, col['accent'])
    n, last = E.put_par(pdf, pi, 44.0, 712.0, D['impl_cap'], 'R', 12, nav, 250, 14)
    y = last + 26
    for t in D['impl']:
        E.copy_shapes(pdf, pi, D['impl_bullet'], 0, y - D['impl_bullet_base'], src_pi=spi, src_pdf=spdf)
        n, last = E.put_par(pdf, pi, 58.0, y, t, 'R', 12, nav, 236, 14)
        y = last + 20
    assert last < 812, ('impl too long', last)
    y = 686.0
    for t in D['effect']:
        E.copy_shapes(pdf, pi, D['eff_bullet'], 0, y - 686.0, src_pi=spi, src_pdf=spdf)
        n, last = E.put_par(pdf, pi, 322.0, y, t, 'R', 12, nav, 245, 14)
        y = last + 20
    assert last < 812, ('effect too long', last)
    # ---- right page
    for i, t in enumerate(D['company']):
        assert T.width(t, 'H', 18) < 390, t
        E.put(pdf, pi, 685.4, 56.0 + 22 * i, t, 'H', 18, rcol)
    sy = 82.0 + 22 * (len(D['company']) - 1)
    E.put_par(pdf, pi, 685.4, sy, D['subtitle'], 'R', 14, rcol, 375, 17)
    cw = T.width(D['city'], 'R', 12)
    icon = (756, 148, 779, 166)
    dx = max(0.0, 704.4 + cw + 10 - 758.0)
    if dx:
        erase(pdf, pi, [icon], text_layer=False)
        E.copy_shapes(pdf, pi, icon, dx, 0, src_pi=spi, src_pdf=spdf)
    E.put(pdf, pi, 704.4, 162.0, D['city'], 'R', 12, rcol)
    E.put(pdf, pi, 781.4 + dx, 162.0, D['staff'], 'R', 12, rcol)
    y = 162.0
    if D.get('sup_head'):
        E.put(pdf, pi, 974.0, 139.0, 'МЕРЫ ПОДДЕРЖКИ', 'H', 14, rcol, tracking=0.28)
    bsrc = D.get('sup_src', (spdf, spi))
    for item in D['support']:
        E.copy_shapes(pdf, pi, D['sup_bullet'], 0, y - 162.0, src_pi=bsrc[1], src_pdf=bsrc[0])
        for k, t in enumerate(item):
            E.put(pdf, pi, 988.0, y + 14 * k, t, 'R', 12, col['support'])
        y += 14 * (len(item) - 1) + 20
    E.put(pdf, pi, 755.4, 213.0, D['speaker'], 'B', 14, rcol)
    E.put(pdf, pi, 755.4, 229.0, D['role'], 'R', 12, rcol)
    y = D['rev_head'] + 27
    for yr, amt, note in D['revenue']:
        w = E.put(pdf, pi, 685.4, y, yr, 'H', 12, col['rev'])
        if note:
            E.put(pdf, pi, 685.4 + w + 3, y, note, 'R', 9, col['rev'])
        w = E.put(pdf, pi, 685.4, y + 21, amt, 'H', 16, col['rev'])
        E.put(pdf, pi, 685.4 + w, y + 21, '\xa0млн', 'H', 12, col['rev'])
        y += 57
    w = E.put(pdf, pi, 685.0, 582.0, D['ask_amt'], 'H', 24, col['ask'])
    E.put(pdf, pi, 685.0 + w, 582.0, '\xa0млн', 'H', 16, col['ask'])
    E.put_par(pdf, pi, 685.0, 602.0, D['ask_text'], 'R', 12, nav, 160, 14)
    # ---- pictures
    put_photos(pdf, pi, D)


def put_photos(pdf, pi, D):
    from PIL import Image
    imgs = image_placements(pdf, pi)
    ph = D.get('photos', {})
    for f, n, x, r, c in imgs:
        vr = c or r
        rw, rh = vr[2] - vr[0], vr[3] - vr[1]
        W, Hh = int(x.Width), int(x.Height)
        if rw < 80 and rh < 110:
            kind = 'speaker'
        elif rh < 40:
            kind = 'logo'
        elif vr[0] < 623:
            kind = 'left'
        else:
            kind = 'right'
        spec = ph.get(kind)
        if kind == 'logo' and D.get('logo_box'):
            E.replace_image(pdf, x, Image.new('RGB', (8, 8), (255, 255, 255)), 'cover')
            if '/SMask' in x:
                del x['/SMask']
            E.add_image(pdf, pi, Image.open(spec[0]), D['logo_box'], pad=0.02)
            continue
        if spec is None:
            if kind == 'logo':
                E.replace_image(pdf, x, wordmark(W, Hh, D['logo_text'], rw, rh), 'cover')
                if '/SMask' in x:
                    del x['/SMask']
            elif kind == 'speaker':
                E.replace_image(pdf, x, placeholder(W, Hh, ''), 'cover')
            else:
                E.replace_image(pdf, x, placeholder(W, Hh, D.get('photo_label', '')), 'cover')
            continue
        path, mode, focus = spec if len(spec) == 3 else (spec[0], spec[1], (0.5, 0.5))
        im = Image.open(path)
        bg = (255, 255, 255)
        if mode == 'contain' and im.mode in ('RGB',):
            px = im.convert('RGB').getpixel((2, 2))
            bg = px
        if kind == 'speaker' and D.get('speaker_clip'):
            c = D['speaker_clip']
        E.fit_image(pdf, x, im, r, c, mode=mode, focus=focus, bg=bg, pad=0.06 if mode == 'logo' else 0.0)


def wordmark(W, Hh, text, rw, rh, color=(12, 22, 40)):
    """White raster with centred bold wordmark; keeps aspect of placed rect."""
    im = Image.new('RGBA', (W, Hh), (255, 255, 255, 255))
    d = ImageDraw.Draw(im)
    sx = W / rw
    sy = Hh / rh
    # target cap height ~ 9pt in placed units
    size_pt = 15.0
    f = ImageFont.truetype(FD + 'SBSansDisplay-Bold.ttf', int(size_pt * sy))
    tw = d.textlength(text, font=f)
    # scale horizontally if pixel aspect differs
    tmp = Image.new('RGBA', (int(tw) + 4, int(size_pt * sy * 1.4)), (255, 255, 255, 0))
    ImageDraw.Draw(tmp).text((2, 0), text, font=f, fill=color + (255,))
    tmp = tmp.resize((max(1, int(tmp.width * sx / sy)), tmp.height), Image.LANCZOS)
    if tmp.width > W * 0.95:
        k = W * 0.95 / tmp.width
        tmp = tmp.resize((int(tmp.width * k), int(tmp.height * k)), Image.LANCZOS)
    bb = tmp.getbbox() or (0, 0, tmp.width, tmp.height)
    tmp = tmp.crop(bb)
    im.alpha_composite(tmp, ((W - tmp.width) // 2, (Hh - tmp.height) // 2))
    return im


def build_robo(pdf, pi, spdf, spi, D):
    """RoboProbeTest: Kinetronika template (g60)."""
    L = {l['text'].strip(): l for l in E.lines(spdf, spi)}
    nav = E.color_in(spdf, spi, E.line_rect(L['волокном']))
    tcol = E.color_in(spdf, spi, E.line_rect(L['КОМПОЗИТОВ']))
    rcol = E.color_in(spdf, spi, E.line_rect(L['и\xa0электроники']))
    acc = E.color_in(spdf, spi, E.line_rect(L['₽50']))
    sup = E.color_in(spdf, spi, E.line_rect(L['Участник Сбер500']))
    erase(pdf, pi, [(40, 38, 600, 84), (40, 100, 322, 270), (40, 288, 322, 470),
                    (75, 552, 222, 650), (250, 552, 398, 650), (425, 552, 600, 650),
                    (40, 650, 610, 815),
                    (683, 38, 1062, 125), (700, 148, 965, 168), (976, 148, 1210, 200),
                    (750, 198, 960, 236), (683, 295, 860, 360), (683, 552, 860, 800)])
    nt, _ = E.put_par(pdf, pi, 44.4, 56.0, D['title'], 'H', 18, tcol, 545, 22)
    assert nt <= 2, D['title']
    n_, last = E.put_rich(pdf, pi, 44.0, 116.0, D['desc'], 14, nav, 255, 17)
    hy = max(280.0, last + 30)
    if hy > 280.0:
        erase(pdf, pi, [(40, 268, 300, 284)])
        E.copy_shapes(pdf, pi, (40, 268, 300, 284), 0, hy - 280.0, src_pi=spi, src_pdf=spdf)
    y = hy + 25
    for runs in D['innov']:
        E.copy_shapes(pdf, pi, (42, 292, 62, 310), 0, y - 305.0, src_pi=spi, src_pdf=spdf)
        n_, last = E.put_rich(pdf, pi, 66.0, y, runs, 14, nav, 234, 17)
        y = last + 22
    assert last < 530, ('robo innov', last)
    for x, t in zip((77.0, 252.3, 427.7), D['adv']):
        n_, last = E.put_par(pdf, pi, x, 566.0, t, 'R', 12, nav, 134, 14)
        assert last < 650, t
    # implementations (header copied from a template with this block) + effect (header moved right)
    hp, hi = D['impl_head_src']
    E.copy_shapes(pdf, pi, (40, 650, 200, 668), 0, 0, src_pi=hi, src_pdf=hp)
    E.copy_shapes(pdf, pi, (40, 650, 300, 668), 264, 0, src_pi=spi, src_pdf=spdf)
    E.put(pdf, pi, 44.0, 696.0, D['impl_num'], 'H', 24, acc)
    n_, last = E.put_par(pdf, pi, 44.0, 712.0, D['impl_cap'], 'R', 12, nav, 250, 14)
    y = last + 22
    for t in D['impl']:
        E.copy_shapes(pdf, pi, (40, 674, 56, 690), 0, y - 686.0, src_pi=spi, src_pdf=spdf)
        n_, last = E.put_par(pdf, pi, 58.0, y, t, 'R', 12, nav, 236, 14)
        y = last + 18
    assert last < 813, ('robo impl', last)
    y = 686.0
    for t in D['effect']:
        E.copy_shapes(pdf, pi, (40, 674, 56, 690), 264, y - 686.0, src_pi=spi, src_pdf=spdf)
        n_, last = E.put_par(pdf, pi, 322.0, y, t, 'R', 12, nav, 262, 14)
        y = last + 18
    assert last < 813, ('robo effect', last)
    # right page
    E.put(pdf, pi, 685.4, 56.0, D['company'], 'H', 18, rcol)
    E.put_par(pdf, pi, 685.4, 82.0, D['subtitle'], 'R', 14, rcol, 375, 17)
    cw = E.put(pdf, pi, 704.4, 162.0, D['city'], 'R', 12, rcol)
    dx = 704.4 + cw + 10 - 874.4
    E.copy_shapes(pdf, pi, (872, 148, 893, 166), dx, 0, src_pi=spi, src_pdf=spdf)
    E.put(pdf, pi, 896.4 + dx, 162.0, D['staff'], 'R', 12, rcol)
    E.copy_shapes(pdf, pi, (970, 150, 986, 166), 0, 0, src_pi=spi, src_pdf=spdf)
    for k, t in enumerate(D['support']):
        E.put(pdf, pi, 988.0, 162.0 + 14 * k, t, 'R', 12, sup)
    E.put(pdf, pi, 755.4, 213.0, D['speaker'], 'B', 14, rcol)
    E.put(pdf, pi, 755.4, 229.0, D['role'], 'R', 12, rcol)
    w = E.put(pdf, pi, 685.0, 582.0, D['ask_amt'], 'H', 24, acc)
    E.put(pdf, pi, 685.0 + w, 582.0, '\xa0млн', 'H', 16, acc)
    E.put_par(pdf, pi, 685.0, 602.0, D['ask_text'], 'R', 12, nav, 160, 14)
    put_photos(pdf, pi, D)


def build_cropgen(pdf, pi, spdf, spi, D):
    """CropGen: Agavita template (g99)."""
    from PIL import Image
    L = {l['text'].strip(): l for l in E.lines(spdf, spi)}
    nav = E.color_in(spdf, spi, E.line_rect(L['упитанность и\xa0поведение']))
    tcol = E.color_in(spdf, spi, E.line_rect(L['с\xa0компьютерным зрением']))
    rcol = E.color_in(spdf, spi, E.line_rect(L['управления аквакультурой']))
    acc = E.color_in(spdf, spi, E.line_rect(L['760']))
    erase(pdf, pi, [(40, 38, 600, 84), (40, 100, 322, 270), (40, 288, 322, 470),
                    (75, 552, 222, 650), (250, 552, 398, 650), (425, 552, 600, 650),
                    (40, 680, 302, 815), (305, 675, 610, 815),
                    (683, 38, 1062, 125), (878, 36, 930, 70), (700, 148, 965, 168),
                    (750, 198, 960, 236), (683, 335, 760, 356), (683, 552, 860, 640)])
    nt, _ = E.put_par(pdf, pi, 44.4, 56.0, D['title'], 'H', 18, tcol, 545, 22)
    assert nt <= 2, D['title']
    E.put_rich(pdf, pi, 44.0, 116.0, D['desc'], 14, nav, 255, 17)
    y = 305.0
    for runs in D['innov']:
        E.copy_shapes(pdf, pi, (42, 292, 62, 310), 0, y - 305.0, src_pi=spi, src_pdf=spdf)
        n_, last = E.put_rich(pdf, pi, 66.0, y, runs, 14, nav, 234, 17)
        y = last + 22
    assert last < 530, ('cropgen innov', last)
    for x, t in zip((77.0, 252.3, 427.7), D['adv']):
        n_, last = E.put_par(pdf, pi, x, 566.0, t, 'R', 12, nav, 134, 14)
        assert last < 650, t
    w = E.put(pdf, pi, 44.0, 696.0, D['impl_num'], 'H', 24, acc)
    E.put(pdf, pi, 44.0 + w, 696.0, D['impl_unit'], 'H', 16, acc)
    n_, last = E.put_par(pdf, pi, 44.0, 712.0, D['impl_cap'], 'R', 12, nav, 250, 14)
    y = last + 26
    for t in D['impl']:
        E.copy_shapes(pdf, pi, (40, 740, 56, 756), 0, y - 752.0, src_pi=spi, src_pdf=spdf)
        n_, last = E.put_par(pdf, pi, 58.0, y, t, 'R', 12, nav, 236, 14)
        y = last + 18
    assert last < 813, ('cropgen impl', last)
    y = 686.0
    for t in D['effect']:
        E.copy_shapes(pdf, pi, (304, 674, 320, 690), 0, y - 686.0, src_pi=spi, src_pdf=spdf)
        n_, last = E.put_par(pdf, pi, 322.0, y, t, 'R', 12, nav, 262, 14)
        y = last + 18
    assert last < 813, ('cropgen effect', last)
    # right page
    fx = None
    for i, t in enumerate(D['company']):
        w = E.put(pdf, pi, 685.4, 56.0 + 22 * i, t, 'H', 18, rcol)
        if i == 0:
            fx = 685.4 + w + 8
    E.put_par(pdf, pi, 685.4, 104.0, D['subtitle'], 'R', 14, rcol, 375, 17)
    E.put(pdf, pi, 704.4, 162.0, D['city'], 'R', 12, rcol)
    E.put(pdf, pi, 755.4, 213.0, D['speaker'], 'B', 14, rcol)
    E.put(pdf, pi, 755.4, 229.0, D['role'], 'R', 12, rcol)
    E.put(pdf, pi, 685.4, 351.0, D['year'], 'H', 16, rcol)
    E.put_par(pdf, pi, 685.0, 566.0, D['ask_text'], 'R', 14, nav, 160, 17)
    put_photos(pdf, pi, D)
    E.add_image(pdf, pi, Image.open(D['flag']), (fx, 44.5, fx + 36, 65.5), pad=0.0, bg=(179, 235, 56))


def build_electica(pdf, pi, spdf, spi, D):
    """Electica Energy: urban template g37 (Accel. Digital), year instead of revenue, no support block."""
    from PIL import Image
    L = {l['text'].strip(): l for l in E.lines(spdf, spi)}
    nav = E.color_in(spdf, spi, E.line_rect(L['модель здания']))
    tcol = E.color_in(spdf, spi, E.line_rect(L['мониторинга стройплощадок']))
    rcol = E.color_in(spdf, spi, E.line_rect(L['московский разработчик цифровых платформ']))
    hcol = E.color_in(spdf, spi, E.line_rect(L['Производство и штат']))
    acc = E.color_in(spdf, spi, E.line_rect(L['15 000+']))
    erase(pdf, pi, [(40, 38, 600, 84), (40, 100, 322, 270), (40, 288, 322, 530),
                    (75, 552, 222, 650), (250, 552, 398, 650), (398, 552, 600, 650),
                    (40, 675, 302, 815), (305, 675, 610, 815),
                    (683, 38, 1062, 125), (700, 148, 965, 168), (750, 198, 960, 236),
                    (683, 295, 860, 430), (968, 128, 1215, 215), (683, 530, 860, 640)])
    nt, _ = E.put_par(pdf, pi, 44.4, 56.0, D['title'], 'H', 18, tcol, 545, 22)
    assert nt <= 2, D['title']
    E.put_rich(pdf, pi, 44.0, 116.0, D['desc'], 14, nav, 255, 17)
    y = 305.0
    for runs in D['innov']:
        E.copy_shapes(pdf, pi, (42, 292, 62, 310), 0, y - 305.0, src_pi=spi, src_pdf=spdf)
        n_, last = E.put_rich(pdf, pi, 66.0, y, runs, 14, nav, 234, 17)
        y = last + 22
    assert last < 530, ('electica innov', last)
    for x, t in zip((77.0, 252.3), D['adv']):
        n_, last = E.put_par(pdf, pi, x, 566.0, t, 'R', 12, nav, 142, 14)
        assert last < 650, t
    E.put(pdf, pi, 44.0, 696.0, D['impl_num'], 'H', 24, acc)
    n_, last = E.put_par(pdf, pi, 44.0, 712.0, D['impl_cap'], 'R', 12, nav, 250, 14)
    y = last + 26
    for t in D['impl']:
        E.copy_shapes(pdf, pi, (40, 726, 56, 742), 0, y - 738.0, src_pi=spi, src_pdf=spdf)
        n_, last = E.put_par(pdf, pi, 58.0, y, t, 'R', 12, nav, 236, 14)
        y = last + 18
    assert last < 813, ('electica impl', last)
    y = 686.0
    for t in D['effect']:
        E.copy_shapes(pdf, pi, (304, 674, 320, 690), 0, y - 686.0, src_pi=spi, src_pdf=spdf)
        n_, last = E.put_par(pdf, pi, 322.0, y, t, 'R', 12, nav, 262, 14)
        y = last + 18
    assert last < 813, ('electica effect', last)
    fx = None
    for i, t in enumerate(D['company']):
        w = E.put(pdf, pi, 685.4, 56.0 + 22 * i, t, 'H', 18, rcol)
        if i == 0:
            fx = 685.4 + w + 8
    E.put_par(pdf, pi, 685.4, 104.0, D['subtitle'], 'R', 14, rcol, 375, 17)
    E.put(pdf, pi, 704.4, 162.0, D['city'], 'R', 12, rcol)
    E.put(pdf, pi, 755.4, 213.0, D['speaker'], 'B', 14, rcol)
    E.put(pdf, pi, 755.4, 229.0, D['role'], 'R', 12, rcol)
    # white panel layout: request + year on top, large full screenshot below
    E.put(pdf, pi, 685.4, 322.0, 'ЗАПРОС', 'H', 14, nav, tracking=0.28)
    E.put_par(pdf, pi, 685.4, 345.0, D['ask_text'], 'R', 14, nav, 230, 17)
    E.put(pdf, pi, 940.0, 322.0, 'ГОД ОСНОВАНИЯ', 'H', 14, nav, tracking=0.28)
    E.put(pdf, pi, 940.0, 348.0, D['year'], 'H', 16, nav)
    D2 = dict(D)
    D2['photos'] = dict(D['photos'])
    D2['photos']['right'] = (D['blank'], 'cover')
    put_photos(pdf, pi, D2)
    E.add_image(pdf, pi, Image.open(D['shot']), (683.0, 395.0, 1197.0, 716.0), pad=0.0, bg=(255, 255, 255))
    E.add_image(pdf, pi, Image.open(D['flag']), (fx, 44.5, fx + 36, 65.5), pad=0.0, bg=(255, 153, 52))
