import pikepdf, pickle
from glyphlib import *
outline={}; inst=[]
for i in range(1,6):
    pdf=pikepdf.open(f'v2/p{i}.pdf')
    for j,pg in enumerate(pdf.pages):
        h=float(pg.mediabox[3])
        gl,samples=match_page(pg,h)
        for s in samples:
            outline.setdefault(s['sig'],s['outline'])
        allg=invisible_glyphs(pg,h)
        lines={}
        for g in allg: lines.setdefault(g['line'],[]).append(g)
        for lid,gs in lines.items():
            txt=''.join(g['u'] for g in gs)
            for g in gs:
                inst.append(dict(pg=(i,j),line=(i,j,lid),text=txt,x=g['x'],y=g['y'],size=g['size'],u=g['u'],sig=g['sig'],wx=g['wx'],adj=g['adj'],x0=gs[0]['x']))
pickle.dump(dict(outline=outline,inst=inst),open('lib2.pkl','wb'))
print(len(outline),len(inst))
