import sys, json, collections
sys.path.insert(0,"/root/mtlm/tools")
import numpy as np
import head_probe as hp
tr=[json.loads(l) for l in open("/root/mtlm/data/s1ent_hard_train.jsonl")]
ev=[json.loads(l) for l in open("/root/mtlm/data/s1ent_hard_eval.jsonl")]
rows=[("sys","",r["user"][:300],r["expect_tool"]) for r in tr]+[("sys","",r["user"][:300],r["expect_tool"]) for r in ev]
F=hp.features("/root/mtlm/hf/router3s384",rows)
lab={"yes":1,"no":0}
ytr=np.array([lab[r["expect_tool"]] for r in tr])
qid=[r["qid"] for r in ev]
for taps in [[(-2,"mean"),(-3,"mean"),(-4,"mean")],[(-4,"max"),(-2,"max"),(-3,"max")]]:
    X=np.concatenate([F[t] for t in taps],axis=1)
    Xtr,Xev=X[:len(tr)],X[len(tr):]
    mu=Xtr.mean(0); sd=hp.feat_sd(Xtr)
    W,b=hp.fit_lr((Xtr-mu)/sd,ytr,2,1e-2)
    Zev=((Xev-mu)/sd)@W+b
    P=hp.softmax(Zev)
    pyes=P[:,1]
    pred=Zev.argmax(1); yev=np.array([lab[r["expect_tool"]] for r in ev])
    acc=(pred==yev).mean()
    bacc=((pred[yev==1]==1).mean()+(pred[yev==0]==0).mean())/2
    grp=collections.defaultdict(list)
    for i,q in enumerate(qid): grp[q].append(i)
    top1=0; top2=0; n=0
    for q,ix in grp.items():
        order=sorted(ix,key=lambda i:-pyes[i])
        gold=[i for i in ix if yev[i]==1]
        if gold:
            g=gold[0]; n+=1
            top1+= order[0]==g
            top2+= g in order[:2]
    print(json.dumps({"taps":taps,"bacc":round(float(bacc),4),"acc":round(float(acc),4),"top1":round(top1/n,4),"top2":round(top2/n,4),"n":n}))
