import sys, json, random, struct
sys.path.insert(0,"/root/mtlm/tools")
import numpy as np, head_probe as hp
random.seed(7)
def load(p):
    return [(hp.DECIDE_SYS,[],r["text"][:300],r.get("route","oos")) for r in (json.loads(l) for l in open(p))]
tr_all = load("/root/mtlm/data/civic_fr_v2_train.jsonl")
te = load("/root/mtlm/data/civic_fr_holdout.jsonl")
oos_ev = load("/root/mtlm/data/civic_fr_oos_eval.jsonl")
meta=[json.loads(l) for l in open("/root/mtlm/data/civic_fr_oos_eval.jsonl")]
by={}
for r in tr_all: by.setdefault(r[3],[]).append(r)
tr,dv=[],[]
for y,rs in by.items():
    random.shuffle(rs); n=int(len(rs)*0.85); tr+=rs[:n]; dv+=rs[n:]
labels=sorted({r[3] for r in tr_all}); lab={l:i for i,l in enumerate(labels)}
ytr=np.array([lab[r[3]] for r in tr]); ydv=np.array([lab[r[3]] for r in dv])
yte=np.array([lab[r[3]] for r in te]); yoos=np.array([lab["oos"]]*len(oos_ev))
taps=[(-2,"mean"),(-3,"mean"),(-4,"mean")]
# emit rows = all train in tr+dv order; eval rows = te + oos_ev
rows=tr+dv+te+oos_ev; n1=len(tr); n2=n1+len(dv); n3=n2+len(te)
F=hp.features("/root/mtlm/hf/router3s384",rows)
X=np.concatenate([F[t] for t in taps],axis=1)
Xtr,Xdv,Xte,Xo=X[:n1],X[n1:n2],X[n2:n3],X[n3:]
mu=Xtr.mean(0); sd=hp.feat_sd(Xtr)
W,b=hp.fit_lr((Xtr-mu)/sd,ytr,len(labels),0.1)
temp,bn=1.0,1e18
for t in np.exp(np.linspace(np.log(.25),np.log(64.),200)):
    P=hp.softmax((((Xdv-mu)/sd)@W+b)/t); nll=-np.log(np.maximum(P[np.arange(len(ydv)),ydv],1e-12)).mean()
    if nll<bn: bn,temp=nll,float(t)
Pte=hp.softmax(((Xte-mu)/sd)@W+b); Po=hp.softmax(((Xo-mu)/sd)@W+b)
res={"in_scope_acc_trainonly":float((Pte.argmax(1)==yte).mean()),
 "oos_recall":float((Po.argmax(1)==lab["oos"]).mean()),
 "id_oos_recall":float((Po[[m["oos_kind"]=="id_oos" for m in meta]].argmax(1)==lab["oos"]).mean()),
 "far_oos_recall":float((Po[[m["oos_kind"]=="far_oos" for m in meta]].argmax(1)==lab["oos"]).mean()),
 "in_scope_false_oos":float((Pte.argmax(1)==lab["oos"]).mean()),
 "temp":round(temp,3),"n_classes":len(labels)}
# emit: fit on ALL train rows (tr+dv order = same as features)
Xall=X[:n2]; yall=np.array([lab[r[3]] for r in tr+dv])
mu2=Xall.mean(0); sd2=hp.feat_sd(Xall)
W2,b2=hp.fit_lr((Xall-mu2)/sd2,yall,len(labels),0.1)
Wr=W2/sd2[:,None]; br=b2-(mu2/sd2)@W2; nl=6
with open("/root/mtlm/models/civic_fr_v2_mt.head","wb") as f:
    f.write(struct.pack("<i",0x3364686d)); f.write(struct.pack("<i",len(labels))); f.write(struct.pack("<i",W2.shape[0]))
    f.write(struct.pack("<f",temp)); f.write(struct.pack("<B",3))
    for pl in (-2,-3,-4): f.write(struct.pack("<BB",2,nl+pl+1))
    f.write(Wr.T.astype(np.float32).tobytes()); f.write(br.astype(np.float32).tobytes())
    for l in labels: f.write(bytes([len(l)])); f.write(l.encode())
res["emitted"]="civic_fr_v2_mt.head"; res["oos_train"]=int((yall==lab["oos"]).sum())
print(json.dumps(res,indent=1))
