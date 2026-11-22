"""Small deterministic KiCad writer for draft circuit sheets.
Pin contracts are exported for independent checking of the generated netlist.
No power flags or ERC exclusions are inserted to hide missing circuitry.
"""
import copy,json,math,uuid
from pathlib import Path
import sexpdata as sx
from audit_rk3568 import fields,walk
ROOT=Path(__file__).resolve().parents[1]
STANDARD=Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols')
def q(x):return json.dumps(str(x))
class Sheet:
 def __init__(self,name,title,library,symbols):
  self.name=name;self.title=title;self.library=library;self.symbols=symbols;self.items=[];self.contract=[];self.used=set();self.root=self.uid('root')
 def uid(self,s):return str(uuid.uuid5(uuid.NAMESPACE_URL,'phoenix-g1/'+self.name+'/'+s))
 def place(self,name,ref,x,y,nets,value=None,fp=None,mpn=None,unit=1):
  symbol=self.symbols[name];self.used.add(name);pins=[p for sub in fields(symbol,'symbol') if str(sub[1]).endswith(f'_{unit}_1') or str(sub[1]).endswith(('_0_1','_0_0')) for p in walk(sub,'pin')]
  assert {str(fields(p,'number')[0][1]) for p in pins}==set(nets),ref
  props={p[1]:p[2] for p in fields(symbol,'property')};footprint=fp if fp is not None else props.get('Footprint','')
  top=max(fields(p,'at')[0][2] for p in pins)
  body=f'(symbol (lib_id {q(self.library+":"+name)}) (at {x} {y} 0) (unit {unit}) (in_bom yes) (on_board yes) (dnp no) (uuid {q(self.uid(ref+str(unit)))})'
  xx=x+12 if name in ('R','C','L') else x
  for k,v,yy,hide in [('Reference',ref,y-top-8,False),('Value',value or name,y-top-5.5,False),('Footprint',footprint,y,True),('MPN',mpn or 'UNQUALIFIED',y,True)]:
   body+=f'(property {q(k)} {q(v)} (at {xx} {yy} 0) (effects (font (size 1 1))'+(' hide' if hide else '')+'))'
  body+=f'(instances (project {q(self.name)} (path {q("/"+self.root)} (reference {q(ref)}) (unit {unit})))))';self.items.append(body)
  for pin in pins:
   num=str(fields(pin,'number')[0][1]);net=nets[num];px,py,angle=fields(pin,'at')[0][1:];px=round(x+px,4);py=round(y-py,4)
   self.contract.append({'ref':ref,'pin':num,'pin_name':fields(pin,'name')[0][1],'net':net})
   if net is None:
    self.items.append(f'(no_connect (at {px} {py}) (uuid {q(self.uid(ref+num+"nc"))}))');continue
   ex=round(px-5.08*math.cos(math.radians(angle)),4);ey=round(py+5.08*math.sin(math.radians(angle)),4)
   self.items.append(f'(wire (pts (xy {px} {py}) (xy {ex} {ey})) (stroke (width 0) (type default)) (uuid {q(self.uid(ref+num+"wire"))}))')
   a=90 if angle in (90,270) else 0;j='right' if angle in (0,90) else 'left'
   self.items.append(f'(label {q(net)} (at {ex} {ey} {a}) (effects (font (size 1 1)) (justify {j} bottom)) (uuid {q(self.uid(ref+num+"label"))}))')
 def note(self,text,x,y):
  self.items.append(f'(text {q(text)} (at {x} {y} 0) (effects (font (size 1.1 1.1)) (justify left)) (uuid {q(self.uid("note"+str(len(self.items))))}))')
 def save(self):
  embedded=[]
  for name in sorted(self.used):
   s=copy.deepcopy(self.symbols[name]);s[1]=self.library+':'+name;embedded.append(sx.dumps(s))
  sch=f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {q(self.root)}) (paper "A3") (title_block (title {q(self.title)}) (rev "DRAFT") (comment 1 "Not for fabrication")) (lib_symbols '+''.join(embedded)+')'+''.join(self.items)+')\n'
  (ROOT/f'kicad/{self.name}.kicad_sch').write_text(sch)
  (ROOT/f'kicad/{self.name}.kicad_pro').write_text(json.dumps({'meta':{'filename':self.name+'.kicad_pro','version':1}},indent=2)+'\n')
  (ROOT/f'review/{self.name}-expected.json').write_text(json.dumps(self.contract,indent=2)+'\n')
  print(self.name,len(self.contract),'pin dispositions')
def load_symbols(candidate_names,standard_names):
 lib=sx.loads((ROOT/'kicad/Phoenix_Candidates.kicad_sym').read_text());std=sx.loads((STANDARD/'Device.kicad_sym').read_text())
 result={n[1]:copy.deepcopy(n) for n in fields(lib,'symbol') if n[1] in candidate_names}
 result.update({n[1]:copy.deepcopy(n) for n in fields(std,'symbol') if n[1] in standard_names})
 for s in result.values():
  for p in fields(s,'property'):p[:]=[v for v in p if not(isinstance(v,list) and v and str(v[0])=='id')]
 return result

def save_library(name,symbols):
 (ROOT/f'kicad/{name}.kicad_sym').write_text('(kicad_symbol_lib (version 20250114) (generator "kicad_symbol_editor")'+''.join(sx.dumps(s) for s in symbols.values())+')\n')
 p=ROOT/'kicad/sym-lib-table';t=p.read_text()
 if f'(name "{name}")' not in t:p.write_text(t.rstrip()[:-1]+f' (lib (name "{name}")(type "KiCad")(uri "${{KIPRJMOD}}/{name}.kicad_sym")(options "")(descr "Circuit draft"))\n)\n')
