#!/usr/bin/env python3
"""Independent read-only Samsung ball/SoC mapping audit; output stays in this dossier."""
import json,hashlib,xml.etree.ElementTree as ET
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
netfile=HERE/'sources/current-integrated.xml'
r=ET.parse(netfile).getroot()
nets={n.attrib['name']:{(x.attrib['ref'],x.attrib['pin']) for x in n} for n in r.find('nets')}
actual={k:name for name, nodes in nets.items() for k in nodes}
components={c.attrib['ref']:c.findtext('value') for c in r.find('components')}
# Independently transcribed from Samsung rev1.21 Table2 (page5).
groups={'EMMC_D0':'A3','EMMC_D1':'A4','EMMC_D2':'A5','EMMC_D3':'B2','EMMC_D4':'B3','EMMC_D5':'B4','EMMC_D6':'B5','EMMC_D7':'B6','EMMC_RESET_N':'K5','EMMC_CMD':'M5','EMMC_CLK':'M6','EMMC_STRB':'H5','EMMC_VDDI':'C2','EMMC_IO_1V8':'C6 M4 N4 P3 P5','EMMC_3V3':'E6 F5 J10 K9','GND':'J5 A6 C4 E7 G5 H10 K8 N2 N5 P4 P6'}
rows=[]
for net,bs in groups.items():
 for b in bs.split():rows.append({'component':'U8001','ball':b,'expected_net':net,'actual_net':actual.get(('U8001',b)),'pass':actual.get(('U8001',b))==net,'evidence':'Samsungrev1.21Table2page5'})
# Independently transcribed from RK3562 rev2.1 pin table.
soc={'EMMC_D0':'J25','EMMC_D1':'J26','EMMC_D2':'H25','EMMC_D3':'K27','EMMC_D4':'K26','EMMC_D5':'K25','EMMC_D6':'H26','EMMC_D7':'H27','EMMC_STRB':'L26','EMMC_CMD':'M26','SOC_EMMC_CLK':'M25','EMMC_IO_1V8':'1F14'}
for net,b in soc.items():rows.append({'component':'U1','ball':b,'expected_net':net,'actual_net':actual.get(('U1',b)),'pass':actual.get(('U1',b))==net,'evidence':'RK3562rev2.1pintable'})
rfu='A7 E5 E8 E9 E10 F10 G3 G10 K6 K7 K10 P7 P10'.split()
rfu_rows=[{'ball':b,'pass':actual.get(('U8001',b),'').startswith('unconnected-'),'actual_net':actual.get(('U8001',b))} for b in rfu]
report={'status':'PIN_MAPPING_PASS_NOT_BOOT_QUALIFIED','netlist_sha256':hashlib.sha256(netfile.read_bytes()).hexdigest(),'pins':rows,'rfu':rfu_rows,'all_pin_mapping_pass':all(x['pass'] for x in rows),'support_values':{k:v for k,v in components.items() if k.startswith(('R800','C800','C801'))},'reset_nodes':sorted(nets['EMMC_RESET_N']),'VDDI_nodes':sorted(nets['EMMC_VDDI']),'flash_present':components.get('U8001'),'physical_boot_test':False}
assert report['all_pin_mapping_pass']
assert nets['EMMC_VDDI']=={('U8001','C2'),('C8001','1')}
assert all(x['pass'] for x in rfu_rows)
(HERE/'pin-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(f"PASS {len(rows)} mapped balls, {len(rfu_rows)} RFU isolated; reset has{len(nets['EMMC_RESET_N'])}nodes; notbootqualified")
