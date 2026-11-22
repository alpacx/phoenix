"""Reattach both pin banks of the expansion supply to the original 1-mm inner spine."""
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import pcbnew as p
from pcb_bounds import inflated_box
from drc_regression import introduced
from local_pcb_router import LocalRouter

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'layout-pmic-pwron-filter.json').read_text());accepted=p.LoadBoard(str(root/cp['board']))
src=root/'runs/pmic-five-stage-feedback-0';dst=root/'runs/pmic-five-stage-addon-0';dst.mkdir(exist_ok=True)
fn='phy-joint.kicad_pcb';j=json.loads((src/'output-legs.json').read_text())
assert hashlib.sha256((src/fn).read_bytes()).hexdigest()==j['board_sha256']
b=p.LoadBoard(str(src/fn));b.BuildConnectivity()
for n in ('fp-lib-table','phy-joint.kicad_pro','phy-joint.kicad_dru'):shutil.copy2(src/n,dst/n)
def pad(ref,num):return b.FindFootprintByReference(ref).FindPadByNumber(num)
def group(q):return {o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(q)}
net='+5V_ADDON';code=b.FindNet(net).GetNetCode()
existing={t.m_Uuid.AsString() for t in b.GetTracks()}
missing=[t for t in accepted.GetTracks() if t.GetNetname()==net and t.m_Uuid.AsString() not in existing]
assert len(missing)==2 and all(isinstance(t,p.PCB_VIA) for t in missing)
results=[]
def candidate_via(at,prototype):
    v=p.PCB_VIA(b);v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetWidth(prototype.GetWidth(p.F_Cu));v.SetDrill(prototype.GetDrillValue());v.SetPosition(p.VECTOR2I(*at));v.SetNetCode(code);return v
def check():
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(dst/fn),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(dst/'drc.json'),str(dst/fn)],capture_output=True,check=True)
    return introduced(json.loads((src/'drc.json').read_text()),json.loads((dst/'drc.json').read_text()))
for n in ('1','2'):
    b.BuildConnectivity();bank=pad('J3',n);driver=pad('U8101','5');bank_ids=group(bank);driver_ids=group(driver)
    assert bank.m_Uuid.AsString() not in driver_ids
    tracks=list(b.GetTracks())
    bank_stems=[t for t in tracks if t.m_Uuid.AsString() in bank_ids and t.GetLayer()==p.F_Cu and not isinstance(t,p.PCB_VIA) and t.GetWidth()==300000]
    anchors={tuple(t.GetStart()) for t in bank_stems}|{tuple(t.GetEnd()) for t in bank_stems}
    proto=min(missing,key=lambda v:min(math.dist(tuple(v.GetPosition()),a) for a in anchors))
    inner=[t.GetEffectiveShape(p.In3_Cu) for t in tracks if t.GetLayer()==p.In3_Cu and t.m_Uuid.AsString() in driver_ids and not isinstance(t,p.PCB_VIA) and t.GetWidth()==1000000]
    objs=[o for o in tracks+[q for f in b.GetFootprints() for q in f.Pads()] if inflated_box(o,5000000).Contains(proto.GetPosition())]
    ls=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
    geoms=[(o.GetEffectiveShape(l),o.GetBoundingBox()) for o in objs if o.GetNetCode()!=code for l in ls if o.IsOnLayer(l)]
    holes=[(o.GetEffectiveHoleShape(),o.GetPosition(),o.GetNetCode()) for o in objs if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
    rules=[a.Outline() for a in list(b.Zones())+[a for f in b.GetFootprints() for a in f.Zones()] if a.GetIsRuleArea() and a.GetDoNotAllowVias()]
    externalpads=[q.GetEffectiveShape(q.GetParentFootprint().GetLayer()) for q in objs if isinstance(q,p.PAD) and q.GetNetCode()==code]
    router=LocalRouter(b,(59,.3,69,7),width=.30,clearance=.205,grid=.05)
    block=router.blocked(p.F_Cu,net)
    options=[]
    trees={a:router.paths_from(block,router.cell(tuple(v*1e-6 for v in a)),3.0) for a in anchors}
    for x in range(proto.GetPosition().x-3000000,proto.GetPosition().x+3000001,50000):
        for y in range(max(450000,proto.GetPosition().y-3000000),proto.GetPosition().y+3000001,50000):
            pos=p.VECTOR2I(x,y);at=(x,y);via=candidate_via(at,proto)
            if not any(s.Collide(pos,0) for s in inner):continue
            sh=via.GetEffectiveShape(p.F_Cu);h=via.GetEffectiveHoleShape();bb=inflated_box(via,400000)
            if any(bb.Intersects(box) and (sh.Collide(g,202000) or h.Collide(g,250000)) for g,box in geoms):continue
            if any(bb.Contains(c) and (h.Collide(g,252000) or k!=code and sh.Collide(g,250000)) for g,c,k in holes):continue
            if any(sh.Collide(g,50000) for g in externalpads) or any(sh.Collide(g,0) for g in rules):continue
            cell=router.cell((x*1e-6,y*1e-6))
            for anchor,tree in trees.items():
                line=router.path_from_tree(tree,cell)
                if line:
                    path=[anchor]+[tuple(round(k*1e6) for k in w) for w in line]+[at]
                    length=sum(math.dist(a,z) for a,z in zip(path,path[1:]))/1e6
                    options.append((length,at,path))
    trials=[];done=False
    for length,at,path in sorted(options):
        v=candidate_via(at,proto);pieces=[v]
        for a,z in zip(path,path[1:]):
            if a==z:continue
            t=p.PCB_TRACK(b);t.SetNetCode(code);t.SetLayer(p.F_Cu);t.SetWidth(300000);t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z));pieces.append(t)
        for t in pieces:b.Add(t)
        delta=check();probe=p.LoadBoard(str(dst/fn));probe.BuildConnectivity();anchor=probe.FindFootprintByReference('J3').FindPadByNumber(n)
        native=driver.m_Uuid.AsString() in {i.m_Uuid.AsString() for i in probe.GetConnectivity().GetConnectedItems(anchor)}
        trials.append(dict(at=at,mm=length,delta=delta,connected=native))
        if not delta and native:done=True;break
        for t in pieces:b.Remove(t)
    results.append(dict(bank=n,via_mm=[proto.GetWidth(p.F_Cu)/1e6,proto.GetDrillValue()/1e6],options=len(options),connected=done,trials=trials))
assert not check();j['board_sha256']=hashlib.sha256((dst/fn).read_bytes()).hexdigest();j['addon_spine']=results
(dst/'output-legs.json').write_text(json.dumps(j,indent=2)+'\n')
print([(r['bank'],r['connected'],r['options']) for r in results],flush=True);os._exit(0)
