import json, sys, itertools
import numpy as np
sys.path.insert(0, "/mnt/project-files/levelup/rng")
from run_plans import data
from fe_growth import level_up, exam_roll
T=json.load(open("tree.json")); par={int(k):v for k,v in T["par"].items()}; root=T["root"]
NAME="迪托利希"; CL=["平民","猎兵","斗士"]
targets={"力9速10技8":(7,9,7,10,8,5,2,8,11),"力8速10技8":(7,8,7,10,8,5,2,8,11),
         "力9速9技9":(7,9,7,9,9,5,2,8,11),"力8速9技9":(7,8,7,9,9,5,2,8,11)}
TG=np.array(list(targets.values()))
def paths(s,L):
    if L==0: yield [s]; return
    for p in par.get(s,[]):
        for q in paths(p,L-1): yield q+[s]
best=[]
for L in range(15,21):
    k=L-15
    if k<1: continue
    for P in paths(root,L):
        st=P[:-1]
        Gm=np.array([[level_up(s,data.growth(NAME,c,10),2).gains for c in CL] for s in st],dtype=int)  # L x3x9
        for E in itertools.combinations(range(L),k):
            Es=set(E); lvl=[i for i in range(L) if i not in Es]
            for a in range(k):
                for b in range(a,k):
                    p1,p2=E[a],E[b]
                    for X in (1,2,0):
                        cls=[0 if i<p1 else (X if i<p2 else 2) for i in lvl]
                        tot=Gm[lvl,cls].sum(0)
                        d=np.abs(TG-tot).sum(1)
                        j=int(d.argmin())
                        if d[j]<=2: best.append((int(d[j]),L,list(targets)[j],P,E,p1,p2,CL[X],tot.tolist()))
best.sort(key=lambda r:(r[0],r[1]))
print(len(best))
seen=set()
for r in best[:40]:
    print(r[0],r[1],r[2],"起始种子",r[3][0],"考试步",r[4],"过1",r[5],"过2",r[6],"中段",r[7],r[8])
json.dump(best[:200],open("fit2.json","w"),ensure_ascii=False)
