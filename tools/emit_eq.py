import sys, json, random
sys.path.insert(0, "/root/mtlm/tools")
import numpy as np
import head_probe as hp

random.seed(7)
tr_all=[(hp.DECIDE_SYS,c,u[:300],y) for s,c,u,y in hp.load("/root/mtlm/data/eq_train.jsonl")]
dv=[(hp.DECIDE_SYS,c,u[:300],y) for s,c,u,y in hp.load("/root/mtlm/data/eq_dev.jsonl")]
te=[(hp.DECIDE_SYS,c,u[:300],y) for s,c,u,y in hp.load("/root/mtlm/data/eq_test.jsonl")]

# balanced train subsample, 2500/class
by={}
for r in tr_all: by.setdefault(r[3],[]).append(r)
tr=[]
for y,rs in by.items():
    random.shuffle(rs); tr+=rs[:2500]
random.shuffle(tr)
print(json.dumps({"n_train":len(tr),"n_dev":len(dv),"n_test":len(te),
                  "per_class":{y:min(len(rs),2500) for y,rs in by.items()}}),flush=True)

labels=sorted({r[3] for r in tr+dv+te}); lab={l:i for i,l in enumerate(labels)}
ytr=np.array([lab[r[3]] for r in tr]); ydv=np.array([lab[r[3]] for r in dv]); yte=np.array([lab[r[3]] for r in te])

rows=tr+dv+te; ntr=len(tr); ndv=len(dv)
F=hp.features("/root/mtlm/hf/router3s384", rows)
n1=ntr; n2=ntr+ndv
best=None
for taps in ([(-2,"mean"),(-3,"mean"),(-4,"mean")],[(-4,"mean")],[(-3,"max"),(-4,"max")],[(-2,"mean"),(-3,"mean"),(-4,"mean"),(-3,"max")]):
    X=np.concatenate([F[t] for t in taps],axis=1); Xtr,Xdv=X[:n1],X[n1:n2]
    for l2 in (1e-2,1e-1):
        mu=Xtr.mean(0); sd=hp.feat_sd(Xtr); W,b=hp.fit_lr((Xtr-mu)/sd,ytr,len(labels),l2)
        Z=((Xdv-mu)/sd)@W+b
        acc=(Z.argmax(1)==ydv).mean()
        print(json.dumps({"taps":taps,"l2":l2,"dev_acc":round(float(acc),4)}),flush=True)
        if best is None or acc>best[0]: best=(acc,taps,l2)
acc,taps,l2=best
X=np.concatenate([F[t] for t in taps],axis=1)
Xtr,Xdv,Xte=X[:n1],X[n1:n2],X[n2:]
mu=Xtr.mean(0); sd=hp.feat_sd(Xtr); W,b=hp.fit_lr((Xtr-mu)/sd,ytr,len(labels),l2)
Zdv=((Xdv-mu)/sd)@W+b; Zte=((Xte-mu)/sd)@W+b
# temperature on dev
temp,bn=1.0,1e18
for t in np.exp(np.linspace(np.log(.25),np.log(64.),200)):
    P=hp.softmax(Zdv/t); nll=-np.log(np.maximum(P[np.arange(len(ydv)),ydv],1e-12)).mean()
    if nll<bn: bn,temp=nll,float(t)
Pte=hp.softmax(Zte/temp); Pdv=hp.softmax(Zdv/temp)
te_acc=(Zte.argmax(1)==yte).mean()
# conformal: calibrate qhat on dev, evaluate on test (nonconformity = 1 - p_true)
def qhat_at(P,y,alpha):
    s=1.-P[np.arange(len(y)),y]; n=len(y)
    return float(np.quantile(s,min(1.0,np.ceil((n+1)*(1-alpha))/n),method="higher"))
conf={}
for alpha in (0.15,0.10,0.05,0.02):
    qh=qhat_at(Pdv,ydv,alpha)
    # eval: prediction sets on test
    inc=Pte>=1.-qh
    setsize=inc.sum(1); auto=setsize==1
    pick=np.where(setsize==1,inc.argmax(1),-1)
    err=(pick[auto]!=yte[auto]).mean() if auto.any() else float("nan")
    conf[f"alpha_{alpha}"]={"qhat":round(qh,4),"auto":round(float(auto.mean()),4),
                            "err":round(float(err),4),"avgset":round(float(setsize.mean()),3)}
Wr=W/sd[:,None]; br=b-(mu/sd)@W
import struct
with open("/root/mtlm/models/eq_tone_mt.head","wb") as f:
    f.write(struct.pack("<i",0x3364686d)); f.write(struct.pack("<i",len(labels))); f.write(struct.pack("<i",X.shape[1]))
    f.write(struct.pack("<f",temp)); f.write(struct.pack("<B",len(taps)))
    for pl,pk in taps: f.write(struct.pack("<BB",1 if pk=="max" else 2,6+pl+1))
    f.write(Wr.T.astype(np.float32).tobytes()); f.write(br.astype(np.float32).tobytes())
    for l in labels: f.write(bytes([len(l)])); f.write(l.encode())
print(json.dumps({"emitted":"eq_tone_mt.head","test_acc":round(float(te_acc),4),"taps":taps,
                  "temp":round(temp,4),"n_classes":len(labels),"labels":labels,"conformal":conf}),flush=True)
