"""
Place lava snakes (CellContents.DRAGON) so that the Bow really gates something.

Model (verify.py, Andrew's "four walls", 2026-11-23): without the Bow a snake
walls off the step between A and B on each of its four sides (B next to it,
A one further out) and its own tile is impassable. You can step past it
sideways, and once you stand on a B you kill it in melee. So a snake out in
the open blocks nothing; a snake at the bend of a 1-wide hallway, where the
only way on is to walk straight down its line, needs the Bow.

Candidates:
  * lava tiles (outdoors, away from spawn), as before, and
  * hallway spots: a tree tile S just past a bend in a 1-wide path (the path
    comes along A -> B and turns at B; S is straight ahead of it). Choosing
    one turns S into a lava pool with a snake in it. The carved trails,
    glade trails and hedge mazes are full of such bends.

For a random sample of candidates, see what you lose (holding every item
except the Bow) if a snake sits there. Pick GATING_SNAKES that cut off a
pocket of at least MIN_POCKET clear tiles (falling back to smaller ones), but
never more than MAX_POCKET_FRACTION of what's reachable, preferring hallway
spots. Then add a few decorative snakes in lava that cut off (almost) nothing:
they still breathe fire at careless runners.

Runs after vaults and before items/gems, so item and gem placement see the Bow
as a real gate.
"""
import random

from support_classes import Coordinates, CellContents, TerrType
import verify

GATING_SNAKES = (2, 3)       # snakes that cut off a pocket
DECOR_SNAKES = (1, 3)        # extra snakes in lava that don't
MIN_POCKET = (12, 5)         # clear tiles a gating snake must cut off (preferred, fallback)
MAX_POCKET_FRACTION = 0.35   # ...but no more than this share of the reachable map
DECOR_MAX_CUT = 2            # a decorative snake may cut off at most this many tiles
SAMPLE = 50                  # candidates scored per round (each is a flood fill or two)
HALL_SHARE = 0.6             # of the sample, this share are hallway spots (if there are enough)
MIN_SPACING = 4              # between snakes
START_CLEARANCE = 8          # keep snakes this far from the spawn shrine
GROUND = (TerrType.GRASS, TerrType.ROAD, TerrType.DESERT, TerrType.BUILDING, TerrType.CASTLE)
WALLED = (TerrType.BUILDING, TerrType.CASTLE)   # hallway spots inside rooms: no item gets around these walls
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]


def _hallway_spots(game_map, v, boss_rooms=()):
    """Tiles straight ahead of a bend in a 1-wide path: a tree outdoors, or a
    floor tile inside a building/castle room (which becomes a lava pit)."""
    out = []
    for y in range(game_map.height):
        for x in range(game_map.width):
            s = Coordinates(x, y)
            terr = game_map.get_cell(x, y)
            room = game_map.get_room_number(x, y)
            outdoor_tree = terr == TerrType.TREE and room == 0
            indoor = terr in WALLED and room != 0 and room not in boss_rooms
            if (not (outdoor_tree or indoor)
                    or game_map.get_cell_contents(x, y) != CellContents.EMPTY
                    or s.get_distance(verify.START) < START_CLEARANCE):
                continue
            for d in DIRS:
                b = Coordinates(x + d[0], y + d[1])
                a = Coordinates(x + 2 * d[0], y + 2 * d[1])
                if not (game_map.is_valid_coordinates(a) and b in v.neighbors[s] and a in v.neighbors[b]):
                    continue
                if game_map.get_cell(b.x, b.y) not in GROUND or game_map.get_cell(a.x, a.y) not in GROUND:
                    continue
                # B turns a corner: a side neighbour is open, and the hallway is
                # narrow at A (both of A's side neighbours are blocked)
                p = (-d[1], d[0])
                side_b = [Coordinates(b.x + k * p[0], b.y + k * p[1]) for k in (1, -1)]
                side_a = [Coordinates(a.x + k * p[0], a.y + k * p[1]) for k in (1, -1)]
                open_b = [t for t in side_b if t in v.neighbors[b] and game_map.get_cell(t.x, t.y) in GROUND]
                blocked_a = [t for t in side_a if t not in v.neighbors[a] or game_map.get_cell(t.x, t.y) not in GROUND]
                if indoor:   # S must not be B's only way on, or the pit seals the room
                    if not open_b or len(blocked_a) != 2:
                        continue
                if open_b and len(blocked_a) == 2:
                    out.append(s)
                    break
    return out


