#!/usr/bin/env python3
"""Build an isolated whole-system LPDDR4 candidate without overwriting DDR3 work."""
import csv,json,shutil,uuid,math
from pathlib import Path
import sexpdata as sx
from audit_rk3568 import fields,walk
import integrate_schematic as integration
import schematic_builder as sb
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'migration-rk3562'
RAM=BASE/'experiments/lpddr4-1gb';OUT=RAM/'system'
def remap_tree(node,mapping):
    if not isinstance(node,list):return
    # Only electrical labels and pin names; do not alter component values accidentally.
    if node and str(node[0]) in ('label','global_label','name') and len(node)>1 and isinstance(node[1],str) and node[1] in mapping:node[1]=mapping[node[1]]
    for child in node:remap_tree(child,mapping)
def change_pin_net(tree,ref,num,net):
    inst=next(s for s in fields(tree,'symbol') if any(p[1]=='Reference' and p[2]==ref for p in fields(s,'property')))
    libid=fields(inst,'lib_id')[0][1];unit=fields(inst,'unit')[0][1]
    lib=next(s for group in fields(tree,'lib_symbols') for s in fields(group,'symbol') if s[1]==libid)
    pin=next(p for sub in fields(lib,'symbol') if str(sub[1]).endswith((f'_{unit}_1','_0_1','_0_0')) for p in walk(sub,'pin') if str(fields(p,'number')[0][1])==num)
    ix,iy=fields(inst,'at')[0][1:3];px,py,a=fields(pin,'at')[0][1:]
    x=round(ix+px,4);y=round(iy-py,4)
    ex=round(x-5.08*math.cos(math.radians(a)),4);ey=round(y+5.08*math.sin(math.radians(a)),4)
    labels=[l for l in fields(tree,'label') if fields(l,'at')[0][1:3]==[ex,ey]]
    if net is None:
        for label in labels:tree.remove(label)
        for wire in list(fields(tree,'wire')):
            pts=fields(wire,'pts')[0]
            if any(xy[1:]==[x,y] for xy in fields(pts,'xy')):tree.remove(wire)
        if not any(fields(n,'at')[0][1:]==[x,y] for n in fields(tree,'no_connect')):
            uid=str(uuid.uuid5(uuid.NAMESPACE_URL,'phoenix-lp4-nc/'+ref+'/'+num))
            tree.append(sx.loads(f'(no_connect (at {x} {y}) (uuid "{uid}"))'))
    else:
        assert len(labels)==1,(ref,num)
        labels[0][1]=net

