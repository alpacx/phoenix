"""Identify native blockers for a power barrel reachable from C470 on the back layer."""
from pathlib import Path
from collections import defaultdict,Counter
import hashlib,json,math,os,sys
import pcbnew as p
from pcb_bounds import inflated_box
r=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
vddq='--vddq-crossovers' in sys.argv
emmc33='--emmc-3v3' in sys.argv
emmc18='--emmc-1v8' in sys.argv
vdd1='--vdd1' in sys.argv
base=json.loads((r/('layout-emmc-data-power.json' if emmc33 else 'layout-memory-n12-neighbors.json' if emmc18 else 'layout-lpddr-vdd1-source.json' if vddq else 'layout-lpddr-vdd1-bank.json' if vdd1 else 'layout-lcd-select-trunk.json')).read_text());src=r/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));c=b.FindFootprintByReference('R8006' if emmc18 else 'L403' if vddq else 'L405' if vdd1 else 'C470').FindPadByNumber('2' if vdd1 or vddq else '1');code=c.GetNetCode()
layers=[p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu]
idx=defaultdict(list);cell=1000000
for obj in list(b.GetTracks())+[q for f in b.GetFootprints() for q in f.Pads()]:
    foreign=obj.GetNetCode()!=code
    if not foreign and not isinstance(obj,(p.PCB_VIA,p.PAD)):continue
    box=inflated_box(obj,900000)
    name=obj.GetParentFootprint().GetReference()+'.'+obj.GetNumber() if isinstance(obj,p.PAD) else obj.GetNetname()+' '+obj.GetLayerName()
    copper=[obj.GetEffectiveShape(l) for l in layers if obj.IsOnLayer(l)]
    hole=obj.GetEffectiveHoleShape() if isinstance(obj,p.PCB_VIA) or isinstance(obj,p.PAD) and obj.GetDrillSize().x else None
    for i in range(box.GetLeft()//cell,box.GetRight()//cell+1):
      for j in range(box.GetTop()//cell,box.GetBottom()//cell+1):idx[i,j].append((name,copper,hole,foreign,isinstance(obj,p.PAD)))
v=p.PCB_VIA(b);v.SetWidth(600000);v.SetDrill(300000);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetViaType(p.VIATYPE_THROUGH)
zones=[z.Outline() for z in list(b.Zones())+[z for f in b.GetFootprints() for z in f.Zones()] if z.GetIsRuleArea() and z.GetDoNotAllowVias()]
stat=Counter();sites=defaultdict(list)
if vddq:
    a=json.loads((r/'runs/lpddr-vddq-copper-frontier.json').read_text())
    z=json.loads((r/'runs/lpddr-vddq-load-frontier.json').read_text())
    srcs=[{(x,y) for k,x,y in a if k==l} for l in range(4)]
    dsts=[{(x,y) for k,x,y in z if k==l} for l in range(4)]
    positions=[(l,x,y) for l in range(4) for k in range(4) if l!=k for x,y in srcs[l]&dsts[k]]
else:
    positions=json.loads((r/('runs/emmc-vcc-current-frontier.json' if emmc33 else 'runs/sys-feed-r8006.1-load-frontier.json' if emmc18 else 'runs/lpddr-vdd1-l405-frontier.json' if vdd1 else 'runs/emmc-staggered-frontier.json')).read_text())
for l,x,y in positions:
    v.SetPosition(p.VECTOR2I(x,y));land=v.GetEffectiveShape(p.F_Cu);hole=v.GetEffectiveHoleShape();block=set()
    for name,shapes,h,foreign,pad in idx[x//cell,y//cell]:
        if foreign and any(land.Collide(s,202000) or hole.Collide(s,252000) for s in shapes) or pad and any(land.Collide(s,52000) for s in shapes) or h and (land.Collide(h,252000) or hole.Collide(h,252000)):block.add(name)
    if any(z.Collide(land,0) for z in zones):block.add('via keepout')
    key=tuple(sorted(block));stat[key]+=1
    if len(key)<=(3 if emmc18 or emmc33 else 2):sites[key].append([x,y])
rows=[dict(blockers=k,count=n,sites_nm=sites[k]) for k,n in sorted(stat.items(),key=lambda pair:(len(pair[0]),-pair[1])) if len(k)<=(3 if emmc18 or emmc33 else 2)]
(r/('emmc-vcc-current-barrier.json' if emmc33 else 'emmc-1v8-via-obstacles.json' if emmc18 else 'vddq-crossover-barrels.json' if vddq else 'vdd1-l405-via-obstacles.json' if vdd1 else 'emmc-frontier-via-obstacles.json')).write_text(json.dumps(dict(parent_sha256=base['sha256'],sites_tested=sum(stat.values()),minimum_blocker_groups=min(map(len,stat)),low_conflict_sites=rows,assembly_ready=False),indent=2)+'\n')
print([(k,len(v)) for k,v in sites.items() if len(k)<2],flush=True);os._exit(0)
