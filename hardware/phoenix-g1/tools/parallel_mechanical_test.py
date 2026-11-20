#!/usr/bin/env python3
"""Fault-injection checks for isolated mechanical clearance work."""
import pcbnew as p,json,sys,os,subprocess,hashlib
from pathlib import Path
from audit_mount_component_reservations import screen
D=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/mechanical-clearance-parallel'
def validate(b):
 fs={f.GetReference():f for f in b.GetFootprints()}
 for row in screen(b):
  if row['reservation'].startswith(('H8103 ','H8105 ')):
   assert row['ref']==row['reservation'].split()[0],('body obstruction',row)
 f=fs['H8105'];pads=list(f.Pads());assert len(pads)==1
 assert pads[0].GetAttribute()==p.PAD_ATTRIB_NPTH
 assert pads[0].GetDrillSize()==p.VECTOR2I(p.FromMM(2.2),p.FromMM(2.2))
 assert f.GetPosition()==p.VECTOR2I(p.FromMM(70),p.FromMM(34))
 z=next(z for z in b.Zones() if z.GetZoneName()=='H8105 mechanical reservation')
 assert z.GetBoundingBox().GetWidth()>=p.FromMM(5.4)
 assert z.GetDoNotAllowTracks() and z.GetDoNotAllowVias() and z.GetDoNotAllowZoneFills()
def main():
 if len(sys.argv)>1:
  case=sys.argv[1];b=p.LoadBoard(str(D/'h8105-hole.kicad_pcb'));fs={f.GetReference():f for f in b.GetFootprints()}
  if case=='obstruct':fs['R525'].SetPosition(p.VECTOR2I(p.FromMM(70),p.FromMM(34)))
  elif case=='wrongdrill':list(fs['H8105'].Pads())[0].SetDrillSize(p.VECTOR2I(p.FromMM(1),p.FromMM(1)))
  elif case=='movehole':fs['H8105'].SetPosition(p.VECTOR2I(p.FromMM(71),p.FromMM(34)))
  elif case=='tracksallowed':next(z for z in b.Zones() if z.GetZoneName()=='H8105 mechanical reservation').SetDoNotAllowTracks(False)
  try:validate(b);good=case=='accepted'
  except (AssertionError,KeyError):good=case!='accepted'
  print(case,good,flush=True);os._exit(0 if good else 1)
 results=[]
 for case in ['accepted','obstruct','wrongdrill','movehole','tracksallowed']:
  r=subprocess.run([sys.executable,__file__,case],capture_output=True,text=True);results.append({'case':case,'passed':r.returncode==0,'output':r.stdout[-300:]})
 report={'tests':results,'all_passed':all(x['passed'] for x in results),'board_sha256':hashlib.sha256((D/'h8105-hole.kicad_pcb').read_bytes()).hexdigest()};(D/'tests.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));sys.exit(0 if report['all_passed'] else 1)

if __name__=="__main__":main()
