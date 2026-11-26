"""
No big empty plains (Andrew, 2026-11-24: seed 47 had large empty areas).

1. place_area_vaults (after vaults/castle, before snakes and items): while
   some spot is EMPTY_DIST+ tiles from anything built (buildings, castle,
   vault spots, anything on a tile), put a set piece at the emptiest one: a
   Winding Wood (most often), a Pond Islet or a Lava Shrine (up to 4).
   Each registers an item spot, so items/gems/shrines get placed there.
2. decorate_empty (at the very end): every 5x5 block of plain grass that is
   still empty gets a copse of trees or a pond in its middle 3x3. Because the
   block's outer ring stays grass, this can never cut a path.

Winding Wood (Andrew's sketch): a block of forest with a serpentine 1-wide
path through it, in at one end and out at the other, and a dead-end nook
part way along with the item spot. Walkable with no items; the Axe cuts
straight across.

    F F F F F C F        <- in
    F C C C C C F
    F C F F F F F
    F C C C C G F        <- nook with the item spot
    F F F F C F F
    F C C C C F F
    F C F F F F F        <- out
"""
import random

from support_classes import Coordinates, TerrType, CellContents
from vaults import register_item_spot, _site_ok, _door_tiles, _castle_box, _near_castle, place_lava_shrine

AREA_WINDOW = 9
MAX_AREA_VAULTS = 4
MAX_SAME = 2          # at most this many of one kind of set piece per map
DECOR_WINDOW = 5


def _empty_tile(m, x, y, doors):
    c = Coordinates(x, y)
    return (m.is_valid_coordinates(c) and m.get_cell(x, y) == TerrType.GRASS and m.get_room_number(x, y) == 0
            and m.get_cell_contents(x, y) == CellContents.EMPTY and c not in doors)


def empty_windows(m, size, doors=None):
    """Top-left corners (x0, y0) of size x size blocks that are all empty grass."""
    doors = _door_tiles(m) if doors is None else doors
    ok = [[_empty_tile(m, x, y, doors) for x in range(m.width)] for y in range(m.height)]
    # prefix sums for fast window checks
    ps = [[0] * (m.width + 1) for _ in range(m.height + 1)]
    for y in range(m.height):
        for x in range(m.width):
            ps[y + 1][x + 1] = ps[y][x + 1] + ps[y + 1][x] - ps[y][x] + (1 if ok[y][x] else 0)
    out = []
    for y0 in range(m.height - size + 1):
        for x0 in range(m.width - size + 1):
            tot = ps[y0 + size][x0 + size] - ps[y0][x0 + size] - ps[y0 + size][x0] + ps[y0][x0]
            if tot == size * size:
                out.append((x0, y0))
    return out


# --- Winding Wood ----------------------------------------------------------------

