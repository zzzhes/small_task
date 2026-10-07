"""Apply catalog edits (round 3) to v2 parts -> e/pN.pdf"""
import io
import sys
import pikepdf
import pymupdf as fitz
import edit as E
import reflow as R
from edit import erase

SIZES = {1: 24, 2: 21, 3: 23, 4: 27, 5: 5}


def gidx(g):
    for p in range(1, 6):
        if g <= SIZES[p]:
            return p, g - 1
        g -= SIZES[p]
    raise ValueError


PARTS = {p: pikepdf.open('v2/p%d.pdf' % p) for p in range(1, 6)}


def page(g):
    p, i = gidx(g)
    return PARTS[p], i


def fitz_lines(pdf, pi, needle):
    """Lines (both text layers) containing needle: (x0, baseline, x1, size)."""
    one = pikepdf.new()
    one.pages.append(pdf.pages[pi])
    b = io.BytesIO()
    one.save(b)
    d = fitz.open('pdf', b.getvalue())
    out = []
    for blk in d[0].get_text('dict')['blocks']:
        for l in blk.get('lines', []):
            t = ''.join(s['text'] for s in l['spans'])
            if needle in t:
                s0 = l['spans'][0]
                out.append((l['bbox'][0], s0['origin'][1], l['bbox'][2], round(s0['size'], 2), t))
    # dedupe (Type3 + sbinv copies)
    res = []
    for o in out:
        if not any(abs(o[0] - r[0]) < 1 and abs(o[1] - r[1]) < 1 for r in res):
            res.append(o)
    return res


# ------------------------------------------------------------------ edits
def sber500():
    n = 0
    for g in range(1, 101):
        pdf, pi = page(g)
        for x0, y, x1, s, t in fitz_lines(pdf, pi, 'Сбер500'):
            assert t.strip() == 'Участник Сбер500', (g, t)
            r = (x0 - 0.5, y - 0.95 * s, x1 + 0.5, y + 0.3 * s)
            col = E.color_in(pdf, pi, r)
            erase(pdf, pi, [r])
            E.put(pdf, pi, x0, y, 'Участник Sber500', 'R', s, col)
            n += 1
    print('Sber500 replaced:', n)


def axis():
    pdf, pi = page(39)
    l = E.find(pdf, pi, '1 человек', exact=True)
    E.replace_line(pdf, pi, l, '5 человек', 'R')


def fitpolis():
    pdf, pi = page(18)
    ref = E.find(pdf, pi, 'Производство и штат')
    col = E.color_in(pdf, pi, E.line_rect(ref))
    E.put(pdf, pi, 685.4, 308.0, 'ГОД', 'H', 14, col, tracking=0.28)
    E.put(pdf, pi, 685.4, 325.0, 'ОСНОВАНИЯ', 'H', 14, col, tracking=0.28)
    E.put(pdf, pi, 685.4, 351.0, '2021', 'H', 16, col)


def robotfight():
    pdf, pi = page(77)
    (x0, y, x1, s, t), = fitz_lines(pdf, pi, 'Партнёр АНО РЧК')
    col = E.color_in(pdf, pi, (x0, y - 10, x1, y + 3))
    dy = 20.0
    nb = E.copy_shapes(pdf, pi, (970, y - 9, 986, y + 1), 0, dy)
    assert nb == 1, nb
    E.put(pdf, pi, x0, y + dy, 'Участник Sber500', 'R', s, col)


SRC = {p: pikepdf.open('v2/p%d.pdf' % p) for p in range(1, 6)}


def src(g):
    p, i = gidx(g)
    return SRC[p], i


def mechbox():
    g = 76
    pdf, pi = page(g)
    spdf, spi = src(g)
    L = {l['text'].strip(): l for l in E.lines(spdf, spi)}
    navy = E.color_in(spdf, spi, E.line_rect(L['наставника с\xa0ИИ']))
    tcol = E.color_in(spdf, spi, E.line_rect(L['образовательные комплекты']))
    white = E.color_in(spdf, spi, E.line_rect(L['разработчик платформы для\xa0обучения робототехнике']))
    acc = E.color_in(spdf, spi, E.line_rect(L['₽8']))
    # ---- erase left page text blocks
    erase(pdf, pi, [
        (40, 38, 600, 84),        # title
        (40, 100, 320, 172),      # description
        (40, 288, 320, 400),      # innovation incl. bullets
        (75, 552, 222, 640), (250, 552, 398, 640), (425, 552, 600, 640),  # advantages text
        (40, 672, 600, 735),      # effects incl. bullets
        (683, 68, 1060, 88),      # subtitle
        (683, 335, 760, 356),     # year
        (683, 552, 860, 628),     # request block
    ])
    # title (H 18, lead 22)
    # ExtendedSemibold 18pt: does not fit in 2 lines -> 3 lines, description shifted down
    nt, _ = E.put_par(pdf, pi, 44.4, 56.0, 'Конструкторы и платформа с ИИ для обучения робототехнике дома и в школе'.upper(),
                      'H', 18, tcol, 545, 22)
    # description
    E.put_rich(pdf, pi, 44.0, 116.0 + 22 * max(0, nt - 2), [('Мехбокс', 'B'), (' объединяет конструкторы с собственным контроллером, '
               'облачную образовательную платформу и ИИ-учителя', 'R')], 14, navy, 255, 17)
    # innovation bullets (copy original bullet 1 shape)
    b1 = (42, 295, 62, 312)
    n1, last = E.put_rich(pdf, pi, 66.0, 305.0, [('ИИ-учитель', 'B'), (' видит программу ребёнка, учитывает '
                          'возможности контроллера и помогает исправлять ошибки', 'R')], 14, navy, 236, 17)
    E.copy_shapes(pdf, pi, b1, 0, 0, src_pi=spi, src_pdf=spdf)
    y2 = last + 22
    E.copy_shapes(pdf, pi, b1, 0, y2 - 305.0, src_pi=spi, src_pdf=spdf)
    E.put_rich(pdf, pi, 66.0, y2, [('Контроллер, облачная платформа и голосовой ИИ-учитель', 'B'),
               (' работают как единая система', 'R')], 14, navy, 236, 17)
    # key advantages (12pt, lead 14)
    for x, t in [(77.0, 'Собственный контроллер работает с накопленными деталями LEGO и продаётся отдельно или с набором деталей'),
                 (252.3, 'Кабинет педагога: готовые уроки, управление оборудованием класса и прогресс учеников'),
                 (427.7, 'Курсы с ИИ-учителем на наборах других производителей')]:
        E.put_par(pdf, pi, x, 566.0, t, 'R', 12, navy, 142, 14)
    # effects (bullets copied from original first effect bullet)
    eb = (40, 677, 56, 690)
    y = 686.0
    for t in ['Больше времени на учеников: платформа упрощает подготовку и ведение урока, ИИ помогает разбирать ошибки',
              'Подсказки ИИ помогают детям преодолевать первые трудности и не бросать обучение',
              'Самостоятельные занятия с ИИ-учителем дома и там, где нет кружка']:
        E.copy_shapes(pdf, pi, eb, 0, y - 686.0, src_pi=spi, src_pdf=spdf)
        n, last = E.put_par(pdf, pi, 58.0, y, t, 'R', 12, navy, 500, 14)
        y = last + 20
    # right page
    E.put_par(pdf, pi, 685.4, 82.0, 'разработчик конструкторов и платформы для обучения робототехнике', 'R', 14, white, 370, 17)
    E.put(pdf, pi, 685.4, 351.0, '2024', 'H', 16, white)
    w = E.put(pdf, pi, 685.0, 582.0, '₽8', 'H', 24, acc)
    E.put(pdf, pi, 685.0 + w, 582.0, ' млн', 'H', 16, acc)
    n, last = E.put_par(pdf, pi, 685.0, 602.0, 'на серийное производство и развитие платформы', 'R', 12, navy, 160, 14)
    E.put_par(pdf, pi, 685.0, last + 20, 'Партнёры для разработки учебных программ', 'R', 12, navy, 160, 14)


