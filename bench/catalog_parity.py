"""catalog_parity.py — golden-suite gate: every shipped head, offline vs live.

Loads each head via head_io (taps from header; mhd2 via --taps override),
scores a probe suite offline AND against a live multi-expert anvil instance,
requires route match + |dconf| <= tol per probe. Exit 1 on any divergence.

Run on rbm21:
  python3 bench/catalog_parity.py --url http://localhost:8398 [--tol 0.05]
"""
import sys, json, argparse, urllib.request
sys.path.insert(0,"/root/mtlm/tools")
import numpy as np, head_probe as hp, head_io

# lane -> (head path, live expert name, taps override for mhd2, probe texts)
M="/root/mtlm/hosted/models"; M2="/root/mtlm/models"
LANES = {
 "civic":     (f"{M}/civic_v2_mt.head",        "civic",  None,
   ["a large pothole on our street","bins not collected again","graffiti on the bus stop","the street light is broken","how do i make pancakes"]),
 "civic_fr":  (f"{M}/civic_fr_v2_mt.head",     "civic_fr", None,
   ["des tags sur le mur de l ecole","un nid de poule devant chez moi","encombrants sur le trottoir","comment faire des crepes"]),
 "clinc":     (f"{M}/clinc150_mt3.head",       "clinc",  None,
   ["what is the weather like today","book me a flight to paris","how many calories in a banana","tell me a joke"]),
 "clinc2":    (f"{M2}/clinc150_v2.head",       "clinc2", None,
   ["what is my account balance","set a timer for 10 minutes","order a large pepperoni pizza","hire a divorce lawyer"]),
 "helpdesk":  (f"{M2}/helpdesk_v2_mt.head",    "helpdesk2", None,
   ["reset my password please","file a bug for the vpn client","check my ticket status","the coffee machine is broken"]),
 "helpdesk1": (f"{M}/helpdesk_pool_L-3_mean.head","helpdesk1",[(-3,"mean")],
   ["reset my password please","provision a vm for the staging env","where is my ticket","hello how are you"]),
 "mairie":    (f"{M}/mairie_mt3.head",         "mairie", None,
   ["1ere dotation bac verre","ramassage encombrants","carte identite renouvellement","depot illicite canape"]),
 "eq":        (f"{M2}/eq_tone_v2.head",        "eq",     None,
   ["i am so frustrated with this service","thank you so much for your help","how do i reset my router","order me a pizza"]),
 "bank77":    (f"{M2}/banking77_mt.head",      "bank77", None,
   ["my card has not arrived yet","i want to dispute a transaction","what is your exchange rate","order me a pizza"]),
}

def live(url, expert, text, key=""):
    req = urllib.request.Request(url+"/v1/route",
        data=json.dumps({"state":text,"expert":expert}).encode(),
        headers={"content-type":"application/json"} | ({"authorization":f"Bearer {key}"} if key else {}))
    r = json.loads(urllib.request.urlopen(req, timeout=60).read())
    return r["route"], float(r["confidence"])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8398")
    ap.add_argument("--key", default="")
    ap.add_argument("--tol", type=float, default=0.05)
    ap.add_argument("--hf", default="/root/mtlm/hf/router3s384")
    ap.add_argument("--only", default="")
    a = ap.parse_args()

    lanes = {k:v for k,v in LANES.items() if not a.only or k==a.only}
    heads, texts, idx = {}, [], []
    for name,(path,exp,taps_ov,probes) in lanes.items():
        h = head_io.load_head(path)
        if taps_ov: h["taps"]=taps_ov
        if not h["taps"]:
            print(f"SKIP {name}: no taps in header and no override"); continue
        heads[name]=(h,exp,probes)
        for t in probes: idx.append((name,t)); texts.append(t)
    rows=[(hp.DECIDE_SYS,[],t,"?") for t in texts]
    F=hp.features(a.hf, rows)
    # features keyed by (hf_idx,kind); each head picks its own taps
    bad=0; report={}
    for name,(h,exp,probes) in heads.items():
        sel=[i for i,(n,t) in enumerate(idx) if n==name]
        X=np.concatenate([F[t][sel] for t in h["taps"]],axis=1)
        P=head_io.probs(h,X)
        rows_r=[]
        for t,i in zip(probes,range(len(probes))):
            j=int(P[i].argmax()); off=(h["labels"][j],float(P[i,j]))
            try: lv=live(a.url,exp,t,a.key)
            except Exception as e: lv=(f"ERR:{e}",0.0)
            ok = off[0]==lv[0] and abs(off[1]-lv[1])<=a.tol
            bad+=not ok
            rows_r.append({"text":t,"off":[off[0],round(off[1],3)],"live":[lv[0],round(lv[1],3)],"ok":bool(ok)})
            print(("ok " if ok else "BAD"),f"{name:9s}",t[:40],"off",off[0],round(off[1],3),"live",lv[0],round(lv[1],3))
        report[name]={"parity":all(r["ok"] for r in rows_r),"rows":rows_r}
    n=sum(len(r["rows"]) for r in report.values())
    print(json.dumps({"probes":n,"diverged":bad,"parity":bad==0,"tol":a.tol,
                      "lanes":{k:v["parity"] for k,v in report.items()}},indent=1))
    sys.exit(0 if bad==0 else 1)
main()
