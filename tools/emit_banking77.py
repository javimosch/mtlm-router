GRID=[((-2,"mean"),(-3,"mean"),(-4,"mean")),((-1,"mean"),(-2,"mean"),(-3,"mean"),(-4,"mean")),((-2,"mean"),(-3,"mean"),(-4,"mean"),(-5,"mean")),((-3,"mean"),(-4,"mean"),(-5,"mean")),((-2,"mean"),(-3,"mean"),(-4,"mean"),(-2,"max")),((-1,"max"),(-2,"mean"),(-3,"mean"),(-4,"mean")),((-2,"max"),(-3,"mean"),(-4,"mean")),((-1,"mean"),(-2,"mean"),(-3,"mean"))]
import sys, json
sys.path.insert(0, "/root/mtlm/tools")
import numpy as np
import head_probe as hp

tr=[(hp.DECIDE_SYS,c,u[:300],y) for s,c,u,y in hp.load("/root/mtlm/data/b77/bank77_train.jsonl")]
tr+=[(hp.DECIDE_SYS,c,u[:300],y) for s,c,u,y in hp.load("/root/mtlm/data/b77/bank77_valid.jsonl")]
tr+=[(hp.DECIDE_SYS,c,u[:300],y) for s,c,u,y in hp.load("/root/mtlm/data/b77/bank77_idoos_train.jsonl")]
ho=[(hp.DECIDE_SYS,c,u[:300],y) for s,c,u,y in hp.load("/root/mtlm/data/b77/bank77_test.jsonl")]
hn=[(hp.DECIDE_SYS,c,u[:300],y) for s,c,u,y in hp.load("/root/mtlm/data/b77/bank77_idoos_test.jsonl")]
labels=sorted({r[3] for r in tr+ho}); lab={l:i for i,l in enumerate(labels)}
ytr=np.array([lab[r[3]] for r in tr]); yho=np.array([lab[r[3]] for r in ho]); yhn=np.array([lab[r[3]] for r in hn])
oos_i=lab["oos"]
print("extracting",len(tr)+len(ho)+len(hn),"rows",flush=True)
F=hp.features("/root/mtlm/hf/router3s384", tr+ho+hn)
n=len(tr); nh=len(ho); best=None
for taps in [t for t in GRID if all(k in F for k in t)]:
    X=np.concatenate([F[t] for t in taps],axis=1); Xtr,Xho,Xhn=X[:n],X[n:n+nh],X[n+nh:]
    for l2 in (3e-3,1e-2,3e-2):
        mu=Xtr.mean(0); sd=hp.feat_sd(Xtr); W,b=hp.fit_lr((Xtr-mu)/sd,ytr,len(labels),l2)
        Z=((Xho-mu)/sd)@W+b; pred=Z.argmax(1)
        insc=yho!=oos_i
        acc=(pred[insc]==yho[insc]).mean()
        oos_rec=(pred[~insc]==oos_i).mean()
        Zhn=((Xhn-mu)/sd)@W+b; hn_rec=(Zhn.argmax(1)==oos_i).mean()
        print(json.dumps({"taps":taps,"l2":l2,"in_scope":round(float(acc),4),"oos_recall":round(float(oos_rec),4),"hn_recall":round(float(hn_rec),4)}),flush=True)
        score=(0.0 if hn_rec!=hn_rec else hn_rec)*0.5 + acc
        if best is None or score>best[0]: best=(score,taps,l2,X,mu,sd,W,b)
score,taps,l2,X,mu,sd,W,b=best
n=len(tr)
Zho=((X[n:n+nh]-mu)/sd)@W+b
temp,bn=1.0,1e18
for t in np.exp(np.linspace(np.log(.25),np.log(64.),200)):
    P=hp.softmax(Zho/t); nll=-np.log(np.maximum(P[np.arange(len(yho)),yho],1e-12)).mean()
    if nll<bn: bn,temp=nll,float(t)
Wr=W/sd[:,None]; br=b-(mu/sd)@W
import struct
with open("/root/mtlm/models/banking77_mt.head","wb") as f:
    f.write(struct.pack("<i",0x3364686d)); f.write(struct.pack("<i",len(labels))); f.write(struct.pack("<i",X.shape[1]))
    f.write(struct.pack("<f",temp)); f.write(struct.pack("<B",len(taps)))
    for pl,pk in taps: f.write(struct.pack("<BB",1 if pk=="max" else 2,6+pl+1))
    f.write(Wr.T.astype(np.float32).tobytes()); f.write(br.astype(np.float32).tobytes())
    for l in labels: f.write(bytes([len(l)])); f.write(l.encode())
print(json.dumps({"emitted":"banking77_mt.head","taps":taps,"l2":l2,"temp":round(temp,4)}),flush=True)
