#!/usr/bin/env python3
"""Unrouted physical feasibility study. NOT a manufacturing board or completed placement.
Run with KiCad's bundled Python (pcbnew). Source netlist is the integrated schematic.
"""
import json,math,xml.etree.ElementTree as ET
from pathlib import Path
import pcbnew as p
ROOT=Path(__file__).resolve().parents[1];K=ROOT/'kicad';OUT=K/'floorplan';OUT.mkdir(exist_ok=True)
def mm(x):return p.FromMM(x)
def pos(x,y):return p.VECTOR2I(mm(x),mm(y))
def rect(fp):
 b=fp.GetBoundingBox(False,False);return [p.ToMM(b.GetX())-.25,p.ToMM(b.GetY())-.25,p.ToMM(b.GetRight())+.25,p.ToMM(b.GetBottom())+.25]
def overlap(a,b):return a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]
def has_drills(fp):
 return any(pad.GetDrillSize().x and pad.GetDrillSize().y for pad in fp.Pads())
def main(footprint_candidates=None, placement_targets=None, orientations=None, fixed_locations=None, placement_keepouts=None, frozen_placement=None):
 footprint_candidates=footprint_candidates or {}
 board=p.BOARD();board.SetCopperLayerCount(6);board.GetDesignSettings().SetBoardThickness(mm(1.6))
 title=board.GetTitleBlock();title.SetTitle('Phoenix G1 - UNROUTED feasibility study');title.SetRevision('DRAFT - NOT FOR FABRICATION')
 x=ET.parse(ROOT/'review/integrated.xml');nets={};assign={}
 for node in x.findall('.//nets/net'):
  n=p.NETINFO_ITEM(board,node.get('name'));board.Add(n);nets[node.get('name')]=n
  for pad in node.findall('node'):assign[pad.get('ref'),pad.get('pin')]=n
 footprints={};missing=[];pad_errors=[]
 for comp in x.findall('.//components/comp'):
  ref=comp.get('ref');fid=footprint_candidates.get(ref,comp.findtext('footprint'))
  if not fid:missing.append({'ref':ref,'value':comp.findtext('value'),'reason':'No qualified footprint'});continue
  lib,name=fid.split(':');fp=p.FootprintLoad(str(K/(lib+'.pretty')),name)
  if not fp:raise RuntimeError(fid)
  fp.SetReference(ref);fp.SetValue(comp.findtext('value'));fp.SetFPID(p.LIB_ID(lib,name));fp.Reference().SetVisible(False);fp.Value().SetVisible(False)
  # Imported relative 3D paths are not reliable. This study uses measured 2D geometry only.
  fp.Models().clear()
  padnums=set()
  for pad in fp.Pads():
   num=pad.GetNumber();padnums.add(num)
   if (ref,num) in assign:pad.SetNet(assign[ref,num])
  for (r,num),net in assign.items():
   if r==ref and num not in padnums:pad_errors.append({'ref':ref,'missing_pad':num,'net':net.GetNetname()})
  path=comp.find('sheetpath');ts=comp.findtext('tstamps')
  if path is not None and ts:
   try:fp.SetPath(p.KIID_PATH(path.get('tstamps')+ts))
   except Exception:pass
  board.Add(fp);footprints[ref]=fp
 fixed={'J1':(7.13,20,-90),'U6':(14,20,0),'U1':(43,20,0),'U2':(25,10,0),'U3':(25,28,0),'U4':(60,9,0),'U5':(63,31,0),'J2':(76.7,20,-90),'U10':(60,22,0),'U17':(14,30.5,0),'L1301':(14,36,0),'L1001':(60,17,0),'U18':(60,39,0)}
 # Flash moved to free top-left area; original lower position would exceed the envelope.
 fixed['U18']=(14,8,0)
 fixed.update(fixed_locations or {})
 for ref,q in (frozen_placement or {}).items():fixed[ref]=(q["x"],q["y"],q["orientation"],int(q["side"]=="back"))
 occupied={0:[],1:[]};placed={};fail=[]
 for keepout in placement_keepouts or []:occupied[keepout["side"]].append(tuple(keepout["rect_mm"]))
 for ref,location in fixed.items():
  cx,cy,ang=location[:3];side=location[3] if len(location)>3 else 0
  fp=footprints[ref]
  if fp.IsFlipped()!=bool(side):fp.Flip(pos(0,0),False)
  fp.SetOrientationDegrees(ang);fp.SetPosition(pos(cx,cy));b=rect(fp)
  if any(overlap(b,r) for r in occupied[side]):fail.append({'ref':ref,'reason':'fixed component bounding-box overlap'})
  occupied[side].append(b);placed[ref]={'x':cx,'y':cy,'side':'back' if side else 'front','orientation':ang}
  if has_drills(fp):occupied[1-side].append(b)
 contracts=json.loads((ROOT/'review/integrated-contract.json').read_text());sheets={r['ref']:r['sheet'] for r in contracts}
 targets={'boot-flash':(14,8),'core-boot-support':(43,34),'cpu-power':(60,22),'ddr-bypass':(25,20),'ddr3-memory':(25,20),'ethernet-phy':(63,31),'ethernet-support':(63,31),'ethernet-esd':(63,31),'ethernet-magnetics':(77,20),'pmic-bucks':(60,9),'pmic-control':(60,9),'pmic-ldos':(60,9),'system-3v3':(14,31),'usb-c-frontend':(10,20),'usb-vbus-guard':(10,8),'usb-power-control':(7,8),'usb-input-protection':(7,30),'soc-core-bypass':(43,20),'soc-io-bypass':(43,20),'usb-analog-bypass':(43,30),'display-power':(42,6),'display-signals':(42,6),'test-access':(45,37)}
 # Reserve source terminations before free packing; physical source comes from the netlist-bound plan.
 routing=json.loads((ROOT/'review/highspeed-routing-plan.json').read_text())
 source_targets={}
 for path in routing['rgmii_paths']:
  source=path['source_ref'];net=path['net_segments'][0 if source=='U1' else 1]
  pads=[pad for pad in footprints[source].Pads() if pad.GetNetname()==net]
  assert len(pads)==1,(source,net)
  q=pads[0].GetPosition();source_targets[path['series']['component']]=(p.ToMM(q.x),p.ToMM(q.y),int(footprints[source].IsFlipped()))
 source_targets.update(placement_targets or {})
 # Place terminations first, then large components. Distributed bypass begins underneath.
 remaining=[(ref,fp) for ref,fp in footprints.items() if ref not in fixed]
 remaining.sort(key=lambda item:(0 if item[0] in source_targets else 1,-(rect(item[1])[2]-rect(item[1])[0])*(rect(item[1])[3]-rect(item[1])[1])))
 for ref,fp in remaining:
  if ref in (orientations or {}):fp.SetOrientationDegrees(orientations[ref])
  sheet=sheets.get(ref,'');tx,ty=targets.get(sheet,(45,20));preferred=1 if sheet in ['ddr-bypass','soc-core-bypass','soc-io-bypass','test-access'] else 0;found=False
  if ref in source_targets:tx,ty,preferred=source_targets[ref]
  positions=sorted(((cx/2,cy/2) for cx in range(4,177) for cy in range(4,77)),key=lambda xy:(xy[0]-tx)**2+(xy[1]-ty)**2)
  positions=[(tx,ty)]+[xy for xy in positions if xy!=(tx,ty)]
  for side in [preferred,1-preferred]:
   if fp.IsFlipped() != bool(side):fp.Flip(pos(0,0),False)
   for cx,cy in positions:
    fp.SetPosition(pos(cx,cy));b=rect(fp)
    if b[0]<1 or b[1]<1 or b[2]>89 or b[3]>39:continue
    if any(overlap(b,r) for r in occupied[side]):continue
    if has_drills(fp) and any(overlap(b,r) for r in occupied[1-side]):continue
    occupied[side].append(b);placed[ref]={'x':cx,'y':cy,'side':'back' if side else 'front','orientation':fp.GetOrientationDegrees()};found=True;break
   if found:
    if has_drills(fp):occupied[1-side].append(b)
    break
  if not found:
   fp.SetPosition(pos(100+len(fail)*8,20));fail.append({'ref':ref,'reason':'No floorplan location in 90x40 envelope'})
 for a,b in [((0,0),(90,0)),((90,0),(90,40)),((90,40),(0,40)),((0,40),(0,0))]:
  e=p.PCB_SHAPE();e.SetShape(p.SHAPE_T_SEGMENT);e.SetStart(pos(*a));e.SetEnd(pos(*b));e.SetLayer(p.Edge_Cuts);e.SetWidth(mm(.05));board.Add(e)
 t=p.PCB_TEXT(board);t.SetText('UNROUTED STUDY - NOT FOR FABRICATION\n90 x 40 mm envelope, stackup/thermal/display fit unqualified');t.SetPosition(pos(45,-5));t.SetTextSize(pos(1,1));t.SetLayer(p.Dwgs_User);board.Add(t)
 board.BuildConnectivity();board.GetConnectivity().RecalculateRatsnest()
 unconnected=board.GetConnectivity().GetUnconnectedCount(False)
 p.SaveBoard(str(OUT/'phoenix-g1-floorplan.kicad_pcb'),board)
 (OUT/'fp-lib-table').write_text((K/'fp-lib-table').read_text().replace('${KIPRJMOD}/','${KIPRJMOD}/../'))
 (OUT/'phoenix-g1-floorplan.kicad_pro').write_text(json.dumps({'meta':{'filename':'phoenix-g1-floorplan.kicad_pro','version':1},'board':{'design_settings':{'rules':{'min_copper_edge_clearance':0.25}}}},indent=2)+'\n')
 report={'status':'UNROUTED FEASIBILITY STUDY','envelope_mm':[90,40],'copper_layers_provisional':6,'placed_footprints':len(placed),'missing_footprints':missing,'placement_failures':fail,'missing_pads':pad_errors,'tracks':0,'placement':placed,'placement_keepouts':placement_keepouts or [],'limitations':['No signal/power routing, no stackup or impedance qualification.','Automated placement is a packing estimate, not final layout.','Display body/flex, heatsink and enclosure not included in the fit claim.','Footprint body boxes do not prove courtyard, drill, BGA escape or assembly compliance.']}
 report['unqualified_footprint_overrides']=footprint_candidates
 report['source_termination_target_refs']=sorted(source_targets)
 report['unconnected_ratsnest_edges']=unconnected
 report['limitations'].append('DRC report may cap displayed unconnected items; full connectivity count is recorded separately.')
 (ROOT/'review/floorplan.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['placement','limitations']},indent=2))
if __name__=='__main__':main()
