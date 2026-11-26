import random
from support_classes import *

class Vault:
    def __init__(self, name, probability, find_location_func, place_func):
        self.name = name
        self.probability = probability
        self.find_location_func = find_location_func
        self.place_func = place_func

def find_desert_pyramid_location(game_map):
    valid = []
    for min_x in range(game_map.width-8):
        for min_y in range(game_map.height-8):
            max_x = min_x + 8
            max_y = min_y + 8
            loc_works = True
            for dx in range(9):
                for y in [min_y, max_y]:
                    if game_map.get_cell(min_x + dx, y) != TerrType.DESERT:
                        loc_works = False
                        break
            for dy in range(9):
                for x in [min_x, max_x]:
                    if game_map.get_cell(x, min_y + dy) != TerrType.DESERT:
                        loc_works = False
                        break
            if loc_works:
                valid.append(Coordinates(min_x + 4, min_y + 4))
    return random.choice(valid) if valid else None

def place_desert_pyramid(game_map, location):
    r1 = [location]
    r2 = []
    for dx in range(-1, 2):
        for dy in range(-1, 2):
            cell_loc = Coordinates(location.x + dx, location.y + dy)
            if cell_loc not in r1:
                r2.append(cell_loc)
    
    r3 = []
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            cell_loc = Coordinates(location.x + dx, location.y + dy)
            if cell_loc not in r1 and cell_loc not in r2:
                r3.append(cell_loc)
    
    r4 = []
    for dx in range(-3, 4):
        for dy in range(-3, 4):
            cell_loc = Coordinates(location.x + dx, location.y + dy)
            if cell_loc not in r1 and cell_loc not in r2 and cell_loc not in r3:
                r4.append(cell_loc)

    game_map.add_room(r1)
    game_map.add_room(r2)
    game_map.add_room(r3)
    game_map.add_room(r4)

    directions = ['up', 'down', 'left', 'right']
    latest_door = None
    for ring in range(0, 4):
        door_direction = random.choice([d for d in directions if d != latest_door])
        if door_direction == 'up':
            game_map.add_door(Coordinates(location.x, location.y + ring), Coordinates(location.x, location.y + ring + 1))
        elif door_direction == 'down':
            game_map.add_door(Coordinates(location.x, location.y - ring), Coordinates(location.x, location.y - ring - 1))
        elif door_direction == 'left':
            game_map.add_door(Coordinates(location.x - ring, location.y), Coordinates(location.x - ring - 1, location.y))
        elif door_direction == 'right':
            game_map.add_door(Coordinates(location.x + ring, location.y), Coordinates(location.x + ring + 1, location.y))
        latest_door = door_direction

    dead_ends = []
    for ring in [r2, r3, r4]:
        while True:
            wall_a = random.choice(ring)
            neighbors = wall_a.get_neighboring_coordinates()
            wall_b = random.choice([n for n in neighbors if n in ring and n != wall_a])
            if not game_map.is_door(wall_a, wall_b):  # don't wall off a ring's door
                break
        game_map.add_forced_wall(wall_a, wall_b)
        dead_ends.append(wall_a)
        dead_ends.append(wall_b)

    if random.random() < 0.5:
        dead_end_terr = TerrType.LAVA
    else:
        dead_end_terr = TerrType.WATER
    
    shrine_done = False
    for dead_end in dead_ends:
        if random.random() < 0.1:
            game_map.set_cell_contents(dead_end.x, dead_end.y, CellContents.GEM)
        elif random.random() < 0.1 and not shrine_done:
            game_map.set_cell_contents(dead_end.x, dead_end.y, CellContents.SHRINE)
            shrine_done = True
        elif random.random() < 0.5:
            game_map.set_cell_contents(dead_end.x, dead_end.y, CellContents.OGRE)
        else:
            game_map.set_cell(dead_end.x, dead_end.y, dead_end_terr)
    
    register_item_spot(game_map, location, 'Desert Pyramid')


# ---------------------------------------------------------------------------
# Item hiding places.
#
# A vault can register "item spots": set-piece places where an item should
# live (the centre of the pyramid, a temple in the deep forest, a hut on an
# island...). gem_placement.place_items_forward_fill puts items there first,
# and any spot left over gets a gem if the gem rules allow it.
# ---------------------------------------------------------------------------

SPAWN = Coordinates(0, 0)
VAULT_SPACING = 10          # between item spots of different vaults
OPEN_TERRAIN = (TerrType.GRASS, TerrType.DESERT, TerrType.TREE, TerrType.ROAD)


