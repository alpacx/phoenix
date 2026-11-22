"""Join nearby GND copper groups with short, clearance-checked outer-layer bridges."""
import hashlib
import json
import math
import shutil
import sys
import subprocess
from collections import Counter,defaultdict
from pathlib import Path
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_power_leg import make
from pcb_preservation import verify_preservation
from drc_regression import introduced

root=Path(__file__).resolve().parents[1]/"migration-rk3562/experiments/phy-power-parallel"
bend="--bend" in sys.argv
stage="ground-surface-bends" if bend else "ground-surface-islands"
cp=json.loads((root/("layout-ground-surface-islands.json" if bend else "layout-cpu-local-hf-bypass.json")).read_text())
src=root/cp["board"];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp["sha256"]
b=p.LoadBoard(str(src));b.BuildConnectivity()
pads={f.GetReference()+"."+q.GetNumber():q for f in b.GetFootprints() for q in f.Pads() if q.GetNetname()=="GND"}
code=next(iter(pads.values())).GetNetCode()
groups=cp["open_nets"]["GND"];names={}
for i,group in enumerate(groups):
    q=pads[group[0]]
    for o in b.GetConnectivity().GetConnectedItems(q):names[o.m_Uuid.AsString()]=i
    for n in group:names[pads[n].m_Uuid.AsString()]=i
seed=defaultdict(lambda:defaultdict(set));objects=[*b.GetTracks(),*(q for f in b.GetFootprints() for q in f.Pads())]
for o in objects:
    idx=names.get(o.m_Uuid.AsString())
    if idx is None:continue
    for layer in (p.F_Cu,p.B_Cu):
        if not o.IsOnLayer(layer):continue
        if isinstance(o,p.PAD) or isinstance(o,p.PCB_VIA):seed[layer][idx].add(tuple(o.GetPosition()));continue
        n=max(1,math.ceil(o.GetLength()/200000));a,z=tuple(o.GetStart()),tuple(o.GetEnd())
        for i in range(n+1):seed[layer][idx].add(tuple(round(u+(v-u)*i/n) for u,v in zip(a,z)))
def key(xy):return tuple(u//1000000 for u in xy)
def cells(bb):return ((i,j) for i in range(bb.GetLeft()//1000000,bb.GetRight()//1000000+1) for j in range(bb.GetTop()//1000000,bb.GetBottom()//1000000+1))
obstacles=defaultdict(lambda:defaultdict(list))
for o in objects:
    if o.GetNetCode()==code:continue
    for layer in (p.F_Cu,p.B_Cu):
        if not o.IsOnLayer(layer):continue
        shape=o.GetEffectiveShape(layer)
        for cell in cells(inflated_box(o,500000)):obstacles[layer][cell].append((o.m_Uuid.AsString(),shape))
proposals=[]
for layer,bygroup in seed.items():
    index=defaultdict(list)
    for gi,sites in bygroup.items():
        for xy in sites:index[key(xy)].append((gi,xy))
    for gi,sites in bygroup.items():
        if len(groups[gi])>15:continue
        for xy in sites:
            i,j=key(xy)
            for x in range(i-3,i+4):
                for y in range(j-3,j+4):
                    for gj,z in index[x,y]:
                        distance=math.dist(xy,z)
                        if gj!=gi and distance<=(2600000 if bend else 1500000):proposals.append((distance,gi,gj,layer,xy,z))
parent=list(range(len(groups)))
def cluster(i):
    while parent[i]!=i:i=parent[i]
    return i
added=[]
for length,gi,gj,layer,a,z in sorted(proposals):
    if cluster(gi)==cluster(gj):continue
    dx=z[0]-a[0];dy=z[1]-a[1];d=min(abs(dx),abs(dy))
    mx=int(math.copysign(d,dx));my=int(math.copysign(d,dy))
    elbows=[(a[0]+mx,a[1]+my),(z[0]-mx,z[1]-my)] if bend else []
    routes=[[a,z]]+[[a,q,z] for q in elbows if q not in (a,z)]
    for points in routes:
        tracks=[make(b,u,v,250000,code,layer) for u,v in zip(points,points[1:])]
        valid=True
        for t in tracks:
            sh=t.GetEffectiveShape(layer);seen=set()
            for cell in cells(inflated_box(t,202000)):
                for ident,shape in obstacles[layer][cell]:
                    if ident in seen:continue
                    seen.add(ident)
                    if sh.Collide(shape,202000):valid=False;break
                if not valid:break
            if not valid:break
        if valid:
            for t in tracks:b.Add(t)
            parent[cluster(gi)]=cluster(gj)
            added.append(dict(first=groups[gi][0],second=groups[gj][0],length_mm=sum(t.GetLength() for t in tracks)/1e6,layer=b.GetLayerName(layer),ends_nm=points))
            break
report=dict(parent_sha256=cp["sha256"],proposed=len(proposals),bridges=added)
if added:
    out=root/"runs"/stage;out.mkdir(exist_ok=True,parents=True);file=out/src.name
    shutil.copy2(src.parent/"fp-lib-table",out/"fp-lib-table")
    for ext in (".kicad_pro",".kicad_dru"):shutil.copy2(src.with_suffix(ext),file.with_suffix(ext))
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(file),b)
    subprocess.run(["/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli","pcb","drc","--format","json","-o",str(out/"drc.json"),str(file)],check=True,capture_output=True)
    db=json.loads((out/"drc.json").read_text())
    delta=introduced(json.loads((src.parent/"drc.json").read_text()),db)
    report.update(board=str(file.relative_to(root)),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),new_drc=delta,remaining_joins=len(db["unconnected_items"]),violations=Counter(x["type"] for x in db["violations"]),preservation=verify_preservation(p.LoadBoard(str(src)),p.LoadBoard(str(file))))
(root/(stage+".json")).write_text(json.dumps(report,indent=2)+"\n")
print(len(proposals),len(added),report.get("remaining_joins"),len(report.get("new_drc",[])))
if added and not report["new_drc"]:
    check=p.LoadBoard(str(file));check.BuildConnectivity()
    def pad(label):
        ref,pin=label.split(".")
        return check.FindFootprintByReference(ref).FindPadByNumber(pin)
    pairs={tuple(sorted(pair)) for pair in cp["verified_pairs"]}
    pairs.update(tuple(sorted((x["first"],x["second"]))) for x in added)
    cached={}
    for a,z in pairs:
        if a not in cached:cached[a]={o.m_Uuid.AsString() for o in check.GetConnectivity().GetConnectedItems(pad(a))}
        assert pad(z).m_Uuid.AsString() in cached[a],(a,z)
    source_groups=cp["open_nets"].copy()
    merged=defaultdict(list)
    for i,g in enumerate(groups):merged[cluster(i)].extend(g)
    source_groups["GND"]=sorted(sorted(g) for g in merged.values())
    assert sum(len(v)-1 for v in source_groups.values())==report["remaining_joins"]==cp["remaining_minimum_joins"]-len(added)
    checkpoint=dict(board=report["board"],sha256=report["sha256"],parent_sha256=cp["sha256"],verified_pairs=sorted(pairs),preservation=report["preservation"],open_nets=source_groups,remaining_minimum_joins=report["remaining_joins"],new_drc=[],drc_counts=report["violations"],assembly_ready=False)
    (root/("layout-"+stage+".json")).write_text(json.dumps(checkpoint,indent=2)+"\n")
