"""Bounded multi-layer grid router for one open join of a KiCad checkpoint.

Draft continuity only: no impedance, pair, length or current qualification.
Obstacles are rasterised from pads, tracks, vias, holes, rule areas and the
board edge with conservative clearances; every result must pass native DRC.
Non-GND copper never enters the In1/In4 ground planes (vias only, refilled).

Usage (KiCad Python):
  route_open_join.py SRC.kicad_pcb DST.kicad_pcb --a REF.PAD|x,y,LAYER --b ... \
      [--width .2] [--clearance .2] [--grid .05] [--margin 3] [--layers F,In2,In3,B]
      [--via-cost 1.5] [--neck REF.PAD:width] [--dry]
"""
import argparse
import heapq
import json
import math
import sys

import numpy as np
import pcbnew as p

NAMES = {"F": p.F_Cu, "In1": p.In1_Cu, "In2": p.In2_Cu, "In3": p.In3_Cu, "In4": p.In4_Cu, "B": p.B_Cu}
ALL = [p.F_Cu, p.In1_Cu, p.In2_Cu, p.In3_Cu, p.In4_Cu, p.B_Cu]
MM = p.ToMM


def pad_clearance(pad, default):
    ref = pad.GetParentFootprint().GetReference()
    return {"U1": .0762, "U2": .1, "J3": .17}.get(ref, default)


class Grid:
    def __init__(self, board, box, grid):
        self.b, self.g = board, grid
        self.x0, self.y0 = box[0], box[1]
        self.nx = int(math.ceil((box[2] - box[0]) / grid)) + 1
        self.ny = int(math.ceil((box[3] - box[1]) / grid)) + 1
        xs = self.x0 + np.arange(self.nx) * grid
        ys = self.y0 + np.arange(self.ny) * grid
        self.X, self.Y = np.meshgrid(xs, ys, indexing="ij")

    def world(self, i, j):
        return (round(self.x0 + i * self.g, 6), round(self.y0 + j * self.g, 6))

    def cell(self, x, y):
        return (int(round((x - self.x0) / self.g)), int(round((y - self.y0) / self.g)))

    def window(self, x0, y0, x1, y1):
        i0 = max(0, int(math.floor((x0 - self.x0) / self.g)))
        i1 = min(self.nx, int(math.ceil((x1 - self.x0) / self.g)) + 1)
        j0 = max(0, int(math.floor((y0 - self.y0) / self.g)))
        j1 = min(self.ny, int(math.ceil((y1 - self.y0) / self.g)) + 1)
        return i0, i1, j0, j1

    def seg_mask(self, mask, a, z, r):
        i0, i1, j0, j1 = self.window(min(a[0], z[0]) - r, min(a[1], z[1]) - r,
                                     max(a[0], z[0]) + r, max(a[1], z[1]) + r)
        if i0 >= i1 or j0 >= j1:
            return
        X, Y = self.X[i0:i1, j0:j1], self.Y[i0:i1, j0:j1]
        dx, dy = z[0] - a[0], z[1] - a[1]
        den = dx * dx + dy * dy
        u = np.clip(((X - a[0]) * dx + (Y - a[1]) * dy) / den, 0, 1) if den else 0
        d = np.hypot(X - a[0] - u * dx, Y - a[1] - u * dy)
        mask[i0:i1, j0:j1] |= d < r - 1e-6

    def poly_mask(self, mask, poly, r):
        bb = poly.BBox()
        i0, i1, j0, j1 = self.window(MM(bb.GetX()) - r, MM(bb.GetY()) - r,
                                     MM(bb.GetRight()) + r, MM(bb.GetBottom()) + r)
        rr = p.FromMM(r) - 1
        for i in range(i0, i1):
            for j in range(j0, j1):
                if mask[i, j]:
                    continue
                pt = p.VECTOR2I(p.FromMM(float(self.X[i, j])), p.FromMM(float(self.Y[i, j])))
                if poly.Collide(pt, rr):
                    mask[i, j] = True


def pad_poly(pad, layer):
    poly = p.SHAPE_POLY_SET()
    pad.TransformShapeToPolygon(poly, layer, 0, p.FromMM(.0005), p.ERROR_OUTSIDE)
    return poly


