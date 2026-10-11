import sys, json, random, struct, os
sys.path.insert(0,"/root/mtlm/tools")
import numpy as np, head_probe as hp
random.seed(7)
"""emit_mairie_v2b.py — fit mairie+oos under BOTH tap configs from one cached
extraction; emits the config with the best in_scope (OOS recall held >=0.95)."""
FEATS="/root/mtlm/data/mairie_v2_feats.npz"
def load(p):
    return [(hp.DECIDE_SYS,[],r["user"][:300],r["expect_tool"]) for r in (json.loads(l) for l in open(p))]
tr_all = load("/root/mtlm/data/municipal12_train.jsonl") + load("/root/mtlm/data/mairie_oos_train.jsonl")
te = load("/root/mtlm/data/municipal12_holdout.jsonl")
oos_ev = load("/root/mtlm/data/mairie_oos_eval.jsonl")
by={}
for r in tr_all: by.setdefault(r[3],[]).append(r)
tr,dv=[],[]
for y,rs in by.items():
    random.shuffle(rs); n=int(len(rs)*0.85); tr+=rs[:n]; dv+=rs[n:]
labels=sorted({r[3] for r in tr_all}); lab={l:i for i,l in enumerate(labels)}
ytr=np.array([lab[r[3]] for r in tr]); ydv=np.array([lab[r[3]] for r in dv])
yte=np.array([lab[r[3]] for r in te]); yoos=np.array([lab["oos"]]*len(oos_ev))
rows=tr+dv+te+oos_ev; n1=len(tr); n2=n1+len(dv); n3=n2+len(te)
if os.path.exists(FEATS): F=hp.load_feats(FEATS)
else:
    F=hp.features("/root/mtlm/hf/router3s384",rows); hp.save_feats(FEATS,F,rows)
out={}
for name,taps in {"max_L243":[(-4,"max"),(-2,"max"),(-3,"max")],
                  "mean_L-234":[(-2,"mean"),(-3,"mean"),(-4,"mean")]}.items():
    X=np.concatenate([F[t] for t in taps],axis=1)
    Xtr,Xdv,Xte,Xo=X[:n1],X[n1:n2],X[n2:n3],X[n3:]
    mu=Xtr.mean(0); sd=hp.feat_sd(Xtr)
    W,b=hp.fit_lr((Xtr-mu)/sd,ytr,len(labels),0.1)
    temp,bn=1.0,1e18
    for t in np.exp(np.linspace(np.log(.25),np.log(64.),200)):
        P=hp.softmax((((Xdv-mu)/sd)@W+b)/t); nll=-np.log(np.maximum(P[np.arange(len(ydv)),ydv],1e-12)).mean()
        if nll<bn: bn,temp=nll,float(t)
    Pte=hp.softmax(((Xte-mu)/sd)@W+b); Po=hp.softmax(((Xo-mu)/sd)@W+b)
    am=Pte.argmax(1)
    out[name]={"in_scope":float((am==yte).mean()),
        "abstain_err":int(((am!=yte)&((am==lab["oos"])|(am==lab["escalate"]))).sum()),
        "wrong_route":int(((am!=yte)&(am!=lab["oos"])&(am!=lab["escalate"])).sum()),
        "oos_recall":float((Po.argmax(1)==lab["oos"]).mean()),
        "in_scope_false_oos":float((am==lab["oos"]).mean()),"temp":round(temp,3)}
print(json.dumps(out,indent=1))
# emit the max-tap variant if it wins in-scope while keeping oos>=0.95
best=max(out, key=lambda k:(out[k]["in_scope"] if out[k]["oos_recall"]>=0.95 else -1))
taps={"max_L243":[(-4,"max"),(-2,"max"),(-3,"max")],"mean_L-234":[(-2,"mean"),(-3,"mean"),(-4,"mean")]}[best]
X=np.concatenate([F[t] for t in taps],axis=1)
Xall=X[:n2]; yall=np.array([lab[r[3]] for r in tr+dv])
mu2=Xall.mean(0); sd2=hp.feat_sd(Xall)
W2,b2=hp.fit_lr((Xall-mu2)/sd2,yall,len(labels),0.1)
Wr=W2/sd2[:,None]; br=b2-(mu2/sd2)@W2; nl=6
KIND={"max":1,"mean":2}
with open("/root/mtlm/models/mairie_v2_mt.head","wb") as f:
    f.write(struct.pack("<i",0x3364686d)); f.write(struct.pack("<i",len(labels))); f.write(struct.pack("<i",W2.shape[0]))
    f.write(struct.pack("<f",out[best]["temp"])); f.write(struct.pack("<B",3))
    for pl,pk in taps: f.write(struct.pack("<BB",KIND[pk],nl+pl+1))
    f.write(Wr.T.astype(np.float32).tobytes()); f.write(br.astype(np.float32).tobytes())
    for l in labels: f.write(bytes([len(l)])); f.write(l.encode())
print(json.dumps({"emitted":"mairie_v2_mt.head","config":best,"taps":taps}))
