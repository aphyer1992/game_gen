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

from support_classes import Coordinates, CellContents, TerrType
import verify

TOTAL_GEMS = 20
MIN_SPACING = 6          # preferred Manhattan distance between gems / other pickups
CLUMP_RADIUS, CLUMP_MAX = 3, 1      # no gem within 3 tiles of another, except as a last resort
SPACING_STEPS = (6, 5, 4, 3, 2, 1)   # relaxed one step at a time (was 4 -> 2 -> 1, which bunched gems up)
COMBO_PREFERENCE = 0.35  # chance to prefer a tile that requires 2+ short items
GATED_PREFERENCE = 0.8   # chance an item goes somewhere not reachable from spawn with no items
SPAWN_GEM_CLEARANCE = 8   # filler gems avoid this radius around spawn when they can
GEM_SPREAD = 5                   # gems moved/steered into buildings keep this far from other gems
IDLE_BUILDING_PREFERENCE = 0.8   # chance a gem pick goes to a big building that holds nothing yet
GEM_TOURNAMENT = 3        # gems: best-hidden of this many random valid tiles
SOFT_QUOTA = 2           # items that can't gate a full quota (often the Bow) still guard this many gems


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
    v.gate_mode = 'open'   # no gems yet: treat the castle (and its gems) as enterable
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
    # Vault hiding places that didn't get an item get first pick of the gems.
    vault_left = [t for t in getattr(game_map, 'unused_vault_spots', [])
                  if game_map.get_cell_contents(t.x, t.y) == CellContents.EMPTY]
    candidates += [t for t in vault_left if t not in candidates]
    req = _requirements(v, candidates + existing_gems)
    # Gems, like items, lean toward interesting places (rooms, tree cover,
    # away from spawn): each pick is the best-hidden of a few random options.
    interest = spot_scores(game_map)

    # Big buildings that hold nothing yet get first pick (buildings.py: every
    # medium-to-large building should hold a gem or item, or connect areas).
    from buildings import building_blocks, BIG
    block_of = {}
    for b in building_blocks(game_map):
        if len(b) >= BIG and not any(game_map.get_cell_contents(c.x, c.y) == CellContents.GEM
                                     or game_map.get_cell_contents(c.x, c.y) in verify.ITEMS for c in b):
            for c in b:
                block_of[c] = id(b)
    idle_blocks = set(block_of.values())

    def pick(options):
        # (only tiles well clear of other gems, so gems don't bunch up in
        # neighbouring buildings: playtest of seed 13, 2026-11-24)
        idle = [t for t in options if block_of.get(t) in idle_blocks
                and all(t.get_distance(g) >= GEM_SPREAD for g in placed)]
        if idle and random.random() < IDLE_BUILDING_PREFERENCE:
            options = idle
        sample = random.sample(options, min(GEM_TOURNAMENT, len(options)))
        return max(sample, key=lambda t: interest.get(t, 0) + random.uniform(0, 1))

    # Which items can gate anything at all on this map?
    gate_count = {item: sum(1 for t in candidates if t in req and item in req[t])
                  for item in verify.TRAVERSAL_ITEMS}
    targets = [item for item in verify.TRAVERSAL_ITEMS if gate_count[item] >= quota]
    # "Soft" targets can't be made strictly required (too few tiles behind
    # them, e.g. a small snake pocket), but should still guard a few gems.
    soft = [item for item in verify.TRAVERSAL_ITEMS
            if item not in targets and gate_count[item] >= 1]

    # The castle item (if any) must stay optional: at most total - need gems
    # may require it, and it should guard CASTLE_ITEM_GEMS of them.
    opt = getattr(game_map, 'castle_item', None)
    targets = [i for i in targets if i != opt]
    soft = [i for i in soft if i != opt]
    opt_cap = total - need
    opt_count = [0]

    placed = [g for g in existing_gems if g in req]
    requiring = {item: sum(1 for g in placed if item in req[g]) for item in targets}
    not_requiring = {item: len(placed) - requiring[item] for item in targets}

    def allowed(t):
        # Never let gems reachable without a target item reach `need`, and
        # never make the castle item required.
        if opt is not None and opt in req[t] and opt_count[0] >= opt_cap:
            return False
        return all(item in req[t] or not_requiring[item] < need - 1 for item in targets)

    clump_ok = [False]

    def spaced(t, spacing):
        if not (spacing == 1 and clump_ok[0]) and sum(1 for g in placed if t.get_distance(g) <= CLUMP_RADIUS) >= CLUMP_MAX:
            return False   # no clumps (only the final fill, as a last resort, may break this)
        return all(t.get_distance(o) >= spacing for o in occupied)

    def put(t):
        game_map.set_cell_contents(t.x, t.y, CellContents.GEM)
        placed.append(t)
        occupied.append(t)
        idle_blocks.discard(block_of.get(t))
        if opt is not None and opt in req[t]:
            opt_count[0] += 1
        for item in targets:
            if item in req[t]:
                requiring[item] += 1
            else:
                not_requiring[item] += 1

    pool = [t for t in candidates if t in req]
    random.shuffle(pool)

    # Phase 1: meet each target item's quota.
    for spacing in SPACING_STEPS:
        while True:
            short = {item for item in targets if requiring[item] < quota}
            if not short or len(placed) >= total:
                break
            options = [t for t in pool if t not in placed and req[t] & short and allowed(t) and spaced(t, spacing)]
            if not options:
                break
            options = [t for t in options if t in vault_left] or options
            if random.random() < COMBO_PREFERENCE:
                best = max(len(req[t] & short) for t in options)
                options = [t for t in options if len(req[t] & short) == best]
            put(pick(options))

    # Phase 1b: put a few gems behind the soft targets (and the castle item) too.
    for item in soft + ([opt] if opt is not None else []):
        have = sum(1 for g in placed if item in req[g])
        quota = CASTLE_ITEM_GEMS if item == opt else SOFT_QUOTA
        for spacing in SPACING_STEPS:
            while have < quota and len(placed) < total:
                options = [t for t in pool if t not in placed and item in req[t]
                           and allowed(t) and spaced(t, spacing)]
                if not options:
                    break
                put(pick([t for t in options if t in vault_left] or options))
                have += 1

    # Phase 2: fill up to the total with anything that keeps every target required.
    # Order of last resorts: drop a target's strict quota first, then allow
    # gems close together, then let the castle item become needed.
    dropped = []
    while True:
        for spacing in SPACING_STEPS:
            while len(placed) < total:
                options = [t for t in pool if t not in placed and allowed(t) and spaced(t, spacing)]
                if not options:
                    break
                # leftover vaults first, then keep gems out of the spawn area if possible
                options = ([t for t in options if t in vault_left]
                           or [t for t in options if t.get_distance(verify.START) >= SPAWN_GEM_CLEARANCE]
                           or options)
                if clump_ok[0]:   # last resort: as far from other gems as possible
                    far = lambda t: min((t.get_distance(g) for g in placed), default=99)
                    best = max(far(t) for t in options)
                    options = [t for t in options if far(t) == best]
                put(pick(options))
        if len(placed) >= total:
            break
        if not targets:
            if not clump_ok[0]:
                clump_ok[0] = True
                continue
            if opt_cap >= total:
                break
            opt_cap = total   # last resort: always place all 20, even if the castle item becomes needed
            continue
        # Stuck short of the total (seed 41: the next gem would have had to
        # need Boots, Shield and Bow at once, and no tile does). Always place
        # every gem: give up the strict quota of the target furthest from it.
        worst = min(targets, key=lambda i: (requiring[i], random.random()))
        targets.remove(worst)
        dropped.append(worst)

    return {
        'targets': targets,
        'soft': soft,
        'requiring': requiring,
        'placed': len(placed),
        'dropped': dropped,
    }


