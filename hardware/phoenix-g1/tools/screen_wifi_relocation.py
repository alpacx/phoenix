#!/usr/bin/env python3
"""Bounded Wi-Fi group placement screen reserving CPU DDR through-vias; no routing claim."""
import json,math,hashlib
from pathlib import Path
import pcbnew as p
R=Path(__file__).resolve().parents[1];P=R/'migration-rk3562/experiments/lpddr4-1gb';D=P/'wifi-relocation';SOURCE=P/'cpu-board-integration/candidate.kicad_pcb'
GROUP={'U25','C2002','C2003','C2004','C2005','C2006','C2008','C2009','L2001'}
def box(f):
 r=f.GetBoundingBox(False,False) if isinstance(f,p.FOOTPRINT) else f.GetBoundingBox();return tuple(p.ToMM(v) for v in (r.GetX(),r.GetY(),r.GetRight(),r.GetBottom()))
def hit(a,b,g=.2):return a[0]<b[2]+g and a[2]>b[0]-g and a[1]<b[3]+g and a[3]>b[1]-g
def main():
 D.mkdir(exist_ok=True);b=p.LoadBoard(str(SOURCE));b.BuildConnectivity();conn=b.GetConnectivity();fs={f.GetReference():f for f in b.GetFootprints()};assert GROUP<=set(fs)
 group=[(ref,box(fs[ref])) for ref in sorted(GROUP)];others=[(ref,box(f),any(len(conn.GetConnectedTracks(pad)) for pad in f.Pads())) for ref,f in fs.items() if ref not in GROUP and f.GetLayer()==p.B_Cu]
 obstacles=[]
 for f in b.GetFootprints():
  if f.GetReference() in GROUP:continue
  for pad in f.Pads():
   if pad.GetAttribute()==p.PAD_ATTRIB_PTH:obstacles.append(('PTH '+f.GetReference()+'.'+pad.GetNumber(),box(pad)))
 for t in b.GetTracks():
  if isinstance(t,p.PCB_VIA) and t.GetNetname().startswith('LPDDR4_'):obstacles.append((t.GetNetname(),box(t)))
 candidates=[]
 for xi in range(22,158):
  for yi in range(16,62):
   x,y=xi/2,yi/2;dx,dy=x-45,y-20;boxes=[(ref,(a+dx,c+dy,z+dx,w+dy)) for ref,(a,c,z,w) in group]
   if any(a<1 or c<1 or z>89 or w>39 for ref,(a,c,z,w) in boxes if ref=='U25'):continue
   if any(hit(bb,o) for ref,bb in boxes if ref=='U25' for _,o in obstacles):continue
   touched=[ref for ref,o,routed in others if any(hit(bb,o) for _,bb in boxes)];routed=[ref for ref,o,r in others if r and any(hit(bb,o) for groupref,bb in boxes if groupref=='U25')]
   if routed:continue
   candidates.append({'module_xy_mm':[x,y],'delta_mm':[dx,dy],'displaced_unrouted_refs':touched,'score':[len(touched),round(math.hypot(dx,dy),4)]})
 candidates.sort(key=lambda r:r['score']);out={'status':'PLACEMENT_SCREEN_ONLY_ROUTING_NOT_VALIDATED','source_sha256':hashlib.sha256(SOURCE.read_bytes()).hexdigest(),'group':sorted(GROUP),'candidate_count':len(candidates),'top_candidates':candidates,'constraints':['90x40 outline with 1mm guard','0.2mm bounding-box guard','Existing CPU and RAM DDR through-vias reserved','Through-hole pads reserved','Other routed backside footprints fixed'],'not_checked':['Existing signal and power tracks outside CPU/RAM fanout','Local passives may need independent movement; only module body strictly clears fixed obstacles','Local ground vias and power reconnection','RF path to antenna, RF matching and keepout','Thermal performance','Compact enclosure target'],'assembly_ready':False}
 (D/'placement-screen.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({'count':len(candidates),'best':candidates[:1]}))
if __name__=='__main__':main()
