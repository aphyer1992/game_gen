"""
Place Power Gems so that collecting enough of them needs most of the items.

The boss needs 16 gems (4 per seal). For an item X to be *required*, at most
15 gems may be reachable without X, i.e. at least TOTAL - 15 gems must sit
somewhere only X opens up: on an island (Boots), behind lava (Shield), inside
a forest (Axe), deep in a desert (Cloak), behind a lava snake (Bow), or a
combination ("behind lava AND deep in the desert" counts for both).

Algorithm:
  1. For every subset of the traversal items, flood-fill what's reachable
     (verify.Verifier.reachable, which knows the rules: walls, terrain, the
     1-tile desert rule, lava snakes).
  2. For each candidate tile, work out which items it *requires*: items that
     appear in every minimal set of items that reaches it.
  3. Greedily place gems on tiles that require the items that are still
     short of their quota (preferring, some of the time, combo tiles that
     require several), while never letting the number of gems reachable
     without some target item reach 16.
  4. Fill up to TOTAL with any tiles that keep that rule.

Gems a vault already placed (the Desert Pyramid) count towards the total.
Items that can't gate anything on this map (e.g. the Bow when there are no
lava snakes, or the Shield when no clear tile is behind lava) are skipped;
verify.py's criteria then decide whether the map is still good enough.
"""
import itertools
import random

from support_classes import Coordinates, CellContents
import verify

TOTAL_GEMS = 20
MIN_SPACING = 4          # preferred Manhattan distance between gems / other pickups
COMBO_PREFERENCE = 0.35  # chance to prefer a tile that requires 2+ short items
GATED_PREFERENCE = 0.8   # chance an item goes somewhere not reachable from spawn with no items


def assign_items_assumed_fill(game_map, locations, items):
    """Assign items to the given locations so every item is collectable.

    "Assumed fill", as used by game randomizers: go through the items in a
    random order; for each one, assume you already hold every item not yet
    placed, and put this item at a random free location reachable with those.
    The last item placed must therefore be reachable with nothing, the one
    before it with at most that one, and so on, so no item is ever locked
    behind itself. Returns a list of (location, item). Falls back to a random
    spot if nothing fits (the verifier will then reject the map).
    """
    v = verify.Verifier(game_map)
    order = list(items)
    random.shuffle(order)
    # Locations a vault picked (e.g. the Desert Pyramid's centre) are kept and
    # filled first; the generic random spots are only a fallback.
    vault_spots = [loc for loc in locations if game_map.get_cell_contents(loc.x, loc.y) == CellContents.ITEM
                   and loc in _vault_item_spots(game_map)]
    spare = [loc for loc in locations if loc not in vault_spots]
    for loc in locations:
        game_map.set_cell_contents(loc.x, loc.y, CellContents.EMPTY)
    unplaced = set(i for i in order if i in verify.TRAVERSAL_ITEMS)
    start_reach = v.reachable(frozenset())
    taken = [Coordinates(x, y) for y in range(game_map.height) for x in range(game_map.width)
             if game_map.get_cell_contents(x, y) not in (CellContents.EMPTY, CellContents.FORCE_EMPTY)]
    assignment = []
    for item in order:
        unplaced.discard(item)
        reach = v.reachable(frozenset(unplaced))
        others = taken + [l for l, _ in assignment]
        loc = None
        usable_vault = [s for s in vault_spots if s in reach]
        if usable_vault:
            loc = random.choice(usable_vault)
            vault_spots.remove(loc)
        else:
            # Prefer spots that are behind something (not reachable from spawn
            # with no items), so items end up gated behind other items.
            gated = random.random() < GATED_PREFERENCE
            loc = _fresh_spot(game_map, reach, others, avoid=start_reach if gated else None)
            if loc is None:
                loc = _fresh_spot(game_map, reach, others)
            if loc is None:
                loc = spare.pop() if spare else random.choice(list(reach))
        assignment.append((loc, item))
    return assignment


def _vault_item_spots(game_map):
    return getattr(game_map, 'vault_item_spots', [])


