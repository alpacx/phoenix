"""Trial a resistor and its factory test point near both ADC ball and analog supply."""
from pathlib import Path
import math,json,hashlib,shutil,subprocess
from collections import Counter
import pcbnew as p
from pcb_power_leg import make
from pcb_bounds import inflated_box
from pcb_preservation import verify_preservation
from drc_regression import introduced
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
cp=json.loads((r/'layout-soc-ground-existing-barrel.json').read_text());src=r/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
b=p.LoadBoard(str(src));b.BuildConnectivity();f=b.FindFootprintByReference('R1504');tp=b.FindFootprintByReference('TP10')
q1=f.FindPadByNumber('1');q2=f.FindPadByNumber('2');service=tp.FindPadByNumber('1');soc=b.FindFootprintByReference('U1').FindPadByNumber('D26')
side=p.B_Cu
assert f.GetLayer()==side and tp.GetLayer()==side
old=[t for t in b.GetTracks() if t.GetNetCode()==q1.GetNetCode()];assert len(old)==1
old_uid=old[0].m_Uuid.AsString();b.Remove(old[0])
fps=[o for o in b.GetFootprints() if o.GetReference() not in ('R1504','TP10')]
items=[*b.GetTracks(),*(q for o in fps for q in o.Pads())]
origin=tuple(soc.GetPosition());bounds=inflated_box(soc,10500000)
items=[o for o in items if bounds.Intersects(o.GetBoundingBox())]
copper=[(o.GetNetCode(),o.GetBoundingBox(),o.GetEffectiveShape(side)) for o in items if o.IsOnLayer(side)]
holes=[(o.GetBoundingBox(),o.GetEffectiveHoleShape()) for o in items if isinstance(o,p.PCB_VIA) or isinstance(o,p.PAD) and o.GetDrillSize().x]
courts=[o.GetCourtyard(side) for o in fps if o.GetLayer()==side and bounds.Intersects(o.GetBoundingBox()) and o.GetCourtyard(side).OutlineCount()]
zones=[z.Outline() for z in [*b.Zones(),*(z for o in fps for z in o.Zones())] if z.GetIsRuleArea() and z.IsOnLayer(side) and z.GetDoNotAllowTracks()]
def clear(obj):
    box=inflated_box(obj,300000);sh=obj.GetEffectiveShape(side)
    return not any(c!=obj.GetNetCode() and box.Intersects(bb) and sh.Collide(s,202000) for c,bb,s in copper) and not any(box.Intersects(bb) and sh.Collide(s,252000) for bb,s in holes) and not any(z.Collide(sh,0) for z in zones)
def fit(part):
    court=part.GetCourtyard(side)
    return all(not court.Collide(o,100000) for o in courts) and all(clear(q) for q in part.Pads())
targets=[(q.GetParentFootprint().GetReference(),tuple(q.GetPosition())) for q in items if isinstance(q,p.PAD) and q.GetNetCode()==q2.GetNetCode() and q.IsOnLayer(side)]
def move(o,x,y):o.SetPosition(p.VECTOR2I(x,y))
options=[];stats=Counter();V=lambda q:tuple(q.GetPosition())
for ref,z in targets:
 for angle in (0,90,180,270):
    f.SetOrientationDegrees(angle)
    for ix in range(-12,13):
     for iy in range(-12,13):
        x,y=z[0]+ix*200000,z[1]+iy*200000
        if math.dist((x,y),origin)>8500000:continue
        move(f,x,y)
        if not fit(f):continue
        trace=make(b,V(q2),z,250000,q2.GetNetCode(),side)
        if not clear(trace) or trace.GetEffectiveShape(side).Collide(q1.GetEffectiveShape(side),202000):continue
        stats['resistor_and_power_fit']+=1
        start=V(q1)
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
         for step in (1200000,1500000,1900000,2300000):
            xy=(start[0]+dx*step,start[1]+dy*step);move(tp,*xy)
            if not fit(tp) or tp.GetCourtyard(side).Collide(f.GetCourtyard(side),100000):continue
            line=make(b,start,xy,200000,q1.GetNetCode(),side)
            if not clear(line) or line.GetEffectiveShape(side).Collide(q2.GetEffectiveShape(side),202000) or line.GetEffectiveShape(side).Collide(trace.GetEffectiveShape(side),202000) or service.GetEffectiveShape(side).Collide(trace.GetEffectiveShape(side),202000):continue
            options.append((math.dist(xy,origin)+trace.GetLength()+line.GetLength(),ref,angle,(x,y),xy))
            break