def register_item_spot(game_map, location, name):
    if not hasattr(game_map, 'vault_item_spots'):
        game_map.vault_item_spots = []
        game_map.vault_spot_names = {}
    game_map.vault_item_spots.append(location)
    game_map.vault_spot_names[location] = name


def _spots(game_map):
    return getattr(game_map, 'vault_item_spots', [])


def _diamond(c, r):
    return [Coordinates(c.x + dx, c.y + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1)
            if abs(dx) + abs(dy) <= r]


def _door_tiles(game_map):
    tiles = set()
    for a, b in game_map.doors:
        tiles.add(a)
        tiles.add(b)
    return tiles


def _castle_tiles(game_map):
    return [Coordinates(x, y) for y in range(game_map.height) for x in range(game_map.width)
            if game_map.get_cell(x, y) == TerrType.CASTLE]


def _near_castle(c, castle_box, margin):
    if castle_box is None:
        return False
    x0, y0, x1, y1 = castle_box
    return x0 - margin <= c.x <= x1 + margin and y0 - margin <= c.y <= y1 + margin


def _castle_box(game_map):
    tiles = _castle_tiles(game_map)
    if not tiles:
        return None
    return (min(t.x for t in tiles), min(t.y for t in tiles), max(t.x for t in tiles), max(t.y for t in tiles))


def _area_ok(game_map, tiles, terrains, doors):
    """Every tile is on the map, outdoors, empty, not a door end, and one of `terrains`."""
    for t in tiles:
        if not game_map.is_valid_coordinates(t):
            return False
        if game_map.get_room_number(t.x, t.y) != 0 or t in doors:
            return False
        if game_map.get_cell_contents(t.x, t.y) != CellContents.EMPTY:
            return False
        if game_map.get_cell(t.x, t.y) not in terrains:
            return False
    return True


def _site_ok(game_map, c, min_spawn=15):
    return (c.get_distance(SPAWN) >= min_spawn
            and all(c.get_distance(s) >= VAULT_SPACING for s in _spots(game_map)))


def _add_hut(game_map, footprint, door_choices):
    """Make a one-room building and give it one door to a random outside tile."""
    game_map.add_room(footprint)
    inside, outside = random.choice(door_choices)
    game_map.add_door(inside, outside)
    return inside


def _hut_doors(footprint):
    fp = set(footprint)
    return [(t, n) for t in footprint for n in t.get_neighboring_coordinates() if n not in fp]


def _farthest(tiles, frm):
    best = max(t.get_distance(frm) for t in tiles)
    return random.choice([t for t in tiles if t.get_distance(frm) == best])


# --- Forest temple: a small building deep in a forest, ringed by trees. ------
# Sometimes there is also a ring of lava between the trees and the temple
# ("behind a lava pit in the deep forest temple"), so you need Axe + Shield.
# A 1-wide lava ring is a knockback skip waiting to be found.

def find_forest_temple_location(game_map):
    doors = _door_tiles(game_map)
    box = _castle_box(game_map)
    scored = []
    for y in range(game_map.height):
        for x in range(game_map.width):
            c = Coordinates(x, y)
            if game_map.get_cell(x, y) not in (TerrType.TREE, TerrType.GRASS):
                continue
            if not _site_ok(game_map, c) or _near_castle(c, box, 3):
                continue
            area = _diamond(c, 3)
            trees = sum(1 for t in area if game_map.get_cell(t.x, t.y) == TerrType.TREE)
            if trees < 12:
                continue
            size = random.choice([1, 1, 2])
            footprint = [Coordinates(c.x + dx, c.y + dy) for dx in range(size) for dy in range(size)]
            zone = _dilate(footprint, 2)
            if not _area_ok(game_map, zone, OPEN_TERRAIN, doors):
                continue
            scored.append((trees, c, footprint))
    if not scored:
        return None
    scored.sort(key=lambda s: -s[0])
    trees, c, footprint = random.choice(scored[:8])
    return footprint


def _dilate(tiles, d):
    """Tiles within Chebyshev distance d of `tiles` (including them)."""
    out = set()
    for t in tiles:
        for dx in range(-d, d + 1):
            for dy in range(-d, d + 1):
                out.add(Coordinates(t.x + dx, t.y + dy))
    return list(out)


def _ring(tiles, d):
    """Tiles at Chebyshev distance exactly d from `tiles`."""
    inner = set(_dilate(tiles, d - 1)) if d > 0 else set(tiles)
    return [t for t in _dilate(tiles, d) if t not in inner]