# ---------------------------------------------------------------------------
# Forward fill: place items one progression step at a time, in hiding places.
#
# Andrew's goals: items should be spread out and hidden (in buildings, ringed
# by trees, on islands, behind lava, in vaults), few should lie in the open
# near spawn, and at every point 1-2 new access-gating items should be
# collectable with what you have.
#
#   step 0: R0 = what you can reach with nothing. Put 1-2 traversal items in
#           the best hiding places in R0.
#   step s: Rs = reach with every item placed so far. Put 1-2 more items in
#           the best hiding places in Rs - R(s-1) (the area the last items
#           opened up), so each step is exactly one verifier "sphere".
# The items for a step are chosen so that, together with what's held, they
# open up somewhere new for the next step's items.
# The Blessing (never needed to reach anything) goes into a leftover vault or
# a later step's area. Leftover vault spots are given gems if possible.
# ---------------------------------------------------------------------------

TWO_ITEM_STEP = 0.45            # chance a step offers 2 traversal items instead of 1
ITEM_SPACING = (12, 9, 6, 4, 2, 0)   # preferred distance between items, relaxed if needed
PICKUP_CLEARANCE = 2            # from shrines/gems/seals/other contents
SPOT_NOISE = 2.5                # randomness when ranking hiding places
VAULT_SCORE = 10.0