def place_lava_snakes(game_map):
    v = verify.Verifier(game_map)
    v.gate_mode = 'open'   # no gems yet: judge the castle as if you could open the gate
    no_bow = frozenset(i for i in verify.TRAVERSAL_ITEMS if i != CellContents.BOW)
    snakes = list(v.snakes)
    placed = {'gating': [], 'decor': [], 'hallway': []}
    boss_rooms = {game_map.get_room_number(x, y) for y in range(game_map.height) for x in range(game_map.width)
                  if game_map.get_cell_contents(x, y) in (CellContents.BOSS, CellContents.SEAL)}
    lava = [Coordinates(x, y) for y in range(game_map.height) for x in range(game_map.width)
            if game_map.get_cell(x, y) == TerrType.LAVA
            and game_map.get_cell_contents(x, y) == CellContents.EMPTY
            and game_map.get_room_number(x, y) == 0   # not in the boss room or a vault
            and Coordinates(x, y).get_distance(verify.START) >= START_CLEARANCE]
    random.shuffle(lava)
    halls = _hallway_spots(game_map, v, boss_rooms)
    random.shuffle(halls)

    def set_terrain(c, terr):
        """Change one tile and patch the verifier's index in place (a full
        rebuild per candidate was most of the generation time)."""
        game_map.set_cell(c.x, c.y, terr)
        v._index()
        v._terr[c.y * v.w + c.x] = terr
        v._cache = {}

    def clear(t):
        return game_map.get_cell(t.x, t.y).clear_terrain

    def spaced(c):
        return all(c.get_distance(s) >= MIN_SPACING for s in snakes)

    def cut(c, base):
        """Clear tiles lost (vs `base`, the reach without it) if a snake sits at c."""
        old = game_map.get_cell(c.x, c.y)
        if old != TerrType.LAVA:
            set_terrain(c, TerrType.LAVA)
        v.set_snakes(snakes + [c])
        after = v.reachable(no_bow)
        if old != TerrType.LAVA:
            set_terrain(c, old)
        v.set_snakes(snakes)
        return sum(1 for t in base - after if clear(t))

    def commit(c, kind):
        if game_map.get_cell(c.x, c.y) != TerrType.LAVA:
            set_terrain(c, TerrType.LAVA)
            placed['hallway'].append(c)
        snakes.append(c)
        v.set_snakes(snakes)
        placed[kind].append(c)

    want_gate = random.randint(*GATING_SNAKES)
    for _ in range(want_gate):
        n_hall = int(SAMPLE * HALL_SHARE)
        cands = [c for c in halls if spaced(c)][:n_hall]
        cands += [c for c in lava if spaced(c)][:SAMPLE - len(cands)]
        base = v.reachable(no_bow)
        scored = []
        for c in cands:
            lost = cut(c, base)
            if lost <= MAX_POCKET_FRACTION * len(base):
                scored.append((c, lost))
        good = []
        for floor in MIN_POCKET:
            good = [c for c, lost in scored if lost >= floor]
            if good:
                break
        if not good:
            break
        hall_good = [c for c in good if c in halls]
        c = random.choice(hall_good or good)
        commit(c, 'gating')

    want_decor = random.randint(*DECOR_SNAKES)
    base = v.reachable(no_bow)
    tried = 0
    for c in lava:
        if len(placed['decor']) >= want_decor or tried >= SAMPLE:
            break
        if c in snakes or not spaced(c):
            continue
        tried += 1
        if cut(c, base) <= DECOR_MAX_CUT:
            commit(c, 'decor')
            base = v.reachable(no_bow)

    for c in placed['gating'] + placed['decor']:
        game_map.set_cell_contents(c.x, c.y, CellContents.DRAGON)
    return placed
