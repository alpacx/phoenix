"""Explicit geometry guards for replacing a constant-width copper branch.

These checks prevent accidental narrowing; they are not ampacity qualification.
"""
import pcbnew as p


def require_constant_width_branch(tracks, *, net, layer, width_mm, start_mm, end_mm):
    tracks = list(tracks)
    assert tracks, 'Replacement branch is empty'
    point = lambda xy: tuple(p.FromMM(v) for v in xy)
    cursor = point(start_mm)
    width = p.FromMM(width_mm)
    for track in tracks:
        assert not isinstance(track, p.PCB_VIA), 'Replacement branch contains a via'
        assert track.GetNetname() == net, 'Replacement branch changes net'
        assert track.GetLayer() == layer, 'Replacement branch changes layer'
        assert track.GetWidth() == width, 'Replacement branch changes required width'
        start = (track.GetStart().x, track.GetStart().y)
        end = (track.GetEnd().x, track.GetEnd().y)
        assert start == cursor, 'Replacement branch is discontinuous'
        assert start != end, 'Replacement branch has zero-length segment'
        cursor = end
    assert cursor == point(end_mm), 'Replacement branch ends at wrong endpoint'
    return {'net': net, 'width_mm': width_mm, 'segments': len(tracks),
            'width_preserved': True, 'current_rating_qualified': False}
