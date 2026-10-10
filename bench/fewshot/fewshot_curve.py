# Few-shot learning curve: N labeled examples/route -> holdout accuracy.
# Run on rbm21 (needs the HF export + head_probe.py):
#   python3 fewshot_curve.py
# Corpus: ../mtl-data/municipal/municipal12_{train,holdout}.jsonl (sync
#   ../mtl-data/municipal/); model: /root/mtlm/hf/router3s384.
# Results committed alongside this file as municipal_curve.jsonl.
import sys, json, random
sys.path.insert(0, "/root/mtlm/tools")
import numpy as np
import head_probe as hp

tr=[(hp.DECIDE_SYS,c,u[:300],y) for s,c,u,y in hp.load("../mtl-data/municipal/municipal12_train.jsonl")]
ho=[(hp.DECIDE_SYS,c,u[:300],y) for s,c,u,y in hp.load("../mtl-data/municipal/municipal12_holdout.jsonl")]
labels=sorted({r[3] for r in tr}); lab={l:i for i,l in enumerate(labels)}
yho=np.array([lab[r[3]] for r in ho])
print(f"train={len(tr)} holdout={len(ho)} classes={len(labels)}", file=sys.stderr)
F=hp.features("/root/mtlm/hf/router3s384", tr+ho)
taps=[(-2,"mean"),(-3,"mean"),(-4,"mean")]
X=np.concatenate([F[t] for t in taps],axis=1)
Xtr,Xho=X[:len(tr)],X[len(tr):]
random.seed(11)
for n in (5,10,25,50,100,200,400,10**9):
    idx=[]
    by={}
    for i,r in enumerate(tr): by.setdefault(r[3],[]).append(i)
    for l,ix in by.items():
        random.shuffle(ix); idx += ix[:n]
    idx=sorted(idx)
    ys=np.array([lab[tr[i][3]] for i in idx])
    Xt=Xtr[idx]
    mu=Xt.mean(0); sd=hp.feat_sd(Xt)
    W,b=hp.fit_lr((Xt-mu)/sd,ys,len(labels),1e-2)
    Z=((Xho-mu)/sd)@W+b
    acc=(Z.argmax(1)==yho).mean()
    P=hp.softmax(Z)
    conf=P.max(1)
    # auto@conf-floor-0.7 and conformal-ish: % rows with top-conf>=0.7 and their error
    m=conf>=0.7; auto=m.mean(); err=(Z.argmax(1)[m]!=yho[m]).mean() if m.sum() else 0
    eff=n if n<10**9 else "all"
    print(json.dumps({"n_per_class":eff,"rows":len(idx),"acc":round(float(acc),4),"auto@0.7":round(float(auto),3),"err_auto":round(float(err),4)}))
