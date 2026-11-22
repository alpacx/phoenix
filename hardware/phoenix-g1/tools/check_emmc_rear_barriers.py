"""Check straight full-width bridges between opposite native eMMC source/load frontiers."""
from pathlib import Path
import hashlib,json,math,os
import pcbnew as p
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
d=json.loads((root/'layout-lcd-select-trunk.json').read_text());src=root/d['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==d['sha256']
b=p.LoadBoard(str(src));net=b.GetNetcodeFromNetname('+3V3_IO');pin=b.FindFootprintByReference('L405').FindPadByNumber('2')
t=p.PCB_TRACK(b);t.SetWidth(500000);t.SetLayer(p.B_Cu);obj=list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]
data=json.loads((root/'runs/emmc-rear-frontier-bridges.json').read_text())
for row in data:
 t.SetStart(p.VECTOR2I(*row['a']));t.SetEnd(p.VECTOR2I(*row['b']));shape=t.GetEffectiveShape(p.B_Cu);hits=[]
 for o in obj:
  if o.GetNetCode()==net or not o.IsOnLayer(p.B_Cu):continue
  sh=o.GetEffectiveShape(p.B_Cu)
  if shape.Collide(sh,202000):
   name=o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if isinstance(o,p.PAD) else o.GetClass()
   hits.append((name,o.GetNetname(),o.m_Uuid.AsString()))
 row['blocked_by']=hits
report=json.loads((root/'emmc-frontier-via-obstacles.json').read_text())
movable=[tuple(pt) for row in report['low_conflict_sites'] if row['blockers'] in (['L405.2'],['C425.1'],['C425.1','L405.2']) for pt in row['sites_nm']]
out=dict(parent_sha256=d['sha256'],single_inductor_barrel_site_nm=[60100000,2400000],inductor_pad_net=pin.GetNetname(),largest_separation_after_removing_both_pads_mm=max(math.dist(x,y) for x in movable for y in movable)/1e6,required_pair_spacing_mm=.8,closest_bridges=data)
(root/'emmc-rear-barriers.json').write_text(json.dumps(out,indent=2)+'\n');print(out['inductor_pad_net'],out['largest_separation_after_removing_both_pads_mm'],[(s,n) for s,n,u in data[0]['blocked_by']],flush=True);os._exit(0)
