#!/usr/bin/env python3
"""Screen front-side PHY bulk placement without writing a PCB or routing power."""
import argparse,collections,hashlib,json,math
from pathlib import Path
import pcbnew as p
from local_pcb_router import LocalRouter
from audit_mount_component_reservations import screen
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/pmic-ldo-inputs'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--placement-step',type=float,default=.25)
parser.add_argument('--inductor-angle',type=int,choices=[0,90,180,270])
parser.add_argument('--output',default='phy-bulk-placement-probe.json')
args=parser.parse_args()
if not .05 <= args.placement_step <= 1:parser.error('placement step must be 0.05 to 1 mm')
if Path(args.output).name != args.output:parser.error('output must be a filename')
if args.inductor_angle is not None and args.output == 'phy-bulk-placement-probe.json':parser.error('use a separate output for hypothetical inductor rotation')
scale=1/args.placement_step
cp=json.loads((D/'working-candidate.json').read_text());source=D/cp['board']
assert hashlib.sha256(source.read_bytes()).hexdigest()==cp['sha256']
reports=[]
for ref,target in [('C511',('L501','2')),('C515',('U5','29'))]:
 b=p.LoadBoard(str(source));fs={f.GetReference():f for f in b.GetFootprints()};f=fs[ref]
 if args.inductor_angle is not None:
  b.BuildConnectivity()
  assert all(not b.GetConnectivity().GetConnectedTracks(q) for q in fs['L501'].Pads()),'Cannot rotate connected inductor in placement-only probe'
  fs['L501'].SetOrientationDegrees(args.inductor_angle)
 pin=next(q for q in fs[target[0]].Pads() if q.GetNumber()==target[1])
 px,py=p.ToMM(pin.GetPosition().x),p.ToMM(pin.GetPosition().y)
 r=LocalRouter(b,(px-6,py-6,px+6,py+6),width=.2,grid=.05)
 r.pads=[q for q in r.pads if q.GetParentFootprint().GetReference()!=ref]
 blocked={q.GetNumber():r.blocked(p.F_Cu,q.GetNetname(),math.hypot(p.ToMM(q.GetSize().x),p.ToMM(q.GetSize().y))) for q in f.Pads()}
 obstacles=[(g.GetReference(),g.GetCourtyard(p.F_Cu).BBox()) for g in b.GetFootprints() if g.GetReference()!=ref and g.GetLayer()==p.F_Cu]
 counts=collections.Counter();candidates=[]; blocker_groups=collections.Counter(); examples={}; copper_rejected=[]
 for x in range(math.ceil((px-6)*scale),math.floor((px+6)*scale)+1):
  for y in range(math.ceil((py-6)*scale),math.floor((py+6)*scale)+1):
   for angle in [0,90,180,270]:
    f.SetPosition(p.VECTOR2I(p.FromMM(x/scale),p.FromMM(y/scale)));f.SetOrientationDegrees(angle)
    pad=next(q for q in f.Pads() if q.GetNumber()=='1');distance=math.dist(r.xy(pad),r.xy(pin))
    if distance>5.08:counts['distance']+=1;continue
    hits=tuple(sorted(name for name,box in obstacles if f.GetCourtyard(p.F_Cu).BBox().Intersects(box)))
    if hits:
     counts['courtyard']+=1;blocker_groups[hits]+=1
     examples.setdefault(hits,{'center_mm':[x/scale,y/scale],'angle_deg':angle,'straight_line_mm':round(distance,4)})
     continue
    if any(r.cell(r.xy(q)) in blocked[q.GetNumber()] for q in f.Pads()):
     counts['pad_copper']+=1;copper_rejected.append({'center_mm':[x/scale,y/scale],'angle_deg':angle,'straight_line_mm':round(distance,4)});continue
    if any(row['ref']==ref for row in screen(b)):counts['mount']+=1;continue
    candidates.append({'center_mm':[x/scale,y/scale],'angle_deg':angle,'straight_line_mm':round(distance,4)})
 candidates.sort(key=lambda row:row['straight_line_mm'])
 reports.append({'reference':ref,'target':'.'.join(target),'candidate_count':len(candidates),'closest_candidates':candidates[:12],'conservative_copper_rejections':sorted(copper_rejected,key=lambda row:row['straight_line_mm']),'rejection_counts':dict(counts),'courtyard_blocker_groups':[{'references':list(k),'positions':v,'example_not_placement':examples[k]} for k,v in sorted(blocker_groups.items(),key=lambda item:(len(item[0]),-item[1]))[:24]]})
result={'status':'PLACEMENT_SCREEN_NOT_POWER_ROUTING','source_sha256':cp['sha256'],'placement_step_mm':args.placement_step,'inductor_angle_override_deg':args.inductor_angle,'capacitors':reports,
 'checkpoint_modified':False,'assembly_ready':False,
 'limitations':['Each capacitor is evaluated independently; simultaneous placement is not proven.',
 'An optional inductor rotation is hypothetical: its pad clearance, switching path and loop geometry require separate verification.',
 'Existing ground connections would need rerouting if a capacitor is moved.',
 'The 5.08 mm straight-line screen is based on historical rev 1.1 guidance; actual wide power and return paths remain unresolved.',
 'No candidate is promoted; no electrical or DRC qualification is implied by the conservative screen.']}
assert hashlib.sha256(source.read_bytes()).hexdigest()==cp['sha256']
(D/'pcb'/args.output).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
