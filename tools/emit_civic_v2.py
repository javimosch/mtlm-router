import sys, json, random
sys.path.insert(0, "/root/mtlm/tools")
import numpy as np, head_probe as hp
random.seed(7)
def load(p):
    return [(hp.DECIDE_SYS, [], r["text"][:300], r.get("route","oos"))
            for r in (json.loads(l) for l in open(p))]
tr_all = load("/root/mtlm/data/civic_v2_train.jsonl")
te = load("/root/mtlm/data/civic_holdout.jsonl")
oos = load("/root/mtlm/data/civic_oos.jsonl")
meta = [json.loads(l) for l in open("/root/mtlm/data/civic_oos.jsonl")]
by = {}
for r in tr_all: by.setdefault(r[3], []).append(r)
tr, dv = [], []
for y, rs in by.items():
    random.shuffle(rs); n = int(len(rs)*0.85); tr += rs[:n]; dv += rs[n:]
labels = sorted({r[3] for r in tr_all}); lab = {l:i for i,l in enumerate(labels)}
ytr = np.array([lab[r[3]] for r in tr]); ydv = np.array([lab[r[3]] for r in dv])
yte = np.array([lab[r[3]] for r in te]); yoos = np.array([lab["oos"]]*len(oos))
taps = [(-2,"mean"),(-3,"mean"),(-4,"mean")]
rows = tr + dv + te + oos; n1 = len(tr); n2 = n1+len(dv); n3 = n2+len(te)
F = hp.features("/root/mtlm/hf/router3s384", rows)
X = np.concatenate([F[t] for t in taps], axis=1)
Xtr,Xdv,Xte,Xo = X[:n1],X[n1:n2],X[n2:n3],X[n3:]
mu = Xtr.mean(0); sd = hp.feat_sd(Xtr)
W,b = hp.fit_lr((Xtr-mu)/sd, ytr, len(labels), 0.1)
temp, bn = 1.0, 1e18
for t in np.exp(np.linspace(np.log(.25), np.log(64.), 200)):
    P = hp.softmax(((Xdv-mu)/sd)@W + b); P = P**(1.0/t); P /= P.sum(1,keepdims=True)
    nll = -np.log(np.maximum(P[np.arange(len(ydv)),ydv],1e-12)).mean()
    if nll<bn: bn,temp = nll,float(t)
def probs(X):
    P = hp.softmax(((X-mu)/sd)@W + b); P = P**(1.0/temp); return P/P.sum(1,keepdims=True)
Pte, Po = probs(Xte), probs(Xo)
in_acc = float((Pte.argmax(1)==yte).mean())
oos_recall = float((Po.argmax(1)==lab["oos"]).mean())
idmask = np.array([m["oos_kind"]=="id_oos" for m in meta]); farmask = ~idmask
p_oos_class_te = 1 - Pte[:,lab["oos"]]  # in-scope confidence excluding oos
res = {"n_classes":len(labels),"temp":round(temp,3),
 "in_scope_acc":in_acc, "oos_recall":oos_recall,
 "id_oos_recall":float((Po[idmask].argmax(1)==lab["oos"]).mean()),
 "far_oos_recall":float((Po[farmask].argmax(1)==lab["oos"]).mean()),
 "in_scope_false_oos":float((Pte.argmax(1)==lab["oos"]).mean()),
 "end2end": float(((Pte.argmax(1)==yte).sum()+(Po.argmax(1)==lab["oos"]).sum())/(len(yte)+len(yoos)))}
# emit head trained on all civic+oos rows
yall = np.array([lab[r[3]] for r in tr_all])
Xall = X[:len(tr_all)]
mu2 = Xall.mean(0); sd2 = hp.feat_sd(Xall)
W2,b2 = hp.fit_lr((Xall-mu2)/sd2, yall, len(labels), 0.1)
res["labels"]=labels; res["oos_train"]=int((yall==lab["oos"]).sum())
print(json.dumps(res, indent=1))
# reuse hp emit? write raw for now
np.savez("/tmp/civic_v2_head.npz", W=W2,b=b2,mu=mu2,sd=sd2,temp=temp)
