import subprocess, json, sys
PM=sys.argv[1]; root=int(sys.argv[2]); D=int(sys.argv[3]); out=sys.argv[4]
par={}  # child -> list of preds
layer=[root]; layers=[[root]]
for d in range(1,D+1):
    if not layer: break
    o=subprocess.run([PM]+[str(x) for x in layer],capture_output=True,text=True).stdout.split("\n")
    nxt=[]
    for l in o:
        if l.strip():
            p,c=map(int,l.split()); par.setdefault(c,[]).append(p); nxt.append(p)
    layer=sorted(set(nxt)); layers.append(layer)
    print(d,len(layer),flush=True)
    json.dump({"root":root,"layers":layers,"par":par},open(out,"w"))