def place_forest_temple(game_map, footprint):
    lava_pit = random.random() < 0.45
    for t in _ring(footprint, 1):
        game_map.set_cell(t.x, t.y, TerrType.LAVA if lava_pit else TerrType.GRASS)
    for t in _ring(footprint, 2):
        game_map.set_cell(t.x, t.y, TerrType.TREE)
    door_inside = _add_hut(game_map, footprint, _hut_doors(footprint))
    spot = _farthest(footprint, door_inside) if len(footprint) > 1 else footprint[0]
    register_item_spot(game_map, spot, 'Forest Temple (lava pit)' if lava_pit else 'Forest Temple')


# --- Lava shrine: a little altar ringed by lava (Flame Shield). -------------

def find_lava_shrine_location(game_map):
    doors = _door_tiles(game_map)
    box = _castle_box(game_map)
    width = random.choice([1, 1, 2])
    options = []
    for y in range(game_map.height):
        for x in range(game_map.width):
            c = Coordinates(x, y)
            if game_map.get_cell(x, y) not in (TerrType.GRASS, TerrType.DESERT):
                continue
            if not _site_ok(game_map, c, min_spawn=18) or _near_castle(c, box, 1):
                continue
            if _area_ok(game_map, _diamond(c, 2 + width), OPEN_TERRAIN + (TerrType.LAVA,), doors):
                options.append(c)
    if not options:
        return None
    return (random.choice(options), width)


def place_lava_shrine(game_map, location):
    c, width = location
    for t in _diamond(c, 1 + width):
        d = t.get_distance(c)
        game_map.set_cell(t.x, t.y, TerrType.GRASS if d <= 1 else TerrType.LAVA)
    register_item_spot(game_map, c, 'Lava Shrine')


# --- Island hut: a hut on a speck of land in the middle of the water (Boots).

def find_island_hut_location(game_map):
    options = []
    for y in range(game_map.height):
        for x in range(game_map.width):
            c = Coordinates(x, y)
            if game_map.get_cell(x, y) != TerrType.WATER or not _site_ok(game_map, c, min_spawn=12):
                continue
            for radius in (3, 2):   # 3: hut on a little island; 2: hut on stilts
                area = _diamond(c, radius)
                if all(game_map.is_valid_coordinates(t) and game_map.get_cell(t.x, t.y) == TerrType.WATER
                       and game_map.get_room_number(t.x, t.y) == 0 for t in area):
                    options.append((radius, c))
                    break
    if not options:
        # Rivers are rarely that wide; use one of the small islands the river
        # generator already made instead.
        options = [(0, c) for c in _small_island_tiles(game_map)]
    if not options:
        return None
    best = max(r for r, _ in options)
    return random.choice([o for o in options if o[0] == best])


def _small_island_tiles(game_map, max_size=30):
    """Empty outdoor grass tiles on small landmasses cut off by water (no
    bridge, no buildings), away from spawn and other vaults."""
    seen = set()
    out = []
    for y in range(game_map.height):
        for x in range(game_map.width):
            start = Coordinates(x, y)
            if start in seen or game_map.get_cell(x, y) == TerrType.WATER:
                continue
            region, stack, bad = [], [start], False
            seen.add(start)
            while stack:
                c = stack.pop()
                region.append(c)
                t = game_map.get_cell(c.x, c.y)
                if t in (TerrType.ROAD, TerrType.BUILDING, TerrType.CASTLE) or c == SPAWN:
                    bad = True
                for n in c.get_neighboring_coordinates():
                    if game_map.is_valid_coordinates(n) and n not in seen and game_map.get_cell(n.x, n.y) != TerrType.WATER:
                        seen.add(n)
                        stack.append(n)
            if bad or len(region) > max_size:
                continue
            out += [c for c in region if game_map.get_cell(c.x, c.y) == TerrType.GRASS
                    and game_map.get_cell_contents(c.x, c.y) == CellContents.EMPTY
                    and _site_ok(game_map, c, min_spawn=12)]
    return out


def place_island_hut(game_map, location):
    radius, c = location
    if radius == 3:
        for t in _diamond(c, 1):
            game_map.set_cell(t.x, t.y, TerrType.GRASS)
    # with radius 2 the hut's door opens straight onto the water
    _add_hut(game_map, [c], _hut_doors([c]))
    register_item_spot(game_map, c, 'Island Hut')


