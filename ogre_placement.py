"""
Place Ogres. Runs last in generate_map, after items and gems.

Two kinds:
  * Guards (GUARD_OGRES): in the same building/castle room as an item or a
    gem, 2-3 tiles from it if the room has space, otherwise just outside the
    room's door. Items are guarded before gems.
  * Castle garrison (CASTLE_OGRES): on castle floor, not by the gate or in
    the boss room.
  * Wanderers (RANDOM_OGRES): on outdoor tiles. About half of them are put
    where they can launch you: a tile two steps from a 1-wide strip of
    water or lava with land beyond, so an ogre hit there can knock you over
    it (a skip for players to find).

The Desert Pyramid's dead-end ogres are kept and count towards the spacing.
Ogres never start within SPAWN_CLEARANCE of spawn, on a pickup, next to a
shrine, in the boss room, or on water/lava/trees. The verifier ignores ogres
(they can be killed, and the beatability check never relies on knockback),
so they can't make a map unbeatable.
"""
import random

from support_classes import Coordinates, CellContents, TerrType

GUARD_OGRES = (3, 5)
RANDOM_OGRES = (2, 2)     # wanderers outdoors (playtest 2026-11-24: more were just clutter)
CASTLE_OGRES = (3, 5)     # garrison inside the castle (not the boss room)
LAUNCHER_SHARE = 1.0      # wanderers stand where a hit can knock you over a 1-wide hazard (when such a spot exists)
SPAWN_CLEARANCE = 10
OGRE_SPACING = 4
HAZARDS = (TerrType.WATER, TerrType.LAVA)
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
ITEM_KINDS = (CellContents.WATER_BOOTS, CellContents.FIRE_SHIELD, CellContents.AXE,
              CellContents.DESERT_CLOAK, CellContents.BOW, CellContents.BLESSING,
              CellContents.SILVER_SWORD, CellContents.HORSE)


def _land(m, c):
    return m.is_valid_coordinates(c) and m.get_cell(c.x, c.y) not in HAZARDS + (TerrType.TREE,)


def place_ogres(m):
    tiles = [Coordinates(x, y) for y in range(m.height) for x in range(m.width)]
    rooms = {}
    for t in tiles:
        rooms.setdefault(m.get_room_number(t.x, t.y), []).append(t)
    boss_rooms = {m.get_room_number(t.x, t.y) for t in tiles
                  if m.get_cell_contents(t.x, t.y) in (CellContents.BOSS, CellContents.SEAL)}
    shrines = [t for t in tiles if m.get_cell_contents(t.x, t.y) == CellContents.SHRINE]
    ogres = [t for t in tiles if m.get_cell_contents(t.x, t.y) == CellContents.OGRE]
    start = Coordinates(0, 0)

    def ok(t):
        return (_land(m, t)
                and m.get_cell_contents(t.x, t.y) == CellContents.EMPTY
                and m.get_room_number(t.x, t.y) not in boss_rooms
                and t.get_distance(start) >= SPAWN_CLEARANCE
                and all(t.get_distance(s) >= 2 for s in shrines)
                and all(t.get_distance(o) >= OGRE_SPACING for o in ogres))

    def put(t, kind):
        m.set_cell_contents(t.x, t.y, CellContents.OGRE)
        ogres.append(t)
        placed[kind].append(t)

    placed = {'guard': [], 'wander': [], 'castle': []}

    # Guards
    targets = []
    for kinds in (ITEM_KINDS, (CellContents.GEM,)):
        group = [t for t in tiles if m.get_cell_contents(t.x, t.y) in kinds
                 and m.get_room_number(t.x, t.y) != 0
                 and m.get_room_number(t.x, t.y) not in boss_rooms]
        random.shuffle(group)
        targets += group
    want = random.randint(*GUARD_OGRES)
    for target in targets:
        if len(placed['guard']) >= want:
            break
        room = m.get_room_number(target.x, target.y)
        inside = [t for t in rooms[room] if ok(t) and 2 <= t.get_distance(target) <= 3]
        if inside:
            put(random.choice(inside), 'guard')
            continue
        members = set(rooms[room])
        outside = [b if a in members else a for a, b in m.doors if (a in members) != (b in members)]
        outside = [t for t in outside if ok(t)]
        if outside:
            put(random.choice(outside), 'guard')

    # Wanderers
    outdoor = [t for t in tiles if m.get_room_number(t.x, t.y) == 0]

    def launcher(t):
        for dx, dy in DIRS:
            p = Coordinates(t.x + dx, t.y + dy)
            h = Coordinates(t.x + 2 * dx, t.y + 2 * dy)
            land = Coordinates(t.x + 3 * dx, t.y + 3 * dy)
            if (_land(m, p) and m.is_valid_coordinates(h) and m.get_cell(h.x, h.y) in HAZARDS
                    and _land(m, land)):
                return True
        return False

    want = random.randint(*RANDOM_OGRES)
    for _ in range(want):
        options = [t for t in outdoor if ok(t)]
        if random.random() < LAUNCHER_SHARE:
            options = [t for t in options if launcher(t)] or options
        if not options:
            break
        put(random.choice(options), 'wander')

    # Castle garrison: the castle should be dangerous (Andrew, 2026-11-23).
    gate_inside = [a for a, b in getattr(m, 'castle_gate', [])]
    castle = [t for t in tiles if m.get_cell(t.x, t.y) == TerrType.CASTLE
              and all(t.get_distance(g) >= 3 for g in gate_inside)]
    placed['castle'] = []
    for _ in range(random.randint(*CASTLE_OGRES)):
        options = [t for t in castle if ok(t)]
        if not options:
            break
        put(random.choice(options), 'castle')
    return placed