def spot_scores(game_map, vault_spots=()):
    """Every tile an item may go on -> how well hidden it is (higher = better)."""
    from vaults import _room_depths
    depth = _room_depths(game_map)
    boss_rooms = {game_map.get_room_number(x, y) for y in range(game_map.height) for x in range(game_map.width)
                  if game_map.get_cell_contents(x, y) in (CellContents.BOSS, CellContents.SEAL)}
    vault_spots = set(vault_spots)
    scores = {}
    for y in range(game_map.height):
        for x in range(game_map.width):
            c = Coordinates(x, y)
            terr = game_map.get_cell(x, y)
            room = game_map.get_room_number(x, y)
            if c == verify.START or game_map.get_cell_contents(x, y) != CellContents.EMPTY:
                continue
            if not (terr.clear_terrain or terr == TerrType.CASTLE) or room in boss_rooms and room != 0:
                continue
            s = 0.0
            if c in vault_spots:
                s += VAULT_SCORE
            if room != 0:
                s += 3 + min(depth.get(room, 1) - 1, 2)   # deeper rooms hide things better
            cover = 0
            for t in c.get_coordinates_in_range(2):
                if t != c and game_map.is_valid_coordinates(t):
                    tt = game_map.get_cell(t.x, t.y)
                    if tt == TerrType.TREE:
                        cover += 1
                    elif tt in (TerrType.WATER, TerrType.LAVA):
                        cover += 0.5
            s += min(cover, 8) * 0.4
            d = c.get_distance(verify.START)
            if d < 12:
                s -= 6
            elif d < 20:
                s -= 2
            scores[c] = s
    return scores


def _occupied(game_map):
    return [Coordinates(x, y) for y in range(game_map.height) for x in range(game_map.width)
            if game_map.get_cell_contents(x, y) not in (CellContents.EMPTY, CellContents.FORCE_EMPTY)]


def _pick_spot(cands, scores, item_locs, occupied):
    for spacing in ITEM_SPACING:
        ok = [t for t in cands
              if all(t.get_distance(o) >= spacing for o in item_locs)
              and all(t.get_distance(o) >= PICKUP_CLEARANCE for o in occupied)]
        if ok:
            return max(ok, key=lambda t: scores[t] + random.uniform(0, SPOT_NOISE))
    return max(cands, key=lambda t: scores[t] + random.uniform(0, SPOT_NOISE)) if cands else None


def _choose_step_items(v, held, reach, unplaced, k, scores):
    """Pick which unplaced items this step offers. A good choice opens up new
    hiding places for whatever is still left."""
    sizes = [k, 3 - k] + list(range(3, len(unplaced) + 1))
    for size in sizes:
        if size > len(unplaced) or size < 1:
            continue
        good, ok = [], []
        for combo in itertools.combinations(unplaced, size):
            rest = len(unplaced) - size
            if rest == 0:
                good.append(combo)
                continue
            opened = [t for t in v.reachable(held | frozenset(combo)) - reach if t in scores]
            if not opened:
                continue
            hidden = sum(1 for t in opened if scores[t] >= 2)
            (good if hidden >= min(rest, 2) else ok).append(combo)
        if good or ok:
            return list(random.choice(good or ok))
    return list(unplaced)


