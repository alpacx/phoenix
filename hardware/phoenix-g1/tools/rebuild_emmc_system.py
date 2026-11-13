#!/usr/bin/env python3
"""Rebuild and validate isolated/integrated eMMC candidates; no PCB mutation."""
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];TOOLS=Path(__file__).resolve().parent
CLI='/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli'
PCB='/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3'
# Run using the sexpdata-capable project environment.
def run(*args):subprocess.run([str(a) for a in args],cwd=ROOT,check=True)
run(sys.executable,TOOLS/'build_rk3562_emmc_candidate.py')
run(sys.executable,TOOLS/'integrate_emmc_system.py')
E=TOOLS.parent/'migration-rk3562/experiments'
for name,sch,net,erc in [('emmc-8gb','kicad/emmc-storage-candidate.kicad_sch','netlist.xml','erc.json'),('emmc-system/system','kicad/integrated/phoenix-g1.kicad_sch','integrated.xml','integrated-erc.json')]:
 d=E/name
 run(CLI,'sch','export','netlist','--format','kicadxml','-o',d/'review'/net,d/sch)
 run(CLI,'sch','erc','--format','json','-o',d/'review'/erc,d/sch)
run(CLI,'sch','export','netlist','--format','kicadxml','-o',E/'emmc-system/system/review/source-stacked.xml',E/'stacked-expansion/system/kicad/integrated/phoenix-g1.kicad_sch')
run(PCB,TOOLS/'audit_rk3562_emmc_candidate.py')
run(sys.executable,TOOLS/'audit_emmc_system.py')
