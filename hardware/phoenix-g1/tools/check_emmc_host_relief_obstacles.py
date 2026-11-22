"""Resolve actual PWM-board host escape obstructions at each candidate, including GND return distances."""
from pathlib import Path
import hashlib,json,math
import pcbnew as p
from pcb_power_leg import barrel
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';cp=json.loads((r/'layout-emmc-strobe-pulldown.json').read_text());file=r/cp['board'];assert hashlib.sha256(file.read_bytes()).hexdigest()==cp['sha256']
d=json.loads((r/'emmc-host-wifi-i2c-relief.json').read_text());assert d['source_sha256']==cp['sha256']
b=p.LoadBoard(str(file));b.BuildConnectivity();uid=lambda t:t.m_Uuid.AsString()
objs=[t for t in b.GetTracks() if uid(t) in set(d['diagnostic_omitted'])]
ls=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
ids={uid(o) for o in b.GetConnectivity().GetConnectedItems(b.FindFootprintByReference('U4').FindPadByNumber('69'))}
grounds=[tuple(t.GetPosition()) for t in b.GetTracks() if isinstance(t,p.PCB_VIA) and uid(t) in ids]
rows=[]
for s in d['sites']:
    xy=tuple(s['path_nm'][-1]);via=barrel(b,xy,b.FindNet('EMMC_STRB').GetNetCode());land=via.GetEffectiveShape(p.F_Cu);hole=via.GetEffectiveHoleShape()
    hit=[dict(uuid=uid(t),net=t.GetNetname(),kind=t.GetClass(),layer=t.GetLayerName(),start=tuple(t.GetStart()),end=tuple(t.GetEnd()),width_mm=(t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth())/1e6) for t in objs if any(t.IsOnLayer(l) and (land.Collide(t.GetEffectiveShape(l),202000) or hole.Collide(t.GetEffectiveShape(l),252000)) for l in ls)]
    closest=min((math.dist(xy,z)/1e6,z) for z in grounds)
    rows.append(dict(xy=xy,hit=hit,nearest_ground=closest,path_nm=s['path_nm']))
out=dict(parent_sha256=cp['sha256'],sites=sorted(rows,key=lambda row:(len(row['hit']),row['nearest_ground'])))
(r/'emmc-host-strobe-blocking-copper.json').write_text(json.dumps(out,indent=2)+'\n');print(out['sites'][0])
if __import__('sys').argv[1:]==['--inner']:
    import subprocess
    candidate=out['sites'][0];omit={o['uuid'] for o in candidate['hit']}
    removed=[t for t in b.GetTracks() if uid(t) in omit]
    for t in removed:b.Remove(t)
    p.ZONE_FILLER(b).Fill(b.Zones())
    from phy_corridor_path import geometry
    target=next(tuple(v.GetPosition()) for v in b.GetTracks() if isinstance(v,p.PCB_VIA) and v.GetNetname()=='EMMC_STRB')
    def points(loop):return [tuple(loop.CPoint(i)) for i in range(loop.PointCount())]
    tests=[]
    for layer,ref in ((p.In2_Cu,p.In1_Cu),(p.In3_Cu,p.In4_Cu)):
        plane=next(z.GetFilledPolysList(ref) for z in b.Zones() if z.GetNetname()=='GND' and z.HasFilledPolysForLayer(ref));polygons=[[points(plane.Outline(i)),[points(plane.Hole(i,j)) for j in range(plane.HoleCount(i))]] for i in range(plane.OutlineCount())]
        keepouts=[points(z.Outline().Outline(i)) for z in [*b.Zones(),*(z for f in b.GetFootprints() for z in f.Zones())] if z.GetIsRuleArea() and z.IsOnLayer(layer) and z.GetDoNotAllowTracks() for i in range(z.Outline().OutlineCount())]
        reply=subprocess.run(['python3',str(Path(__file__).with_name('ddr_plane_grid.py'))],input=json.dumps(dict(geometry=[*geometry(b,layer,b.FindNet('EMMC_STRB').GetNetCode(),oval_caps=True),keepouts],via_nm=[candidate['xy'],target],plane=polygons,reference_half_width_nm=200000,compact_45=True,max_path_nm=24000000)),text=True,capture_output=True,check=True)
        tests.append(dict(layer=b.GetLayerName(layer),result=json.loads(reply.stdout)))
    (r/'emmc-host-strobe-reference-path.json').write_text(json.dumps(dict(parent_sha256=cp['sha256'],omitted=sorted(omit),host_nm=candidate['xy'],socket_nm=target,trials=tests),indent=2)+'\n')
    print([(x['layer'],list(x['result'])) for x in tests])