def plastilin():
    from PIL import Image
    from cat import image_placements
    g = 93
    pdf, pi = page(g)
    spdf, spi = src(g)
    L = {l['text'].strip(): l for l in E.lines(spdf, spi)}
    navy = E.color_in(spdf, spi, E.line_rect(L['прогнозирует урожайность,']))
    rnavy = E.color_in(spdf, spi, E.line_rect(L['Москва']))
    acc = E.color_in(spdf, spi, E.line_rect(L['17']))
    rev = E.color_in(spdf, spi, E.line_rect(L['₽35,9']))
    erase(pdf, pi, [
        (40, 100, 300, 190),                      # description
        (40, 290, 300, 385),                      # innovation (+bullets)
        (250, 552, 400, 600), (425, 552, 600, 600),   # advantages 2,3
        (40, 680, 302, 775),                      # implementations
        (779, 150, 850, 166),                     # staff
        (683, 322, 800, 420),                     # revenue entries
        (985, 150, 1200, 166),                    # support line
        (683, 552, 850, 600),                     # request
    ])
    E.put_rich(pdf, pi, 44.0, 116.0, [('Пластилин', 'B'), (' — ИИ-платформа для селекции и семеноводства: '
               'моделирует признаки сорта в конкретном регионе с учётом технологии возделывания на основе '
               'геномных данных и полностью цифровизирует селекционный процесс', 'R')], 14, navy, 255, 17)
    b1 = (42, 292, 62, 310)
    y = 305.0
    LIM = R.limits(pdf, pi)
    for lead, rest in [('Генотип, фенотип, почва и климат', ' в одной прогностической модели'),
                       ('Анализ ДНК-маркеров', ' и ИИ-прогноз для подбора родительских пар'),
                       ('Оптимальный район', ' для сорта или гибрида с детальной технологической картой')]:
        E.copy_shapes(pdf, pi, b1, 0, y - 305.0, src_pi=spi, src_pdf=spdf)
        n, last = E.put_rich(pdf, pi, 66.0, y, [(lead, 'B'), (rest, 'R')], 14, navy, LIM(66.0, 14, 234), 17)
        y = last + 22
    E.put_par(pdf, pi, 252.3, 566.0, 'Выведение нового сорта за 3 года', 'R', 12, navy, 142, 14)
    E.put_par(pdf, pi, 427.7, 566.0, 'Подбор генов-мишеней и генетическое редактирование', 'R', 12, navy, 142, 14)
    # implementations: bullets (copy bullet of '4 сорта гороха…')
    bsrc = (40, 742, 56, 754)
    y = 686.0
    for t in ['Технологический партнёр Тимирязевского геномного центра и платформы ПУСК: 86 организаций, более 100 точек высева',
              'На платформе — данные по пшенице, ячменю, кукурузе, рапсу, подсолнечнику, сахарной свёкле, картофелю и другим культурам']:
        E.copy_shapes(pdf, pi, bsrc, 0, y - 752.0, src_pi=spi, src_pdf=spdf)
        n, last = E.put_par(pdf, pi, 58.0, y, t, 'R', 12, navy, 242, 14)
        y = last + 20
    # right page
    E.put(pdf, pi, 781.4, 162.0, '50\xa0человек', 'R', 12, rnavy)
    yy = 335.0
    for yr, amt in [('2026', '₽102'), ('2025', '₽35'), ('2024', '₽6')]:
        E.put(pdf, pi, 685.4, yy, yr, 'H', 12, rev)
        w = E.put(pdf, pi, 685.4, yy + 21, amt, 'H', 16, rev)
        E.put(pdf, pi, 685.4 + w, yy + 21, ' млн', 'H', 12, rev)
        yy += 57
    E.put(pdf, pi, 988.0, 162.28, 'Резидент технопарка «Сколково»', 'R', 12, rnavy)
    E.put_par(pdf, pi, 685.0, 566.0, 'Автономные пилотные проекты с хозяйствами на базе ИИ-платформы', 'R', 14, navy, 160, 17)
    # pictures
    imgs = image_placements(pdf, pi)
    left = [x for f, n, x, r, c in imgs if r[0] < 400 and x.Width == 688][0]
    right = [x for f, n, x, r, c in imgs if r[0] > 800 and x.Width == 688][0]
    E.replace_image(pdf, left, Image.open('x/ppt/media/image2.png'), 'contain', bg=(21, 21, 21, 255))
    E.replace_image(pdf, right, Image.open('x/ppt/media/image1.png'), 'contain', bg=(21, 21, 21, 255))