# --- Desert ruin: a hut 3+ tiles into the desert (Cloak). --------------------

def find_desert_ruin_location(game_map):
    doors = _door_tiles(game_map)
    options = []
    for y in range(game_map.height):
        for x in range(game_map.width):
            c = Coordinates(x, y)
            if game_map.get_cell(x, y) != TerrType.DESERT or not _site_ok(game_map, c):
                continue
            if _area_ok(game_map, _diamond(c, 2), (TerrType.DESERT,), doors):
                options.append(c)
    return random.choice(options) if options else None


def place_desert_ruin(game_map, c):
    _add_hut(game_map, [c], _hut_doors([c]))
    register_item_spot(game_map, c, 'Desert Ruin')


# --- Castle armory: the deepest room of the castle (behind the most doors). --

def _room_depths(game_map):
    """Room number -> fewest doors to walk through from outdoors."""
    links = {}
    for a, b in game_map.doors:
        ra = game_map.get_room_number(a.x, a.y)
        rb = game_map.get_room_number(b.x, b.y)
        if ra is None or rb is None or ra == rb:
            continue
        links.setdefault(ra, set()).add(rb)
        links.setdefault(rb, set()).add(ra)
    depth = {0: 0}
    frontier = [0]
    while frontier:
        nxt = []
        for r in frontier:
            for n in links.get(r, ()):
                if n not in depth:
                    depth[n] = depth[r] + 1
                    nxt.append(n)
        frontier = nxt
    return depth


def find_castle_armory_location(game_map):
    depth = _room_depths(game_map)
    rooms = {}
    boss_room = None
    for y in range(game_map.height):
        for x in range(game_map.width):
            if game_map.get_cell(x, y) != TerrType.CASTLE:
                continue
            r = game_map.get_room_number(x, y)
            rooms.setdefault(r, []).append(Coordinates(x, y))
            if game_map.get_cell_contents(x, y) == CellContents.BOSS:
                boss_room = r
    cands = [r for r in rooms if r != boss_room and r in depth]
    if not cands:
        return None
    deepest = max(depth[r] for r in cands)
    room = random.choice([r for r in cands if depth[r] == deepest])
    tiles = [t for t in rooms[room] if game_map.get_cell_contents(t.x, t.y) == CellContents.EMPTY]
    if not tiles:
        return None
    door_tiles = [t for t in rooms[room] if t in _door_tiles(game_map)] or tiles
    return max(tiles, key=lambda t: (min(t.get_distance(d) for d in door_tiles), random.random()))


def place_castle_armory(game_map, spot):
    register_item_spot(game_map, spot, 'Castle Armory')


# --- Castle moat: a ring of lava around the castle, so the boss needs the ---
# Flame Shield (or a knockback over a 1-wide moat, which is a skip).

def find_castle_moat_location(game_map):
    tiles = _castle_tiles(game_map)
    return tiles if tiles else None


def place_castle_moat(game_map, castle_tiles):
    width = random.choice([1, 2])
    for t in _dilate(castle_tiles, width):
        if not game_map.is_valid_coordinates(t):
            continue
        if game_map.get_room_number(t.x, t.y) != 0:
            continue
        if game_map.get_cell(t.x, t.y) in OPEN_TERRAIN and game_map.get_cell_contents(t.x, t.y) == CellContents.EMPTY:
            game_map.set_cell(t.x, t.y, TerrType.LAVA)
    game_map.castle_moat = width



# --- Hedge maze: a square of trees with a maze carved through it; the item
# sits at the dead end farthest from the entrance. Walkable with no items
# (the long way round); the Axe cuts straight in.

