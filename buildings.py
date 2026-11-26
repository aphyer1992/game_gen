"""
Give every medium-to-large building a purpose (Andrew, 2026-11-23).

A building (a connected block of BUILDING tiles, whatever its rooms) of at
least BIG tiles must do at least one of:
  * contain an access item,
  * contain a Power Gem, or
  * be a connector: walking through it opens up a real area (MIN_CONNECT
    tiles) that you couldn't reach otherwise, for some set of items you
    might be holding (none, any single item, or everything).

Runs after gems and before ogres. For each building with no purpose:
  1. Move a gem in: take a gem lying outdoors whose requirement (the items
     every route to it needs) is exactly the same as some free floor tile of
     the building, and move it there. The gating quotas are untouched.
  2. Otherwise move a gem from a less-needy spot whose requirement is a
     subset of the tile's (the gem gets a little harder to reach, never
     easier) as long as no target item's quota drops below what verify.py
     needs (re-checked by the verifier afterwards).
  3. Otherwise flood or set fire to an inner room: the floor just inside
     its door(s) becomes water or lava, so the rest of the room needs the
     Boots or the Shield, and move in an outdoor gem whose requirement is
     exactly that room's new requirement. If none fits, undo it.
  4. Otherwise leave it; measure.py counts what's left.
"""
import random

from support_classes import Coordinates, CellContents, TerrType
import verify

BIG = 12
from gem_placement import GEM_SPREAD   # keep moved gems this far from other gems
SHRINE_MOVE = 15        # a shrine this close may move into an empty vault spot
MAX_BONUS_GEMS = 3     # extra gems (beyond 20) allowed to fill otherwise-empty vaults
MIN_CONNECT = 15


def building_blocks(m):
    tiles = {Coordinates(x, y) for y in range(m.height) for x in range(m.width)
             if m.get_cell(x, y) == TerrType.BUILDING}
    seen, out = set(), []
    for t in tiles:
        if t in seen:
            continue
        comp, stack = [], [t]
        seen.add(t)
        while stack:
            c = stack.pop()
            comp.append(c)
            for n in c.get_neighboring_coordinates():
                if n in tiles and n not in seen:
                    seen.add(n)
                    stack.append(n)
        out.append(comp)
    return out


def _reach_without(v, tiles, items):
    """Reach while the given tiles are sealed off (patches the index in place)."""
    v._index()
    banned = {t.y * v.w + t.x for t in tiles}
    saved = (v._nbr, v._nbr_closed, v._cache)
    v._nbr = [[] if i in banned else [n for n in ns if n not in banned] for i, ns in enumerate(saved[0])]
    v._nbr_closed = [[] if i in banned else [n for n in ns if n not in banned] for i, ns in enumerate(saved[1])]
    v._cache = {}
    try:
        return v.stand_tiles(frozenset(items))
    finally:
        v._nbr, v._nbr_closed, v._cache = saved


def is_connector(v, block):
    sets = [frozenset()] + [frozenset([i]) for i in verify.TRAVERSAL_ITEMS] + [frozenset(verify.TRAVERSAL_ITEMS)]
    bset = set(block)
    for items in sets:
        full = v.stand_tiles(items)
        if not any(t in full for t in block):
            continue
        cut = _reach_without(v, block, items)
        if sum(1 for t in full - cut if t not in bset) >= MIN_CONNECT:
            return True
    return False


def has_purpose(m, v, block):
    for c in block:
        k = m.get_cell_contents(c.x, c.y)
        if k == CellContents.GEM or k in verify.ITEMS:
            return True
    return is_connector(v, block)


