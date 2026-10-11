import sys, json, random, struct, os
sys.path.insert(0,"/root/mtlm/tools")
import numpy as np, head_probe as hp
random.seed(7)
"""emit_mairie_v4.py — ORIGINAL municipal_train.jsonl (5.8k real rows, granular
labels merged to the 12-taxonomy) + oos negatives. Tests whether the synthetic
aug corpus was what degraded v2/v3's in-scope."""
MERGE={"dotation_de_bacs_om":"dotation_bacs","dotation_de_bacs_ts":"dotation_bacs",
 "dotation_de_bacs_om_et_ts":"dotation_bacs","dotation_de_bacs_om_ts_et_bio":"dotation_bacs",
 "dotation_bio_dechets":"dotation_bacs","changement_de_bacs_om":"changement_bacs",
 "changement_de_bacs_ts":"changement_bacs","changement_de_bacs_om_et_ts":"changement_bacs",
 "changement_biobac":"changement_bacs","changement_bioseau":"changement_bacs",
 "positionnement_des_bacs_om":"positionnement_bacs","positionnement_des_bacs_ts":"positionnement_bacs",
 "positionnement_des_bacs_om_et_ts":"positionnement_bacs","colonne_papier":"colonne_apport",
 "colonne_verre":"colonne_apport","collecte_bio_dechets":"collecte_bio",
 "composteurs":"compostage","sacs_jaunes":"sacs","agents_de_collecte":"agents"}
FEATS="/root/mtlm/data/mairie_v4_feats.npz"
def load(p, merge=False):
    out=[]
    for l in open(p):
        r=json.loads(l); y=MERGE.get(r["expect_tool"],r["expect_tool"]) if merge else r["expect_tool"]
        out.append((hp.DECIDE_SYS,[],r["user"][:300],y))
    return out
tr_all = load("/root/mtlm/data/municipal_train.jsonl",True) + load("/root/mtlm/data/mairie_oos_train.jsonl")
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
taps=[(-4,"max"),(-2,"max"),(-3,"max")]
X=np.concatenate([F[t] for t in taps],axis=1)
Xtr,Xdv,Xte,Xo=X[:n1],X[n1:n2],X[n2:n3],X[n3:]
mu=Xtr.mean(0); sd=hp.feat_sd(Xtr)
from sklearn.linear_model import LogisticRegression
m=LogisticRegression(C=0.01,max_iter=1500).fit((Xtr-mu)/sd,ytr)
Pte=m.predict_proba((Xte-mu)/sd); Po=m.predict_proba((Xo-mu)/sd)
am=Pte.argmax(1)
clean=set(json.load(open("/tmp/clean_idx.json")))
idx=[i for i in range(633) if i in clean]
res={"in_scope_full":float((am==yte).mean()),
 "in_scope_clean":float((am[idx]==yte[idx]).mean()),"n_clean":len(idx),
 "oos_recall":float((Po.argmax(1)==lab["oos"]).mean()),
 "in_scope_false_oos":float((am==lab["oos"]).mean()),
 "train_acc":float(m.score((Xtr-mu)/sd,ytr)),"n_train":n1,"n_classes":len(labels)}
print(json.dumps(res,indent=1))
# emit: refit on tr+dv
Xall=X[:n2]; yall=np.array([lab[r[3]] for r in tr+dv])
mu2=Xall.mean(0); sd2=hp.feat_sd(Xall)
m2=LogisticRegression(C=0.01,max_iter=1500).fit((Xall-mu2)/sd2,yall)
W2=m2.coef_.T; b2=m2.intercept_
temp,bn=1.0,1e18
Pdv=m2.predict_proba((Xdv-mu2)/sd2)
for t in np.exp(np.linspace(np.log(.25),np.log(64.),200)):
    Pr=hp.softmax(np.log(np.maximum(Pdv,1e-12))*t)  # temp via sharpen on log-probs
    nll=-np.log(np.maximum(Pr[np.arange(len(ydv)),ydv],1e-12)).mean()
    if nll<bn: bn,temp=nll,float(t)
Wr=W2/sd2[:,None]; br=b2-(mu2/sd2)@W2; nl=6
with open("/root/mtlm/models/mairie_v4_mt.head","wb") as f:
    f.write(struct.pack("<i",0x3364686d)); f.write(struct.pack("<i",len(labels))); f.write(struct.pack("<i",W2.shape[0]))
    f.write(struct.pack("<f",temp)); f.write(struct.pack("<B",3))
    for pl in (-4,-2,-3): f.write(struct.pack("<BB",1,nl+pl+1))
    f.write(Wr.T.astype(np.float32).tobytes()); f.write(br.astype(np.float32).tobytes())
    for l in labels: f.write(bytes([len(l)])); f.write(l.encode())
res["temp"]=round(temp,3); res["emitted"]="mairie_v4_mt.head"
print(json.dumps(res))
