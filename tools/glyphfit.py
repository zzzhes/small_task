import pikepdf, io, glob, os
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from cat import *
from t3 import page_buf
_tt={}
def ink(f,ch,sz):
    if f not in _tt:
        t=TTFont(f); _tt[f]=(t,t.getGlyphSet(),t.getBestCmap(),t['head'].unitsPerEm)
    t,gs,cm,u=_tt[f]; p=BoundsPen(gs); gs[cm[ord(ch)]].draw(p); b=p.bounds
    adv=t['hmtx'][cm[ord(ch)]][0]*sz/u
    return (b[0]*sz/u,b[1]*sz/u,b[2]*sz/u,b[3]*sz/u,adv) if b else (0,0,0,0,adv)
def glyph_boxes(fi,pi,rect):
    p=pikepdf.open(io.BytesIO(page_buf(fi,pi)))
    bs=[b for b in path_boxes(p,0,rect) if b[2]-b[0]>0.05]
    # merge overlapping in x (holes) -> glyphs
    bs.sort(key=lambda b:b[0]); g=[]
    for b in bs:
        if g and b[0] < g[-1][2]-0.1 and b[2] <= g[-1][2]+0.3:
            o=g[-1]; g[-1]=(min(o[0],b[0]),min(o[1],b[1]),max(o[2],b[2]),max(o[3],b[3]))
        else: g.append(b)
    return g
def score(fi,pi,rect,text,sz,fonts):
    g=glyph_boxes(fi,pi,rect)
    chars=[c for c in text if c not in ' \xa0']
    print('glyphs',len(g),'chars',len(chars))
    res=[]
    for f in fonts:
        e=0;n=0
        for b,ch in zip(g,chars):
            i=ink(f,ch,sz); e+=abs((b[2]-b[0])-(i[2]-i[0]))+abs((b[3]-b[1])-(i[3]-i[1])); n+=1
        res.append((round(e/n,3),os.path.basename(f)))
    return sorted(res)[:5], g
ALL=[f for f in glob.glob(FD+'SBSans*.ttf') if 'Comp' not in f and 'Mono' not in f]
def analyze(fi,pi,rect,text,sz,fonts=None,verbose=False):
    g=glyph_boxes(fi,pi,rect)
    chars=[c for c in text if c not in ' \xa0']
    fonts=fonts or ALL
    out=[]
    for f in fonts:
        if len(g)!=len(chars): break
        e=0
        for b,ch in zip(g,chars):
            i=ink(f,ch,sz); e+=abs((b[2]-b[0])-(i[2]-i[0]))+abs((b[3]-b[1])-(i[3]-i[1]))
        # tracking
        adv=sum(ink(f,c,sz)[4] for c in text[:-1])
        lsb_f=ink(f,text[0],sz)[0]; lsb_l=ink(f,text[-1],sz)[0]
        span=g[-1][0]-g[0][0]
        tr=(span-(adv+lsb_l-lsb_f))/(len(text)-1)
        x0=g[0][0]-lsb_f
        out.append((round(e/len(g),3),os.path.basename(f),round(tr,3),round(x0,2)))
    out.sort()
    return out[:4], len(g), len(chars), (round(g[0][0],2), round(max(b[3] for b in g),2))
