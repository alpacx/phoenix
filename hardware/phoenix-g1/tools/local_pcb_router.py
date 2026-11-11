"""Small bounded two-layer routing helper for low-current draft connections.

No differential pairs, impedance or current rating. Every result requires DRC.
Power-current paths must be designed separately rather than passed here.
"""
import heapq
import math
import pcbnew as p


class LocalRouter:
    def __init__(self, board, extent, width=.2, clearance=.2, grid=.05):
        self.board, self.extent = board, extent
        self.width, self.clearance, self.grid = width, clearance, grid
        self.pads = [a for f in board.GetFootprints() for a in f.Pads()]

    def xy(self, item):
        return (p.ToMM(item.GetPosition().x), p.ToMM(item.GetPosition().y))

    def cell(self, q):
        return tuple(round(v/self.grid) for v in q)

    def world(self, q):
        return tuple(v*self.grid for v in q)

    def within(self, q):
        x, y = self.world(q)
        return self.extent[0] <= x <= self.extent[2] and self.extent[1] <= y <= self.extent[3]

    def blocked(self, layer, name, diameter=None, via=False):
        diameter = self.width if diameter is None else diameter
        result = set()
        margin = self.clearance+diameter/2

        def rect(x0, y0, x1, y1):
            for x in range(math.ceil(max(x0, self.extent[0])/self.grid), math.floor(min(x1, self.extent[2])/self.grid)+1):
                for y in range(math.ceil(max(y0, self.extent[1])/self.grid), math.floor(min(y1, self.extent[3])/self.grid)+1):
                    result.add((x, y))

        for a in self.pads:
            if not a.IsOnLayer(layer) or (a.GetNetname() == name and not via):
                continue
            q = a.GetBoundingBox(layer)
            rect(p.ToMM(q.GetX())-margin, p.ToMM(q.GetY())-margin,
                 p.ToMM(q.GetRight())+margin, p.ToMM(q.GetBottom())+margin)
        for z in list(self.board.Zones())+[z for f in self.board.GetFootprints() for z in f.Zones()]:
            if z.GetIsRuleArea() and z.IsOnLayer(layer) and (z.GetDoNotAllowVias() if via else z.GetDoNotAllowTracks()):
                q = z.GetBoundingBox()
                rect(p.ToMM(q.GetX())-diameter/2, p.ToMM(q.GetY())-diameter/2,
                     p.ToMM(q.GetRight())+diameter/2, p.ToMM(q.GetBottom())+diameter/2)
        for t in self.board.GetTracks():
            if not t.IsOnLayer(layer):
                continue
            same = t.GetNetname() == name
            if same and not (via and isinstance(t, p.PCB_VIA)):
                continue
            a = tuple(p.ToMM(v) for v in (t.GetStart().x, t.GetStart().y))
            z = tuple(p.ToMM(v) for v in (t.GetEnd().x, t.GetEnd().y))
            r = (.25+(.2+p.ToMM(t.GetDrillValue()))/2) if same else self.clearance+(diameter+p.ToMM(t.GetWidth(layer) if isinstance(t, p.PCB_VIA) else t.GetWidth()))/2
            dx, dy = z[0]-a[0], z[1]-a[1]
            den = dx*dx+dy*dy
            for x in range(math.floor(max(self.extent[0], min(a[0], z[0])-r)/self.grid), math.ceil(min(self.extent[2], max(a[0], z[0])+r)/self.grid)+1):
                for y in range(math.floor(max(self.extent[1], min(a[1], z[1])-r)/self.grid), math.ceil(min(self.extent[3], max(a[1], z[1])+r)/self.grid)+1):
                    wx, wy = self.world((x, y))
                    u = max(0, min(1, ((wx-a[0])*dx+(wy-a[1])*dy)/den)) if den else 0
                    if math.hypot(wx-a[0]-u*dx, wy-a[1]-u*dy) < r-1e-6:
                        result.add((x, y))
        return result

    def solve(self, blocked, start, goal):
        if start in blocked or goal in blocked or not self.within(start) or not self.within(goal):
            return None
        queue = [(math.dist(start, goal), 0, start)]
        distances, prev = {start: 0}, {}
        while queue:
            _, cost, q = heapq.heappop(queue)
            if cost != distances[q]:
                continue
            if q == goal:
                path = [q]
                while path[-1] != start:
                    path.append(prev[path[-1]])
                path.reverse()
                compact = [path[0]]
                for i in range(1, len(path)-1):
                    if (path[i][0]-path[i-1][0], path[i][1]-path[i-1][1]) != (path[i+1][0]-path[i][0], path[i+1][1]-path[i][1]):
                        compact.append(path[i])
                if len(path) > 1:
                    compact.append(path[-1])
                return [self.world(c) for c in compact]
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                n = (q[0]+dx, q[1]+dy)
                if not self.within(n) or n in blocked:
                    continue
                if dx and dy and ((q[0]+dx, q[1]) in blocked or (q[0], q[1]+dy) in blocked):
                    continue
                new_cost = cost+math.hypot(dx, dy)
                if new_cost < distances.get(n, float('inf')):
                    distances[n], prev[n] = new_cost, q
                    heapq.heappush(queue, (new_cost+math.dist(n, goal), new_cost, n))
        return None

    def vias_near(self, pad, name, limit=12):
        front, back = self.blocked(p.F_Cu, name), self.blocked(p.B_Cu, name)
        forbidden = set()
        for layer in (p.F_Cu, p.In1_Cu, p.In2_Cu, p.In3_Cu, p.In4_Cu, p.B_Cu):
            forbidden |= self.blocked(layer, name, .45, True)
        start = self.cell(self.xy(pad))
        options = {(start[0]+dx, start[1]+dy) for dx in range(-50, 51, 2) for dy in range(-50, 51, 2)}
        existing = {self.cell(self.xy(t)) for t in self.board.GetTracks() if isinstance(t, p.PCB_VIA) and t.GetNetname() == name}
        options = {q for q in options if self.within(q) and q not in forbidden} | existing
        paths = []
        for q in sorted(options, key=lambda q: math.dist(q, start)):
            if q in front or q in back:
                continue
            path = self.solve(front, start, q)
            if path and sum(math.dist(a, z) for a, z in zip(path, path[1:])) <= 4:
                paths.append((q, [self.xy(pad)]+path, q in existing))
                if len(paths) == limit:
                    break
        return paths

    def back_pair(self, a, z, add_tracks, add_via):
        name = a.GetNetname()
        assert name == z.GetNetname()
        back = self.blocked(p.B_Cu, name)
        starts, goals = self.vias_near(a, name), self.vias_near(z, name)
        for sa, pa, ea in starts:
            for sz, pz, ez in goals:
                # Do not create two drilled holes closer than the manufacturing rule.
                if sa != sz and math.dist(self.world(sa), self.world(sz)) < .45:
                    continue
                path = self.solve(back, sa, sz)
                if path:
                    add_tracks(name, self.width, pa)
                    add_tracks(name, self.width, pz)
                    add_tracks(name, self.width, path, p.B_Cu)
                    if not ea:
                        add_via(name, self.world(sa))
                    if not ez and sa != sz:
                        add_via(name, self.world(sz))
                    return
        raise RuntimeError(f'No local back-layer route (starts={len(starts)}, goals={len(goals)}): {a.GetParentFootprint().GetReference()}.{a.GetNumber()} to {z.GetParentFootprint().GetReference()}.{z.GetNumber()}')

    def ground_escape(self, pad, add_tracks, add_via):
        assert pad.GetNetname() == 'GND'
        choices = self.vias_near(pad, 'GND', limit=1)
        if not choices:
            raise RuntimeError('No local ground via for '+pad.GetParentFootprint().GetReference())
        q, path, existing = choices[0]
        add_tracks('GND', self.width, path)
        if not existing:
            add_via('GND', self.world(q))