def aiolos():
    from PIL import Image
    from cat import image_placements
    pdf, pi = page(58)
    x = [x for f, n, x, r, c in image_placements(pdf, pi) if r[0] < 400 and r[3] - r[1] > 300][0]
    W, Hh = int(x.Width), int(x.Height)
    src = Image.open('/root/.claude/uploads/01d9064f-fcc0-5c7c-99c9-dd8b7cd80bb4/cc6baba3-image.jpg').convert('RGB')
    # fit to width (slight zoom so the three devices fill the frame), extend the plain backdrop up/down
    k = W / src.width * 1.15
    im = src.resize((round(src.width * k), round(src.height * k)), Image.LANCZOS)
    im = im.crop(((im.width - W) // 2, 0, (im.width - W) // 2 + W, im.height))
    can = Image.new('RGB', (W, Hh))
    top = (Hh - im.height) // 2 - 40
    can.paste(im, (0, top))
    can.paste(im.crop((0, 0, W, 1)).resize((W, top)), (0, 0))
    bot = top + im.height
    can.paste(im.crop((0, im.height - 1, W, im.height)).resize((W, Hh - bot)), (0, bot))
    E.replace_image(pdf, x, can, 'cover', quality=92)


def aiolos_text():
    g = 58
    pdf, pi = page(g)
    spdf, spi = src(g)
    L = {l['text'].strip(): l for l in E.lines(spdf, spi)}
    navy = E.color_in(spdf, spi, E.line_rect(L['Простое']))
    white = E.color_in(spdf, spi, E.line_rect(L['Производство и штат']))
    acc = (0.478431, 0.752941, 1.0)
    erase(pdf, pi, [(40, 100, 322, 270), (40, 266, 300, 284), (40, 288, 322, 470),
                    (75, 552, 222, 650), (250, 552, 398, 650), (425, 552, 600, 650),
                    (305, 675, 610, 840), (683, 38, 1062, 125), (683, 552, 860, 800)])
    n, last = E.put_rich(pdf, pi, 44.0, 116.0, [('Aiolos Bridge', 'B'), (' — универсальная аппаратно-программная '
        'платформа для создания бытовых автономных IoT-устройств. Первый продукт на базе данной платформы — '
        'полностью автономная умная система защиты от протечки, которая обнаруживает протечки воды и обеспечивает '
        'защиту объекта независимо от наличия электричества и интернета', 'R')], 14, navy, 255, 17)
    hy = max(280.0, last + 26)
    E.copy_shapes(pdf, pi, (40, 266, 300, 284), 0, hy - 280.0, src_pi=spi, src_pdf=spdf)
    y = hy + 24
    wfn = lambda yy: 234 if yy < 476 else 330
    for lead_, rest in [('Полная автономность устройств', ' не только позволяет установить систему без ремонта, '
                         'но и обеспечивает защиту даже при отключении электричества во всем доме'),
                        ('Децентрализованная архитектура', ' коммуникации устройств обеспечивает работу автономных '
                         'узлов без центрального хаба и подключения к интернету'),
                        ('Собственная масштабируемая универсальная платформа IoT-устройств', ' ускоряет разработку '
                         'и вывод на рынок новых умных устройств и форм-факторов')]:
        E.copy_shapes(pdf, pi, (42, 292, 62, 310), 0, y - 305.0 - 1.5, src_pi=spi, src_pdf=spdf)
        n, last = E.put_rich(pdf, pi, 66.0, y, [(lead_, 'B'), (rest, 'R')], 12, navy, wfn, 14)
        y = last + 18
    assert last < 528, ('aiolos innovation too long', last)
    for x, t in [(77.0, 'Простое развёртывание и масштабирование системы'),
                 (252.3, 'Постоянный доступ к информации о состоянии устройств'),
                 (427.7, 'Высокий уровень безопасности за счёт полной автономности')]:
        E.put_par(pdf, pi, x, 566.0, t, 'R', 12, navy, 142, 14)
    y = 686.0
    for t in ['Снижение потенциального ущерба от протечек за счёт автоматической локализации аварии',
              'Повышение автоматизации водных коммуникаций за счёт создания системы удалённого управления '
              'запорной арматурой через удалённый контроль всех устройств по сети интернет',
              'Снижение нагрузки на эксплуатационный персонал за счёт автоматического реагирования и удалённого уведомления']:
        E.copy_shapes(pdf, pi, (304, 674, 320, 690), 0, y - 686.0, src_pi=spi, src_pdf=spdf)
        n, last = E.put_par(pdf, pi, 322.0, y, t, 'R', 12, navy, 285, 14)
        y = last + 20
    assert last < 815, ('aiolos effects too long', last)
    E.put(pdf, pi, 685.4, 56.0, 'ООО\xa0«ЭОЛ БРИДЖ»', 'H', 18, white)
    E.put_par(pdf, pi, 685.4, 82.0, 'разработчик универсальной платформы автономных IoT-устройств', 'R', 14, white, 375, 17)
    w = E.put(pdf, pi, 685.0, 582.0, '₽30', 'H', 24, acc)
    E.put(pdf, pi, 685.0 + w, 582.0, '\xa0млн', 'H', 16, acc)
    E.put_par(pdf, pi, 685.0, 602.0, 'на масштабирование пилотного производства', 'R', 12, navy, 160, 14)


def trendsee():
    from PIL import Image
    from cat import image_placements
    g = 81
    pdf, pi = page(g)
    l = E.find(pdf, pi, 'Анна Береснева')
    E.replace_line(pdf, pi, l, 'Кирилл Береснев', 'B')
    A = 'assets/'
    for f, n, x, r, c in image_placements(pdf, pi):
        vr = c or r
        if vr[3] - vr[1] < 40:
            E.fit_image(pdf, x, Image.open(A + 'trendsee_logo.png'), r, c, mode='logo', pad=0.08)
        elif vr[2] - vr[0] < 80:
            E.fit_image(pdf, x, Image.open(A + 'beresnev.jpg'), r, c, mode='cover', focus=(0.5, 0.2))


def neurocode_team():
    from PIL import Image
    from cat import image_placements
    g = 62
    pdf, pi = page(g)
    col = E.color_in(pdf, pi, (750, 200, 900, 216))
    sp = [x for f, n, x, r, c in image_placements(pdf, pi) if f == 'page' and abs(r[0] - 685) < 2 and abs(r[1] - 186) < 2]
    assert len(sp) == 1
    assert E.remove_do(pdf, pi, sp[0]) == 1
    erase(pdf, pi, [(750, 198, 960, 236)])
    team = [('Дмитрий Гайдук', 'сооснователь, CEO', 'gaiduk', 685, 182),
            ('Владислав Бушуев', 'сооснователь, CTPO', 'bushuev', 820, 182),
            ('Евгения Петина', 'COO', 'petina', 685, 232),
            ('Иван Глытов', 'руководитель ML', 'glytov', 820, 232)]
    for name, role, f, x, y in team:
        E.add_image(pdf, pi, Image.open('assets/nc_%s.jpg' % f), (x, y, x + 40, y + 40), radius=7, cover=True)
        E.put(pdf, pi, x + 46, y + 18, name, 'B', 10, col)
        E.put(pdf, pi, x + 46, y + 30, role, 'R', 9, col)


def medcomm():
    from PIL import Image
    from cat import image_placements
    g = 24
    pdf, pi = page(g)
    spdf, spi = src(g)
    L = {l['text'].strip(): l for l in E.lines(spdf, spi)}
    tcol = E.color_in(spdf, spi, E.line_rect(L['ПАЦИЕНТОВ РОССИЙСКИХ КЛИНИК']))
    navy = E.color_in(spdf, spi, E.line_rect(L['заявку на\xa0лечение в\xa0России']))
    rcol = E.color_in(spdf, spi, E.line_rect(L['генеральный директор']))
    erase(pdf, pi, [(40, 38, 600, 84), (40, 100, 322, 192), (750, 198, 960, 218)])
    nt, _ = E.put_par(pdf, pi, 44.4, 56.0, 'МУЛЬТИЯЗЫЧНЫЙ ЦИФРОВОЙ ИНСТРУМЕНТ ДЛЯ ИНОСТРАННЫХ ПАЦИЕНТОВ ИЗ СТРАН БРИКС+ И СНГ',
                      'H', 18, tcol, 545, 22)
    E.put_rich(pdf, pi, 44.0, 116.0 + 22 * max(0, nt - 2), [('«Медицинские коммуникации»', 'B'),
               (' — собирает анамнез на родном языке пациента, переводит медицинские документы и оформляет '
                'заявку на лечение в России', 'R')], 14, navy, 255, 17)
    E.put(pdf, pi, 755.4, 213.0, 'Ульяна Каниовская', 'B', 14, rcol)
    for f, n, x, r, c in image_placements(pdf, pi):
        if r[0] > 800 and (r[3] - r[1]) > 300:
            E.fit_image(pdf, x, Image.open('assets/mk_phone.png'), r, c, mode='contain', bg=(255, 255, 255), pad=0.07)


def dot(pdf, pi, cx, cy, r, col):
    k = r * 0.5523
    c = ('q %.4f %.4f %.4f rg %.3f %.3f m %.3f %.3f %.3f %.3f %.3f %.3f c %.3f %.3f %.3f %.3f %.3f %.3f c '
         '%.3f %.3f %.3f %.3f %.3f %.3f c %.3f %.3f %.3f %.3f %.3f %.3f c h f Q\n') % (
        col[0], col[1], col[2], cx + r, E.H - cy,
        cx + r, E.H - cy + k, cx + k, E.H - cy + r, cx, E.H - cy + r,
        cx - k, E.H - cy + r, cx - r, E.H - cy + k, cx - r, E.H - cy,
        cx - r, E.H - cy - k, cx - k, E.H - cy - r, cx, E.H - cy - r,
        cx + k, E.H - cy - r, cx + r, E.H - cy - k, cx + r, E.H - cy)
    pdf.pages[pi].contents_add(pdf.make_stream(c.encode()), prepend=False)


def sber_support():
    for g in (25, 67, 98, 99, 55, 56, 57, 61):
        pdf, pi = page(g)
        spdf, spi = src(g)
        col = E.color_in(spdf, spi, E.line_rect(E.find(spdf, spi, 'Производство и штат')))
        dx = 26.0 if g == 55 else 0.0
        E.put(pdf, pi, 974.0 + dx, 139.0, 'МЕРЫ ПОДДЕРЖКИ', 'H', 14, col, tracking=0.28)
        dot(pdf, pi, 978.0 + dx, 158.0, 3.0, col)
        E.put(pdf, pi, 988.0 + dx, 162.0, 'Участник Sber500', 'R', 12, col)


def fitpolis_trackers():
    pdf, pi = page(18)
    spdf, spi = src(18)
    col = E.color_in(spdf, spi, (58, 740, 290, 754))
    erase(pdf, pi, [(40, 726, 300, 816)])
    y = 731.0
    for t in ['Пилот в Бразилии завершён, продукт запущен в России',
              '115 видов спорта, подключается к 95% трекеров и приложений',
              '91% пользователей возвращаются к тренировкам с защитой']:
        E.copy_shapes(pdf, pi, (40, 726, 56, 742), 0, y - 738.0, src_pi=spi, src_pdf=spdf)
        n, last = E.put_par(pdf, pi, 58.0, y, t, 'R', 12, col, 232, 14)
        y = last + 15
    assert last <= 806, last


def heart():
    pdf, pi = page(22)
    spdf, spi = src(22)
    col = E.color_in(spdf, spi, (58, 750, 270, 762))
    l = E.find(spdf, spi, 'МОНИКИ')
    erase(pdf, pi, [E.line_rect(l)])
    E.put(pdf, pi, 58.0, 760.0, 'ГКБ 23 им.\xa0И.В.\xa0Давыдовского', 'R', 12, col)
    scol = E.color_in(spdf, spi, (985, 150, 1100, 164))
    E.copy_shapes(pdf, pi, (970, 150, 986, 166), 0, 20, src_pi=spi, src_pdf=spdf)
    E.put(pdf, pi, 988.0, 182.0, 'Поддержка фонда МедТех', 'R', 12, scol)


def statanly():
    pdf, pi = page(61)
    spdf, spi = src(61)
    col = E.color_in(pdf, pi, (44, 136, 260, 152))
    erase(pdf, pi, [(40, 100, 322, 250)])
    n, last = E.put_rich(pdf, pi, 44.0, 116.0, [('Statanly Technologies', 'B'), (' — AI-платформа, которая превращает '
        'текстовый запрос в готовый сценарий видеоаналитики на существующих камерах. Система сама готовит данные '
        'и обучает модель, позволяя запускать новые задачи контроля без длительной разработки', 'R')], 14, col, 255, 17)
    assert last < 262, last


def freze():
    pdf, pi = page(59)
    spdf, spi = src(59)
    col = E.color_in(pdf, pi, (44, 120, 260, 136))
    erase(pdf, pi, [(40, 288, 322, 470), (683, 590, 860, 640)])
    y = 305.0
    for lead_, rest in [('Иммерсивное FPV-управление', ' — оператор видит обстановку от лица робота через видеоочки '
                         'и управляет им с помощью джойстика'),
                        ('Многофункциональная платформа', ' — сменное оборудование позволяет адаптировать робота '
                         'под разные задачи: от пожаротушения до расчистки завалов')]:
        E.copy_shapes(pdf, pi, (42, 292, 62, 310), 0, y - 305.0, src_pi=spi, src_pdf=spdf)
        n, last = E.put_rich(pdf, pi, 66.0, y, [(lead_, 'B'), (rest, 'R')], 14, col, 234, 17)
        y = last + 22
    assert last < 530, last
    E.put_par(pdf, pi, 685.0, 602.0, 'На развитие продукта и пилотные запуски', 'R', 12, col, 160, 14)


def neurocode_corners():
    from PIL import Image, ImageDraw
    from cat import image_placements
    pdf, pi = page(62)
    x = [x for f, n, x, r, c in image_placements(pdf, pi) if f == 'page' and r[0] > 900 and r[3] - r[1] > 300][0]
    im = pikepdf.PdfImage(x).as_pil_image().convert('RGB')
    frame = (17, 19, 38)
    for seed in [(0, 0), (im.width - 1, 0), (0, im.height - 1), (im.width - 1, im.height - 1)]:
        if sum(im.getpixel(seed)) > 600:
            ImageDraw.floodfill(im, seed, frame, thresh=60)
    E.replace_image(pdf, x, im, 'cover', quality=93)


def kinetronika_staff():
    pdf, pi = page(60)
    l = E.find(pdf, pi, '2 человека')
    E.replace_line(pdf, pi, l, '5\xa0человек', 'R')


def plastilin_sber():
    pdf, pi = page(93)
    spdf, spi = src(93)
    col = E.color_in(spdf, spi, E.line_rect(E.find(spdf, spi, 'Москва')))
    E.copy_shapes(pdf, pi, (970, 150, 986, 166), 0, 20, src_pi=spi, src_pdf=spdf)
    E.put(pdf, pi, 988.0, 182.28, 'Участник Sber500', 'R', 12, col)


def trendsee_ask():
    pdf, pi = page(81)
    spdf, spi = src(81)
    nav = E.color_in(spdf, spi, E.line_rect(E.find(spdf, spi, 'Поиск новых')))
    sp2, si2 = src(80)
    acc = E.color_in(sp2, si2, E.line_rect(E.find(sp2, si2, '₽50')))
    erase(pdf, pi, [(683, 552, 860, 600)])
    LIM = R.limits(pdf, pi)
    w = E.put(pdf, pi, 685.0, 582.0, '₽20', 'H', 24, acc)
    E.put(pdf, pi, 685.0 + w, 582.0, '\xa0млн', 'H', 16, acc)
    E.put_par(pdf, pi, 685.0, 602.0, 'Для масштабирования в СНГ и выхода в страны БРИКС. Открыты к стратегическим партнёрствам',
              'R', 12, nav, LIM(685.0, 12, 175), 14)


def maplab_title():
    """Last title word ran into the orange shape: move it to a fifth line, description 22pt lower."""
    pdf, pi = page(34)
    spdf, spi = src(34)
    word = (316, 104, 600, 128)
    desc = (40, 130, 330, 236)
    erase(pdf, pi, [word, desc], text_layer=False)
    E.copy_shapes(pdf, pi, word, 44.6 - 319.25, 22, src_pi=spi, src_pdf=spdf)
    E.copy_shapes(pdf, pi, desc, 0, 22, src_pi=spi, src_pdf=spdf)


def robkom_support():
    """Staff line ran into the support column: move the column right."""
    pdf, pi = page(51)
    spdf, spi = src(51)
    box = (968, 125, 1215, 175)
    erase(pdf, pi, [box], max_wh=200)
    E.copy_shapes(pdf, pi, box, 26, 0, src_pi=spi, src_pdf=spdf)
    og = pdf.pages[pi].objgen
    E.LOG.append((id(pdf), og, 1000.0, 139.0, 'МЕРЫ ПОДДЕРЖКИ', 14))
    E.LOG.append((id(pdf), og, 1014.0, 162.0, 'Пилотное тестирование', 12))


def znay_nashih():
    """ICE+ and Qmonitoring took part in the «Знай наших» demo day."""
    for g, y in ((28, 216.0), (32, 210.0)):
        pdf, pi = page(g)
        spdf, spi = src(g)
        col = E.color_in(spdf, spi, (985, 150, 1200, 166))
        E.copy_shapes(pdf, pi, (970, 150, 986, 166), 0, y - 162.0, src_pi=spi, src_pdf=spdf)
        E.put(pdf, pi, 988.0, y, 'Участник инвестиционного Демо-', 'R', 12, col)
        E.put(pdf, pi, 988.0, y + 14, 'дня конкурса брендов «Знай\xa0наших»', 'R', 12, col)


def synapsion_strip():
    """Tongo-Test: the strip photo was tiny inside its transparent canvas."""
    from PIL import Image
    from pikepdf import PdfImage
    from cat import image_placements
    import zlib
    pdf, pi = page(15)
    for f, n, x, r, c in image_placements(pdf, pi):
        if r[2] < 623 and r[3] - r[1] > 200:
            W, Hh = int(x.Width), int(x.Height)
            rgb = PdfImage(x).as_pil_image().convert('RGB')
            a = PdfImage(x.SMask).as_pil_image().convert('L')
            im = rgb.copy()
            im.putalpha(a)
            bb = a.point(lambda v: 255 if v > 8 else 0).getbbox()
            obj = im.crop(bb)
            k = min(W * 0.96 / obj.width, Hh * 0.96 / obj.height)
            obj = obj.resize((round(obj.width * k), round(obj.height * k)), Image.LANCZOS)
            can = Image.new('RGBA', (W, Hh), (255, 255, 255, 0))
            can.alpha_composite(obj, ((W - obj.width) // 2, (Hh - obj.height) // 2))
            print('synapsion strip scale', round(k, 2))
            E.replace_image(pdf, x, can.convert('RGB'), 'cover', quality=92)
            sm = x.SMask
            sm.write(zlib.compress(can.getchannel('A').tobytes()), filter=pikepdf.Name.FlateDecode)
            sm.Width, sm.Height = W, Hh
            sm.ColorSpace = pikepdf.Name.DeviceGray
            sm.BitsPerComponent = 8
            for k_ in ('/DecodeParms', '/Decode'):
                if k_ in sm:
                    del sm[k_]
        elif r[0] > 800 and r[3] - r[1] > 300:
            from PIL import ImageFilter
            tear = Image.open('assets/tongo_tear.jpg').convert('RGB')
            tear = tear.resize((tear.width * 3, tear.height * 3), Image.LANCZOS).filter(
                ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))
            E.fit_image(pdf, x, tear, r, c, mode='cover', focus=(0.5, 0.5))


def reflow_all():
    """Rewrap body text that runs into photos, logos or panels (all original spreads)."""
    for g in range(5, 100):
        pdf, pi = page(g)
        if g != 34:  # MapLab: description moved as shapes, text layer stays put
            R.reflow(pdf, pi, (40, 90, 330, 470), log='g%d left' % g)
        R.reflow(pdf, pi, (683, 75, 1000, 125), log='g%d subtitle' % g)
        R.reflow(pdf, pi, (683, 555, 960, 720), log='g%d ask' % g)


def rrect(pdf, pi, r, rad, col):
    x0, y0, x1, y1 = r
    X0, Y0, X1, Y1 = x0, E.H - y1, x1, E.H - y0
    k = rad * 0.5523
    c = ('q %.4f %.4f %.4f rg %.3f %.3f m %.3f %.3f l %.3f %.3f %.3f %.3f %.3f %.3f c %.3f %.3f l '
         '%.3f %.3f %.3f %.3f %.3f %.3f c %.3f %.3f l %.3f %.3f %.3f %.3f %.3f %.3f c %.3f %.3f l '
         '%.3f %.3f %.3f %.3f %.3f %.3f c h f Q\n') % (
        col[0], col[1], col[2], X0 + rad, Y0, X1 - rad, Y0, X1 - rad + k, Y0, X1, Y0 + rad - k, X1, Y0 + rad,
        X1, Y1 - rad, X1, Y1 - rad + k, X1 - rad + k, Y1, X1 - rad, Y1,
        X0 + rad, Y1, X0 + rad - k, Y1, X0, Y1 - rad + k, X0, Y1 - rad,
        X0, Y0 + rad, X0, Y0 + rad - k, X0 + rad - k, Y0, X0 + rad, Y0)
    pdf.pages[pi].contents_add(pdf.make_stream(c.encode()), prepend=False)


def summit_page():
    """Last page: instead of notes — contacts, QR to the summit site and the summit logo."""
    import qrcode
    from PIL import Image
    pdf, pi = page(100)
    erase(pdf, pi, [(20, 20, 610, 815)])
    NAV = (0.047059, 0.090196, 0.160784)
    GREY = (0.42, 0.47, 0.53)
    CARD = (0.949, 0.953, 0.961)
    og = pdf.pages[pi].objgen
    E.put(pdf, pi, 44.0, 62.0, 'ОБСУДИМ ПАРТНЁРСТВО', 'H', 26, NAV)
    E.put_par(pdf, pi, 44.0, 96.0, 'Контакты для обсуждения стартапов выставки', 'R', 14, GREY, 520, 17)
    cards = [('assets/contact_glazkova.jpg', 'Екатерина Глазкова', 'ESergeevGlazkova@sberbank.ru'),
             ('assets/contact_daudi.png', 'Дауди Дауддин', 'DIDaudi@sberbank.ru')]
    for k, (ph, name, mail) in enumerate(cards):
        x0 = 44.0 + k * 273.0
        y0 = 124.0
        rrect(pdf, pi, (x0, y0, x0 + 262, y0 + 172), 24, CARD)
        E.add_image(pdf, pi, Image.open(ph), (x0 + 20, y0 + 20, x0 + 96, y0 + 96), pad=0, bg=(242, 243, 245),
                    radius=38, cover=True)
        E.put(pdf, pi, x0 + 20, y0 + 128, name, 'B', 16, NAV)
        E.put(pdf, pi, x0 + 20, y0 + 150, mail, 'R', 14, NAV)
    # site + QR
    E.put(pdf, pi, 44.0, 348.0, 'САЙТ САММИТА', 'H', 14, NAV, tracking=0.28)
    q = qrcode.QRCode(border=0, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data('https://startupsummit.ru')
    q.make(fit=True)
    m = q.get_matrix()
    n = len(m)
    qs, qx, qy = 92.0, 44.0, 366.0
    cell = qs / n
    ops = ['q %.4f %.4f %.4f rg' % NAV]
    for r_, row in enumerate(m):
        for c_, v in enumerate(row):
            if v:
                ops.append('%.3f %.3f %.3f %.3f re' % (qx + c_ * cell, E.H - (qy + (r_ + 1) * cell), cell + 0.02, cell + 0.02))
    ops.append('f Q\n')
    pdf.pages[pi].contents_add(pdf.make_stream('\n'.join(ops).encode()), prepend=False)
    # address centred on the QR code's height
    E.put(pdf, pi, qx + qs + 20, qy + qs / 2 + 6, 'startupsummit.ru', 'B', 18, NAV)
    # summit logo (vector, from the partnership slide)
    logo = pikepdf.open('assets/summit_logo_navy.pdf')
    _KEEP.append(logo)
    fx = pdf.copy_foreign(logo.pages[0].as_form_xobject())
    res = pdf.pages[pi].obj.Resources
    if '/XObject' not in res:
        res.XObject = pikepdf.Dictionary()
    res.XObject['/SummitLogo'] = fx
    lw = float(logo.pages[0].mediabox[2])
    lh = float(logo.pages[0].mediabox[3])
    w = 210.0
    s = w / lw
    y1 = 772.0
    pdf.pages[pi].contents_add(pdf.make_stream(('q %.5f 0 0 %.5f %.3f %.3f cm /SummitLogo Do Q\n' % (
        s, s, 44.0, E.H - y1)).encode()), prepend=False)
    E.LOG.append((id(pdf), og, 44.0, 760.0, 'Московский Стартап Саммит', 20))


def gemotek():
    """Legal name: ООО «ГЕМОТЭК» (drop « ИИ», move the closing quote)."""
    import numpy as np
    pdf, pi = page(6)
    spdf, spi = src(6)
    a = R._arr(R._single(spdf, spi))
    Z = R.Z
    band = a[int(40 * Z):int(60 * Z), int(683 * Z):int(1000 * Z)]
    ink = (np.abs(band - np.median(band.reshape(-1, 3), 0)).sum(2) > 80).any(0)
    xs = np.nonzero(ink)[0] / Z + 683
    # clusters of ink = glyphs
    cl, start = [], xs[0]
    for p_, q_ in zip(xs, xs[1:]):
        if q_ - p_ > 0.9:
            cl.append((start, p_))
            start = q_
    cl.append((start, xs[-1]))
    quote, i2, i1, k = cl[-1], cl[-2], cl[-3], cl[-4]
    nx = k[1] + (quote[0] - i2[1])
    erase(pdf, pi, [(i1[0] - 1, 38, quote[1] + 2, 62)], text_layer=False, max_wh=30)
    E.copy_shapes(pdf, pi, (quote[0] - 0.5, 38, quote[1] + 0.5, 62), nx - quote[0], 0, src_pi=spi, src_pdf=spdf)
    cat_remove = __import__('cat').remove_text_pdf
    cat_remove(pdf, pi, [(684, 40, 930, 60)])
    E.LOG.append((id(pdf), pdf.pages[pi].objgen, 685.0, 56.0, 'ООО «ГЕМОТЭК»', 18))
    print('gemotek clusters', [(round(c[0]), round(c[1])) for c in cl[-5:]])


def setirays_role():
    pdf, pi = page(43)
    spdf, spi = src(43)
    col = E.color_in(spdf, spi, (755, 218, 885, 232))
    erase(pdf, pi, [(753, 218, 960, 233)])
    E.put(pdf, pi, 755.4, 229.0, 'Основатель', 'R', 12, col)


def hemotech():
    """HemoTech AI: new product data from the MSS table (round 7) and new photos."""
    from PIL import Image
    from cat import image_placements
    pdf, pi = page(6)
    spdf, spi = src(6)
    navy = E.color_in(spdf, spi, E.line_rect(E.find(spdf, spi, 'анализатор для')))
    tcol = E.color_in(spdf, spi, E.line_rect(E.find(spdf, spi, 'СКРИНИНГА')))
    acc = E.color_in(spdf, spi, E.line_rect(E.find(spdf, spi, '600+')))
    scol = E.color_in(spdf, spi, E.line_rect(E.find(spdf, spi, 'поддержкой в')))
    erase(pdf, pi, [(40, 38, 600, 84), (40, 100, 322, 200), (40, 290, 322, 495),
                    (75, 552, 222, 612), (250, 552, 398, 612), (425, 552, 600, 612),
                    (40, 680, 302, 775), (305, 675, 600, 775),
                    (970, 150, 1210, 215), (683, 592, 860, 640)])
    LIM = R.limits(pdf, pi)
    nt, _ = E.put_par(pdf, pi, 44.4, 56.0, 'ОПТИЧЕСКИЙ АНАЛИЗАТОР КАЧЕСТВА ОБРАЗЦОВ КРОВИ', 'H', 18, tcol,
                      LIM(44.4, 18, 545), 22)
    assert nt <= 2
    E.put_rich(pdf, pi, 44.0, 116.0, [('HemoTech AI', 'B'), (' — портативный анализатор гемолиза, липемии '
               'и иктеричности в закрытой пробирке без реагентов', 'R')], 14, navy, LIM(44.0, 14, 255), 17)
    y = 305.0
    for runs in ([('Оптический контроль:', 'B'), (' световые источники и фотодетектор измеряют отклик образца '
                  'через стенку закрытой пробирки', 'R')],
                 [('ИИ-анализ сигнала:', 'B'), (' модель оценивает гемолиз, липемию и иктеричность '
                  'по оптическим данным', 'R')]):
        E.copy_shapes(pdf, pi, (42, 292, 62, 310), 0, y - 305.0, src_pi=spi, src_pdf=spdf)
        n, last = E.put_rich(pdf, pi, 66.0, y, runs, 14, navy, LIM(66.0, 14, 234), 17)
        y = last + 22
    for x, t in zip((77.0, 252.3, 427.7), ('Измерение за 2 секунды', 'Без реагентов и вскрытия пробирки',
                                          'Компактный прибор для медицинского офиса')):
        E.put_par(pdf, pi, x, 566.0, t, 'R', 12, navy, 142, 14)
    erase(pdf, pi, [(40, 680, 200, 702)])
    E.put(pdf, pi, 44.0, 696.0, '25\xa0000+', 'H', 24, acc)
    E.put_par(pdf, pi, 44.0, 712.0, 'образцов в базе для обучения модели', 'R', 12, navy, 250, 14)
    E.copy_shapes(pdf, pi, (40, 736, 56, 752), 0, 738.0 - 746.0, src_pi=spi, src_pdf=spdf)
    E.put_par(pdf, pi, 58.0, 738.0, 'Пилоты на сыворотке и плазме: МНПЦЛИ ДЗМ и Hadassah', 'R', 12, navy, 236, 14)
    y = 686.0
    for t in ('Раннее выявление дефекта до отправки пробы',
              'Решение о повторном взятии, пока пациент ещё на месте',
              'Снижение затрат на реагентный контроль'):
        E.copy_shapes(pdf, pi, (304, 674, 320, 690), 0, y - 686.0, src_pi=spi, src_pdf=spdf)
        n, last = E.put_par(pdf, pi, 322.0, y, t, 'R', 12, navy, 245, 14)
        y = last + 20
    y = 162.0
    for t in ('Резидент «Сколково»', 'Московский инновационный кластер', 'Участник Sber500'):
        E.copy_shapes(pdf, pi, (970, 150, 986, 166), 0, y - 162.0, src_pi=spi, src_pdf=spdf)
        E.put(pdf, pi, 988.0, y, t, 'R', 12, scol)
        y += 20
    E.put_par(pdf, pi, 685.0, 602.0, 'на масштабирование производства и выпуск первой серии приборов', 'R', 12,
              navy, LIM(685.0, 12, 160), 14)
    for f, n, x, r, c in image_placements(pdf, pi):
        if r[2] < 640 and r[3] - r[1] > 300:
            dev = Image.open('assets/hemo_device.png').convert('RGBA')
            bb = dev.getchannel('A').point(lambda v: 255 if v > 10 else 0).getbbox()
            E.fit_image(pdf, x, dev.crop(bb), r, c, mode='contain', pad=0.08, bg=(255, 255, 255))
        elif r[0] > 800 and r[3] - r[1] > 300:
            E.fit_image(pdf, x, Image.open('assets/hemo_lab.png'), r, c, mode='cover', focus=(0.80, 0.5))


def new_logos():
    """Round 8: new logos (Медкоммуникации, Tongo-test, ПептиГен, Циклоп)."""
    from PIL import Image
    from cat import image_placements
    box = (1101, 47, 1193, 79)
    for g, f, pad in ((24, 'assets/logo_medcomm.png', 0.0), (15, 'assets/logo_tongo.png', 0.02),
                      (19, 'assets/logo_peptigen.webp', 0.02), (53, 'assets/logo_cyclop.webp', 0.04)):
        pdf, pi = page(g)
        for fn, n, x, r, c in image_placements(pdf, pi):
            if r[0] > 1040 and r[1] < 110:
                E.replace_image(pdf, x, Image.new('RGB', (8, 8), (255, 255, 255)), 'cover')
                if '/SMask' in x:
                    del x['/SMask']
        if g == 53:   # no logo plate on this spread: copy the outlined plate from the next spread
            spdf, spi = src(54)
            E.copy_shapes(pdf, pi, (1085, 30, 1210, 96), 0, 0, src_pi=spi, src_pdf=spdf)
            erase(pdf, pi, [(1100, 45, 1195, 81)], text_layer=False, max_wh=60)
        im = Image.open(f).convert('RGBA')
        im = im.crop(im.getchannel('A').point(lambda v: 255 if v > 10 else 0).getbbox())
        E.add_image(pdf, pi, im, box, pad=pad)


def youth_accel():
    """Меры поддержки: «Выпускник молодёжных акселераторов Сбера» (Эва Лаб, Климбиотех)."""
    for g in (23, 91):
        pdf, pi = page(g)
        spdf, spi = src(g)
        col = E.color_in(spdf, spi, E.line_rect(E.find(spdf, spi, 'Производство')))
        E.put(pdf, pi, 974.0, 139.0, 'МЕРЫ ПОДДЕРЖКИ', 'H', 14, col, tracking=0.28)
        dot(pdf, pi, 978.0, 158.0, 3.0, col)
        E.put(pdf, pi, 988.0, 162.0, 'Выпускник молодёжных', 'R', 12, col)
        E.put(pdf, pi, 988.0, 176.0, 'акселераторов Сбера', 'R', 12, col)


def freze_city():
    pdf, pi = page(59)
    spdf, spi = src(59)
    l = E.find(spdf, spi, 'ХМАО')
    col = E.color_in(spdf, spi, E.line_rect(l))
    erase(pdf, pi, [E.line_rect(l), (750, 148, 965, 170)], max_wh=26)
    E.put(pdf, pi, l['x0'], l['y'], 'Санкт-Петербург', 'R', 12, col)


def new_descriptions():
    for g, t in ((55, 'Тактильный оптоволоконный сенсор, который с точностью до грамма измеряет силу воздействия '
                     'для бережной работы с хрупкими, мягкими и деформируемыми объектами'),
                 (67, 'Роботизированная платформа для автоматического тестирования электроники: компьютерное зрение '
                      'распознаёт платы и разъёмы, а манипулятор адаптируется к их расположению, позволяя тестировать '
                      'разные модели без сложной перенастройки'),
                 (98, 'Комплексная AI- и IoT-платформа для повышения продуктивности молочных хозяйств. Умные ошейники '
                      'и датчики отслеживают здоровье и активность коров, изменения в кормлении и уровень метана, '
                      'помогая принимать более точные решения по управлению стадом')):
        pdf, pi = page(g)
        spdf, spi = src(g)
        l0 = [l for l in E.lines(spdf, spi) if abs(l['y'] - 133) < 1 and l['x0'] < 60][0]
        col = E.color_in(spdf, spi, E.line_rect(l0))
        erase(pdf, pi, [(40, 100, 330, 262)], max_wh=40)
        LIM = R.limits(pdf, pi)
        n, last = E.put_rich(pdf, pi, 44.0, 116.0, [(t, 'R')], 14, col, LIM(44.0, 14, 255), 17)
        print('desc', g, 'lines', n, 'last', last)
        assert last <= 252, (g, last)


def trendsee_role():
    pdf, pi = page(81)
    spdf, spi = src(81)
    l = [l for l in E.lines(spdf, spi) if abs(l['y'] - 229) < 1.5 and l['x0'] > 740][0]
    col = E.color_in(spdf, spi, E.line_rect(l))
    erase(pdf, pi, [E.line_rect(l, 1.0)])
    E.put(pdf, pi, l['x0'], l['y'], 'Генеральный директор', 'R', 12, col)


EDITS = [sber500, kinetronika_staff, axis, fitpolis, robotfight, mechbox, plastilin, aiolos, aiolos_text, trendsee, neurocode_team, medcomm, sber_support, fitpolis_trackers, heart, statanly, freze, neurocode_corners, plastilin_sber, trendsee_ask, maplab_title, robkom_support, znay_nashih, synapsion_strip, reflow_all, summit_page, gemotek, setirays_role, hemotech, new_logos, youth_accel, freze_city, new_descriptions, trendsee_role]

# new spreads: (data, insert after global g of the ORIGINAL v2 numbering)
import spreads_data as SD
INSERTS = [(SD.GARPIX, 45), (SD.HIVETRACE, 67), (SD.ROBOPROBE, 67), (SD.WEGOSTY, 83), (SD.CROPGEN, 99), (SD.ELECTICA, 45), (SD.RVS, 45)]


def old_to_new(n, inserts):
    # inserts: list of (printed number of new left page)
    return n + 2 * sum(1 for ins in inserts if ins <= n)


def finalize():
    import finalize as F
    import toc_data as TD
    k, ch = F.renumber(PARTS)
    print('spreads', k, 'page numbers redrawn', ch)
    ins = sorted(2 * (after + 1) - 4 for D, after in INSERTS)   # old numbering of slot
    def secrows(txt, extra):
        rows = [(t, old_to_new(n, ins)) for t, n in TD.parse(txt)]
        rows += extra
        return sorted(rows, key=lambda r: r[1])
    newrows = {}
    for D, after in INSERTS:
        slot = 2 * (after + 1) - 4
        newrows.setdefault(D['section'], []).append((D['toc'], old_to_new(slot, [i for i in ins if i < slot]) + 2 * D.get('order', 0)))
    med = secrows(TD.MED, newrows.get('med', []))
    urb = secrows(TD.URB, newrows.get('urban', []))
    rob = secrows(TD.ROB, newrows.get('robots', []))
    cre = secrows(TD.CRE, newrows.get('create', []))
    agr = secrows(TD.AGR, newrows.get('agro', []))
    print('urban', urb[-2:], 'robots', rob[-2:], 'create', cre[:1], cre[-1:], 'agro', agr[-1:])
    toc = PARTS[1]
    stoc = SRC[1]
    pitch = 21.0
    RIGHT = dict(label=(655, 800), bar=(803.8, 809.8), x=821.8, right=1202.8)
    LEFT = dict(label=(35, 178), bar=(179.8, 185.8), x=197.8, right=578.8)
    col = lambda c: c
    # page g2 (index 1): right column = Медтех (21) + first 10 Урбан rows
    erase(toc, 1, [(650, 88, 1215, 840)], max_wh=500)
    F.build_column(toc, 1, stoc, 1, RIGHT, [
        dict(label_src_top=94.0, color=(0.184314, 0.682353, 0.588235), rows=med, label=['Медтех', 'и биотех']),
        dict(label_src_top=597.0, color=(1.0, 0.6, 0.207843), rows=urb[:11], suffix=True,
             label=['Урбантех', 'и стройтех'])], pitch)
    # page g3 (index 2)
    erase(toc, 2, [(30, 88, 600, 840), (650, 88, 1215, 840)], max_wh=500)
    F.build_column(toc, 2, stoc, 2, LEFT, [
        dict(label_src_top=94.0, color=(1.0, 0.6, 0.207843), rows=urb[11:], suffix=True,
             label=['Урбантех', 'и стройтех']),
        dict(label_src_top=321.0, color=(0.478431, 0.752941, 0.996078), rows=rob, label=['Роботы', 'и девайсы'])], pitch)
    F.build_column(toc, 2, stoc, 2, RIGHT, [
        dict(label_src_top=94.0, color=(0.14902, 0.203922, 0.596078), rows=cre, label=['Креатех', 'и эдтех']),
        dict(label_src_top=459.0, color=(0.705882, 0.921569, 0.219608), rows=agr, label=['Агротех', 'и финтех'])], pitch)
    # section divider: УРБАН -> УРБАНТЕХ
    from cat import remove_text_pdf
    p, i = gidx(26)
    print('divider suffix', E.add_suffix(PARTS[p], i, (600, 680, 1240, 830)))
    remove_text_pdf(PARTS[p], i, [(600, 640, 1240, 840)])
    E.LOG.append((id(PARTS[p]), PARTS[p].pages[i].objgen, 665.0, 742.0, 'Урбантех', 66))
    E.LOG.append((id(PARTS[p]), PARTS[p].pages[i].objgen, 642.0, 815.0, 'и стройтех', 66))


_KEEP = []


def do_inserts():
    import newspread as NS
    # process from the end so earlier indices stay valid
    SD.ROBOPROBE['impl_head_src'] = src(37)
    for D, after in sorted(INSERTS, key=lambda t: (-t[1], t[0].get('order', 0))):
        p, i = gidx(after)
        i += D.get('order', 0)
        tp, ti = gidx(D['tpl'])
        fresh = pikepdf.open('v2/p%d.pdf' % tp)   # own copy: templates used twice must not share objects
        PARTS[p].pages.insert(i + 1, fresh.pages[ti])
        _KEEP.append(fresh)
        if D.get('sup_tpl'):  # noqa
            sp_, si_ = gidx(D['sup_tpl'])
            D['sup_src'] = (SRC[sp_], si_)
        getattr(NS, D.get('builder', 'build'))(PARTS[p], i + 1, SRC[tp], ti, D)
        print('inserted', D['logo_text'], 'part', p, 'index', i + 1)

if __name__ == '__main__':
    import os
    os.makedirs('e', exist_ok=True)
    only = sys.argv[1:]
    for f in EDITS:
        if not only or f.__name__ in only:
            f()
            print('done', f.__name__)
    if not only or 'inserts' in only:
        do_inserts()
        import facts
        facts.facts_pass(PARTS, src(14))
    if not only or 'finalize' in only:
        finalize()
    # map page objgen -> index per part, then save + invisible text layer
    import pymupdf
    from cat import FD
    for p, pdf in PARTS.items():
        idx = {pg.objgen: i for i, pg in enumerate(pdf.pages)}
        todo = [(idx[og], x, y, t, s) for pid, og, x, y, t, s in E.LOG if pid == id(pdf) and og in idx]
        b = io.BytesIO()
        pdf.save(b)
        d = pymupdf.open('pdf', b.getvalue())
        done = set()
        for i, x, y, t, s in todo:
            pg = d[i]
            if i not in done:
                pg.insert_font(fontname='sbinv3', fontfile=FD + 'SBSansText-Regular.ttf')
                done.add(i)
            pg.insert_text((x, y), t.replace('\xa0', ' '), fontname='sbinv3', fontsize=s, render_mode=3)
        d.save('e/p%d.pdf' % p, garbage=3, deflate=True)
        print('part', p, 'pages', len(d), 'invisible lines', len(todo))