def _fresh_spot(game_map, reach, others, avoid=None):
    spots = [c for c in reach
             if (avoid is None or c not in avoid)
             and game_map.get_cell(c.x, c.y).clear_terrain
             and game_map.get_cell_contents(c.x, c.y) == CellContents.EMPTY
             and c != Coordinates(0, 0)]
    for spacing in (9, 6, 4, 2, 1):
        good = [c for c in spots if all(c.get_distance(o) >= spacing for o in others)]
        if good:
            return random.choice(good)
    return None


def _requirements(v, tiles):
    """tile -> frozenset of items required (present in every minimal set).
    Tiles unreachable even with every item are left out."""
    pool = verify.TRAVERSAL_ITEMS
    subsets = [frozenset(c) for r in range(len(pool) + 1) for c in itertools.combinations(pool, r)]
    reach = {s: v.reachable(s) for s in subsets}
    everything = reach[frozenset(pool)]
    result = {}
    for t in tiles:
        if t not in everything:
            continue
        minimal = []
        for s in subsets:  # ordered by size, so the first hits are minimal
            if t in reach[s] and not any(m <= s for m in minimal):
                minimal.append(s)
        required = frozenset.intersection(*minimal) if minimal else frozenset()
        result[t] = required
    return result


def place_gated_gems(game_map, total=TOTAL_GEMS, need=None):
    v = verify.Verifier(game_map)
    if need is None:
        need = verify.GEMS_PER_SEAL * max(1, len(v.seals))
    quota = total - (need - 1)   # gems that must require X so that <= need-1 are reachable without X

    occupied = []
    existing_gems = []
    for y in range(game_map.height):
        for x in range(game_map.width):
            c = game_map.get_cell_contents(x, y)
            if c == CellContents.GEM:
                existing_gems.append(Coordinates(x, y))
            if c not in (CellContents.EMPTY, CellContents.FORCE_EMPTY):
                occupied.append(Coordinates(x, y))

    candidates = [Coordinates(x, y) for y in range(game_map.height) for x in range(game_map.width)
                  if game_map.get_cell(x, y).clear_terrain
                  and game_map.get_cell_contents(x, y) == CellContents.EMPTY]
    req = _requirements(v, candidates + existing_gems)

    # Which items can gate anything at all on this map?
    targets = [item for item in verify.TRAVERSAL_ITEMS
               if sum(1 for t in candidates if t in req and item in req[t]) >= quota]

    placed = [g for g in existing_gems if g in req]
    requiring = {item: sum(1 for g in placed if item in req[g]) for item in targets}
    not_requiring = {item: len(placed) - requiring[item] for item in targets}

    def allowed(t):
        # Never let gems reachable without a target item reach `need`.
        return all(item in req[t] or not_requiring[item] < need - 1 for item in targets)

    def spaced(t, spacing):
        return all(t.get_distance(o) >= spacing for o in occupied)

    def put(t):
        game_map.set_cell_contents(t.x, t.y, CellContents.GEM)
        placed.append(t)
        occupied.append(t)
        for item in targets:
            if item in req[t]:
                requiring[item] += 1
            else:
                not_requiring[item] += 1

    pool = [t for t in candidates if t in req]
    random.shuffle(pool)

    # Phase 1: meet each target item's quota.
    for spacing in (MIN_SPACING, 2, 1):
        while True:
            short = {item for item in targets if requiring[item] < quota}
            if not short or len(placed) >= total:
                break
            options = [t for t in pool if t not in placed and req[t] & short and allowed(t) and spaced(t, spacing)]
            if not options:
                break
            if random.random() < COMBO_PREFERENCE:
                best = max(len(req[t] & short) for t in options)
                options = [t for t in options if len(req[t] & short) == best]
            put(random.choice(options))

    # Phase 2: fill up to the total with anything that keeps every target required.
    for spacing in (MIN_SPACING, 2, 1):
        while len(placed) < total:
            options = [t for t in pool if t not in placed and allowed(t) and spaced(t, spacing)]
            if not options:
                break
            put(random.choice(options))

    return {
        'targets': targets,
        'requiring': requiring,
        'placed': len(placed),
    }
