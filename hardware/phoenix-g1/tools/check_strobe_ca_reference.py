"""Compare filled ground under the reworked command trace, strobe and surrounding digital routing."""
from pathlib import Path
from collections import defaultdict
import math,json,hashlib
import pcbnew as p
from pcb_bounds import inflated_box
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
base=json.loads((r/'layout-recovery-adc-relocated.json').read_text());work=json.loads((r/'emmc-strobe-pulldown-poses.json').read_text())
def board(cp):
    src=r/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256']
    return p.LoadBoard(str(src))
before=board(base);after=board(work)
refs={p.F_Cu:p.In1_Cu,p.In2_Cu:p.In1_Cu,p.In3_Cu:p.In4_Cu,p.B_Cu:p.In4_Cu}
def reference(b,layer):return next(z.GetFilledPolysList(layer) for z in b.Zones() if z.GetNetname()=='GND' and z.HasFilledPolysForLayer(layer))
old_planes={l:reference(before,l) for l in set(refs.values())};new_planes={l:reference(after,l) for l in set(refs.values())}
via=next(t for t in after.GetTracks() if isinstance(t,p.PCB_VIA) and t.GetNetname()=='EMMC_STRB')
missing_dist=defaultdict(list)
prev={t.m_Uuid.AsString() for t in before.GetTracks()};projections=[];fresh=defaultdict(lambda:[0,0,0])
for t in after.GetTracks():
    if isinstance(t,p.PCB_VIA) or t.GetLayer() not in refs:continue
    name=t.GetNetname();layer=refs[t.GetLayer()]
    if not name.startswith(('LPDDR4_','SOC_EMMC','EMMC_','USB_','ETH_','WIFI_')):continue
    if t.m_Uuid.AsString() not in prev:
        a,z=tuple(t.GetStart()),tuple(t.GetEnd());n=max(1,math.ceil(t.GetLength()/25000));fresh[name][0]+=t.GetLength();fresh[name][1]+=n
        for i in range(n):
            v=p.VECTOR2I(*(round(u+(w-u)*(i+.5)/n) for u,w in zip(a,z)))
            if not new_planes[layer].Contains(v):
                fresh[name][2]+=1
                missing_dist[name].append(math.dist(tuple(v),tuple(via.GetPosition()))/1e6)
    elif inflated_box(t,1000000).Contains(via.GetPosition()):
        shape=p.SHAPE_POLY_SET();t.TransformShapeToPolygon(shape,t.GetLayer(),200000,500,p.ERROR_OUTSIDE)
        shape.BooleanIntersection(old_planes[layer]);shape.BooleanSubtract(new_planes[layer])
        if shape.Area()>100000:projections.append((name,shape.Area()/1e12,t.m_Uuid.AsString()))
after.BuildConnectivity()
ids={o.m_Uuid.AsString() for o in after.GetConnectivity().GetConnectedItems(after.FindFootprintByReference('U4').FindPadByNumber('69'))}
ground=min((math.dist(tuple(t.GetPosition()),tuple(via.GetPosition()))/1e6,tuple(t.GetPosition())) for t in after.GetTracks() if isinstance(t,p.PCB_VIA) and t.m_Uuid.AsString() in ids)
out=dict(nearest_ground_barrel=ground,furthest_plane_opening_mm={k:max(v) for k,v in missing_dist.items()},sha256=work['sha256'],via_nm=tuple(via.GetPosition()),old_fast_reference_losses=sorted(projections),new_signals={k:dict(length_mm=v[0]/1e6,samples=v[1],missing_plane=v[2]) for k,v in fresh.items()})
(r/'emmc-strobe-ca-reference.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
from collections import Counter
if not projections and fresh['LPDDR4_A1_A'][2]==0 and max(missing_dist['EMMC_STRB'])<.45 and work['remaining']==base['remaining_minimum_joins']-1:
    def pad(name):
        ref,num=name.split('.');return after.FindFootprintByReference(ref).FindPadByNumber(num)
    pairs={tuple(sorted(p)) for p in base['verified_pairs']}|{tuple(sorted(('U8001.H5','R8005.1'))),tuple(sorted(('U4.69','R8005.2')))}
    cache={}
    for a,z in pairs:
        if a not in cache:cache[a]={q.m_Uuid.AsString() for q in after.GetConnectivity().GetConnectedItems(pad(a))}
        assert pad(z).m_Uuid.AsString() in cache[a],(a,z)
    opens=base['open_nets'].copy();groups=opens['EMMC_STRB'];aa=next(g for g in groups if 'R8005.1' in g);bb=next(g for g in groups if 'U8001.H5' in g)
    opens['EMMC_STRB']=[g for g in groups if g!=aa and g!=bb]+[sorted(aa+bb)]
    assert work['remaining']==sum(len(g)-1 for g in opens.values())
    db=json.loads(((r/work['board']).parent/'drc.json').read_text())
    cp=dict(board=work['board'],sha256=work['sha256'],parent_sha256=base['sha256'],verified_pairs=sorted(pairs),preservation=work['preservation'],open_nets=opens,remaining_minimum_joins=work['remaining'],new_drc=work['attempts'][-1]['delta'],drc_counts=dict(Counter(v['type'] for v in db['violations'])),assembly_ready=False)
    assert not cp['new_drc']
    (r/'layout-emmc-strobe-pulldown.json').write_text(json.dumps(cp,indent=2)+'\n')