def build(board, G, net, width, clr, layers, lpddr_clr, guard=0.0):
    """Return per-layer track masks, via mask and own-net cell masks."""
    half = width / 2
    track = {l: np.zeros((G.nx, G.ny), bool) for l in ALL}
    via = np.zeros((G.nx, G.ny), bool)
    own = {l: np.zeros((G.nx, G.ny), bool) for l in ALL}
    vr = .225
    bx0, by0 = G.x0, G.y0
    bx1, by1 = G.x0 + G.nx * G.g, G.y0 + G.ny * G.g
    near = lambda q, r: bx0 - r <= q[0] <= bx1 + r and by0 - r <= q[1] <= by1 + r
    for fp in board.GetFootprints():
        for pad in fp.Pads():
            c = (MM(pad.GetPosition().x), MM(pad.GetPosition().y))
            if not near(c, 3):
                continue
            pc = pad_clearance(pad, clr)
            mine = pad.GetNetname() == net and net != ""
            for l in ALL:
                if pad.IsOnLayer(l) and pad.FlashLayer(l):
                    poly = pad_poly(pad, l)
                    if mine:
                        G.poly_mask(own[l], poly, .001)
                        if pad.GetAttribute() == p.PAD_ATTRIB_SMD:
                            G.poly_mask(via, poly, vr + .05)  # no via-in-pad
                    else:
                        G.poly_mask(track[l], poly, pc + half)
                        G.poly_mask(via, poly, max(pc + vr, .25 + .1))
            if pad.HasHole():
                d = MM(pad.GetDrillSizeX()) / 2
                G.seg_mask(via, c, c, d + .25 + .1)
                if not mine:
                    for l in ALL:
                        G.seg_mask(track[l], c, c, d + .25 + half)
    for t in board.GetTracks():
        a = (MM(t.GetStart().x), MM(t.GetStart().y))
        z = (MM(t.GetEnd().x), MM(t.GetEnd().y))
        if (max(a[0], z[0]) < bx0 - 3 or min(a[0], z[0]) > bx1 + 3 or
                max(a[1], z[1]) < by0 - 3 or min(a[1], z[1]) > by1 + 3):
            continue
        mine = t.GetNetname() == net
        tc = lpddr_clr if t.GetNetname().startswith("LPDDR4_") else clr
        if isinstance(t, p.PCB_VIA):
            for l in ALL:
                w = MM(t.GetWidth(l)) / 2
                if mine:
                    G.seg_mask(own[l], a, a, w)
                else:
                    G.seg_mask(track[l], a, a, w + tc + half)
                    G.seg_mask(via, a, a, max(w + tc + vr, w + .25 + .1))
            G.seg_mask(via, a, a, MM(t.GetDrillValue()) / 2 + .25 + .1)
            if not mine:
                for l in ALL:
                    G.seg_mask(track[l], a, a, MM(t.GetDrillValue()) / 2 + .25 + half)
        else:
            l = t.GetLayer()
            w = MM(t.GetWidth()) / 2
            if mine:
                G.seg_mask(own[l], a, z, w)
            else:
                G.seg_mask(track[l], a, z, w + tc + half)
                G.seg_mask(via, a, z, max(w + tc + vr, w + .25 + .1, w + guard if t.GetNetname() not in ("GND", "") else 0))
    for zn in list(board.Zones()) + [z for f in board.GetFootprints() for z in f.Zones()]:
        if not zn.GetIsRuleArea():
            continue
        bb = zn.GetBoundingBox()
        box = (MM(bb.GetX()), MM(bb.GetY()), MM(bb.GetRight()), MM(bb.GetBottom()))
        outline = zn.Outline()
        for l in ALL:
            if zn.IsOnLayer(l) and zn.GetDoNotAllowTracks():
                G.poly_mask(track[l], outline, half + .001)
        if zn.GetDoNotAllowVias():
            G.poly_mask(via, outline, vr + .001)
    eb = board.GetBoardEdgesBoundingBox()
    e = (MM(eb.GetX()), MM(eb.GetY()), MM(eb.GetRight()), MM(eb.GetBottom()))
    for m, r in [(track[l], .25 + half) for l in ALL] + [(via, .25 + vr)]:
        inside = (G.X >= e[0] + r) & (G.X <= e[2] - r) & (G.Y >= e[1] + r) & (G.Y <= e[3] - r)
        m |= ~inside
    for l in ALL:
        if l not in layers:
            track[l][:] = True
        if l in (p.In1_Cu, p.In4_Cu) and net != "GND":
            track[l][:] = True
    return track, via, own


def find_item(board, key):
    for t in board.GetTracks():
        if t.m_Uuid.AsString() == key:
            return t
    for f in board.GetFootprints():
        for pad in f.Pads():
            if pad.m_Uuid.AsString() == key:
                return pad
    ref, num = key.split(".")
    return board.FindFootprintByReference(ref).FindPadByNumber(num)


def island(board, item):
    items = [item] + [i for i in board.GetConnectivity().GetConnectedItems(item)]
    seen, out = set(), []
    for i in items:
        k = i.m_Uuid.AsString()
        if k not in seen and i.GetNetname() == item.GetNetname():
            seen.add(k)
            out.append(i)
    return out


