#!/usr/bin/env python3
"""Reuse support circuits in an explicitly incomplete migration hierarchy."""
from pathlib import Path
import json,shutil,hashlib
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'migration-rk3562'
overlays=list((OUT/'overrides/footprints').glob('*.pretty/*.kicad_mod'))
if overlays:
 repairs={a['library_id']:a for a in json.loads((OUT/'review/courtyard-library-repair.json').read_text())['libraries']}
 for overlay in overlays:
  key=overlay.parent.stem+':'+overlay.stem;record=repairs[key]
  original=ROOT/'kicad'/overlay.parent.name/overlay.name
  assert hashlib.sha256(original.read_bytes()).hexdigest()==record['original_before_any_repair_sha256'], 'Shared footprint changed; review envelope override: '+key
  assert hashlib.sha256(overlay.read_bytes()).hexdigest()==record['after_sha256'], 'Envelope override differs from audit: '+key
(OUT/'sourcing').mkdir(exist_ok=True)
# Shared library definitions/footprints are copied; legacy SoC sheets are excluded.
for p in (ROOT/'kicad').iterdir():
 if p.name=='integrated' or p.name=='floorplan':continue
 if p.is_dir() and p.suffix=='.pretty':shutil.copytree(p,OUT/'kicad'/p.name,dirs_exist_ok=True)
 elif p.is_file() and (p.suffix=='.kicad_sym' or p.name in ['sym-lib-table','fp-lib-table']):
  if p.name=='sym-lib-table':
   t=p.read_text().rstrip();t=t[:-1]+' (lib (name "Phoenix_RK3562")(type "KiCad")(uri "${KIPRJMOD}/Phoenix_RK3562.kicad_sym")(options "")(descr "Incomplete RK3562 migration"))\n)\n';(OUT/'kicad'/p.name).write_text(t)
  else:shutil.copy2(p,OUT/'kicad'/p.name)
# Preserve reviewed RK3562-only assembly envelopes when refreshing shared libraries.
for override in overlays:
 target=OUT/'kicad'/override.parent.name/override.name
 target.parent.mkdir(parents=True,exist_ok=True)
 shutil.copy2(override,target)
# Candidate library remains explicitly separate from qualified footprints.
fp_table=OUT/'kicad/fp-lib-table'
t=fp_table.read_text().rstrip()
if 'Phoenix_RK3562_Candidates' not in t:
 t=t[:-1]+' (lib (name "Phoenix_RK3562_Candidates")(type "KiCad")(uri "${KIPRJMOD}/Phoenix_RK3562_Candidates.pretty")(options "")(descr "UNQUALIFIED RK3562 package candidate"))\n)\n'
 fp_table.write_text(t)
reused=[]
for p in (ROOT/'review').glob('*-expected.json'):
 name=p.name.removesuffix('-expected.json')
 if name.startswith('soc-') and name[4:6].isdigit() or name=='power-source-model':continue
 sch=ROOT/'kicad'/(name+'.kicad_sch')
 if sch.exists():shutil.copy2(p,OUT/'review'/p.name);shutil.copy2(sch,OUT/'kicad'/sch.name);reused.append(name)
# Regenerate only flash support with RK3562-specific strap handling.
import schematic_builder as sb, build_core_support as core
sb.ROOT=OUT;core.ROOT=OUT;core.main(target='RK3562',flash_only=True)
import build_cpu_power as cpu
cpu.ROOT=OUT;cpu.main(target='RK3562')
# Source annotations must identify the new chip, not inherit RK3568 from the baseline BOM.
sel=json.loads((ROOT/'sourcing/selected-references.json').read_text());sel.pop('C2938930');sel['C29779896']='U1'
removed_code=None
for code,refs in list(sel.items()):
 tokens=refs.replace(',', ' ').split()
 if 'R1405' in tokens:
  removed_code=code;tokens.remove('R1405')
  if tokens:sel[code]=' '.join(tokens)
  else:del sel[code]
(OUT/'sourcing/selected-references.json').write_text(json.dumps(sel,indent=2)+'\n')
v=json.loads((ROOT/'sourcing/selected-main-parts.json').read_text());v['parts']=[p for p in v['parts'] if p['jlc']!='C2938930'];d=json.loads((ROOT/'sourcing/public/C29779896.json').read_text());v['parts'].append({'jlc':'C29779896','qty':1,'mpn':'RK3562','unit_usd':d['initialPrice'],'extended_usd':d['initialPrice'],'source':d['source_url']});v['parts']=[dict(p,qty=len(sel[p['jlc']].split()),extended_usd=round(p['unit_usd']*len(sel[p['jlc']].split()),4)) for p in v['parts'] if p['jlc'] in sel];v['subtotal']=round(sum(p['extended_usd'] for p in v['parts']),4);v['status']='MIGRATION CANDIDATES; SUPPORT CIRCUITS NOT REQUALIFIED';(OUT/'sourcing/selected-main-parts.json').write_text(json.dumps(v,indent=2)+'\n')
shutil.copy2(ROOT/'review/footprint-overrides.json',OUT/'review/footprint-overrides.json')
(OUT/'review/reuse-review.json').write_text(json.dumps({'status':'INTEGRATION DRAFT; NOT ELECTRICALLY APPROVED','reused_sheets':reused,'excluded':'Old SoC and old artificial power-source model','removed_legacy_components':['R1405 FLASH_VOL_SEL; no equivalent RK3562 strap inferred'],'cost_note':'Quantities follow migrated reference inventory; prices are catalog snapshots, not an assembly quote.','mandatory_review':['All original RK3568-specific notes, pin functions and firmware labels','PMIC variant, defaults, sequence and analog supplies','DDR reference, calibration and clock circuits','Expansion IO bank voltages and pullup supply','Boot flash voltage strap: no corresponding RK3562 strap assumed','Decoupling must be redesigned for new ball map','Thermal shutdown polarity and reset thresholds']},indent=2)+'\n')
print(len(reused),'support sheets copied for review')
