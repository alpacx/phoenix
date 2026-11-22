"""Move the two existing neighboring DDR dogbones away from the DQ0_B return window."""
from collections import Counter
from pathlib import Path
import hashlib
import itertools
import json
import math
import os
import shutil
import subprocess
import pcbnew as p
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen

root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((root/'layout-lpddr-clock-return.json').read_text());src=root/cp['board']
assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
source=p.LoadBoard(str(src));b=p.LoadBoard(str(src));b.BuildConnectivity()
folder=root/'runs/lpddr-dq0-return';folder.mkdir(exist_ok=True)
for f in ('phy-joint.kicad_pro','phy-joint.kicad_dru','fp-lib-table'):shutil.copy2(src.parent/f,folder/f)
record=json.loads((root/'lpddr-return-void-map.json').read_text());assert record['source_sha256']==cp['sha256']
window=record['foreign_or_unattributed'];assert {r['net'] for r in window}=={'LPDDR4_DQ0_B'}
v=lambda pt:p.VECTOR2I(*pt)
def uid(o):return o.m_Uuid.AsString()
ts={uid(t):t for t in b.GetTracks()}
layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
u1=b.FindFootprintByReference('U1')
move=[]
for number in ('4','5'):
    net='LPDDR4_DQ'+number+'_B';hole_id=next(key for r in window for s in r['slices'] for name,key in s['neighbors'] if name==net)
    via=ts[hole_id];coords=tuple(via.GetPosition())
    stub=[t for t in ts.values() if not isinstance(t,p.PCB_VIA) and t.GetNetname()==net and coords in (tuple(t.GetStart()),tuple(t.GetEnd()))]
    assert len(stub)==1 and stub[0].GetLayer()==p.F_Cu
    line=stub[0];q=next(o for o in b.GetConnectivity().GetConnectedItems(via) if isinstance(o,p.PAD))
    assert q.GetParentFootprint().GetReference()=='U1' and tuple(q.GetPosition())==tuple(line.GetStart())
    assert line.GetWidth()==76200 and via.GetWidth(p.F_Cu)==450000 and via.GetDrillValue()==200000
    move.append((via,line,q,coords))
targets=[]
for item in window:
    t=ts[item['uuid']];a,z=t.GetStart(),t.GetEnd();n=max(1,math.ceil(t.GetLength()/10000))
    for i in range(n+1):
        xy=(round(a.x+(z.x-a.x)*i/n),round(a.y+(z.y-a.y)*i/n))
        targets.extend((xy,(xy[0],xy[1]-50000),(xy[0],xy[1]+50000)))
def refzones(board,l):
    return [z.GetFilledPolysList(l) for z in board.Zones() if z.GetNetname()=='GND' and z.HasFilledPolysForLayer(l)]
def referenced(polys,at):return any(z.Contains(v(at)) for z in polys)
def setvia(row,xy):
    via,stub,_,_=row;via.SetPosition(v(xy));stub.SetEnd(v(xy))
