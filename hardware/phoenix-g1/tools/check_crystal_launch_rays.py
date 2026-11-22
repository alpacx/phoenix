"""Locate traces that enclose the SoC's 24 MHz pins on the package face."""
from pathlib import Path
import hashlib,json,math,os
import pcbnew as p
from pcb_bounds import inflated_box
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';d=json.loads((root/'layout-usb-enable-trunk.json').read_text());src=root/d['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==d['sha256'];b=p.LoadBoard(str(src));f=b.FindFootprintByReference('U1');records={}
for pin in ('AG25','AF25'):
 q=f.FindPadByNumber(pin);center=tuple(q.GetPosition());net=q.GetNetCode();t=p.PCB_TRACK(b);t.SetWidth(200000);t.SetLayer(p.F_Cu);t.SetNetCode(net)
 objs=[o for o in list(b.GetTracks())+[pad for fp in b.GetFootprints() for pad in fp.Pads()] if o.GetNetCode()!=net and o.IsOnLayer(p.F_Cu) and inflated_box(o,2600000).Contains(q.GetPosition())]
 rays=[]
 for phi in range(0,360,5):
  dx=math.cos(math.radians(phi));dy=math.sin(math.radians(phi));a=(round(center[0]+90000*dx),round(center[1]+90000*dy));z=(round(center[0]+1600000*dx),round(center[1]+1600000*dy));t.SetStart(p.VECTOR2I(*a));t.SetEnd(p.VECTOR2I(*z));tr=t.GetEffectiveShape(p.F_Cu);hits=[]
  for o in objs:
   pad=isinstance(o,p.PAD);c=78200 if pad and o.GetParentFootprint().GetReference()=='U1' or o.GetNetname().startswith('LPDDR4_') else 202000
   if tr.Collide(o.GetEffectiveShape(p.F_Cu),c) or isinstance(o,p.PCB_VIA) and tr.Collide(o.GetEffectiveHoleShape(),252000):
    hits.append(dict(kind=o.GetClass(),net=o.GetNetname(),pad=o.GetParentFootprint().GetReference()+'.'+o.GetNumber() if pad else None,uuid=o.m_Uuid.AsString()))
  rays.append(dict(degrees=phi,start_nm=a,end_nm=z,blockers=hits))
 feasible=[row for row in rays if not any(o['kind']=='PAD' for o in row['blockers'])]
 records[pin]=dict(net=q.GetNetname(),tested=len(rays),pad_free=len(feasible),best=sorted(feasible,key=lambda row:(len({o['net'] for o in row['blockers']}),len(row['blockers'])))[:5])
(root/'soc-crystal-launch-rays.json').write_text(json.dumps(dict(parent_sha256=d['sha256'],length_mm=1.6,records=records,assembly_ready=False),indent=2)+'\n');print([(k,v['pad_free'],[(o['kind'],o['net']) for o in v['best'][0]['blockers']] if v['best'] else None) for k,v in records.items()],flush=True);os._exit(0)