def place_items_forward_fill(game_map, items):
    """Place `items` (CellContents) on the map; returns [(location, item)]."""
    v = verify.Verifier(game_map)
    vault_spots = list(getattr(game_map, 'vault_item_spots', []))
    scores = spot_scores(game_map, vault_spots)
    occupied = _occupied(game_map)
    trav = [i for i in items if i in verify.TRAVERSAL_ITEMS]
    extra = [i for i in items if i not in verify.TRAVERSAL_ITEMS]
    random.shuffle(trav)

    placement = []
    held = frozenset()
    prev = frozenset()
    regions = []
    unplaced = list(trav)

    def place(item, cands):
        loc = _pick_spot(cands, scores, [l for l, _ in placement], occupied)
        if loc is None:   # nothing hidden left anywhere reachable: any reachable clear tile
            loc = _pick_spot([t for t in v.reachable(held) if t in scores], scores, [l for l, _ in placement], occupied)
        if loc is None:
            raise RuntimeError('No reachable tile left to place {} on'.format(item.label))
        game_map.set_cell_contents(loc.x, loc.y, item)
        scores.pop(loc, None)
        occupied.append(loc)
        placement.append((loc, item))
        if loc in vault_spots:
            vault_spots.remove(loc)

    while unplaced:
        reach = v.reachable(held)
        new = reach - prev
        cands = [t for t in new if t in scores]
        hidden_spots = sum(1 for t in cands if scores[t] >= 2)
        k = 2 if (len(unplaced) >= 2 and hidden_spots >= 2 and random.random() < TWO_ITEM_STEP) else 1
        chosen = _choose_step_items(v, held, reach, unplaced, k, scores)
        if len(cands) < len(chosen):
            cands = [t for t in reach if t in scores]
        for item in chosen:
            # a vault opened up by this step always gets an item first
            vault_here = [t for t in cands if t in vault_spots and t in scores
                          and all(t.get_distance(l) >= 6 for l, _ in placement)]
            place(item, vault_here or cands)
            cands = [t for t in cands if t in scores]
            unplaced.remove(item)
        regions.append(new)
        held = held | frozenset(chosen)
        prev = reach

    # The Blessing goes after the first step but not behind every item (where
    # it would be useless to a route): a leftover vault in that area if any.
    for item in extra:
        later = [r for r in regions[1:] if any(t in scores for t in r)] or regions[:1]
        area = frozenset().union(*later)
        left = [t for t in vault_spots if t in area and t in scores
                and all(t.get_distance(l) >= ITEM_SPACING[1] for l, _ in placement)]
        if left and random.random() < 0.7:
            place(item, left)
            continue
        region = random.choice(later)
        place(item, [t for t in region if t in scores])

    game_map.unused_vault_spots = list(vault_spots)
    return placement


# ---------------------------------------------------------------------------
# Shrines: spread across the whole map, in interesting places.
#
# Farthest-point sampling: each new shrine goes in the band of tiles farthest
# from spawn and the shrines already placed (at least SHRINE_FAR_BAND times
# the farthest such distance), and within that band on the best-hidden tile
# (spot_scores: rooms, tree cover). Only tiles you can reach with every item,
# off lava snakes' lines and not on top of a vault's item spot.
# ---------------------------------------------------------------------------

SHRINE_FAR_BAND = 0.8      # only tiles at least this fraction of the farthest distance


def place_shrines_spread(game_map, count):
    v = verify.Verifier(game_map)
    everything = v.reachable(frozenset(verify.TRAVERSAL_ITEMS))
    vault = list(getattr(game_map, 'vault_item_spots', []))
    scores = spot_scores(game_map)
    cands = [t for t in everything if t in scores
             and game_map.get_cell(t.x, t.y).clear_terrain
             and t not in v.snake_lines
             and all(t.get_distance(s) >= 3 for s in vault)]
    taken = [verify.START]
    placed = []
    for _ in range(count):
        if not cands:
            break
        dist = {t: min(t.get_distance(o) for o in taken) for t in cands}
        cut = max(dist.values()) * SHRINE_FAR_BAND
        band = [t for t in cands if dist[t] >= cut]
        loc = max(band, key=lambda t: scores[t] + random.uniform(0, 2))
        game_map.set_cell_contents(loc.x, loc.y, CellContents.SHRINE)
        taken.append(loc)
        placed.append(loc)
        cands = [t for t in cands if t.get_distance(loc) >= 2]
    return placed


