"""
Winding trails: let players reach more of the map before their first item.

Andrew (2026-11-22): the start area was small (on average only ~15% of the
reachable map), so the first access item had to sit near spawn. This carves
a few winding 1-wide trails from the start area through forests, lava
fields and deserts, sometimes ending in a short ford across a river (at most
3 water tiles), so more of the map is open with no items. The item is then
a *shortcut* (cut straight through the forest instead of walking the trail),
which is a routing decision rather than a hard gate.

Runs after terrain (rivers, deserts, bridges, castle, buildings, lava,
forests, spawn clearing) and before vaults, snakes and items, so everything
placed later sees the trails.

How a trail is found: a Dijkstra search from every tile you can stand on
with no items, through obstacle tiles (cost 1 + a small per-terrain extra + WIND x a
smooth random field, so the cheapest route meanders; water costs most) and
open ground outside the start area (cost 1). Every patch of open ground (grass/road) it reaches that
isn't in the start area is a candidate; one is picked at random weighted by
size, and the obstacle tiles on the route there become grass (road through
desert or water).
"""
import heapq
import random

from support_classes import Coordinates, TerrType
import verify

CARVE = {   # obstacle -> what the trail turns it into, and the extra cost of crossing it
    TerrType.TREE: (TerrType.GRASS, 0.0),
    TerrType.LAVA: (TerrType.GRASS, 0.5),
    TerrType.DESERT: (TerrType.ROAD, 0.5),
    TerrType.WATER: (TerrType.ROAD, 4.0),   # a ford/bridge: allowed, but avoided if land works
}
MAX_WATER = 3               # water tiles per trail (one short ford)
MAX_OBSTACLE = 45           # obstacle tiles per trail
TARGET_SHARE = (0.30, 0.45)  # stop once this share of the map is open with no items
MAX_TRAILS = 4
MIN_TARGET = 25             # a trail must open at least this many ground tiles
WIND = 10.0                 # how strongly the random field bends the trail
GROUND = (TerrType.GRASS, TerrType.ROAD)


def _noise(w, h):
    f = [[random.random() for _ in range(w)] for _ in range(h)]
    for _ in range(2):   # box blur twice: smooth hills and valleys
        g = [[0.0] * w for _ in range(h)]
        for y in range(h):
            for x in range(w):
                tot = n = 0
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if 0 <= x + dx < w and 0 <= y + dy < h:
                            tot += f[y + dy][x + dx]
                            n += 1
                g[y][x] = tot / n
        f = g
    lo = min(min(r) for r in f)
    hi = max(max(r) for r in f)
    return [[(c - lo) / (hi - lo + 1e-9) for c in r] for r in f]


def _components(m, tiles):
    comp = {}
    sizes = []
    tiles = set(tiles)
    for t in tiles:
        if t in comp:
            continue
        idx = len(sizes)
        stack = [t]
        comp[t] = idx
        n = 0
        while stack:
            c = stack.pop()
            n += 1
            for nb in c.get_neighboring_coordinates():
                if nb in tiles and nb not in comp:
                    comp[nb] = idx
                    stack.append(nb)
        sizes.append(n)
    return comp, sizes


def _find_trail(m, v, start, noise):
    outdoor = lambda c: m.get_room_number(c.x, c.y) == 0
    ground = [c for c in v.neighbors if outdoor(c) and m.get_cell(c.x, c.y) in GROUND and c not in start]
    comp, sizes = _components(m, ground)
    dist = {}
    prev = {}
    heap = []
    for s in start:
        dist[s] = 0.0
        heap.append((0.0, 0, 0, s.x, s.y))
    heapq.heapify(heap)
    reached = {}   # component -> tile where the trail first reaches it
    while heap:
        d, n_obs, n_wet, x, y = heapq.heappop(heap)
        c = Coordinates(x, y)
        if d > dist.get(c, 1e18):
            continue
        if c in comp:
            k = comp[c]
            if k not in reached and n_obs > 0:
                reached[k] = c
            continue   # open ground outside the start area is a destination
        for nb in v.neighbors[c]:
            if not outdoor(nb) or nb in start:
                continue
            terr = m.get_cell(nb.x, nb.y)
            if terr in CARVE:
                step = 1 + CARVE[terr][1] + WIND * noise[nb.y][nb.x]
                obs, wet = n_obs + 1, n_wet + (terr == TerrType.WATER)
            elif nb in comp:
                step, obs, wet = 1, n_obs, n_wet
            else:
                continue
            if obs > MAX_OBSTACLE or wet > MAX_WATER:
                continue
            nd = d + step
            if nd < dist.get(nb, 1e18):
                dist[nb] = nd
                prev[nb] = c
                heapq.heappush(heap, (nd, obs, wet, nb.x, nb.y))
    options = [(k, t) for k, t in reached.items() if sizes[k] >= MIN_TARGET]
    if not options:
        return None
    k, t = random.choices(options, weights=[sizes[k] for k, _ in options])[0]
    path = []
    while t in prev:
        path.append(t)
        t = prev[t]
    return [c for c in path if m.get_cell(c.x, c.y) in CARVE]


