"""Refill and validate the relocated LOGIC output bulk capacitor and its paired barrels."""
from pathlib import Path
from collections import Counter
import sys,hashlib,json,subprocess,shutil
import pcbnew as p
from pcb_power_leg import make,barrel
from pcb_preservation import verify_preservation
from drc_regression import introduced
from audit_mount_component_reservations import screen
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
npu='--npu' in sys.argv;capref='C434' if npu else 'C431';lref='L404' if npu else 'L401';rail='VDD_NPU' if npu else 'VDD_LOGIC';name='npu-c434-paired-load' if npu else 'logic-c431-paired-load'
cp=json.loads((r/('layout-logic-c431-paired-load.json' if npu else 'layout-npu-output-cap-c444.json')).read_text());src=r/cp['board'];poses=json.loads((r/('npu-output-cap-rear-stitch-placement.json' if npu else 'logic-output-cap-rear-stitch-placement.json')).read_text());ss=json.loads((r/('npu-output-source-face-anchors.json' if npu else 'logic-output-source-face-anchors.json')).read_text());assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']==ss['parent_sha256']==poses['parent_sha256']
routes={tuple(q['pt_nm']):q['route_nm'] for q in ss['source']};out=r/'runs'/name;out.mkdir(exist_ok=True);file=out/src.name
for ext in ('.kicad_pro','.kicad_dru'):shutil.copy2(src.with_suffix(ext),file.with_suffix(ext))
shutil.copy2(src.parent/'fp-lib-table',out/'fp-lib-table')
old=json.loads((src.parent/'drc.json').read_text());uid=lambda o:o.m_Uuid.AsString()
trials=[];seen=set();winner=None
for _,at,angle,sites,gnd in poses['best']:
    key=(tuple(at),angle,tuple(sorted(map(tuple,sites))))
    if key in seen:continue
    seen.add(key);b=p.LoadBoard(str(src));b.BuildConnectivity();cap=b.FindFootprintByReference(capref);positive,ret=[cap.FindPadByNumber(n) for n in ('1','2')]
    stroke=list(b.GetConnectivity().GetConnectedTracks(ret));assert len(stroke)==1;ident=uid(stroke[0]);items=list(b.GetTracks());stub=next(t for t in items if uid(t)==ident)
    if cap.GetLayer()!=p.B_Cu:cap.Flip(cap.GetPosition(),False)
    cap.SetPosition(p.VECTOR2I(*at));cap.SetOrientationDegrees(angle);code=positive.GetNetCode();segments=set();p_xy=tuple(positive.GetPosition());r_xy=tuple(ret.GetPosition());groundcode=ret.GetNetCode();b.Remove(stub)
    for pt in sites:
        b.Add(barrel(b,pt,code,650000,300000))
        for layer,path in [(p.F_Cu,routes[tuple(pt)]),(p.B_Cu,[p_xy,pt])]:
            for a,z in zip(path,path[1:]):
                pair=layer,*sorted([tuple(a),tuple(z)])
                if a!=z and pair not in segments:b.Add(make(b,a,z,800000,code,layer));segments.add(pair)
    b.Add(make(b,r_xy,gnd,800000,groundcode,p.B_Cu));p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(file),b)
    subprocess.run(['/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli','pcb','drc','--format','json','-o',str(out/'drc.json'),str(file)],capture_output=True,check=True)
    db=json.loads((out/'drc.json').read_text());delta=introduced(old,db);fresh=p.LoadBoard(str(file));fresh.BuildConnectivity()
    def pad(label):
        f,n=label.split('.');return fresh.FindFootprintByReference(f).FindPadByNumber(n)
    cache={}
    def connected(a,z):
        if a not in cache:cache[a]={uid(o) for o in fresh.GetConnectivity().GetConnectedItems(pad(a))}
        return uid(pad(z)) in cache[a]
    joins=len(db['unconnected_items']);placement=screen(fresh);result=dict(at=at,angle=angle,sites=sites,return_via=gnd,source_branches=[routes[tuple(pt)] for pt in sites],new_drc=delta,joins=joins,power=connected(capref+'.1',lref+'.2'),ground=connected(capref+'.2','U4.69'),reservation_conflicts=placement)
    trials.append(result)
    if delta or not result['power'] or not result['ground'] or placement or joins>=cp['remaining_minimum_joins']:continue
    pairs=sorted({tuple(sorted(x)) for x in cp['verified_pairs']+[[capref+'.1',lref+'.2'],[capref+'.2','U4.69']]})
    assert all(connected(a,z) for a,z in pairs)
    nets=cp['open_nets'].copy();gs=nets[rail];member=[g for g in gs if capref+'.1' in g or lref+'.2' in g];assert len(member)==2
    nets[rail]=[g for g in gs if g not in member]+[sorted(member[0]+member[1])]
    assert sum(len(gs)-1 for gs in nets.values())==joins
    state=dict(board=str(file.relative_to(r)),sha256=hashlib.sha256(file.read_bytes()).hexdigest(),parent_sha256=cp['sha256'],verified_pairs=pairs,preservation=verify_preservation(p.LoadBoard(str(src)),fresh,replaced_copper=[ident]),open_nets=nets,remaining_minimum_joins=joins,new_drc=delta,drc_counts=dict(Counter(x['type'] for x in db['violations'])),assembly_ready=False)
    (r/('layout-'+name+'.json')).write_text(json.dumps(state,indent=2)+'\n');winner=result;break
(r/(name+'.json')).write_text(json.dumps(dict(parent_sha256=cp['sha256'],trials=trials,winner=winner),indent=2)+'\n')
print(bool(winner),[(v['joins'],[x['type'] for x in v['new_drc']]) for v in trials])