def find_hedge_maze_location(game_map):
    doors = _door_tiles(game_map)
    box = _castle_box(game_map)
    cells = random.choice([3, 4])
    size = 2 * cells + 1
    mid = 1 + 2 * (cells // 2)      # an odd offset, so the entrance meets a maze cell
    options = []
    for y0 in range(1, game_map.height - size - 1):
        for x0 in range(1, game_map.width - size - 1):
            c = Coordinates(x0 + size // 2, y0 + size // 2)
            if not _site_ok(game_map, c, min_spawn=16) or _near_castle(c, box, size):
                continue
            area = [Coordinates(x0 + dx, y0 + dy) for dx in range(size) for dy in range(size)]
            if not _area_ok(game_map, area, (TerrType.GRASS, TerrType.TREE), doors):
                continue
            sides = [(Coordinates(x0 + mid, y0), (0, -1)),
                     (Coordinates(x0 + mid, y0 + size - 1), (0, 1)),
                     (Coordinates(x0, y0 + mid), (-1, 0)),
                     (Coordinates(x0 + size - 1, y0 + mid), (1, 0))]
            good = []
            for e, d in sides:
                out = Coordinates(e.x + d[0], e.y + d[1])
                if (game_map.is_valid_coordinates(out)
                        and game_map.get_cell(out.x, out.y) in (TerrType.GRASS, TerrType.ROAD)
                        and game_map.get_room_number(out.x, out.y) == 0):
                    good.append(e)
            if good:
                options.append((x0, y0, cells, random.choice(good)))
    return random.choice(options) if options else None


def place_hedge_maze(game_map, location):
    x0, y0, cells, entrance = location
    size = 2 * cells + 1
    for dx in range(size):
        for dy in range(size):
            game_map.set_cell(x0 + dx, y0 + dy, TerrType.TREE)

    def cell_xy(i, j):
        return Coordinates(x0 + 1 + 2 * i, y0 + 1 + 2 * j)

    seen = {(0, 0)}
    stack = [(0, 0)]
    first = cell_xy(0, 0)
    game_map.set_cell(first.x, first.y, TerrType.GRASS)
    while stack:   # recursive backtracker
        i, j = stack[-1]
        nbrs = [(i + a, j + b) for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= i + a < cells and 0 <= j + b < cells and (i + a, j + b) not in seen]
        if not nbrs:
            stack.pop()
            continue
        ni, nj = random.choice(nbrs)
        a, b = cell_xy(i, j), cell_xy(ni, nj)
        game_map.set_cell((a.x + b.x) // 2, (a.y + b.y) // 2, TerrType.GRASS)
        game_map.set_cell(b.x, b.y, TerrType.GRASS)
        seen.add((ni, nj))
        stack.append((ni, nj))
    game_map.set_cell(entrance.x, entrance.y, TerrType.GRASS)
    # item on the open tile farthest (walking) from the entrance
    dist = {entrance: 0}
    queue = [entrance]
    for c in queue:
        for n in c.get_neighboring_coordinates():
            if (n not in dist and x0 <= n.x < x0 + size and y0 <= n.y < y0 + size
                    and game_map.get_cell(n.x, n.y) == TerrType.GRASS):
                dist[n] = dist[c] + 1
                queue.append(n)
    far = max(dist, key=lambda c: (dist[c], random.random()))
    register_item_spot(game_map, far, 'Hedge Maze')


# --- Snake gallery: a 1-wide walled corridor (a building) with a lava snake
# at the far end looking straight down it. The item sits right in front of
# the snake: reaching it means walking down the snake's line, so you need
# the Bow.

GALLERY_LEN = 5


def find_snake_gallery_location(game_map):
    doors = _door_tiles(game_map)
    box = _castle_box(game_map)
    options = []
    for y in range(game_map.height):
        for x in range(game_map.width):
            c = Coordinates(x, y)
            if not _site_ok(game_map, c, min_spawn=14) or _near_castle(c, box, 2):
                continue
            for d in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                p = (-d[1], d[0])
                line = [Coordinates(x + k * d[0], y + k * d[1]) for k in range(GALLERY_LEN + 1)]
                sides = [Coordinates(t.x + s * p[0], t.y + s * p[1]) for t in line for s in (1, -1)]
                behind = Coordinates(x - d[0], y - d[1])
                if not _area_ok(game_map, line + sides, OPEN_TERRAIN, doors):
                    continue
                if (not game_map.is_valid_coordinates(behind)
                        or game_map.get_cell(behind.x, behind.y) not in (TerrType.GRASS, TerrType.ROAD)
                        or game_map.get_room_number(behind.x, behind.y) != 0):
                    continue
                options.append((line, sides))
    return random.choice(options) if options else None


def place_snake_gallery(game_map, location):
    """A walled, 1-wide gallery building: its door is at the near end, a lava
    pit with a snake at the far end. Walls mean no item gets you round the
    snake's line: only the Bow does (Andrew's four-walls model)."""
    line, sides = location
    game_map.add_room(line)                     # BUILDING floor, walls all round
    behind = Coordinates(2 * line[0].x - line[1].x, 2 * line[0].y - line[1].y)
    game_map.add_door(line[0], behind)
    snake = line[-1]
    game_map.set_cell(snake.x, snake.y, TerrType.LAVA)
    game_map.set_cell_contents(snake.x, snake.y, CellContents.DRAGON)
    register_item_spot(game_map, line[-2], 'Snake Gallery')


# --- Oasis: a pond ringed by grass and a few palms, deep in the desert (Cloak).

def find_oasis_location(game_map):
    doors = _door_tiles(game_map)
    options = []
    for y in range(game_map.height):
        for x in range(game_map.width):
            c = Coordinates(x, y)
            if game_map.get_cell(x, y) != TerrType.DESERT or not _site_ok(game_map, c):
                continue
            if _area_ok(game_map, _diamond(c, 3), (TerrType.DESERT,), doors):
                options.append(c)
    return random.choice(options) if options else None


def place_oasis(game_map, c):
    for t in _diamond(c, 1):
        game_map.set_cell(t.x, t.y, TerrType.GRASS)
    game_map.set_cell(c.x, c.y, TerrType.WATER)
    for t in _diamond(c, 2):
        if t.get_distance(c) == 2 and random.random() < 0.35:
            game_map.set_cell(t.x, t.y, TerrType.TREE)   # a few palms
    register_item_spot(game_map, random.choice(c.get_neighboring_coordinates()), 'Oasis')


# --- Ogre camp: a clearing inside a palisade of trees with one gap, 2-3
# ogres, and something worth taking in the middle.

def find_ogre_camp_location(game_map):
    doors = _door_tiles(game_map)
    box = _castle_box(game_map)
    dirs = ((1, 0), (-1, 0), (0, 1), (0, -1))
    options = []
    for y in range(3, game_map.height - 3):
        for x in range(3, game_map.width - 3):
            c = Coordinates(x, y)
            if game_map.get_cell(x, y) != TerrType.GRASS or not _site_ok(game_map, c, min_spawn=18):
                continue
            if _near_castle(c, box, 4):
                continue
            if not _area_ok(game_map, _dilate([c], 3), OPEN_TERRAIN, doors):
                continue
            gaps = []
            for d in dirs:
                g = Coordinates(c.x + 3 * d[0], c.y + 3 * d[1])
                out = Coordinates(g.x + d[0], g.y + d[1])
                if (game_map.is_valid_coordinates(out)
                        and game_map.get_cell(out.x, out.y) in (TerrType.GRASS, TerrType.ROAD)
                        and game_map.get_room_number(out.x, out.y) == 0):
                    gaps.append(g)
            if gaps:
                options.append((c, random.choice(gaps)))
    return random.choice(options) if options else None


def place_ogre_camp(game_map, location):
    c, gap = location
    for t in _dilate([c], 2):
        game_map.set_cell(t.x, t.y, TerrType.GRASS)
    for t in _ring([c], 3):
        game_map.set_cell(t.x, t.y, TerrType.GRASS if t == gap else TerrType.TREE)
    inner = [t for t in _dilate([c], 2) if t.get_distance(c) >= 2]
    random.shuffle(inner)
    want = random.randint(2, 3)
    ogres = []
    for t in inner:
        if len(ogres) >= want:
            break
        if all(t.get_distance(o) >= 3 for o in ogres) and t.get_distance(gap) > 1:
            game_map.set_cell_contents(t.x, t.y, CellContents.OGRE)
            ogres.append(t)
    register_item_spot(game_map, c, 'Ogre Camp')

vaults = [
    # The moat goes first so other vaults never sit inside it.
    Vault('Castle Moat', 0.4, find_castle_moat_location, place_castle_moat),
    Vault('Castle Armory', 1.0, find_castle_armory_location, place_castle_armory),
    Vault('Desert Pyramid', 1.0, find_desert_pyramid_location, place_desert_pyramid),
    Vault('Forest Temple', 0.9, find_forest_temple_location, place_forest_temple),
    Vault('Lava Shrine', 0.7, find_lava_shrine_location, place_lava_shrine),
    Vault('Island Hut', 0.6, find_island_hut_location, place_island_hut),
    Vault('Desert Ruin', 0.5, find_desert_ruin_location, place_desert_ruin),
    Vault('Snake Gallery', 0.5, find_snake_gallery_location, place_snake_gallery),
    Vault('Hedge Maze', 0.5, find_hedge_maze_location, place_hedge_maze),
    Vault('Oasis', 0.5, find_oasis_location, place_oasis),
    Vault('Ogre Camp', 0.6, find_ogre_camp_location, place_ogre_camp),
    Vault('Forest Temple', 0.35, find_forest_temple_location, place_forest_temple),
]
