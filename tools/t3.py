import pikepdf, pymupdf as fitz, io, glob, os
import numpy as np
from cat import *
import cat
def page_buf(fi,pi):
    src=pikepdf.open(f'v2/p{fi}.pdf'); one=pikepdf.new(); one.pages.append(src.pages[pi]); b=io.BytesIO(); one.save(b); return b.getvalue()
def render(d,clip):
    pix=d[0].get_pixmap(dpi=300,clip=clip,colorspace=fitz.csGRAY); return np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.h,pix.w).astype(int)
def test(fi,pi,rect,x,y,text,size,color,cands,tracks=(0,)):
    buf=page_buf(fi,pi); clip=fitz.Rect(rect)+(-3,-3,3,3)
    orig=render(fitz.open('pdf',buf),clip); out=[]
    for k in cands:
        FONTS[k]=FD+k; cat._fcache.pop(k,None)
        for tr in tracks:
            p2=pikepdf.open(io.BytesIO(buf)); erase(p2,0,[rect]); b2=io.BytesIO(); p2.save(b2); d=fitz.open('pdf',b2.getvalue())
            draw(d[0],x,y,text,k,size,color,tracking=tr)
            out.append((np.abs(render(d,clip)-orig).mean(),k,tr))
    out.sort(); return out[:5]
if __name__=='__main__':
    c=[os.path.basename(f) for f in glob.glob(FD+'SBSans*.ttf') if 'Italic' not in f]
    print(test(4,7,(985,150,1110,168),988,161.52,'Участник Сбер500',12,hexc('0c1628'),c))
