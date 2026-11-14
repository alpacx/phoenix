#!/usr/bin/env python3
"""Rebuild eMMC placement and short ground returns; publish only after audits pass."""
import subprocess,json,shutil,tempfile,hashlib
from pathlib import Path
T=Path(__file__).resolve().parent;D=T.parent/'migration-rk3562/experiments/emmc-system';P=D/'pcb';N='/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3';CLI='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
def run(*args):subprocess.run([str(a) for a in args],check=True)
with tempfile.TemporaryDirectory(prefix='phoenix-emmc-checkpoint-') as temp:
 backup=Path(temp)/'pcb';shutil.copytree(P,backup);pointer=D/'working-candidate.json';old=pointer.read_bytes() if pointer.exists() else None
 try:
  for tool in ['migrate_emmc_pcb.py','search_emmc_floorplan.py','place_emmc_backside.py']:run(N,T/tool)
  run(CLI,'pcb','drc','--format','json','-o',P/'emmc-repacked-drc.json',P/'emmc-repacked.kicad_pcb')
  run(N,T/'audit_emmc_pcb.py','emmc-repacked');assert json.loads((P/'emmc-repacked-audit.json').read_text())['placement_geometry_passed']
  run(N,T/'route_emmc_ground.py');run(N,T/'audit_emmc_pcb.py','emmc-ground')
  a=json.loads((P/'emmc-ground-audit.json').read_text());g=json.loads((P/'emmc-ground.json').read_text());assert a['placement_geometry_passed'];assert len(g['connections'])==11 and all(c['accepted'] for c in g['connections']);assert all(c.get('length_mm',0)<=2 for c in g['connections'])
  board=P/'emmc-ground.kicad_pcb';assert a['board_sha256']==hashlib.sha256(board.read_bytes()).hexdigest()
  pointer.write_text(json.dumps({'status':'EMMC_PLACEMENT_AND_EXTERNAL_GROUNDS_ROUTED_OTHER_STORAGE_ROUTING_OPEN','board':'pcb/emmc-ground.kicad_pcb','sha256':a['board_sha256'],'verification':'pcb/emmc-ground-audit.json','schematic':'system/kicad/integrated/phoenix-g1.kicad_sch','source_checkpoint':'../stacked-expansion/working-candidate.json','assembly_ready':False},indent=2)+'\n')
 except BaseException:
  shutil.copytree(backup,P,dirs_exist_ok=True)
  if old is not None:pointer.write_bytes(old)
  elif pointer.exists():pointer.unlink()
  raise
print('eMMC work checkpoint updated; high-speed routing, PI, boot and manufacturing remain open')