report=dict(parent_sha256=cp['sha256'],targets=targets,stats=dict(stats),options=len(options))
if options:
    _,ref,ang,at,xy=min(options);f.SetOrientationDegrees(ang);move(f,*at);move(tp,*xy)
    target=b.FindFootprintByReference(ref).FindPadByNumber('1')
    assert target.GetNetCode()==q2.GetNetCode()
    for a,z,code,w in [(V(q2),V(target),q2.GetNetCode(),250000),(V(q1),V(service),q1.GetNetCode(),200000)]:b.Add(make(b,a,z,w,code,side))
    out=r/'runs/recovery-adc-relocated';out.mkdir(exist_ok=True,parents=True);file=out/src.name
    for ext in ('.kicad_pro','.kicad_dru'):shutil.copy2(src.with_suffix(ext),file.with_suffix(ext))
    shutil.copy2(src.parent/'fp-lib-table',out/'fp-lib-table');p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(file),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(out/'drc.json'),str(file)],capture_output=True,check=True)
    after=p.LoadBoard(str(file));after.BuildConnectivity();db=json.loads((out/'drc.json').read_text())
    report.update(board=str(file.relative_to(r)),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),new_drc=introduced(json.loads((src.parent/'drc.json').read_text()),db),remaining=len(db['unconnected_items']),preservation=verify_preservation(p.LoadBoard(str(src)),after,replaced_copper=[old_uid]),selected=[ref,ang,at,xy])
(r/'recovery-adc-relocated.json').write_text(json.dumps(report,indent=2)+'\n');print(dict(stats),len(options),report.get('selected'),report.get('remaining'))
if options and not report['new_drc'] and report['remaining']==cp['remaining_minimum_joins']-1:
    from audit_mount_component_reservations import screen
    assert not any(row['ref'] in ('TP10','R1504') for row in screen(after))
    def native(label):
        ref,num=label.split('.');return after.FindFootprintByReference(ref).FindPadByNumber(num)
    pairs={tuple(sorted(pair)) for pair in cp['verified_pairs']}|{tuple(sorted(('R1504.2',ref+'.1'))),tuple(sorted(('TP10.1','R1504.1')))}
    cache={}
    for a,z in pairs:
        if a not in cache:cache[a]={o.m_Uuid.AsString() for o in after.GetConnectivity().GetConnectedItems(native(a))}
        assert native(z).m_Uuid.AsString() in cache[a],(a,z)
    opens=cp['open_nets'].copy();net='VCCA_1V8';power=next(g for g in opens[net] if ref+'.1' in g);pin=next(g for g in opens[net] if 'R1504.2' in g)
    opens[net]=[g for g in opens[net] if g!=power and g!=pin]+[sorted(power+pin)]
    assert sum(len(g)-1 for g in opens.values())==report['remaining']
    state=dict(board=report['board'],sha256=report['sha256'],parent_sha256=cp['sha256'],verified_pairs=sorted(pairs),preservation=report['preservation'],open_nets=opens,remaining_minimum_joins=report['remaining'],new_drc=[],drc_counts=dict(Counter(v['type'] for v in db['violations'])),assembly_ready=False)
    (r/'layout-recovery-adc-relocated.json').write_text(json.dumps(state,indent=2)+'\n')
