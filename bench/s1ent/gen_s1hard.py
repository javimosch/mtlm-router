import json, random, collections, re
random.seed(7)
tr=[json.loads(l) for l in open("/root/mtlm/data/clinc_train.jsonl")]
ho=[json.loads(l) for l in open("/root/mtlm/data/clinc_holdout.jsonl")]
intents=sorted({r["expect_tool"] for r in tr if r["expect_tool"]!="oos"})
def desc(x): return x.replace("_"," ")
INSTR=["Which of the options applies to the state?","Choose the best category for the message.","Which intent does the user express?","Pick the matching option."]
# hard negatives: intents sharing a token (lost_luggage~damaged_luggage, card_* ~ *_card)
toks={i:set(i.split("_")) for i in intents}
def hard_negs(it,k):
    sib=[j for j in intents if j!=it and toks[it]&toks[j]]
    pool=sib if len(sib)>=k else sib+random.sample([j for j in intents if j!=it and j not in sib],k-len(sib))
    return random.sample(pool,k)
by={}
for r in tr: by.setdefault(r["expect_tool"],[]).append(r["user"])
byh={}
for r in ho: byh.setdefault(r["expect_tool"],[]).append(r["user"])
out=[]
for it in intents:
    for u in by[it][:8]:
        instr=random.choice(INSTR)
        hn=hard_negs(it,1)[0]
        for opt,yes in ((it,True),(hn,False)):
            out.append({"user":f"State: {u}\nQuestion: {instr}\nOption: {desc(opt)}\nCorrect?","expect_tool":"yes" if yes else "no"})
random.shuffle(out)
with open("/root/mtlm/data/s1ent_hard_train.jsonl","w") as f:
    for o in out: f.write(json.dumps(o)+"\n")
# eval: holdout states x (gold + 4 hard neg siblings), keep qid grouping
ev=[]
qid=0
for it in intents:
    for u in byh.get(it,[])[:6]:
        instr=random.choice(INSTR)
        opts=[it]+hard_negs(it,4)
        random.shuffle(opts)
        for opt in opts:
            ev.append({"user":f"State: {u}\nQuestion: {instr}\nOption: {desc(opt)}\nCorrect?","expect_tool":"yes" if opt==it else "no","qid":qid})
        qid+=1
with open("/root/mtlm/data/s1ent_hard_eval.jsonl","w") as f:
    for o in ev: f.write(json.dumps(o)+"\n")
print("train",len(out),collections.Counter(o["expect_tool"] for o in out))
print("eval",len(ev),"qids",qid)