def ensure_purposeful_buildings(m):
    from gem_placement import _requirements
    v = verify.Verifier(m)
    blocks = [b for b in building_blocks(m) if len(b) >= BIG]
    report = {'big': len(blocks), 'fixed': 0, 'connectors': 0, 'left': 0}
    idle = []
    for b in blocks:
        if any(m.get_cell_contents(c.x, c.y) == CellContents.GEM or m.get_cell_contents(c.x, c.y) in verify.ITEMS
               for c in b):
            continue
        if is_connector(v, b):
            report['connectors'] += 1
            continue
        idle.append(b)
    if not idle:
        m.building_report = report
        return report

    gems = [Coordinates(x, y) for y in range(m.height) for x in range(m.width)
            if m.get_cell_contents(x, y) == CellContents.GEM]
    occupied = [Coordinates(x, y) for y in range(m.height) for x in range(m.width)
                if m.get_cell_contents(x, y) not in (CellContents.EMPTY, CellContents.FORCE_EMPTY)]
    floor = [c for b in idle for c in b if m.get_cell_contents(c.x, c.y) == CellContents.EMPTY]
    req = _requirements(v, floor + gems)
    castle_item = getattr(m, 'castle_item', None)   # must stay optional
    movable = [g for g in gems if g in req and m.get_room_number(g.x, g.y) == 0]   # outdoor gems only
    random.shuffle(movable)

    for b in idle:
        spots = [c for c in b if c in req and m.get_cell_contents(c.x, c.y) == CellContents.EMPTY
                 and all(c.get_distance(o) >= 2 for o in occupied)]
        random.shuffle(spots)
        done = False
        for exact in (True, False):
            for g in movable:
                for c in spots:
                    if any(c.get_distance(o) < GEM_SPREAD for o in gems if o != g):
                        continue
                    ok = req[g] == req[c] if exact else (req[g] <= req[c] and len(req[c]) - len(req[g]) <= 1
                                                         and castle_item not in req[c] - req[g])
                    if ok:
                        m.set_cell_contents(g.x, g.y, CellContents.EMPTY)
                        m.set_cell_contents(c.x, c.y, CellContents.GEM)
                        movable.remove(g)
                        occupied.append(c)
                        gems[gems.index(g)] = c
                        report['fixed'] += 1
                        done = True
                        break
                if done:
                    break
            if done:
                break
        if not done:
            done = _hazard_room(m, b, movable, occupied, v, req)
            if done:
                report['hazard_rooms'] = report.get('hazard_rooms', 0) + 1
        if not done:
            report['left'] += 1
    m.building_report = report
    return report


HAZARDS = [(TerrType.WATER, CellContents.WATER_BOOTS), (TerrType.LAVA, CellContents.FIRE_SHIELD)]


def _hazard_room(m, block, movable, occupied, v, gem_req):
    """Try 1-2 inner rooms of this building with water/lava just inside the door."""
    from gem_placement import _requirements
    if not movable:
        return False
    rooms = {}
    for c in block:
        rooms.setdefault(m.get_room_number(c.x, c.y), []).append(c)
    room_ids = list(rooms)
    random.shuffle(room_ids)
    tries = 0
    for r in room_ids:
        if tries >= 2:
            break
        tiles = rooms[r]
        inside_doors = {a if a in tiles else b for a, b in m.doors if (a in tiles) != (b in tiles)}
        gem_tiles = [o for o in occupied if m.get_cell_contents(o.x, o.y) == CellContents.GEM]
        rest = [c for c in tiles if c not in inside_doors
                and m.get_cell_contents(c.x, c.y) == CellContents.EMPTY
                and all(c.get_distance(o) >= 2 for o in occupied)
                and all(c.get_distance(o) >= GEM_SPREAD for o in gem_tiles)]
        if not inside_doors or not rest or any(m.get_cell_contents(d.x, d.y) != CellContents.EMPTY for d in inside_doors):
            continue
        for terr, item in random.sample(HAZARDS, len(HAZARDS)):
            # cheap check first: some outdoor gem must need this item at all
            if not any(item in gem_req.get(g, ()) for g in movable):
                continue
            tries += 1
            for d in inside_doors:
                _set(m, v, d, terr)
            spot = random.choice(rest)
            req = _requirements(v, [spot]).get(spot)
            match = [g for g in movable if req is not None and item in req and gem_req.get(g) == req]
            if match:
                g = match[0]
                m.set_cell_contents(g.x, g.y, CellContents.EMPTY)
                m.set_cell_contents(spot.x, spot.y, CellContents.GEM)
                movable.remove(g)
                occupied.append(spot)
                return True
            for d in inside_doors:
                _set(m, v, d, TerrType.BUILDING)
    return False


def _set(m, v, c, terr):
    """Change one tile and patch the verifier's index in place."""
    m.set_cell(c.x, c.y, terr)
    v._index()
    v._terr[c.y * v.w + c.x] = terr
    v._cache = {}


