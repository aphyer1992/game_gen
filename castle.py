"""
Make the castle a dangerous place worth entering (Andrew, 2026-11-23).

Runs after vaults and before snakes/items/gems:
  * Power Gems inside the castle. Usually (CORNER_CHANCE) one in each corner
    tower; otherwise 2-3 in random castle rooms, or sometimes just 1. They are
    part of the 20 (gem placement counts them), so fewer are scattered
    outside. They can't help open the gate, which needs gems from outside.
  * Lava traps: LAVA_TRAPS castle floor tiles become lava, never next to a
    door, never in the boss room, and never cutting any castle tile off from
    the gate (you can always walk round them, but an ogre's knockback can
    throw you in).
Castle ogres are placed later by ogre_placement (they need the final map).
"""
import random

from support_classes import Coordinates, CellContents, TerrType

CORNER_CHANCE = 0.6      # one gem per corner tower
SCATTER_CHANCE = 0.25    # else 2-3 gems in random rooms; else 1 gem
LAVA_TRAPS = (3, 6)


def _castle_info(m):
    tiles = [Coordinates(x, y) for y in range(m.height) for x in range(m.width)
             if m.get_cell(x, y) == TerrType.CASTLE]
    boss_rooms = {m.get_room_number(t.x, t.y) for t in tiles
                  if m.get_cell_contents(t.x, t.y) in (CellContents.BOSS, CellContents.SEAL)}
    floor = [t for t in tiles if m.get_room_number(t.x, t.y) not in boss_rooms]
    return tiles, floor


def _connected(adj, floor_set, start_tiles):
    """Castle floor tiles reachable from the gate's inside tiles without
    crossing walls (doors count) or lava. adj: tile -> open neighbours."""
    seen = set(t for t in start_tiles if t in floor_set)
    stack = list(seen)
    while stack:
        c = stack.pop()
        for n in adj.get(c, ()):
            if n in floor_set and n not in seen:
                seen.add(n)
                stack.append(n)
    return seen


def furnish_castle(m):
    tiles, floor = _castle_info(m)
    if not floor:
        return {}
    vault = set(getattr(m, 'vault_item_spots', []))
    door_tiles = {c for pair in m.doors for c in pair}
    gate_inside = [a for a, b in getattr(m, 'castle_gate', [])]
    report = {'gems': [], 'lava': []}

    def free(t):
        return (m.get_cell_contents(t.x, t.y) == CellContents.EMPTY and t not in vault
                and t not in gate_inside and m.get_cell(t.x, t.y) == TerrType.CASTLE)

    # --- gems ---------------------------------------------------------------
    roll = random.random()
    x0, y0 = min(t.x for t in tiles), min(t.y for t in tiles)
    x1, y1 = max(t.x for t in tiles), max(t.y for t in tiles)
    if roll < CORNER_CHANCE:
        for cx, cy in ((x0, y0), (x0, y1), (x1, y0), (x1, y1)):
            corner = Coordinates(cx, cy)
            options = sorted((t for t in floor if free(t)), key=lambda t: (t.get_distance(corner), random.random()))
            if options and options[0].get_distance(corner) <= 3:
                g = options[0]
                m.set_cell_contents(g.x, g.y, CellContents.GEM)
                report['gems'].append(g)
    else:
        rooms = {}
        for t in floor:
            if free(t):
                rooms.setdefault(m.get_room_number(t.x, t.y), []).append(t)
        want = random.randint(2, 3) if roll < CORNER_CHANCE + SCATTER_CHANCE else 1
        for r in random.sample(list(rooms), min(want, len(rooms))):
            g = random.choice(rooms[r])
            m.set_cell_contents(g.x, g.y, CellContents.GEM)
            report['gems'].append(g)
    m.castle_gems = list(report['gems'])

    # --- lava traps -----------------------------------------------------------
    floor_set = set(t for t in floor if m.get_cell(t.x, t.y) == TerrType.CASTLE)
    adj = {t: [n for n in t.get_neighboring_coordinates() if n in floor_set and not m.is_wall(t, n)]
           for t in floor_set}
    reach = _connected(adj, floor_set, gate_inside)
    want = random.randint(*LAVA_TRAPS)
    options = [t for t in floor_set if free(t) and t not in door_tiles
               and not any(n in door_tiles for n in t.get_neighboring_coordinates())]
    random.shuffle(options)
    for t in options:
        if len(report['lava']) >= want:
            break
        trial = floor_set - {t}
        if len(_connected(adj, trial, gate_inside)) == len(reach) - (1 if t in reach else 0):
            m.set_cell(t.x, t.y, TerrType.LAVA)
            floor_set = trial
            reach = reach - {t}
            report['lava'].append(t)
    return report
