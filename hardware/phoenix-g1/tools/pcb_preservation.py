"""Preserve original copper and physical pad groups, including duplicate pad numbers."""
import pcbnew as p

def verify_preservation(source, derived, removed_refs=(), changed_nets=None, replaced_copper=()):
    removed_refs=set(removed_refs);changed_nets=changed_nets or {}
    original={q.m_Uuid.AsString():(f.GetReference(),q.GetNumber(),q) for f in source.GetFootprints() if f.GetReference() not in removed_refs for q in f.Pads()}
    current={q.m_Uuid.AsString():(f.GetReference(),q.GetNumber(),q) for f in derived.GetFootprints() for q in f.Pads()}
    for uid,(ref,num,pad) in original.items():
        assert uid in current,('Original pad removed',ref,num,uid)
        assert current[uid][2].GetNetname()==changed_nets.get((ref,num),pad.GetNetname()),('Original pad net changed',ref,num)
    def tracks(board):
        return {t.m_Uuid.AsString():(t.GetNetname(),t.GetLayer(),t.GetStart().x,t.GetStart().y,t.GetEnd().x,t.GetEnd().y,t.GetWidth(p.F_Cu) if isinstance(t,p.PCB_VIA) else t.GetWidth(),t.GetDrillValue() if isinstance(t,p.PCB_VIA) else None) for t in board.GetTracks()}
    old,new=tracks(source),tracks(derived)
    replaced=set(replaced_copper)
    assert replaced <= old.keys(), 'Replacement references unknown copper'
    assert all(new.get(uid)!=old[uid] for uid in replaced), 'Declared replacement was not changed'
    assert all(new.get(uid)==data for uid,data in old.items() if uid not in replaced),'Original copper removed or modified'
    source.BuildConnectivity();derived.BuildConnectivity();eligible={uid for uid,(ref,num,_) in original.items() if (ref,num) not in changed_nets};seen=set();groups=0
    for uid in sorted(eligible):
        if uid in seen:continue
        group=({q.m_Uuid.AsString() for q in source.GetConnectivity().GetConnectedItems(original[uid][2])}|{uid}) & eligible;seen|=group
        if len(group)<2:continue
        actual={q.m_Uuid.AsString() for q in derived.GetConnectivity().GetConnectedItems(current[uid][2])}|{uid}
        assert group<=actual,('Existing physical connection broken',original[uid][:2],sorted(group-actual))
        groups+=1
    return {'existing_pad_instances_preserved':len(original),'existing_tracks_vias_preserved':len(old)-len(replaced),'explicitly_replaced_copper':{uid:old[uid] for uid in sorted(replaced)},'added_tracks_vias':len(new)-len(old),'existing_connected_pad_groups_preserved':groups}
