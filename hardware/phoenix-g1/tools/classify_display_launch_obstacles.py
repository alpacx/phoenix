"""Associate legal land-field paths with actual signal and drill obstacles on all six layers."""
from pathlib import Path
from collections import Counter
import hashlib,json,os,sys
import pcbnew as p
from pcb_bounds import inflated_box
root=Path(__file__).resolve().parents[1]/'migration-rk3562/experiments/phy-power-parallel'
reset_ctrl='--reset-controls' in sys.argv
u3_first='--u3-first' in sys.argv
keep_u3='--keep-u3' in sys.argv or u3_first
ground_vias='--ground-via-relief' in sys.argv
base=json.loads((root/('layout-lcd-select-trunk.json' if reset_ctrl else 'display-mosi-u3-first.json' if u3_first else 'layout-lcd-select-trunk.json' if ground_vias else 'layout-lcd-clock-trunk.json')).read_text());base=base['candidate'] if u3_first else base;src=root/base['board'];assert hashlib.sha256(src.read_bytes()).hexdigest()==base['sha256']
b=p.LoadBoard(str(src));layers=(p.F_Cu,p.In1_Cu,p.In2_Cu,p.In3_Cu,p.In4_Cu,p.B_Cu);out={};v=lambda xy:p.VECTOR2I(*xy)
for net in (('LCD_RESET_N',) if reset_ctrl else ('LCD_MOSI',) if ground_vias else ('LCD_MOSI','LCD_RESET_N','LCD_CS_N')):
    env=json.loads((root/('lcd-reset-control-window.json' if reset_ctrl else net.lower()+('-u3-first-window.json' if u3_first else '-preserve-u3.json' if keep_u3 else '-ground-via-relief.json' if ground_vias else '-fixed-pad-envelope.json'))).read_text());assert env['parent_sha256']==base['sha256']
    q=next(q for q in b.FindFootprintByReference('U1').Pads() if q.GetNetname()==net)
    obstacles=[o for o in b.GetTracks() if o.GetNetCode()!=q.GetNetCode() and inflated_box(o,2600000).Contains(q.GetPosition())]
    shapes=[(o,l,o.GetEffectiveShape(l),78200 if o.GetNetname().startswith('LPDDR4_') else 202000) for o in obstacles for l in layers if o.IsOnLayer(l)]
    vias=[(o,o.GetEffectiveHoleShape()) for o in obstacles if isinstance(o,p.PCB_VIA)]
    t=p.PCB_TRACK(b);t.SetWidth(200000);t.SetLayer(p.F_Cu);barrel=p.PCB_VIA(b);barrel.SetLayerPair(p.F_Cu,p.B_Cu);barrel.SetViaType(p.VIATYPE_THROUGH);barrel.SetWidth(450000);barrel.SetDrill(200000)
    cases=[]
    for rec in env['sites']:
        path=rec['path_nm'];at=path[-1];barrel.SetPosition(v(at));land=barrel.GetEffectiveShape(p.F_Cu);hole=barrel.GetEffectiveHoleShape();blocks={}
        def add(o,reason):
            u=o.m_Uuid.AsString();c=blocks.setdefault(u,dict(net=o.GetNetname(),kind=o.GetClass(),layer=o.GetLayerName(),violates=set(),uuid=u))
            c['violates'].add(reason)
        for o,l,s,c in shapes:
            if land.Collide(s,c):add(o,'via land')
            if hole.Collide(s,252000):add(o,'hole')
        for o,h in vias:
            if h.Collide(hole,252000) or h.Collide(land,252000):add(o,'existing drill')
        for a,z in zip(path,path[1:]):
            t.SetStart(v(a));t.SetEnd(v(z));sh=t.GetEffectiveShape(p.F_Cu)
            for o,l,s,c in shapes:
                if l==p.F_Cu and sh.Collide(s,c):add(o,'signal neck')
            for o,h in vias:
                if sh.Collide(h,252000):add(o,'signal/drill')
        for c in blocks.values():c['violates']=sorted(c['violates'])
        cases.append(dict(via_nm=at,signal_path_nm=path,blockers=sorted(blocks.values(),key=lambda r:r['uuid']),nets=sorted({c['net'] for c in blocks.values()})))
    out[net]=sorted(cases,key=lambda r:(len(r['nets']),len(r['blockers'])))
(root/('lcd-reset-control-obstacles.json' if reset_ctrl else 'lcd-mosi-u3-first-obstacles.json' if u3_first else 'lcd-mosi-u3-preserved-obstacles.json' if keep_u3 else 'lcd-mosi-ground-obstacles.json' if ground_vias else 'lcd-soc-rework-obstacles.json')).write_text(json.dumps(dict(source_sha256=base['sha256'],lines=out,assembly_ready=False),indent=2)+'\n');print([(n,r[0]['nets'],len(r[0]['blockers'])) for n,r in out.items() if r],flush=True);os._exit(0)