def ensure_vaults_filled(m):
    """Every vault's hiding place should hold something: a snake gallery or
    an ogre camp guarding nothing looks broken (playtest, 2026-11-24). Move in
    a gem (outdoors, or from a building that holds something else too) with
    the same requirement as the spot, or failing that one whose requirement
    is a subset of the spot's (it only gets harder to reach; never adding
    the castle item)."""
    from gem_placement import _requirements
    spots = [c for c in getattr(m, 'vault_item_spots', [])
             if m.get_cell_contents(c.x, c.y) == CellContents.EMPTY]
    report = {'empty_vaults': len(spots), 'filled': 0}
    if not spots:
        m.vault_report = report
        return report
    vault_set = set(getattr(m, 'vault_item_spots', []))
    gems = [Coordinates(x, y) for y in range(m.height) for x in range(m.width)
            if m.get_cell_contents(x, y) == CellContents.GEM]
    # Outdoor gems, plus gems from buildings that hold something else too.
    holders = {}
    for b in building_blocks(m):
        things = [c for c in b if m.get_cell_contents(c.x, c.y) == CellContents.GEM
                  or m.get_cell_contents(c.x, c.y) in verify.ITEMS]
        for c in b:
            holders[c] = len(things)
    movable = [g for g in gems if g not in vault_set
               and (m.get_room_number(g.x, g.y) == 0 or holders.get(g, 0) >= 2)]
    v = verify.Verifier(m)
    req = _requirements(v, spots + movable)
    castle_item = getattr(m, 'castle_item', None)
    random.shuffle(movable)
    for c in spots:
        if c not in req:
            continue
        done = False
        for exact in (True, False):
            for g in movable:
                if g not in req:
                    continue
                # Moving a gem somewhere that needs more items only makes the
                # gating stronger, so any superset is safe (castle item aside).
                ok = req[g] == req[c] if exact else (req[g] <= req[c] and castle_item not in req[c] - req[g])
                if ok:
                    m.set_cell_contents(g.x, g.y, CellContents.EMPTY)
                    m.set_cell_contents(c.x, c.y, CellContents.GEM)
                    movable.remove(g)
                    report['filled'] += 1
                    done = True
                    break
            if done:
                break
    # Last resort: a bonus gem (beyond the 20), if it can't stop any item that
    # is required to win from being required (gems reachable without it stay
    # below what the seals need).
    need = verify.GEMS_PER_SEAL * len(v.seals)
    gems_now = lambda: [Coordinates(x, y) for y in range(m.height) for x in range(m.width)
                        if m.get_cell_contents(x, y) == CellContents.GEM]
    without = {x: v.reachable(frozenset(i for i in verify.TRAVERSAL_ITEMS if i != x))
               for x in verify.TRAVERSAL_ITEMS}
    report['bonus'] = 0
    for c in spots:
        if m.get_cell_contents(c.x, c.y) != CellContents.EMPTY or report['bonus'] >= MAX_BONUS_GEMS:
            continue
        g_all = gems_now()
        ok = True
        for x, reach in without.items():
            count = sum(1 for g in g_all if g in reach)
            if count < need and c in reach and count + 1 >= need:
                ok = False
                break
        if ok:
            m.set_cell_contents(c.x, c.y, CellContents.GEM)
            report['bonus'] += 1
            report['filled'] += 1
    # Gem quotas are usually exactly tight (each required item has exactly
    # 15 gems reachable without it), so a bonus gem rarely fits. Instead move
    # the nearest shrine (not spawn) into the spot: a shrine at the end of a
    # glade trail or by an oasis is a fine reward.
    report['shrines_moved'] = 0
    names = getattr(m, 'vault_spot_names', {})
    for c in spots:
        if m.get_cell_contents(c.x, c.y) != CellContents.EMPTY:
            continue
        shrines = [Coordinates(x, y) for y in range(m.height) for x in range(m.width)
                   if m.get_cell_contents(x, y) == CellContents.SHRINE and (x, y) != (0, 0)
                   and Coordinates(x, y) not in vault_set]
        near = [sh for sh in shrines if sh.get_distance(c) <= SHRINE_MOVE]
        if near and c in v.reachable(frozenset(verify.TRAVERSAL_ITEMS)):
            sh = min(near, key=lambda t: t.get_distance(c))
            m.set_cell_contents(sh.x, sh.y, CellContents.EMPTY)
            m.set_cell_contents(c.x, c.y, CellContents.SHRINE)
            report['shrines_moved'] += 1
            report['filled'] += 1
            continue
        # Still nothing to guard: a hostile vault drops its guards.
        if names.get(c, '').startswith(('Ogre Camp', 'Snake Gallery')):
            for t in c.get_coordinates_in_range(3):
                if m.is_valid_coordinates(t) and m.get_cell_contents(t.x, t.y) in (CellContents.OGRE, CellContents.DRAGON):
                    m.set_cell_contents(t.x, t.y, CellContents.EMPTY)
    report['still_empty'] = report['empty_vaults'] - report['filled']
    m.vault_report = report
    return report