# ---------------------------------------------------------------------------
# Branching placement: keep 2 access items on offer at once.
#
# Andrew (2026-11-22): a map where the only item you can reach at the start
# is the Cloak, and everything after it is also forced, is too linear for
# routing to be interesting. We'd rather usually have 2 access items to
# choose between.
#
# Simulated player: holds `held`, and a "pool" of items that are placed and
# reachable but not yet collected. Whenever the pool has fewer than 2, place
# another item: in the area the last collected item opened up if possible
# (so each item still leads somewhere new), else anywhere reachable. Then
# collect a random pooled item and repeat. Several attempts are made and the
# best one is kept: at least MIN_SPHERES spheres, then the fewest "forced"
# moments over every possible collection order (choice_profile), then the
# best-hidden spots.
# ---------------------------------------------------------------------------

BRANCH_ATTEMPTS = 10
POOL_SIZE = 2
MIN_SPHERES = 3


def choice_profile(v, placements):
    """placements: traversal item -> location. Over every order a player
    could collect the items in, look at each moment with 2+ items still to
    get. Returns (moments, forced, start_options): forced = moments where only
    one item is reachable; start_options = items reachable at the start."""
    items = list(placements)
    def options(held):
        reach = v.reachable(held)
        return [i for i in items if i not in held and placements[i] in reach]
    seen = {frozenset()}
    stack = [frozenset()]
    moments = forced = 0
    while stack:
        held = stack.pop()
        opts = options(held)
        if len(items) - len(held) >= 2:
            moments += 1
            forced += len(opts) < 2
        for i in opts:
            nxt = held | {i}
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return moments, forced, len(options(frozenset()))


def _spheres(v, placements):
    held = frozenset()
    count = 0
    while True:
        reach = v.reachable(held)
        new = {i for i, l in placements.items() if i not in held and l in reach}
        if not new:
            return count, held
        count += 1
        held = held | new


def _branch_attempt(v, trav, scores, vault_spots, occupied):
    scores = dict(scores)
    unplaced = list(trav)
    random.shuffle(unplaced)
    placements = {}
    held = frozenset()
    pool = []
    opened = v.reachable(held)
    total = 0.0
    while unplaced or pool:
        reach = v.reachable(held)
        while len(pool) < POOL_SIZE and unplaced:
            # Prefer an item that opens new places once you have it (with
            # everything held or on offer), so the chain doesn't dead-end.
            have = held | frozenset(pool)
            base = v.reachable(have)
            useful = [i for i in unplaced
                      if any(t in scores for t in v.reachable(have | {i}) - base)]
            item = random.choice(useful if useful and len(unplaced) > 1 else unplaced)
            cands = [t for t in opened if t in scores] or [t for t in reach if t in scores]
            locs = list(placements.values())
            vault_here = [t for t in cands if t in vault_spots
                          and all(t.get_distance(l) >= 6 for l in locs)]
            loc = _pick_spot(vault_here or cands, scores, locs, occupied)
            if loc is None:
                return None
            total += scores.pop(loc)
            placements[item] = loc
            pool.append(item)
            unplaced.remove(item)
        if not pool:
            break
        got = random.choice(pool)
        pool.remove(got)
        new_held = held | {got}
        opened = v.reachable(new_held) - reach
        held = new_held
    return placements, total


