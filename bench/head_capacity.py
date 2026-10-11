import sys, json, random
sys.path.insert(0,"/root/mtlm/tools")
import numpy as np, head_probe as hp
"""head_capacity.py — linear vs 2-layer MLP head on identical frozen features.
Answers: is the ~7KB linear head the bottleneck, or the feature space?
Runs on rbm21 (needs hf/router3s384 + head_probe)."""
random.seed(7); np.random.seed(7)
def load(p):
    return [(hp.DECIDE_SYS,[],r["text"][:300],r.get("route","oos")) for r in (json.loads(l) for l in open(p))]
tr_all = load("/root/mtlm/data/civic_fr_v2_train.jsonl") + load("/root/mtlm/data/civic_fr_natural_train.jsonl")*4
te = load("/root/mtlm/data/civic_fr_holdout.jsonl")
oos_ev = load("/root/mtlm/data/civic_fr_oos_eval.jsonl")
nat_ev = load("/root/mtlm/data/civic_fr_natural_eval.jsonl")
meta=[json.loads(l) for l in open("/root/mtlm/data/civic_fr_oos_eval.jsonl")]
by={}
for r in tr_all: by.setdefault(r[3],[]).append(r)
tr,dv=[],[]
for y,rs in by.items():
    random.shuffle(rs); n=int(len(rs)*0.85); tr+=rs[:n]; dv+=rs[n:]
labels=sorted({r[3] for r in tr_all}); lab={l:i for i,l in enumerate(labels)}; C=len(labels)
taps=[(-2,"mean"),(-3,"mean"),(-4,"mean")]
rows=tr+dv+te+oos_ev+nat_ev; n1=len(tr); n2=n1+len(dv); n3=n2+len(te); n4=n3+len(oos_ev)
F=hp.features("/root/mtlm/hf/router3s384",rows)
X=np.concatenate([F[t] for t in taps],axis=1)
Xtr,Xdv,Xte,Xo,Xn=X[:n1],X[n1:n2],X[n2:n3],X[n3:n4],X[n4:]
ytr=np.array([lab[r[3]] for r in tr]); ydv=np.array([lab[r[3]] for r in dv])
yte=np.array([lab[r[3]] for r in te]); ynat=np.array([lab[r[3]] for r in nat_ev])
mu=Xtr.mean(0); sd=hp.feat_sd(Xtr)
def ev(P,tag):
    return {f"{tag}_acc":float((P.argmax(1)[-len(tag):]*0))} # unused
# --- linear ---
W,b=hp.fit_lr((Xtr-mu)/sd,ytr,C,0.1)
def linp(Xx): return hp.softmax(((Xx-mu)/sd)@W+b)
# --- MLP 384x64 x C, numpy, 60 epochs adam ---
H=64; rng=np.random.default_rng(7)
W1=rng.normal(0,np.sqrt(2/Xtr.shape[1]),(Xtr.shape[1],H)); b1=np.zeros(H)
W2=rng.normal(0,np.sqrt(2/H),(H,C)); b2=np.zeros(C)
Z=(Xtr-mu)/sd; Y=np.eye(C)[ytr]
m={k:np.zeros_like(v) for k,v in [("W1",W1),("b1",b1),("W2",W2),("b2",b2)]}
v={k:np.zeros_like(kk) for k,kk in m.items()}
lr=1e-3; b1a,b2a,eps=0.9,0.999,1e-8
for ep in range(60):
    h=np.maximum(Z@W1+b1,0); logits=h@W2+b2
    P=np.exp(logits-logits.max(1,keepdims=True)); P/=P.sum(1,keepdims=True)
    g=(P-Y)/len(Z)
    dW2=h.T@g; db2=g.sum(0); dh=(g@W2.T)*(Z@W1+b1>0); dW1=Z.T@dh; db1=dh.sum(0)
    for k,gg in [("W1",dW1),("b1",db1),("W2",dW2),("b2",db2)]:
        m[k]=b1a*m[k]+(1-b1a)*gg; v[k]=b2a*v[k]+(1-b2a)*gg*gg
    t=ep+1
    W1-=lr*m["W1"]/(1-b1a**t)/(np.sqrt(v["W1"]/(1-b2a**t))+eps)
    b1-=lr*m["b1"]/(1-b1a**t)/(np.sqrt(v["b1"]/(1-b2a**t))+eps)
    W2-=lr*m["W2"]/(1-b1a**t)/(np.sqrt(v["W2"]/(1-b2a**t))+eps)
    b2-=lr*m["b2"]/(1-b1a**t)/(np.sqrt(v["b2"]/(1-b2a**t))+eps)
def mlpp(Xx):
    h=np.maximum(((Xx-mu)/sd)@W1+b1,0); lo=h@W2+b2
    P=np.exp(lo-lo.max(1,keepdims=True)); return P/P.sum(1,keepdims=True)
res={}
for name,fn in [("linear",linp),("mlp64",mlpp)]:
    Pte,Po,Pn=fn(Xte),fn(Xo),fn(Xn)
    res[name]={"in_scope":round(float((Pte.argmax(1)==yte).mean()),3),
     "oos_recall":round(float((Po.argmax(1)==lab["oos"]).mean()),3),
     "id_oos":round(float((Po[[m["oos_kind"]=="id_oos" for m in meta]].argmax(1)==lab["oos"]).mean()),3),
     "far_oos":round(float((Po[[m["oos_kind"]=="far_oos" for m in meta]].argmax(1)==lab["oos"]).mean()),3),
     "natural_acc":round(float((Pn.argmax(1)==ynat).mean()),3),
     "natural_foos":round(float((Pn.argmax(1)==lab["oos"]).mean()),3)}
print(json.dumps(res,indent=1))