def _winding_layout(w, h):
    """Local grid (x right, y down) of 'F' tree / 'C' clear, plus entry, exit and nook."""
    g = [['F'] * w for _ in range(h)]
    rows = list(range(1, h - 1, 2))
    left, right = 2, w - 3
    start = random.choice([left, right])
    pos = start
    g[0][pos] = 'C'                                    # way in
    spans = []
    for i, r in enumerate(rows):
        end = right if pos == left else left
        lo, hi = min(pos, end), max(pos, end)
        for x in range(lo, hi + 1):
            g[r][x] = 'C'
        spans.append((r, pos, end))
        if i + 1 < len(rows):
            g[r + 1][end] = 'C'                        # connector down to the next row
        pos = end
    g[h - 1][pos] = 'C'                                # way out
    # nook: a middle row's corridor pokes one tile past its start, to a dead end
    mid = spans[len(spans) // 2] if len(spans) > 2 else spans[0]
    r, s, e = mid
    nook_x = s - 1 if s < e else s + 1
    g[r][nook_x] = 'C'
    return g, (start, 0), (pos, h - 1), (nook_x, r)


def _winding_fits(m, x0, y0, w, h, doors, entry_out, exit_out):
    for ly in range(h):
        for lx in range(w):
            x, y = x0 + lx, y0 + ly
            c = Coordinates(x, y)
            if not m.is_valid_coordinates(c) or m.get_room_number(x, y) != 0 or c in doors:
                return False
            if m.get_cell(x, y) not in (TerrType.GRASS, TerrType.TREE, TerrType.DESERT) or m.get_cell_contents(x, y) != CellContents.EMPTY:
                return False
    for c in (entry_out, exit_out):
        if not m.is_valid_coordinates(c) or m.get_cell(c.x, c.y) not in (TerrType.GRASS, TerrType.ROAD) \
                or m.get_room_number(c.x, c.y) != 0:
            return False
    return True


def place_winding_wood(m, center, doors):
    w, h = random.choice([(7, 7), (9, 7), (11, 7), (9, 9), (11, 9)])
    transpose = random.random() < 0.5
    if transpose:
        w, h = h, w
    layout, entry, exit_, nook = _winding_layout(w if not transpose else h, h if not transpose else w)
    if transpose:   # swap axes so the path runs the other way
        layout = [list(row) for row in zip(*layout)]
        entry, exit_, nook = (entry[1], entry[0]), (exit_[1], exit_[0]), (nook[1], nook[0])
    x0, y0 = center.x - w // 2, center.y - h // 2
    to_map = lambda lx, ly: Coordinates(x0 + lx, y0 + ly)

    def outside(p):
        lx, ly = p
        if ly == 0:
            return to_map(lx, -1)
        if ly == h - 1:
            return to_map(lx, h)
        if lx == 0:
            return to_map(-1, ly)
        return to_map(w, ly)
    if not _winding_fits(m, x0, y0, w, h, doors, outside(entry), outside(exit_)):
        return False
    for ly in range(h):
        for lx in range(w):
            c = to_map(lx, ly)
            m.set_cell(c.x, c.y, TerrType.GRASS if layout[ly][lx] == 'C' else TerrType.TREE)
    spot = to_map(*nook)
    register_item_spot(m, spot, 'Winding Wood')
    return True


# --- Pond Islet: a speck of land in a little pond (Boots) --------------------------

def place_pond_islet(m, center, doors):
    for t in center.get_coordinates_in_range(3):
        if not _empty_tile(m, t.x, t.y, doors):
            return False
    for t in center.get_coordinates_in_range(2):
        if t != center:
            m.set_cell(t.x, t.y, TerrType.WATER)
    register_item_spot(m, center, 'Pond Islet')
    return True


def place_area_lava_shrine(m, center, doors):
    for t in center.get_coordinates_in_range(4):
        if not _empty_tile(m, t.x, t.y, doors):
            return False
    place_lava_shrine(m, (center, random.choice([1, 1, 2])))
    return True


AREA_FEATURES = [(place_winding_wood, 0.6), (place_pond_islet, 0.25), (place_area_lava_shrine, 0.15)]


EMPTY_DIST = 8     # a spot this far from anything built counts as empty


def _distance_to_stuff(m):
    """Grid distance from each tile to the nearest built thing: building or
    castle floor, a vault's item spot, or anything on a tile."""
    from collections import deque
    spots = set(getattr(m, 'vault_item_spots', []))
    dist = {}
    q = deque()
    for y in range(m.height):
        for x in range(m.width):
            c = Coordinates(x, y)
            if (m.get_room_number(x, y) != 0 or c in spots
                    or m.get_cell_contents(x, y) != CellContents.EMPTY):
                dist[c] = 0
                q.append(c)
    while q:
        c = q.popleft()
        for n in c.get_neighboring_coordinates():
            if m.is_valid_coordinates(n) and n not in dist:
                dist[n] = dist[c] + 1
                q.append(n)
    # the map edge counts as 'something' too, or the corners always look emptiest
    for c in dist:
        dist[c] = min(dist[c], 3 + min(c.x, c.y, m.width - 1 - c.x, m.height - 1 - c.y))
    return dist


def place_area_vaults(m):
    placed = []
    box = _castle_box(m)
    rejected = set()
    weights = dict(AREA_FEATURES)
    for _ in range(60):
        if len(placed) >= MAX_AREA_VAULTS:
            break
        doors = _door_tiles(m)
        dist = _distance_to_stuff(m)
        cands = [c for c, d in dist.items() if d >= EMPTY_DIST and c not in rejected
                 and m.get_cell(c.x, c.y) in (TerrType.GRASS, TerrType.TREE)]
        if not cands:
            break
        center = max(cands, key=lambda c: (dist[c], random.random()))
        if not _site_ok(m, center, min_spawn=12) or _near_castle(center, box, 3):
            rejected.add(center)
            continue
        done = False
        shifts = sorted(((dx, dy) for dx in range(-4, 5) for dy in range(-4, 5)),
                        key=lambda d: abs(d[0]) + abs(d[1]) + random.random())
        used = [n for n, _ in placed]
        for f in sorted(weights, key=lambda f: -weights[f] * random.random()):
            if used.count(f.__name__) >= MAX_SAME:
                continue
            for dx, dy in shifts:
                c = Coordinates(center.x + dx, center.y + dy)
                if m.is_valid_coordinates(c) and _site_ok(m, c, min_spawn=12) and f(m, c, doors):
                    placed.append((f.__name__, c))
                    done = True
                    break
            if done:
                break
        if not done:
            rejected.add(center)
    m.area_vaults = placed
    return placed


# --- final decoration ---------------------------------------------------------------

def decorate_empty(m):
    """Every 5x5 block of empty plain grass gets a copse or a pond in its middle."""
    made = 0
    while True:
        wins = empty_windows(m, DECOR_WINDOW)
        if not wins:
            break
        x0, y0 = random.choice(wins)
        mid = [Coordinates(x0 + 1 + dx, y0 + 1 + dy) for dx in range(3) for dy in range(3)]
        center = Coordinates(x0 + 2, y0 + 2)
        if random.random() < 0.25:
            m.set_cell(center.x, center.y, TerrType.WATER)
            for t in random.sample([t for t in mid if t != center and t.get_distance(center) == 1], random.randint(0, 2)):
                m.set_cell(t.x, t.y, TerrType.WATER)
        else:
            m.set_cell(center.x, center.y, TerrType.TREE)
            for t in random.sample([t for t in mid if t != center], random.randint(2, 5)):
                m.set_cell(t.x, t.y, TerrType.TREE)
        made += 1
    m.decorations = made
    return made