def place_items_branching(game_map, items):
    """Place `items` (CellContents) on the map; returns [(location, item)]."""
    v = verify.Verifier(game_map)
    vault_spots = list(getattr(game_map, 'vault_item_spots', []))
    scores = spot_scores(game_map, vault_spots)
    occupied = _occupied(game_map)
    trav = [i for i in items if i in verify.TRAVERSAL_ITEMS]
    extra = [i for i in items if i not in verify.TRAVERSAL_ITEMS]
    castle_item, armory = choose_castle_item(game_map, trav, scores)
    if castle_item is not None:
        trav = [i for i in trav if i != castle_item]

    best, best_key = None, None
    for _ in range(BRANCH_ATTEMPTS):
        result = _branch_attempt(v, trav, scores, vault_spots, occupied)
        if result is None:
            continue
        placements, total = result
        spheres, held = _spheres(v, placements)
        moments, forced, start = choice_profile(v, placements)
        key = (len(held) == len(trav), spheres >= MIN_SPHERES, -forced, start >= 2,
               total + random.uniform(0, 3))
        if best_key is None or key > best_key:
            best, best_key = placements, key
    if best is None:   # fall back to the step-by-step placement
        return place_items_forward_fill(game_map, items)

    placement = []
    if castle_item is not None:
        best = dict(best)
        best[castle_item] = armory
        game_map.castle_item = castle_item
    for item, loc in best.items():
        game_map.set_cell_contents(loc.x, loc.y, item)
        scores.pop(loc, None)
        occupied.append(loc)
        placement.append((loc, item))
        if loc in vault_spots:
            vault_spots.remove(loc)

    # The Blessing: behind something, but within the first two spheres so it
    # still matters to a route. A leftover vault there 70% of the time.
    start = v.reachable(frozenset())
    held = frozenset()
    for _ in range(2):
        held = held | {i for i, l in best.items() if l in v.reachable(held) and i != castle_item}
    area = (v.reachable(held) - start) or (v.reachable(frozenset(trav)) - start) or start
    for item in extra:
        locs = [l for l, _ in placement]
        left = [t for t in vault_spots if t in area and t in scores
                and all(t.get_distance(l) >= ITEM_SPACING[1] for l in locs)]
        cands = left if left and random.random() < 0.7 else [t for t in area if t in scores]
        loc = _pick_spot(cands, scores, locs, occupied)
        if loc is None:
            loc = _pick_spot([t for t in v.reachable(frozenset(trav)) if t in scores], scores, locs, occupied)
        game_map.set_cell_contents(loc.x, loc.y, item)
        scores.pop(loc, None)
        occupied.append(loc)
        placement.append((loc, item))
        if loc in vault_spots:
            vault_spots.remove(loc)

    game_map.unused_vault_spots = list(vault_spots)
    return placement


# ---------------------------------------------------------------------------
# Castle item (Andrew, 2026-11-23): the castle gate opens only for a player
# holding GATE_GEMS gems, and one important access item waits inside, in the
# Castle Armory. You gather gems outside, go in for it, and come back out to
# use it, unless your route can do without it.
#
# The item is chosen so that the armory and every seal are reachable without
# it (it can't be locked behind itself, and you can always finish without
# it), preferring items that open up more of the map. place_gated_gems then
# puts a few gems behind it (CASTLE_ITEM_GEMS) but never so many that 16
# stop being reachable without it, so it is useful but optional.
# ---------------------------------------------------------------------------

CASTLE_ITEM_GEMS = 3


def choose_castle_item(game_map, trav, scores):
    import map as map_module
    if not getattr(map_module, 'CASTLE_ITEM', False) or not getattr(game_map, 'gate_gems', 0):
        return None, None
    names = getattr(game_map, 'vault_spot_names', {})
    armory = next((c for c, n in names.items() if n == 'Castle Armory'
                   and game_map.get_cell_contents(c.x, c.y) == CellContents.EMPTY), None)
    if armory is None:
        return None, None
    v = verify.Verifier(game_map)
    v.gate_mode = 'open'
    everything = v.reachable(frozenset(trav))
    options, weights = [], []
    for item in trav:
        without = v.reachable(frozenset(i for i in trav if i != item))
        if armory in without and all(sl in without for sl in v.seals):
            options.append(item)
            weights.append((1 + sum(1 for t in everything - without if t in scores)) ** 0.5)
    if not options:
        return None, None
    return random.choices(options, weights=weights)[0], armory
