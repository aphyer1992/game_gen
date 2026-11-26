"""
Place Ghosts (CellContents.GHOST), which the Silver Sword is needed to hurt.

Ghosts roam like ogres in the simulator, but the verifier (play "as
intended") treats each one as blocking the tile it starts on until you hold
the Silver Sword (Andrew, 2026-11-23). Luring a ghost away to slip past is
speedrun tech, deliberately not modelled.

So a ghost gates something when its starting tile is a chokepoint: a
building doorway, a 1-wide corridor or trail. Like snake_placement:
  * candidates: floor/ground tiles with exactly two open neighbours (a
    corridor) or right inside a door, away from spawn, not in the boss room;
  * for a sample, see what you lose (holding every item but the Sword, gate
    treated as open) with a ghost there;
  * pick GATING_GHOSTS that cut off a pocket of MIN_POCKET+ clear tiles but no
    more than MAX_POCKET_FRACTION of the map, then a few wandering ghosts out
    in the open that cut off (almost) nothing.
Runs after snakes and before items, so items and gems see the Sword as a gate.
"""
import random

from support_classes import Coordinates, CellContents, TerrType
import verify

GATING_GHOSTS = (2, 3)
WANDER_GHOSTS = (1, 2)
MIN_POCKET = (12, 5)
MAX_POCKET_FRACTION = 0.35
WANDER_MAX_CUT = 2
SAMPLE = 50
MIN_SPACING = 6
START_CLEARANCE = 10
FLOOR = (TerrType.GRASS, TerrType.ROAD, TerrType.BUILDING, TerrType.CASTLE)


def place_ghosts(game_map):
    v = verify.Verifier(game_map)
    v.gate_mode = 'open'
    no_sword = frozenset(i for i in verify.TRAVERSAL_ITEMS if i != CellContents.SILVER_SWORD)
    boss_rooms = {game_map.get_room_number(x, y) for y in range(game_map.height) for x in range(game_map.width)
                  if game_map.get_cell_contents(x, y) in (CellContents.BOSS, CellContents.SEAL)}
    door_tiles = {c for pair in game_map.doors for c in pair}
    ghosts = list(v.ghosts)
    placed = {'gating': [], 'wander': []}

    def usable(c):
        return (game_map.get_cell(c.x, c.y) in FLOOR
                and game_map.get_cell_contents(c.x, c.y) == CellContents.EMPTY
                and game_map.get_room_number(c.x, c.y) not in boss_rooms
                and c.get_distance(verify.START) >= START_CLEARANCE)

    tiles = [Coordinates(x, y) for y in range(game_map.height) for x in range(game_map.width)]
    choke = [c for c in tiles if usable(c) and (
        (c in door_tiles and game_map.get_room_number(c.x, c.y) != 0)
        or len([n for n in v.neighbors[c] if game_map.get_cell(n.x, n.y) in FLOOR + (TerrType.DESERT,)]) == 2)]
    random.shuffle(choke)
    opened = [c for c in tiles if usable(c) and game_map.get_room_number(c.x, c.y) == 0]
    random.shuffle(opened)

    def spaced(c):
        return all(c.get_distance(g) >= MIN_SPACING for g in ghosts)

    def with_ghosts(gs):
        v.ghosts = list(gs)
        v._cache = {}

    def cut(c, base):
        with_ghosts(ghosts + [c])
        after = v.reachable(no_sword)
        with_ghosts(ghosts)
        return sum(1 for t in base - after if game_map.get_cell(t.x, t.y).clear_terrain)

    for _ in range(random.randint(*GATING_GHOSTS)):
        base = v.reachable(no_sword)
        scored = []
        for c in [c for c in choke if spaced(c)][:SAMPLE]:
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
        c = random.choice(good)
        ghosts.append(c)
        with_ghosts(ghosts)
        placed['gating'].append(c)

    want = random.randint(*WANDER_GHOSTS)
    base = v.reachable(no_sword)
    tried = 0
    for c in opened:
        if len(placed['wander']) >= want or tried >= SAMPLE:
            break
        if not spaced(c) or c not in base:
            continue
        tried += 1
        if cut(c, base) <= WANDER_MAX_CUT:
            ghosts.append(c)
            with_ghosts(ghosts)
            placed['wander'].append(c)
            base = v.reachable(no_sword)

    for c in placed['gating'] + placed['wander']:
        game_map.set_cell_contents(c.x, c.y, CellContents.GHOST)
    return placed
