import sys, json
sys.path.insert(0, "/root/mtlm/tools")
import numpy as np, head_probe as hp

def load(p):
    return [(hp.DECIDE_SYS, [], r["text"][:300], r.get("route","<oos>"))
            for r in (json.loads(l) for l in open(p))]

tr = load("/root/mtlm/data/civic_train.jsonl")
te = load("/root/mtlm/data/civic_holdout.jsonl")
oos = load("/root/mtlm/data/civic_oos.jsonl")
meta = [json.loads(l) for l in open("/root/mtlm/data/civic_oos.jsonl")]

labels = sorted({r[3] for r in tr}); lab = {l:i for i,l in enumerate(labels)}
ytr = np.array([lab[r[3]] for r in tr]); yte = np.array([lab[r[3]] for r in te])
taps = [(-2,"mean"),(-3,"mean"),(-4,"mean")]
rows = tr + te + oos
ntr, nte = len(tr), len(tr)+len(te)
F = hp.features("/root/mtlm/hf/router3s384", rows)
X = np.concatenate([F[t] for t in taps], axis=1)
Xtr, Xte, Xoos = X[:ntr], X[ntr:nte], X[nte:]
mu = Xtr.mean(0); sd = hp.feat_sd(Xtr)
W,b = hp.fit_lr((Xtr-mu)/sd, ytr, len(labels), 0.1)
# temp: refit on train-split dev? reuse emitted temp 0.593
temp = 0.593
def probs(X): return hp.softmax(((X-mu)/sd) @ W + b / temp if False else (((X-mu)/sd) @ W + b)/temp)
Pte, Poos = probs(Xte), probs(Xoos)
# conformal qhat at alpha .05 needs calib probs on labeled dev; reuse train->dev logic is complex;
# use simpler abstention rule consistent with served minconf/maxprob AND set-size via APS:
# auto iff prediction set size==1 under APS with qhat; approximate qhat from holdout itself? NO leak.
# honest: report maxprob distributions + auto-rate at minconf thresholds.
mp_te, mp_oos = Pte.max(1), Poos.max(1)
out = {"in_scope_acc": float((Pte.argmax(1)==yte).mean()),
       "maxprob": {"in_scope": {"p10":float(np.percentile(mp_te,10)),"median":float(np.median(mp_te))},
                    "oos": {"median":float(np.median(mp_oos)),"p90":float(np.percentile(mp_oos,90))}}}
for th in (0.5,0.7,0.9):
    out.setdefault("abstain_curve",{})[str(th)] = {
        "in_scope_auto": float((mp_te>=th).mean()),
        "oos_leak": float((mp_oos>=th).mean()),
        "id_oos_leak": float((mp_oos[[m["oos_kind"]=="id_oos" for m in meta]]>=th).mean()),
        "far_oos_leak": float((mp_oos[[m["oos_kind"]=="far_oos" for m in meta]]>=th).mean())}
# per-topic leak at th=0.5
per = {}
for m,p in zip(meta, mp_oos):
    per.setdefault(m["topic"],[]).append(float(p))
out["per_topic_median_maxprob"] = {k:float(np.median(v)) for k,v in per.items()}
print(json.dumps(out, indent=1))