def item_xy(item):
    if isinstance(item, p.ZONE):
        raise ValueError("zone endpoint")
    if isinstance(item, p.PAD) or isinstance(item, p.PCB_VIA):
        return (MM(item.GetPosition().x), MM(item.GetPosition().y))
    return (MM(item.GetStart().x), MM(item.GetStart().y))


def island_cells(G, items, track, layers, half=0.0):
    ov = max(.001, half - .015)  # track copper overlaps the island by >= 15 um
    out = set()
    for it in items:
        for l in layers:
            mask = np.zeros((G.nx, G.ny), bool)
            if isinstance(it, p.PAD):
                if not (it.IsOnLayer(l) and it.FlashLayer(l)):
                    continue
                G.poly_mask(mask, pad_poly(it, l), ov)
            elif isinstance(it, p.ZONE):
                if not it.IsOnLayer(l):
                    continue
                G.poly_mask(mask, it.GetFilledPolysList(l), .001)
            elif isinstance(it, p.PCB_VIA):
                c = item_xy(it)
                G.seg_mask(mask, c, c, MM(it.GetWidth(l)) / 2 - .001)
            else:
                if it.GetLayer() != l:
                    continue
                a = (MM(it.GetStart().x), MM(it.GetStart().y))
                z = (MM(it.GetEnd().x), MM(it.GetEnd().y))
                G.seg_mask(mask, a, z, MM(it.GetWidth()) / 2 + ov)
            ii, jj = np.nonzero(mask & ~track[l])
            out |= {(l, int(i), int(j)) for i, j in zip(ii, jj)}
    return sorted(out)


