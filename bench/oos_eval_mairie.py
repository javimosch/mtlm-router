"""mairie head OOS probe — offline vs live parity verified 2026-10-11.
Layout: file W is (n_classes, featdim) row-major (reshape(nr,fd)).
TAPS MUST BE READ FROM THE HEADER: kind,layer+1 pairs — mairie uses
3x max at anvil layers 2,4,3 (hf -4,-2,-3), NOT the civic mean taps.
Using the wrong taps produces confident garbage (collecte_om on everything).
"""
import sys, struct
sys.path.insert(0,"/root/mtlm/tools")
import numpy as np, head_probe as hp
d=open("/root/mtlm/hosted/models/mairie_mt3.head","rb").read()
nr,fd=struct.unpack("<ii",d[4:12]); temp=struct.unpack("<f",d[12:16])[0]; ntaps=d[16]
taps_meta=[struct.unpack("<BB",d[17+2*i:19+2*i]) for i in range(ntaps)]
off=17+2*ntaps
W=np.frombuffer(d[off:off+4*nr*fd],dtype=np.float32).reshape(nr,fd); off+=4*nr*fd
b=np.frombuffer(d[off:off+4*nr],dtype=np.float32); off+=4*nr
labels=[]
for i in range(nr):
    ln=d[off]; off+=1; labels.append(d[off:off+ln].decode()); off+=ln
nl=6
taps=[(pl-(nl+1)+(-1), "max" if k==1 else "mean") for k,pl in taps_meta]  # stored layer+1 -> hf index
taps=[(k_pl-1-nl if k_pl-1>=0 else k_pl-1-nl, "max" if k==1 else "mean") for k,k_pl in taps_meta]
print("taps resolved:",taps)
texts_in=["1ere dotation bac verre","changement bac casse","ramassage encombrants","depot illicite canape","collecte bio quand ca passe","sacs jaunes distribution","point apport verre plein","dechetterie horaires"]
texts_oos=["carte identite renouvellement","mariage rendez vous","stationnement payant","nid de poule rue des fleurs","bruit voisinage nuit","bus 42 en retard","cantine scolaire inscription","taxe fonciere augmentation","lampadaire clignotant","mariage civil dossier","permis de construire","passage pieton efface"]
rows=[(hp.DECIDE_SYS,[],t,"in") for t in texts_in]+[(hp.DECIDE_SYS,[],t,"oos") for t in texts_oos]
F=hp.features("/root/mtlm/hf/router3s384",rows)
X=np.concatenate([F[t] for t in taps],axis=1)
Z=X@W.T+b; P=np.exp(Z/temp); P/=P.sum(1,keepdims=True)
nin=len(texts_in)
out={"in":[], "oos":[]}
for t,i in zip(texts_in,range(nin)):
    j=P[i].argmax(); out["in"].append({"text":t,"route":labels[j],"conf":round(float(P[i,j]),3)})
for k,t in enumerate(texts_oos):
    i=nin+k; j=P[i].argmax(); out["oos"].append({"text":t,"route":labels[j],"conf":round(float(P[i,j]),3)})
mp_in,mp_oos=P[:nin].max(1),P[nin:].max(1)
esc=labels.index("escalate")
out["summary"]={"in_scope_median":float(np.median(mp_in)),"oos_median":float(np.median(mp_oos)),
 "oos_escalate_share":float((P[nin:].argmax(1)==esc).mean()),
 "oos_leak_05":float((mp_oos>=0.5).mean()),"oos_leak_07":float((mp_oos>=0.7).mean())}
import json; print(json.dumps(out,indent=1,ensure_ascii=False))
