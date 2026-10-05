"""Apply catalog edits (round 3) to v2 parts -> e/pN.pdf"""
import io
import sys
import pikepdf
import pymupdf as fitz
import edit as E
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
    for lead, rest in [('Генотип, фенотип, почва и климат', ' в одной прогностической модели'),
                       ('Анализ ДНК-маркеров', ' и ИИ-прогноз для подбора родительских пар'),
                       ('Оптимальный район', ' для сорта или гибрида с детальной технологической картой')]:
        E.copy_shapes(pdf, pi, b1, 0, y - 305.0, src_pi=spi, src_pdf=spdf)
        n, last = E.put_rich(pdf, pi, 66.0, y, [(lead, 'B'), (rest, 'R')], 14, navy, 234, 17)
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


EDITS = [sber500, axis, fitpolis, robotfight, mechbox, plastilin, aiolos, aiolos_text, trendsee, neurocode_team]

# new spreads: (data, insert after global g of the ORIGINAL v2 numbering)
import spreads_data as SD
INSERTS = [(SD.GARPIX, 45), (SD.HIVETRACE, 67), (SD.ROBOPROBE, 67), (SD.WEGOSTY, 83)]


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
    pitch = 21.5
    RIGHT = dict(label=(655, 800), bar=(803.8, 809.8), x=821.8, right=1202.8)
    LEFT = dict(label=(35, 178), bar=(179.8, 185.8), x=197.8, right=578.8)
    col = lambda c: c
    # page g2 (index 1): right column = Медтех (21) + first 10 Урбан rows
    erase(toc, 1, [(650, 88, 1215, 840)], max_wh=500)
    F.build_column(toc, 1, stoc, 1, RIGHT, [
        dict(label_src_top=94.0, color=(0.184314, 0.682353, 0.588235), rows=med, label=['Медтех', 'и биотех']),
        dict(label_src_top=597.0, color=(1.0, 0.6, 0.207843), rows=urb[:10], suffix=True,
             label=['Урбантех', 'и стройтех'])], pitch)
    # page g3 (index 2)
    erase(toc, 2, [(30, 88, 600, 840), (650, 88, 1215, 840)], max_wh=500)
    F.build_column(toc, 2, stoc, 2, LEFT, [
        dict(label_src_top=94.0, color=(1.0, 0.6, 0.207843), rows=urb[10:], suffix=True,
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


def do_inserts():
    import newspread as NS
    # process from the end so earlier indices stay valid
    for D, after in sorted(INSERTS, key=lambda t: (-t[1], t[0].get('order', 0))):
        p, i = gidx(after)
        i += D.get('order', 0)
        tp, ti = gidx(D['tpl'])
        PARTS[p].pages.insert(i + 1, SRC[tp].pages[ti])
        if D.get('sup_tpl'):
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
