#!/usr/bin/env python3
"""Audit source preservation, pad assignments, narrow neck and full Wi-Fi continuity."""
import json,hashlib,collections
from pathlib import Path
import pcbnew as p
R=Path(__file__).resolve().parents[1];P=R/'migration-rk3562/experiments/lpddr4-1gb';D=P/'wifi-relocation';SOURCE=P/'system/kicad/pcb/phoenix-lpddr4-placement.kicad_pcb'
def point(q):return q.x,q.y
def copper(t):
 return (t.GetNetname(),t.GetLayer(),point(t.GetStart()),point(t.GetEnd()),t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth(),t.GetDrillValue() if isinstance(t,p.PCB_VIA) else None)
def main():
 m=json.loads((D/'manifest.json').read_text());assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==m['source_sha256'];a=p.LoadBoard(str(SOURCE));b=p.LoadBoard(str(D/'io.kicad_pcb'));old={t.m_Uuid.AsString():copper(t) for t in a.GetTracks()};new={t.m_Uuid.AsString():copper(t) for t in b.GetTracks()};removed=set(m['removed_source_copper_uuids']);assert set(old)-set(new)==removed
 for uid in set(old)-removed:assert old[uid]==new[uid],('Unexpected source copper change',uid)
 oldfs={f.GetReference():f for f in a.GetFootprints()};newfs={f.GetReference():f for f in b.GetFootprints()};assert oldfs.keys()==newfs.keys();allowed=set(m['group'])|{r['ref'] for r in m['unrouted_component_relocations']};padcount=0
 for ref,f in oldfs.items():
  g=newfs[ref];assert {q.GetNumber():q.GetNetname() for q in f.Pads()}=={q.GetNumber():q.GetNetname() for q in g.Pads()},('Pad net changed',ref);padcount+=len(list(f.Pads()))
  if ref not in allowed:assert (point(f.GetPosition()),f.GetOrientationDegrees(),f.GetLayer())==(point(g.GetPosition()),g.GetOrientationDegrees(),g.GetLayer()),('Unexpected footprint move',ref)
 narrow=[]
 for t in b.GetTracks():
  if isinstance(t,p.PCB_VIA) or t.GetNetname()!='+3V3_IO' or p.ToMM(t.GetWidth())>=.2-1e-6:continue
  ends={point(t.GetStart()),point(t.GetEnd())};expected={(p.FromMM(61.75),p.FromMM(5.59)),(p.FromMM(61.75),p.FromMM(4.65))};assert ends==expected and abs(p.ToMM(t.GetWidth())-.127)<1e-6;narrow.append(t.m_Uuid.AsString())
 assert len(narrow)==1,'PMIC neck exception must be unique and bounded'
 drc=json.loads((D/'io-drc.json').read_text());unexpected=[v for v in drc['violations'] if v['type'] not in ('via_dangling','silk_over_copper','silk_overlap','silk_edge_clearance')];assert not unexpected,unexpected[:2]
 wifi=json.loads((D/'io-audit.json').read_text());assert wifi['pcb_sha256']==hashlib.sha256((D/'io.kicad_pcb').read_bytes()).hexdigest();assert all(v for k,v in wifi.items() if isinstance(v,bool) and k!='production_ready')
 assert sum(v['type']=='via_dangling' for v in drc['violations'])==125
 result={'status':'SOURCE_PRESERVATION_AND_WIFI_COPPER_VERIFIED_NOT_RELEASE','source_sha256':m['source_sha256'],'board_sha256':wifi['pcb_sha256'],'pad_assignments_preserved':padcount,'source_copper_items_preserved':len(old)-len(removed),'explicitly_replaced_source_copper_items':len(removed),'unique_PMIC_neck_127um':True,'all_wifi_continuity_flags':True,'critical_DRC_findings':0,'intentional_DDR_dangling_vias':125,'DRC_counts':dict(collections.Counter(v['type'] for v in drc['violations'])),'assembly_ready':False,'limits':['Wi-Fi continuity is not an operational RF/boot test','CPU and DDR routing incomplete','Source/SoC decoupling and power integrity require review','Stackup, impedance, timing, thermal and fabrication qualifications remain open']};(D/'preservation-audit.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
