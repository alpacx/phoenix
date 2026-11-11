"""Envelope-only screen, not a KiCad placement/routing or fabrication qualification."""
import json,math,argparse
from pathlib import Path
D=Path(__file__).resolve().parent
rows=json.loads((D/'footprint-envelopes.json').read_text());parts={r['ref']:r for r in rows if r['ref']!='J3'}
ap=argparse.ArgumentParser();ap.add_argument('--optimistic',action='store_true');args=ap.parse_args();W,H=(78,28) if args.optimistic else (76,26);guard=0 if args.optimistic else 1;G=.25;N,M=int(W/G),int(H/G)
occ={'front':[0]*M,'back':[0]*M};placements=[]
def put(ref,x,y,w,h,side,through=False):
 ix,iy=int(x/G),int(y/G);nw,nh=math.ceil(w/G),math.ceil(h/G)
 if ix<2 or iy<2 or ix+nw>N-2 or iy+nh>M-2:return False
 mask=((1<<nw)-1)<<ix;sides=['front','back'] if through else [side]
 if any(occ[s][j]&mask for s in sides for j in range(iy,iy+nh)):return False
 for s in sides:
  for j in range(max(0,iy-guard),min(M,iy+nh+guard)):occ[s][j]|=(((1<<min(N-ix+guard,nw+2*guard))-1)<<max(0,ix-guard))
 placements.append(dict(ref=ref,x=x,y=y,w=w,h=h,side=side,through_exclusion=through));return True
# Manually reserved major packages, envelopes only; connector overhang not optimized.
fixed=[('J1',.5,7.25,9.05,11.05,'front',True),('J2',53.75,3.5,21.54,18.75,'front',True),('U1',26.5,5,14.775,14.775,'front',False),('U2',11,3,13.2,8.24,'front',False),('U3',11,12.25,13.2,8.24,'front',False),('U4',43,2,8.4,8.17,'front',False),('U5',44,16,6.01,6.355,'front',False),('U25',11,6,13.05,13.05,'back',False)]
for a in fixed:assert put(*a),a
unplaced=[]
for r in rows:
 ref=r['ref']
 if ref=='J3' or ref in {a[0] for a in fixed}:continue
 done=False
 for side in [r['side'],'back' if r['side']=='front' else 'front']:
  for w,h in [(r['width_mm'],r['height_mm']),(r['height_mm'],r['width_mm'])]:
   for iy in range(2,M-2):
    for ix in range(2,N-2):
     if put(ref,ix*G,iy*G,w,h,side):done=True;break
    if done:break
   if done:break
  if done:break
 if not done:unplaced.append(ref)
report={'status':'ENVELOPE SCREEN ONLY; NOT A VALID PCB LAYOUT','enclosure_target_mm':[80,30],'assumed_pcb_mm':[W,H],'wall_and_board_allowance_per_side_mm':(80-W)/2,'extra_grid_guard_mm':guard*G,'grid_mm':G,'placements':placements,'unplaced':unplaced,'count_placed':len(placements),'count_total':len(parts),'limitations':['Greedy rectangular packing is neither a proof of feasible routing nor a proof of impossibility.','No electrical grouping, DDR timing, RF keepout, power loops, thermal paths, FPC bends or 3D heights validated.','Display and controls require a separate upper mechanical plane; excluded from base PCB packing.','Some PCB pads and footprints remain unqualified in source.','Major connectors excluded on both sides as conservative through-hole reservation.'],'production_ready':False}
(D/('envelope-optimistic.json' if args.optimistic else 'envelope-screen.json')).write_text(json.dumps(report,indent=2)+'\n');print('placed',len(placements),'total',len(parts),'unplaced',len(unplaced),unplaced)