def main():
    for folder in ['kicad','review','sourcing']:(OUT/folder).mkdir(parents=True,exist_ok=True)
    for old in (OUT/'review').glob('*-expected.json'):old.unlink()
    for f in (BASE/'kicad').iterdir():
        if f.is_dir() and f.suffix=='.pretty':shutil.copytree(f,OUT/'kicad'/f.name,dirs_exist_ok=True)
        elif f.is_file() and (f.suffix=='.kicad_sym' or f.name in ['sym-lib-table','fp-lib-table']):shutil.copy2(f,OUT/'kicad'/f.name)
    changes={};required=list(csv.DictReader((RAM/'signal-map.csv').open()));new_by_ball={r['soc_ball']:r['signal'] for r in required if 'ODT0_CA' not in r['signal']}
    unused_memory={'1B6','1B10','1B7','B12','B16','C17','B9','B19','1C9','C11'}
    leftovers=[];used=set()
    for src in sorted((BASE/'review').glob('*-expected.json')):
        name=src.name.removesuffix('-expected.json');sch=BASE/'kicad'/(name+'.kicad_sch')
        if not sch.exists() or name=='ddr3-memory':continue
        rows=json.loads(src.read_text());rename={'+1V5_DDR':'+1V1_LPDDR4','PENDING_1D4':'DDR_RZQ'};activate={}
        if name.startswith('rk3562-pins-'):
            for r in rows:
                old=r['net'];ball=r['pin']
                if ball in new_by_ball:
                    if old is None:activate[ball]=new_by_ball[ball]
                    else:rename[old]=new_by_ball[ball]
                    changes[ball]={'old':old,'new':new_by_ball[ball]}
                elif ball in unused_memory:pass
                elif old and old.startswith('DDR3_'):
                    rename[old]='PENDING_LPDDR4_'+ball;leftovers.append({'ball':ball,'old':old,'new':rename[old]})
        tree=sx.loads(sch.read_text());remap_tree(tree,rename)
        for ball,net in activate.items():
            inst=next(s for s in fields(tree,'symbol') if any(p[1]=='Reference' and p[2]=='U1' for p in fields(s,'property')))
            unit=fields(inst,'unit')[0][1];ix,iy=fields(inst,'at')[0][1:3]
            sub=next(s for lib in fields(tree,'lib_symbols') for sym in fields(lib,'symbol') for s in fields(sym,'symbol') if str(s[1]).endswith(f'_{unit}_1'))
            pin=next(p for p in walk(sub,'pin') if str(fields(p,'number')[0][1])==ball)
            fields(pin,'name')[0][1]=net;pin[1]=sx.Symbol('output')
            px,py,a=fields(pin,'at')[0][1:];x=round(ix+px,4);y=round(iy-py,4)
            nc=next(n for n in fields(tree,'no_connect') if fields(n,'at')[0][1:]==[x,y]);tree.remove(nc)
            ex=round(x-5.08*math.cos(math.radians(a)),4);ey=y
            uid=lambda key:str(uuid.uuid5(uuid.NAMESPACE_URL,'phoenix-lp4/'+ball+key))
            tree.append(sx.loads(f'(wire (pts (xy {x} {y}) (xy {ex} {ey})) (stroke (width 0) (type default)) (uuid "{uid("wire")}"))'))
            justify='right' if a==0 else 'left'
            tree.append(sx.loads(f'(label "{net}" (at {ex} {ey} 0) (effects (font (size 1 1)) (justify {justify} bottom)) (uuid "{uid("label")}"))'))
        for r in rows:
            r['net']=activate.get(r['pin'],rename.get(r['net'],r['net']));used.add(r['ref'])
            if r['pin_name'] in rename:r['pin_name']=rename[r['pin_name']]
        if name.startswith('rk3562-pins-'):
            for r in rows:
                if r['pin'] in unused_memory:
                    change_pin_net(tree,'U1',r['pin'],None);r['net']=None
        if name=='core-boot-support':
            change_pin_net(tree,'R1503','2','+1V1_LPDDR4')
            for r in rows:
                if r['ref']=='R1503' and r['pin']=='2':r['net']='+1V1_LPDDR4'
        if name=='pmic-bucks':
            for symbol in fields(tree,'symbol'):
                props={p[1]:p for p in fields(symbol,'property')};ref=props['Reference'][2]
                if ref in ['R431','R432']:
                    props['Value'][2]={'R431':'45.3k 0.1%','R432':'121k 0.1%'}[ref]
                    if 'MPN' in props:props['MPN'][2]={'R431':'RT0603BRD0745K3L','R432':'RT0603BRD07121KL'}[ref]
        (OUT/'kicad'/sch.name).write_text(sx.dumps(tree)+'\n');(OUT/'review'/src.name).write_text(json.dumps(rows,indent=2)+'\n')
    assert len(changes)==65
    name='lpddr4-memory-candidate';tree=sx.loads((RAM/'kicad'/(name+'.kicad_sch')).read_text());remap_tree(tree,{'+1V8_LPDDR4':'+1V8_SYS','LPDDR4_ODT0_CA_A':'+1V1_LPDDR4','LPDDR4_ODT0_CA_B':'+1V1_LPDDR4'})
    (OUT/'kicad'/(name+'.kicad_sch')).write_text(sx.dumps(tree)+'\n')
    rows=json.loads((RAM/'review'/(name+'-expected.json')).read_text())
    for r in rows:
        if r['net']=='+1V8_LPDDR4':r['net']='+1V8_SYS'
        if r['net'] in ['LPDDR4_ODT0_CA_A','LPDDR4_ODT0_CA_B']:r['net']='+1V1_LPDDR4'
        used.add(r['ref'])
    (OUT/'review'/(name+'-expected.json')).write_text(json.dumps(rows,indent=2)+'\n')
    shutil.copy2(RAM/'kicad/Phoenix_LPDDR4.kicad_sym',OUT/'kicad/Phoenix_LPDDR4.kicad_sym')
    shutil.copytree(RAM/'Phoenix_LPDDR4_Draft.pretty',OUT/'kicad/Phoenix_LPDDR4_Draft.pretty',dirs_exist_ok=True)
    for table,lib,typ,suffix in [('sym-lib-table','Phoenix_LPDDR4','KiCad','.kicad_sym'),('fp-lib-table','Phoenix_LPDDR4_Draft','KiCad','.pretty')]:
        p=OUT/'kicad'/table;t=p.read_text().rstrip();p.write_text(t[:-1]+f'(lib (name "{lib}") (type "{typ}") (uri "${{KIPRJMOD}}/{lib}{suffix}") (options "") (descr "LPDDR4 candidate")))\n')
    # VDD1 bypass topology from RK3562 LPDDR4 reference sheet13; placement/derating pending.
    sb.ROOT=ROOT
    caps=sb.load_symbols([],['C']);sb.ROOT=OUT
    bypass=sb.Sheet('lpddr4-vdd1-bypass','Phoenix LPDDR4 VDD1 bypass candidate','Phoenix_LPDDR4_Bypass',caps)
    for i in range(8):
        ref='C'+str(2301+i);bulk=i in (0,4)
        bypass.place('C',ref,50.8+(i%4)*88.9,63.5+(i//4)*76.2,{'1':'+1V8_SYS','2':'GND'},value='10u' if bulk else '100n',fp='Phoenix_Passives:C_0805_2012Metric' if bulk else 'Phoenix_Passives:C_0402_1005Metric',mpn='CL21A106KAYNNNE' if bulk else 'CL05B104KO5NNNC')
        used.add(ref)
    bypass.note('Candidate VDD1 bypass: 2 x 10u + 6 x 100n. Split between the two package sides.',20,220)
    bypass.note('Existing stocked packages reused; effective capacitance, PDN and placement not qualified.',20,228)
    bypass.save()
    sb.save_library('Phoenix_LPDDR4_Bypass',caps)
    sel=json.loads((BASE/'sourcing/selected-references.json').read_text())
    # Avoid stale Hynix DDR3 and divider MPNs overwriting the new sheet properties.
    for code in list(sel):
        refs=[r for r in sel[code].split() if r in used and r not in ['U2','U3','R431','R432']]
        if refs:sel[code]=' '.join(refs)
        else:del sel[code]
    sel['C1525']+=' C2302 C2303 C2304 C2306 C2307 C2308'
    sel['C15850']+=' C2301 C2305'
    sel['C2912103']='U2';parts=json.loads((BASE/'sourcing/selected-main-parts.json').read_text())
    parts['parts']=[p for p in parts['parts'] if p['jlc'] in sel]
    parts['parts'].append({'jlc':'C2912103','mpn':'H9HCNNN8KUMLHR-NME','qty':1,'unit_usd':26.5722,'extended_usd':26.5722,'source':'2026-11-10 saved stock snapshot'})
    observations=[]
    for filename in ['stock-refresh.json','divider-stock-refresh.json','divider-alternate-stock.json']:observations+=json.loads((RAM/filename).read_text())
    fresh={r['jlc']:r for r in observations}
    for code,ref in [('C861415','R431'),('C861095','R432')]:
        r=fresh[code];assert r['available_order_qty']>0
        sel[code]=ref;parts['parts'].append({'jlc':code,'mpn':r['mpn'],'qty':1,'unit_usd':r['unit_usd_1plus'],'extended_usd':r['unit_usd_1plus'],'source':r['source']})
    for p in parts['parts']:
        if p['jlc'] in fresh:p['unit_usd']=fresh[p['jlc']]['unit_usd_1plus'];p['source']=fresh[p['jlc']]['source']
        p['qty']=len(sel[p['jlc']].split());p['extended_usd']=round(p['qty']*p['unit_usd'],4)
    parts['subtotal']=round(sum(p['extended_usd'] for p in parts['parts']),4);parts['status']='CANDIDATE COST: selected divider and VDD1 bypass included; assembly/PDN not qualified'
    (OUT/'sourcing/selected-references.json').write_text(json.dumps(sel,indent=2)+'\n');(OUT/'sourcing/selected-main-parts.json').write_text(json.dumps(parts,indent=2)+'\n')
    shutil.copy2(BASE/'review/footprint-overrides.json',OUT/'review/footprint-overrides.json')
    integration.ROOT=OUT;integration.main()
    report={'status':'INTEGRATED_CANDIDATE_NOT_RELEASED','changed_soc_signals':changes,'remaining_memory_pin_review':leftovers,'removed_memory_package':'U3','new_ram':'U2 H9HCNNN8KUMLHR-NME','DDR_rail':'+1V1_LPDDR4','VDD1_rail':'+1V8_SYS','holds':['Requalify existing DDR bypass bank and new VDD1 bypass placement/derating','PMIC load budgets, transients and sequencing','Boot firmware training and exact chip support','PCB migration and SI'], 'main_board_modified':False,'unused_memory_nc':sorted(unused_memory),'ODT_strategy':'G2/T2 tied VDD2; mode-register termination control; RK3562 reference sheet13 and Hynix MR22'}
    (OUT/'review/migration.json').write_text(json.dumps(report,indent=2)+'\n')
    print('65 SoC signals migrated; remaining memory pin review:',len(leftovers))
if __name__=='__main__':main()
