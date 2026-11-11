# Experimental fine-pitch escape: retains a known width DRC error.
import pcbnew as p, json, hashlib, argparse
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();assert a.input.resolve()!=a.output.resolve();src=a.input;b=p.LoadBoard(str(src));n=b.FindNet('+3V3_IO').GetNetCode()
def pt(x,y):return p.VECTOR2I(p.FromMM(x),p.FromMM(y))
t=p.PCB_TRACK(b);t.SetStart(pt(61.75,5.59));t.SetEnd(pt(61.75,4.65));t.SetWidth(p.FromMM(.127));t.SetLayer(p.F_Cu);t.SetNetCode(n);b.Add(t)
v=p.PCB_VIA(b);v.SetPosition(pt(61.75,4.65));v.SetWidth(p.FromMM(.6));v.SetDrill(p.FromMM(.3));v.SetViaType(p.VIATYPE_THROUGH);v.SetLayerPair(p.F_Cu,p.B_Cu);v.SetNetCode(n);b.Add(v)
p.ZONE_FILLER(b).Fill(b.Zones());p.SaveBoard(str(a.output),b)
