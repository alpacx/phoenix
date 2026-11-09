#!/usr/bin/env python3
"""Rebuild draft migration and audits. Never exports manufacturing files."""
import sys,subprocess,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];TOOLS=ROOT/'tools';OUT=ROOT/'migration-rk3562'
EDA=Path('/tmp/phoenix-eda-venv/bin/python');KICAD=Path('/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')
def run(script,python=sys.executable):subprocess.run([str(python),str(TOOLS/script)],check=True)
def main():
 if not EDA.exists() or not KICAD.exists():raise SystemExit('Requires existing sexpdata Python environment and KiCad CLI; no dependencies installed automatically.')
 for s in ['extend_rk3562_allocation.py','map_rk3562_power.py','build_rk3562_signal_types.py','audit_rk3562_pending.py','audit_rk3562_reference.py','build_rk3562_io_domains.py']:run(s)
 for s in ['build_rk3562_migration.py','prepare_rk3562_integration.py']:run(s,EDA)
 code="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import integrate_schematic as i;i.ROOT=Path(sys.argv[2]);i.main()"
 subprocess.run([str(EDA),'-c',code,str(TOOLS),str(OUT)],check=True)
 sch=OUT/'kicad/integrated/phoenix-g1.kicad_sch'
 subprocess.run([str(KICAD),'sch','export','netlist','--format','kicadxml','-o',str(OUT/'review/integrated.xml'),str(sch)],check=True)
 subprocess.run([str(KICAD),'sch','erc','-o',str(OUT/'review/integrated-erc.txt'),str(sch)],check=True)
 for s in ['check_rk3562_integration.py','audit_rk3562_power_paths.py']:run(s)
 code="import sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);import build_bom_review as b;b.ROOT=Path(sys.argv[2]);b.main()"
 subprocess.run([sys.executable,'-c',code,str(TOOLS),str(OUT)],check=True)
 status=json.loads((OUT/'review/completion-status.json').read_text());status.update(json.loads((OUT/'review/schematic-status.json').read_text()));checks=json.loads((OUT/'review/integrated-connectivity.json').read_text())
 status.update({'checked_pin_dispositions':checks['checked_pin_dispositions'],'erc_messages':sum(checks['erc_categories'].values()),'pending_pins':checks['pending_soc_pins'],'active_signal_directions_modelled':136,'power_nets_with_dc_path':len(json.loads((OUT/'review/power-path-audit.json').read_text())['rails']),'assembly_ready':False,'routing_complete':False})
 status['other_unfinished_work'][0]='CPU feedback renamed CPU_FB_SENSE; capacitor-side sense documented, inherited RC loop stability remains unqualified'
 (OUT/'review/completion-status.json').write_text(json.dumps(status,indent=2)+'\n')
 print('DRAFT rebuilt. ERC and unresolved design holds remain; no manufacturing release.')
if __name__=='__main__':main()
