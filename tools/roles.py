import pickle, statistics
from collections import defaultdict, Counter
D=pickle.load(open('lib2.pkl','rb')); outline=D['outline']; inst=D['inst']
HEAD={'инновационность','ключевые преимущества','эффект от внедрения','внедрения','запрос','производство','меры поддержки','выручка','год основания','производство и штат','достижения','штат','год','основания','производство и\xa0штат','ключевые преимущества'}
lines=defaultdict(list)
for g in inst: lines[(g['pg'],round(g['y'],1),round(g['size'],2))].append(g)
role_of={}
for k,gs in lines.items():
    gs.sort(key=lambda g:g['x'])
    txt=''.join(g['u'] for g in gs).strip().lower().replace(' ','')
    x0=gs[0]['x']; size=k[2]
    if size>=15.5 or txt in HEAD: r='H'
    elif abs(x0-755)<1.5 and abs(size-14)<0.1: r='B'
    elif size in (12.0,14.0): r='R'
    else: r=None
    for g in gs: g['role']=r
    role_of[k]=r
cnt={r:defaultdict(Counter) for r in 'HBR'}
for g in inst:
    r=g.get('role')
    if r and g['u'].strip():
        u=g['u'].replace('\u2028','').replace('\n','')
        if len(u)!=1: continue
        u=u.upper() if r=='H' else u
        cnt[r][u][g['sig']]+=1
sigH=set(c.most_common(1)[0][0] for c in cnt['H'].values()); sigB=set(c.most_common(1)[0][0] for c in cnt['B'].values())
sigHall=set(s for c in cnt['H'].values() for s in c)
def area(sig):
    tot=0.0
    for sub in outline.get(sig,[]):
        pts=[]; cur=None
        for op,p in sub:
            if op=='c' and cur:
                (x1,y1),(x2,y2),(x3,y3)=p
                for k in range(1,9):
                    t=k/8; a=(1-t)**3; b=3*(1-t)**2*t; c=3*(1-t)*t*t; d=t**3
                    pts.append((a*cur[0]+b*x1+c*x2+d*x3, a*cur[1]+b*y1+c*y2+d*y3))
                cur=p[-1]
            elif p:
                pts.extend(p); cur=p[-1]
        if len(pts)>2:
            tot+=sum(pts[i][0]*pts[i-1][1]-pts[i-1][0]*pts[i][1] for i in range(len(pts)))/2
    return abs(tot)
style={}
for r in 'HBR':
    m={}
    for u,c in cnt[r].items():
        if r=='R':
            cands=[(s,n) for s,n in c.items() if s in outline and s not in sigH and s not in sigB]
            if not cands:
                cands=[(s,n) for s,n in c.items() if s in outline and s not in sigHall]
            tot=sum(n for _,n in cands)
            cands=[(s,n) for s,n in cands if n>=max(2,0.03*tot)] or cands
            if cands:
                cands.sort(key=lambda sn:-sn[1])
                top=cands[0]
                for s2,n2 in cands[1:]:
                    if n2>=0.3*top[1] and 0.4*area(top[0])<area(s2)<0.8*area(top[0]):
                        top=(s2,n2)
                m[u]=top[0]
            continue
        for s,n in c.most_common():
            if s in outline: m[u]=s; break
    style[r]=m
# tracking: median adj between consecutive non-space glyphs per role
trk={}
for r in 'HBR':
    S=set(style[r].values())
    v=[g['adj'] for g in inst if g.get('role')==r and g['sig'] in S]
    trk[r]=statistics.median(v) if v else 0
# space widths per role
spw={}
for r in 'HBR':
    v=[g['wx'] for g in inst if g.get('role')==r and g['u'] in (' ','\xa0')]
    spw[r]=statistics.median(v) if v else 0.25
wx={}
for g in inst: wx[g['sig']]=g['wx']
# kerning: consecutive pairs within a line
kern=defaultdict(list)
for k,gs in lines.items():
    m=Counter(round(g['adj'],3) for g in gs[:-1]).most_common(1)
    base=m[0][0] if m else 0.0
    for a,b in zip(gs,gs[1:]):
        kern[(a['sig'],b['sig'])].append(a['adj']-base)
kern={k:statistics.median(v) for k,v in kern.items()}
pickle.dump(dict(style=style,trk=trk,spw=spw,wx=wx,outline=outline,kern=kern),open('styles.pkl','wb'))
if __name__=='__main__':
    for r in 'HBR':
        print(r,len(style[r]),'trk %.4f sp %.3f'%(trk[r],spw[r]),''.join(sorted(style[r])))
