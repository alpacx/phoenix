"""Measure pad-group fragmentation after the full W3006 antenna opening at representative edge sites."""
from pathlib import Path
from collections import defaultdict,Counter
from tempfile import TemporaryDirectory
import os,math,hashlib,json,subprocess,sys
import pcbnew as p
from w3006_layout1_geometry import xy_nm,GROUND,SIGNAL,MARGIN
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel';read=lambda n:json.loads((root/(n+'.json')).read_text());base=read('wifi-selector-branch-coupon')['candidate'];src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256'];rows=read('runs/w3006-edge-site-census');old=p.LoadBoard(str(src));old.BuildConnectivity();edge=old.GetBoardEdgesBoundingBox();bounds=tuple(x/1e6 for x in (edge.GetLeft(),edge.GetTop(),edge.GetRight(),edge.GetBottom()));layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu)
def groups(b):
 pads={q.m_Uuid.AsString():q for f in b.GetFootprints() for q in f.Pads() if q.GetNetCode() and q.GetNumber()};g={}
 for k,q in pads.items():
  if k in g:continue
  ids=frozenset(({k}|{o.m_Uuid.AsString() for o in b.GetConnectivity().GetConnectedItems(q)}) & pads.keys())
  for n in ids:g[n]=ids
 return pads,g
pads,prior=groups(old);names=defaultdict(set)
for k,q in pads.items():names[q.GetParentFootprint().GetReference()+'.'+q.GetNumber()].add(k)
comps=set(prior.values());ledger=read('layout-usb-enable-trunk')['verified_pairs'];samples=[]
# Sample physically distinct sectors and include the trade-off among the
# smallest part count, fewest affected tracks and low pad-group repair counts.
for side,lo,hi in [('top',0,91),('bottom',0,14),('bottom',14,20),('bottom',20,24),('bottom',24,28),('bottom',28,34),('bottom',34,91)]:
 pool=[r for r in rows if r['side']==side and lo<=r['offset_mm']<hi]
 for key in [lambda r:(len(r['critical_conductors']),r['isolated_pad_rejoin_lower_bound'],sum(r['nets'].values())),lambda r:(r['isolated_pad_rejoin_lower_bound'],sum(r['nets'].values())),lambda r:(sum(r['nets'].values()),len(r['components']))]:
  if pool:
   r=min(pool,key=key)
   if r not in samples:samples.append(r)
def cut(b,r):
 side=r['side'];off=r['offset_mm'];mirror=r['rf_face']=='B.Cu'
 def shape(verts):
  k=p.SHAPE_POLY_SET();k.NewOutline()
  for u,v in verts:k.Append(*xy_nm(side,off,mirror,u,v,bounds))
  return k
 g=shape(GROUND);s=shape(SIGNAL);s.Inflate(round(MARGIN*1e6),p.CORNER_STRATEGY_ROUND_ALL_CORNERS,1000);mask=s.BBox();removed=[]
 for t in b.GetTracks():
  if not t.GetBoundingBox().Intersects(mask):continue
  if any(t.IsOnLayer(l) and (g if l in (p.In1_Cu,p.In4_Cu) else s).Collide(t.GetEffectiveShape(l),0) for l in layers):removed.append(t)
 for t in removed:b.Remove(t)
 for j,ref in enumerate(r['components']):
  f=b.FindFootprintByReference(ref);f.SetPosition(p.VECTOR2I(160000000+j*15000000,170000000))
 for idx,l in enumerate(layers):
  z=p.ZONE(b);z.SetLayer(l);z.SetIsRuleArea(True);z.SetDoNotAllowZoneFills(True);z.Outline().AddOutline((g if l in (p.In1_Cu,p.In4_Cu) else s).Outline(0));b.Add(z)
 p.ZONE_FILLER(b).Fill(b.Zones());return len(removed)
reports=[]
with TemporaryDirectory() as tmp:
 trial=Path(tmp)/'trial.kicad_pcb'
 for idx,r in enumerate(samples):
  if len(sys.argv)==1:
   subprocess.run([sys.executable,__file__,str(idx),tmp],check=True,stdout=subprocess.DEVNULL)
   reports.append(json.loads((Path(tmp)/('result-'+str(idx)+'.json')).read_text()));continue
  if idx!=int(sys.argv[1]):continue
  trial=Path(sys.argv[2])/('site-'+str(idx)+'.kicad_pcb');amount=trial.with_suffix('.txt')
  if len(sys.argv)>3:
   b=p.LoadBoard(str(src));n=cut(b,r);p.SaveBoard(str(trial),b);amount.write_text(str(n));os._exit(0)
  subprocess.run([sys.executable,__file__,str(idx),sys.argv[2],'--cut-only'],check=True,stdout=subprocess.DEVNULL)
  n=int(amount.read_text());saved=p.LoadBoard(str(trial));saved.BuildConnectivity();after,g=groups(saved)
  assert after.keys()==pads.keys()
  repairs=Counter()
  for group in comps:
   parts={g[k]&group for k in group};need=len(parts)-1
   if need:repairs[pads[next(iter(group))].GetNetname()]+=need
  lost=[pair for pair in ledger if not any(g[k]&names[pair[1]] for k in names[pair[0]])]
  reports.append(dict(site=r,removed_copper_items=n,minimum_repairs=sum(repairs.values()),by_net=dict(repairs),lost_ledger_assertions=len(lost),lost_pairs=lost))
  (Path(sys.argv[2])/('result-'+str(idx)+'.json')).write_text(json.dumps(reports[-1]));os._exit(0)
out=dict(source_sha256=base['sha256'],sites_screened=len(rows),native_opening_tests=len(samples),simulations=reports,method='Remove intersecting copper, isolate parts individually, impose layer-specific filled-zone openings. Refill, save and reload each board, measure original pad-group components. Counts are minimum electrical joins; RF, power loops and DFM impose extra constraints.',assembly_ready=False)
(root/'w3006-relocation-repair-costs.json').write_text(json.dumps(out,indent=2)+'\n');print([(r['site']['side'],r['site']['offset_mm'],r['minimum_repairs'],r['lost_ledger_assertions']) for r in reports],flush=True);os._exit(0)
