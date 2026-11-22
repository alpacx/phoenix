"""HanRun HR911130A Rev A, drawing page 2, component-side mounting pattern."""
from pathlib import Path
import re

even_centers = {'P2':4.44,'P4':1.90,'P6':-.64,'P8':-3.18,'P10':-5.72}
filename='RJ45-TH_HR911130A.kicad_mod'

def apply(path: Path):
    text=path.read_text()
    for name,target in even_centers.items():
        pattern=r'(\(pad "?'+name+r'"?\s+thru_hole\s+\w+\s+\(at\s+)(-?[\d.]+)(\s+4\.35\b)'
        match=re.search(pattern,text)
        assert match and round(float(match[2])-target,2) in (0,.11),(name,target,path)
        text=re.sub(pattern,lambda match:match[1]+str(target)+match[3],text,count=1)
    path.write_text(text)
