import sys, json, random, os, struct
sys.path.insert(0, "/root/mtlm/tools")
import numpy as np
import head_probe as hp

MODEL="/root/mtlm/hf/router3s384"
SYS="Classify the emotional tone of the message. Labels: confused, distressed, frustrated, neutral, positive, oos."
random.seed(11)

tr_all=[(SYS,c,u[:300],y) for s,c,u,y in hp.load("/root/mtlm/data/eq_train.jsonl")]
dv=[(SYS,c,u[:300],y) for s,c,u,y in hp.load("/root/mtlm/data/eq_dev.jsonl")]
te=[(SYS,c,u[:300],y) for s,c,u,y in hp.load("/root/mtlm/data/eq_test.jsonl")]
by={}
for r in tr_all: by.setdefault(r[3],[]).append(r)
tr=[]
for y,rs in by.items():
    random.shuffle(rs); tr+=rs[:2500]

# hard negatives: text that is NOT an emotional-tone message (in-domain OOS)
neg=[]
for f in ("/root/mtlm/data/clinc_hn_train.jsonl",
          "/root/mtlm/data/b77/bank77_train.jsonl",
          "/root/mtlm/data/b77/bank77_idoos_train.jsonl"):
    rs=hp.load(f); random.shuffle(rs)
    neg+=[(SYS,c,u[:300],"oos") for s,c,u,y in rs[:500]]
tr+=neg; random.shuffle(tr)

neg_eval=[]
for f in ("/root/mtlm/data/clinc_hn_eval.jsonl",
          "/root/mtlm/data/b77/bank77_oodoos_test.jsonl",
          "/root/mtlm/data/b77/bank77_test.jsonl"):
    rs=hp.load(f); random.shuffle(rs)
    neg_eval+=[(SYS,c,u[:300],"oos") for s,c,u,y in rs[:500]]

labels=sorted({r[3] for r in tr+dv+te+neg_eval}); lab={l:i for i,l in enumerate(labels)}
ytr=np.array([lab[r[3]] for r in tr]); ydv=np.array([lab[r[3]] for r in dv]); yte=np.array([lab[r[3]] for r in te])
yneg=np.array([lab[r[3]] for r in neg_eval])
rows=tr+dv+te+neg_eval; n1=len(tr); n2=n1+len(dv); n3=n2+len(te)

if os.path.exists("/tmp/eq3F.npz"):
    F=hp.load_feats("/tmp/eq3F.npz")
else:
    F=hp.features(MODEL, rows); hp.save_feats("/tmp/eq3F.npz", F, rows)

best=None
for taps in [t for t in (((-2,"mean"),(-3,"mean"),(-4,"mean")),((-1,"mean"),(-2,"mean"),(-3,"mean"),(-4,"mean")),((-4,"mean"),),((-3,"max"),(-4,"max")),((-2,"mean"),(-3,"mean"),(-4,"mean"),(-3,"max"))) if all(k in F for k in t)]:
    X=np.concatenate([F[t] for t in taps],axis=1); Xtr,Xdv=X[:n1],X[n1:n2]
    for l2 in (3e-3,1e-2,1e-1):
        mu=Xtr.mean(0); sd=hp.feat_sd(Xtr); W,b=hp.fit_lr((Xtr-mu)/sd,ytr,len(labels),l2)
        Z=((Xdv-mu)/sd)@W+b
        acc=(Z.argmax(1)==ydv).mean()
        print(json.dumps({"taps":taps,"l2":l2,"dev_acc":round(float(acc),4)}),flush=True)
        if best is None or acc>best[0]: best=(acc,taps,l2)
acc,taps,l2=best
X=np.concatenate([F[t] for t in taps],axis=1)
Xtr,Xdv,Xte,Xneg=X[:n1],X[n1:n2],X[n2:n3],X[n3:]
mu=Xtr.mean(0); sd=hp.feat_sd(Xtr); W,b=hp.fit_lr((Xtr-mu)/sd,ytr,len(labels),l2)
Zdv=((Xdv-mu)/sd)@W+b; Zte=((Xte-mu)/sd)@W+b; Zneg=((Xneg-mu)/sd)@W+b
temp,bn=1.0,1e18
for t in np.exp(np.linspace(np.log(.25),np.log(64.),200)):
    P=hp.softmax(Zdv/t); nll=-np.log(np.maximum(P[np.arange(len(ydv)),ydv],1e-12)).mean()
    if nll<bn: bn,temp=nll,float(t)
te_acc=(Zte.argmax(1)==yte).mean()
oos_i=lab["oos"]
neg_rec=(Zneg.argmax(1)==oos_i).mean()

Wr=W/sd[:,None]; br=b-(mu/sd)@W
with open("/root/mtlm/models/eq_tone_v2.head","wb") as f:
    f.write(struct.pack("<i",0x3364686d)); f.write(struct.pack("<i",len(labels))); f.write(struct.pack("<i",X.shape[1]))
    f.write(struct.pack("<f",temp)); f.write(struct.pack("<B",len(taps)))
    for pl,pk in taps: f.write(struct.pack("<BB",1 if pk=="max" else 2,6+pl+1))
    f.write(Wr.T.astype(np.float32).tobytes()); f.write(br.astype(np.float32).tobytes())
    for l in labels: f.write(bytes([len(l)])); f.write(l.encode())
print(json.dumps({"emitted":"eq_tone_v2.head","taps":taps,"l2":l2,"temp":round(temp,4),"te_acc":round(float(te_acc),4),"oos_recall":round(float(neg_rec),4),"n_tr":len(tr),"labels":labels}))
