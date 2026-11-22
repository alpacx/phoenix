"""Identify existing wide +3V3_IO copper physically contiguous with the C470 reservoir."""
from pathlib import Path
import hashlib,json,math,os,sys
current='--current-vcc' in sys.argv
staggered='--staggered' in sys.argv or current
import pcbnew as p
from pcb_bounds import inflated_box
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';base=json.loads((root/('layout-emmc-data-power.json' if current else 'layout-lcd-select-trunk.json' if staggered else 'layout-cpu-enable-bias.json')).read_text());src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();cap=b.FindFootprintByReference('C470').FindPadByNumber('1');link=b.FindFootprintByReference('R8007').FindPadByNumber('1')
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu];uid=lambda o:o.m_Uuid.AsString()
group={uid(o) for o in b.GetConnectivity().GetConnectedItems(cap)}
objects=[t for t in b.GetTracks() if uid(t) in group and (isinstance(t,p.PCB_VIA) or t.GetWidth()>=500000)]+[q for f in b.GetFootprints() for q in f.Pads() if uid(q) in group and min(q.GetSize())>=500000]
barrels=[o for o in objects if isinstance(o,p.PCB_VIA)];nodes={(uid(o),l):(o,o.GetEffectiveShape(l),o.GetBoundingBox()) for o in objects for l in layers if o.IsOnLayer(l)}
parents={k:k for k in nodes}
def find(k):
 while parents[k]!=k:parents[k]=parents[parents[k]];k=parents[k]
 return k
def union(x,y):parents[find(x)]=find(y)
for layer in layers:
    subset=[(k,o,sh,bb) for k,(o,sh,bb) in nodes.items() if k[1]==layer]
    for i,(k,o,sh,bb) in enumerate(subset):
        for kk,oo,ss,zz in subset[i+1:]:
            if bb.Intersects(zz) and sh.Collide(ss,0):union(k,kk)
# Permit a layer transition only if a pair of barrels touches a common wide
# conductor on each side. The other parallel route must already exist in copper.
original={k:find(k) for k in nodes};crossings=[]
for i,a in enumerate(barrels):
 for z in barrels[i+1:]:
    if (a.GetPosition()-z.GetPosition()).EuclideanNorm()>1500000:continue
    common=[l for l in layers if original[uid(a),l]==original[uid(z),l]]
    if len(common)>=2:
        crossings.append(dict(vias=[uid(a),uid(z)],layers=[b.GetLayerName(l) for l in common]))
        for l in common:union((uid(a),common[0]),(uid(a),l))
anchor=find((uid(cap),p.B_Cu));eligible=[]
for k,(o,sh,bb) in nodes.items():
    if find(k)!=anchor:continue
    if isinstance(o,p.PCB_VIA):continue
    a=tuple(o.GetPosition()) if isinstance(o,p.PAD) else tuple(o.GetStart());z=a if isinstance(o,p.PAD) else tuple(o.GetEnd())
    eligible.append(dict(uuid=k[0],layer=b.GetLayerName(k[1]),ends_nm=[a,z],width_mm=None if isinstance(o,p.PAD) else o.GetWidth()/1e6))
out=dict(parent_sha256=base['sha256'],capacitor='C470.1',link='R8007.1',minimum_trace_width_mm=.5,pair_span_limit_mm=1.5,existing_crossings=crossings,wide_source_objects=eligible,assembly_ready=False)
(root/('emmc-vcc-current-source.json' if current else 'emmc-staggered-source-inventory.json' if staggered else 'emmc-wide-source-inventory.json')).write_text(json.dumps(out,indent=2)+'\n')
print('objects',len(eligible),'crossings',len(crossings),sorted((round(min(math.dist(x,tuple(link.GetPosition())) for x in o['ends_nm'])/1e6,2),o['layer']) for o in eligible)[:4],flush=True);os._exit(0)