def route(track, via, own, G, sources, targets, via_cost, layers):
    li = {l: k for k, l in enumerate(ALL)}
    tset = set(targets)
    dist, prev, q = {}, {}, []
    tx = np.mean([G.world(i, j)[0] for _, i, j in targets])
    ty = np.mean([G.world(i, j)[1] for _, i, j in targets])
    h = lambda i, j: 0.0 * math.hypot(G.x0 + i * G.g - tx, G.y0 + j * G.g - ty)
    for s in sources:
        dist[s] = 0.0
        heapq.heappush(q, (h(s[1], s[2]), 0.0, s))
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    while q:
        _, c, n = heapq.heappop(q)
        if c != dist.get(n):
            continue
        if n in tset:
            path = [n]
            while path[-1] in prev:
                path.append(prev[path[-1]])
            return path[::-1], c
        l, i, j = n
        T = track[l]
        for dx, dy in steps:
            a, b = i + dx, j + dy
            if not (0 <= a < G.nx and 0 <= b < G.ny) or T[a, b]:
                continue
            if dx and dy and (T[i + dx, j] or T[i, j + dy]):
                continue
            m = (l, a, b)
            nc = c + math.hypot(dx, dy) * G.g
            if nc < dist.get(m, 1e18):
                dist[m], prev[m] = nc, n
                heapq.heappush(q, (nc + h(a, b), nc, m))
        if not via[i, j]:
            for l2 in layers:
                if l2 == l or track[l2][i, j]:
                    continue
                m = (l2, i, j)
                nc = c + via_cost
                if nc < dist.get(m, 1e18):
                    dist[m], prev[m] = nc, n
                    heapq.heappush(q, (nc + h(i, j), nc, m))
    return None, None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--net")
    ap.add_argument("--width", type=float, default=.2)
    ap.add_argument("--clearance", type=float, default=.2)
    ap.add_argument("--lpddr-clearance", type=float, default=.2)
    ap.add_argument("--grid", type=float, default=.05)
    ap.add_argument("--margin", type=float, default=3)
    ap.add_argument("--layers", default="F,In2,In3,B")
    ap.add_argument("--via-cost", type=float, default=1.5)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--guard", type=float, default=.7,
                    help="min distance from a new via centre to foreign signal track copper, so the refilled "
                         "In1/In4 antipad and removed slivers stay off existing return paths")
    ap.add_argument("--keepout", action="append", default=[],
                    help="x0,y0,x1,y1 rectangle (mm) kept free of new tracks on all layers and of new vias, "
                         "to reserve an escape for a later route")
    ap.add_argument("--rip", default="",
                    help="comma-separated track/via UUID prefixes removed before routing (rip-up); the caller "
                         "must restore and re-verify every pad pair those items connected")
    args = ap.parse_args()
    board = p.LoadBoard(args.src)
    rip = [k for k in args.rip.split(",") if k]
    if rip:
        gone = [t for t in board.GetTracks() if any(t.m_Uuid.AsString().startswith(k) for k in rip)]
        assert len(gone) == len(rip), ("rip prefixes must match exactly one item each", len(gone), len(rip))
        for t in gone:
            board.Remove(t)
    board.BuildConnectivity()
    ia, ib = find_item(board, args.a), find_item(board, args.b)
    net = ia.GetNetname()
    assert net == ib.GetNetname(), (net, ib.GetNetname())
    A, B = island(board, ia), island(board, ib)
    assert not ({i.m_Uuid.AsString() for i in A} & {i.m_Uuid.AsString() for i in B}), "already joined"
    layers = [NAMES[s] for s in args.layers.split(",")]
    if net == "GND":
        layers = sorted(set(layers) | {p.In1_Cu, p.In4_Cu}, key=ALL.index)
    pa, pb = item_xy(ia), item_xy(ib)
    m = args.margin
    box = [min(pa[0], pb[0]) - m, min(pa[1], pb[1]) - m, max(pa[0], pb[0]) + m, max(pa[1], pb[1]) + m]
    # Align the lattice to the smaller pad so its centreline exit is representable.
    pads = [(min(MM(i.GetSize().x), MM(i.GetSize().y)), xy) for i, xy in ((ia, pa), (ib, pb)) if isinstance(i, p.PAD)]
    if pads:
        ax, ay = min(pads)[1]
        box[0] = ax - args.grid * math.ceil((ax - box[0]) / args.grid - 1e-9)
        box[1] = ay - args.grid * math.ceil((ay - box[1]) / args.grid - 1e-9)
    G = Grid(board, box, args.grid)
    track, via, own = build(board, G, net, args.width, args.clearance, layers, args.lpddr_clearance, args.guard)
    for k in args.keepout:
        x0, y0, x1, y1 = map(float, k.split(","))
        ko = (G.X >= x0) & (G.X <= x1) & (G.Y >= y0) & (G.Y <= y1)
        via |= ko
        for l in ALL:
            track[l] |= ko
    src, dst = island_cells(G, A, track, layers, args.width / 2), island_cells(G, B, track, layers, args.width / 2)
    if not src or not dst:
        print(json.dumps({"result": "blocked_endpoint", "src": len(src), "dst": len(dst)}))
        sys.exit(2)
    path, cost = route(track, via, own, G, src, dst, args.via_cost, layers)
    if not path:
        print(json.dumps({"result": "no_path", "src": len(src), "dst": len(dst)}))
        sys.exit(3)
    # compress
    pts = [(l, G.world(i, j)) for l, i, j in path]
    segs, vias = [], []
    start = pts[0]
    for k in range(1, len(pts)):
        l0, q0 = pts[k - 1]
        l1, q1 = pts[k]
        if l1 != l0:
            if start[1] != q0:
                segs.append((l0, start[1], q0))
            vias.append(q0)
            start = pts[k]
            continue
        if k + 1 < len(pts) and pts[k + 1][0] == l1:
            d0 = (round((q1[0] - q0[0]) / G.g), round((q1[1] - q0[1]) / G.g))
            q2 = pts[k + 1][1]
            d1 = (round((q2[0] - q1[0]) / G.g), round((q2[1] - q1[1]) / G.g))
            if d0 == d1:
                continue
        segs.append((l1, start[1], q1))
        start = pts[k]
    # Connect into pad centres when the path starts/ends inside a pad.
    length = sum(math.dist(a, z) for _, a, z in segs)
    report = {"result": "path", "net": net, "a": args.a, "b": args.b, "width": args.width, "clearance": args.clearance, "lpddr_clearance": args.lpddr_clearance, "guard": args.guard, "grid": args.grid, "cost": round(cost, 3), "length_mm": round(length, 3),
              "vias": [list(v) for v in vias],
              "segments": [[board.GetLayerName(l), list(a), list(z)] for l, a, z in segs]}
    print(json.dumps(report))
    if args.dry:
        return
    code = board.FindNet(net).GetNetCode()
    for l, a, z in segs:
        if a == z:
            continue
        t = p.PCB_TRACK(board)
        t.SetStart(p.VECTOR2I(p.FromMM(a[0]), p.FromMM(a[1])))
        t.SetEnd(p.VECTOR2I(p.FromMM(z[0]), p.FromMM(z[1])))
        t.SetWidth(p.FromMM(args.width))
        t.SetLayer(l)
        t.SetNetCode(code)
        board.Add(t)
    for q in vias:
        v = p.PCB_VIA(board)
        v.SetPosition(p.VECTOR2I(p.FromMM(q[0]), p.FromMM(q[1])))
        v.SetViaType(p.VIATYPE_THROUGH)
        v.SetWidth(p.FromMM(.45))
        v.SetDrill(p.FromMM(.2))
        v.SetNetCode(code)
        board.Add(v)
    p.ZONE_FILLER(board).Fill(board.Zones())
    p.SaveBoard(args.dst, board)


if __name__ == "__main__":
    main()
