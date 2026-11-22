"""Rank internal-antenna edge sites on the RF selector candidate using native copper and mechanical reservations."""
from pathlib import Path
from collections import Counter
import json,math,hashlib,os
import pcbnew as p
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';read=lambda n:json.loads((root/(n+'.json')).read_text());cp=read('wifi-selector-branch-coupon')['candidate'];src=root/cp['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==cp['sha256'];b=p.LoadBoard(str(src));edge=b.GetBoardEdgesBoundingBox();outline=[edge.GetLeft(),edge.GetTop(),edge.GetRight(),edge.GetBottom()];v=lambda xy:p.VECTOR2I(*xy)
fps=[(f.GetReference(),f.GetCourtyard(f.GetLayer()),f.GetLayerName()) for f in b.GetFootprints()];ls=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
rails=[(t.m_Uuid.AsString(),t.GetNetname(),t.GetBoundingBox(),[(l,t.GetEffectiveShape(l)) for l in ls if t.IsOnLayer(l)]) for t in b.GetTracks()]
pin=b.FindFootprintByReference('R2005').FindPadByNumber('2').GetPosition()
mounts=[(z.GetZoneName(),z.Outline()) for z in b.Zones() if z.GetIsRuleArea() and z.GetZoneName().endswith(' mechanical reservation')]
hard={'J1','J2','J3','U1','U2','U8001','U25'};allrows=[]
# A nesting of necessary central ground opening and conservative full-height
# projected envelope avoids treating every isolated via in a bounding rectangle as fatal.
for side in ('top','bottom','left','right'):
 along=(outline[2]-outline[0]) if side in ('top','bottom') else (outline[3]-outline[1])
 for i in range(0,math.floor((along-14150000)/250000)+1):
  offset=i*250000
  for flip in (False,True):
   def xy(u,vv):
    uu=(14150000-u) if flip else u
    if side=='top':return outline[0]+offset+uu,outline[1]+vv
    if side=='bottom':return outline[0]+offset+uu,outline[3]-vv
    if side=='left':return outline[0]+vv,outline[1]+offset+uu
    return outline[2]-vv,outline[1]+offset+uu
   def poly(start,end,depth):
    a=p.SHAPE_POLY_SET();a.NewOutline()
    for uv in ((start,0),(end,0),(end,depth),(start,depth)):a.Append(*xy(*uv))
    return a
   entire=poly(0,14150000,7400000);core=poly(0,11600000,6250000);bb=entire.BBox()
   bodies=[ref for ref,s,l in fps if s.OutlineCount() and s.BBox().Intersects(bb) and s.Collide(entire,0)]
   fixed=sorted(hard.intersection(bodies));obstruct=[name for name,polygon in mounts if polygon.Collide(entire,0)]
   if fixed or obstruct:continue
   nets=Counter();uu=set();plane_hits=set()
   for uid,net,tb,shapes in rails:
    if not bb.Intersects(tb):continue
    if any((core if l in (p.F_Cu,p.B_Cu,p.In1_Cu,p.In4_Cu) else entire).Collide(sh,0) for l,sh in shapes):nets[net]+=1;uu.add(uid)
   for zone in b.Zones():
    if zone.GetIsRuleArea():continue
    for l in ls:
     if zone.IsOnLayer(l) and zone.HasFilledPolysForLayer(l) and zone.GetFilledPolysList(l).Collide(core,0):plane_hits.add((b.GetLayerName(l),zone.GetNetname()))
   fixed_signal=sorted(n for n in nets if n.startswith(('SOC_USB_','USB_RX','USB_TX','MUX_TX','LPDDR4_')));score=(len(fixed_signal),len([r for r in bodies if r.startswith(('U','J','Y','L'))]),len(bodies),sum(nets.values()),math.dist(tuple(pin),xy(11600000,5000000)))
   allrows.append(dict(side=side,offset_mm=offset/1e6,mirror=flip,component_refs=bodies,net_counts=dict(nets),critical_nets=fixed_signal,projection_fills=sorted(plane_hits),score=score))
allrows.sort(key=lambda row:row['score']);best=[]
for row in allrows:
 if all(row['side']!=r['side'] or abs(row['offset_mm']-r['offset_mm'])>=3 for r in best):best.append(row)
 if len(best)>=8:break
report=dict(sha256=cp['sha256'],outline_nm=outline,step_mm=.25,ground_core_mm=[11.6,6.25],other_layer_envelope_mm=[14.15,7.4],fixed_mechanical_clear=len(allrows),best=best,specification='Pulse/Yageo W3006 issue 2137 p6 layout 1, https://productfinder.pulseeng.com/doc_type/WEB301/doc_num/W3006/doc_part/W3006.pdf',limitations=['Alignment of core relative to the conservative envelope is provisional. Confirm the feed-side step and 0.4 mm offsets on the dimensioned drawing before materializing exact layer-specific keepouts.','Necessary/core geometry and conservative envelope are distinct. Enclosure, ground metallization and RF tuning require separate verification.'],assembly_ready=False)
(root/'internal-antenna-edge-recovery.json').write_text(json.dumps(report,indent=2)+'\n');print(len(allrows),[(r['side'],r['offset_mm'],r['component_refs'],len(r['net_counts'])) for r in best[:3]],flush=True);os._exit(0)