def carve_trails(m):
    v = verify.Verifier(m)

    def refresh():
        v._idx_ready = False
        v._cache = {}

    full = len(v.stand_tiles(frozenset(verify.TRAVERSAL_ITEMS)))
    goal = random.uniform(*TARGET_SHARE) * full
    noise = _noise(m.width, m.height)
    m.trails = []
    while len(m.trails) < MAX_TRAILS:
        start = v.stand_tiles(frozenset())
        if len(start) >= goal:
            break
        trail = _find_trail(m, v, start, noise)
        if not trail:
            break
        kinds = sorted({m.get_cell(c.x, c.y).label.lower() for c in trail})
        for c in trail:
            m.set_cell(c.x, c.y, CARVE[m.get_cell(c.x, c.y)][0])
        m.trails.append(('+'.join(kinds), trail))
        refresh()
    m.trails += carve_glades(m, v)
    return m.trails


# ---------------------------------------------------------------------------
# Glade trails: a winding 1-wide trail that snakes deep into a forest (or a
# lava field) from the start area and ends in a small clearing, which is
# registered as an item hiding place ("Forest Glade"). The first items can
# then sit at the end of a long walk instead of near spawn; the Axe (or
# Shield) is a shortcut straight to them.
# ---------------------------------------------------------------------------

GLADES = (1, 3)
GLADE_LEN = (12, 26)
GLADE_MIN = 9
GLADE_TERRAIN = (TerrType.TREE, TerrType.LAVA)
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _walk(m, entry, first, start):
    """Self-avoiding winding walk over trees/lava. Each new tile may touch
    only the previous one, so the trail stays 1 wide with walls between bends."""
    path = [first]
    taken = {first}
    d = (first.x - entry.x, first.y - entry.y)
    want = random.randint(*GLADE_LEN)
    while len(path) < want:
        cur = path[-1]
        dirs = DIRS[:]
        random.shuffle(dirs)
        if random.random() < 0.45:          # some momentum
            dirs.remove(d)
            dirs.insert(0, d)
        moved = False
        for dd in dirs:
            n = Coordinates(cur.x + dd[0], cur.y + dd[1])
            if (not m.is_valid_coordinates(n) or n in taken or n in start
                    or m.get_cell(n.x, n.y) not in GLADE_TERRAIN
                    or m.get_room_number(n.x, n.y) != 0):
                continue
            touching = [t for t in n.get_neighboring_coordinates() if t in taken or t in start]
            if touching != [cur]:
                continue
            path.append(n)
            taken.add(n)
            d = dd
            moved = True
            break
        if not moved:
            break
    return path


def carve_glades(m, v):
    from vaults import register_item_spot, _site_ok
    start = v.stand_tiles(frozenset())
    edges = [(s, n) for s in start for n in v.neighbors[s]
             if m.get_cell(n.x, n.y) in GLADE_TERRAIN and m.get_room_number(n.x, n.y) == 0]
    random.shuffle(edges)
    made = []
    want = random.randint(*GLADES)
    for entry, first in edges:
        if len(made) >= want:
            break
        if any(first.get_distance(t) < 6 for _, path in made for t in path):
            continue
        path = _walk(m, entry, first, start)
        end = path[-1]
        if len(path) < GLADE_MIN or end.get_distance(entry) < 5 or not _site_ok(m, end, min_spawn=12):
            continue
        for c in path:
            m.set_cell(c.x, c.y, TerrType.GRASS)
        for c in end.get_neighboring_coordinates():   # the glade itself
            if m.is_valid_coordinates(c) and m.get_room_number(c.x, c.y) == 0 and m.get_cell(c.x, c.y) in GLADE_TERRAIN:
                m.set_cell(c.x, c.y, TerrType.GRASS)
        register_item_spot(m, end, 'Forest Glade' if m.get_cell(first.x, first.y) != TerrType.LAVA else 'Lava Causeway')
        made.append(('glade', path))
    return made
