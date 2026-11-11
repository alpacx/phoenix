#!/usr/bin/env python3
"""Rebuild the LPDDR4 engineering candidate and checks, never manufacturing exports."""
import subprocess,json,hashlib,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];T=ROOT/'tools';P=ROOT/'migration-rk3562/experiments/lpddr4-1gb';S=P/'system';EDA='/tmp/phoenix-eda-venv/bin/python';PCB='/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/bin/python3.9';CLI='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
def run(args):subprocess.run([str(a) for a in args],check=True)
def main():
    mainpcb=ROOT/'migration-rk3562/kicad/pcb/phoenix-g1.kicad_pcb';before=hashlib.sha256(mainpcb.read_bytes()).hexdigest()
    manifest=S/'review/candidate-checkpoint.json';manifest.unlink(missing_ok=True)
    for script,python in [('build_rk3562_lpddr4_candidate.py',sys.executable),('build_rk3562_lpddr4_package.py',sys.executable),('build_rk3562_lpddr4_sheet.py',EDA),('integrate_rk3562_lpddr4_candidate.py',EDA),('audit_rk3562_lpddr4_system.py',sys.executable),('build_lpddr4_fanout_coupon.py',PCB),('build_rk3562_lpddr4_pcb_candidate.py',PCB)]:run([python,T/script])
    board=S/'kicad/pcb/phoenix-lpddr4-placement.kicad_pcb'
    run([CLI,'pcb','drc','--format','json','--severity-all','-o',S/'review/pcb-drc.json',board])
    run([PCB,T/'audit_rk3562_lpddr4_pcb.py'])
    run([PCB,T/'audit_rk3562_wifi_converter.py','--board',board,'--report',S/'review/preserved-wifi-audit.json','--require-local','--require-module-supply','--require-module-ground','--require-module-buck','--require-vddio-bypass','--require-lpo','--require-lpo-bypass'])
    run([CLI,'sch','erc','--format','json','-o',S/'review/integrated-erc.json',S/'kicad/integrated/phoenix-g1.kicad_sch'])
    for script in ['check_lpddr4_escape_geometry.py','screen_rk3562_ddr_escape.py','screen_rk3562_ddr_escape_bends.py']:run([sys.executable,T/script])
    run([PCB,T/'build_cpu_ddr_corner_coupon.py'])
    run([CLI,'pcb','drc','--format','json','--severity-all','-o',P/'cpu-corner-coupon/drc.json',P/'cpu-corner-coupon/cpu-corners.kicad_pcb'])
    corners=json.loads((P/'cpu-corner-coupon/drc.json').read_text())
    assert len(corners['violations'])==5 and all(v['type']=='via_dangling' for v in corners['violations'])
    run([PCB,T/'build_cpu_ddr_simultaneous_coupon.py'])
    run([CLI,'pcb','drc','--format','json','-o',P/'cpu-simultaneous-coupon/drc.json',P/'cpu-simultaneous-coupon/cpu-simultaneous.kicad_pcb'])
    run([PCB,T/'audit_cpu_ddr_simultaneous_coupon.py'])
    simultaneous=json.loads((P/'cpu-simultaneous-coupon/audit.json').read_text())
    run([PCB,T/'integrate_cpu_ddr_escape_experiment.py'])
    run([CLI,'pcb','drc','--format','json','-o',P/'cpu-board-integration/drc.json',P/'cpu-board-integration/candidate.kicad_pcb'])
    run([sys.executable,T/'report_cpu_ddr_interference.py'])
    run([sys.executable,T/'rebuild_wifi_relocation.py'])
    assert hashlib.sha256(mainpcb.read_bytes()).hexdigest()==before
    result={'status':'ENGINEERING_CHECKPOINT_NOT_RELEASE','main_ddr3_pcb_unchanged_sha256':before,'candidate_board_sha256':hashlib.sha256(board.read_bytes()).hexdigest(),'source_part':'H9HCNNN8KUMLHR-NME','RAM_MiB':1024,'end_to_end_schematic_signals':65,'RAM_signal_escape_vias':65,'CPU_corner_coupon_signals':5,'CPU_corner_coupon_geometric_drc':'PASS; 5 intentional dangling vias','CPU_simultaneous_coupon_verified_signals':simultaneous['connected_escape_count'],'CPU_full_board_integration':'60 escapes integrated after Wi-Fi relocation; see working-board.json and preservation audit','CPU_routing_complete':False,'assembly_ready':False,'holds':['CPU and complete DDR routing; five CPU signals need finer local geometry in tested searches','Land/stencil and fabrication profile qualification','Power/ground DDR escape and return planes','Controlled impedance, length/skew and timing','PMIC load/thermal/startup/shutdown validation','Display footprint and overall board completion','DDR firmware training and physical prototype tests'],'purchases':False}
    manifest.write_text(json.dumps(result,indent=2)+'\n');print('Checkpoint saved; unfinished design holds remain explicit.')
if __name__=='__main__':main()