old_polys=refzones(source,p.In1_Cu);old_support=sum(referenced(old_polys,t) for t in targets)
fixed=[o for o in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()] if inflated_box(o,2000000).Contains(v((47500000,14250000))) and uid(o) not in {uid(t) for r in move for t in r[:2]}]
all_holes=[o for o in fixed if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
keep=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
choices=[];stats=[]
for row in move:
    via,stub,q,old=row;sign=1 if q.GetNetname()=='LPDDR4_DQ4_B' else -1
    qualified=[];counts=Counter()
    for dx in range(-250000,250001,25000):
        for offset in range(175000,575001,25000):
            at=(q.GetPosition().x+dx,q.GetPosition().y+sign*offset);setvia(row,at)
            if any(math.dist(at,t)<430000 for t in targets):continue
            counts['target_window_clear']+=1
            sh=via.GetEffectiveShape(p.F_Cu);h=via.GetEffectiveHoleShape();track=stub.GetEffectiveShape(p.F_Cu)
            if any(sh.Collide(k,0) for k in keep):continue
            if any(h.Collide(o.GetEffectiveHoleShape(),252000) for o in all_holes):continue
            # Existing U1-specific copper rules apply at lands; preserve the previous
            # etch/mask margin to every *other* solder contact as a separate guard.
            foreign=[o for o in fixed if o.GetNetCode()!=via.GetNetCode()]
            conflicts=False
            for o in foreign:
                for l in layers:
                    if not o.IsOnLayer(l):continue
                    g=o.GetEffectiveShape(l);local=isinstance(o,p.PAD) and o.GetParentFootprint().GetReference()=='U1'
                    gap=76200 if local or o.GetNetname().startswith('LPDDR4_') else 200000
                    if sh.Collide(g,gap) or l==p.F_Cu and track.Collide(g,gap) or h.Collide(g,250000):
                        conflicts=True;break
                if conflicts:break
            if conflicts:continue
            counts['native_copper_screen']+=1
            # Prefer sites clearing the original solder land completely.
            clearance=math.dist(at,tuple(q.GetPosition()))-.225e6-q.GetSize().x/2
            score=(max(0,75000-clearance),stub.GetLength(),abs(dx))
            qualified.append((score,at))
    setvia(row,old);stats.append(counts);choices.append(sorted(qualified))
def verify():
    p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(folder/src.name),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(folder/'drc.json'),str(folder/src.name)],check=True,capture_output=True)
    return introduced(json.loads((src.parent/'drc.json').read_text()),json.loads((folder/'drc.json').read_text()))
report=dict(parent_sha256=cp['sha256'],source_window_points=len(targets),source_supported=old_support,site_stats=stats,site_counts=[len(x) for x in choices],attempts=[],accepted=False)
for a,z in sorted(itertools.product(*choices),key=lambda r:(sum(c[0][0] for c in r),sum(c[0][1] for c in r))):
    at=[a[1],z[1]]
    for row,xy in zip(move,at):setvia(row,xy)
    delta=verify();probe=p.LoadBoard(str(folder/src.name));probe.BuildConnectivity();polys=refzones(probe,p.In1_Cu)
    score=sum(referenced(polys,k) for k in targets);loss=[]
    if not delta and score==len(targets):
        for t in source.GetTracks():
            if isinstance(t,p.PCB_VIA) or t.GetLayer()!=p.F_Cu or not t.GetNetname().startswith('LPDDR4_') or t.GetNetname() in [r[2].GetNetname() for r in move] or not inflated_box(t,1500000).Contains(v((47500000,14250000))):continue
            u,w=t.GetStart(),t.GetEnd();n=max(1,math.ceil(t.GetLength()/10000))
            for k in range(n):
                pt=(round(u.x+(w.x-u.x)*(k+.5)/n),round(u.y+(w.y-u.y)*(k+.5)/n))
                if referenced(old_polys,pt) and not referenced(polys,pt):loss.append((t.GetNetname(),pt))
    report['attempts'].append(dict(centers_nm=at,delta=delta,supported=score,new_reference_losses=loss))
    if delta or loss or score!=len(targets):continue
    assert not screen(probe)
    proof=verify_preservation(source,probe,replaced_copper={uid(i) for row in move for i in row[:2]})
    for row in move:
        rr=probe.FindFootprintByReference('U1').FindPadByNumber(row[2].GetNumber())
        assert uid(row[0]) in {uid(k) for k in probe.GetConnectivity().GetConnectedItems(rr)}
    report.update(accepted=True,sha256=hashlib.sha256((folder/src.name).read_bytes()).hexdigest(),board=str((folder/src.name).relative_to(root)),preservation=proof)
    break
(root/'lpddr-dq0-reference.json').write_text(json.dumps(report,indent=2)+'\n')
print(report['site_stats'],report['site_counts'],len(report['attempts']),report['accepted'],flush=True);os._exit(0)
