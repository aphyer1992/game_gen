"""
Map verification: is a generated map beatable, and is it interesting?

Model (glitchless, deliberately simple):
  * Movement is 4-way, blocked by walls (Map.is_wall) and the map edge.
  * Water needs Water Boots, Lava needs the Flame Shield, Trees need the Axe
    (you cut them). Grass/Road/Building/Castle floors are always fine.
  * Desert without the Cloak: you take 1 damage at the start of every turn you
    begin in desert and can only move 1. With 3 Life and a full-health entry
    you can walk at most DESERT_MAX_RUN (3) desert tiles in a row: e.g. step
    2 tiles in from outside, then 1 more, then step out on 1 Life. A pickup
    up to 3 deep is also gettable (you can die afterwards, progress is kept).
  * The Shrine Maiden's Blessing lets you warp from any shrine to any other,
    so with it every shrine becomes a starting point.
  * Lava snakes (CellContents.DRAGON) without the Bow act as four extra
    walls, on the edges 1->2 tiles away from the snake along each of its
    four lines (A|B below), and the snake's own tile is impassable:
        . . A . .
        . . B . .
        A B S B A
        . . B . .
        . . A . .
    So you can't walk up a line towards a snake, but you can step in from the
    side. A snake at the end of a 1-wide corridor 2+ long blocks it. With the
    Bow, snakes don't block (step into line, it aims, shoot it first).
  * Skips are deliberately NOT modelled: beatability must never depend on
    knockback over hazards, glitches, etc. Other enemies don't block.

Main entry points:
  verify_map(game_map) -> VerificationReport
  generate_verified_map(width, height, seed, criteria) -> (Map, report, seed)
"""
import itertools
import random
import io
import contextlib
from collections import deque

from support_classes import Coordinates, TerrType, CellContents

ITEMS = [
    CellContents.WATER_BOOTS,
    CellContents.FIRE_SHIELD,
    CellContents.AXE,
    CellContents.DESERT_CLOAK,
    CellContents.BLESSING,
    CellContents.BOW,
]
# Items that can change what is reachable.
TRAVERSAL_ITEMS = list(ITEMS)  # the Bow matters because of lava snakes

TERRAIN_NEEDS = {
    TerrType.WATER: CellContents.WATER_BOOTS,
    TerrType.LAVA: CellContents.FIRE_SHIELD,
    TerrType.TREE: CellContents.AXE,
}

DESERT_MAX_RUN = 3
GEMS_PER_SEAL = 4
START = Coordinates(0, 0)


def _short(items):
    return '{' + ', '.join(sorted(i.label for i in items)) + '}' if items else '{}'


class Verifier:
    def __init__(self, game_map):
        self.map = game_map
        self.w, self.h = game_map.width, game_map.height
        # Precompute open edges once (Map.is_wall does list scans).
        self.neighbors = {}
        for y in range(self.h):
            for x in range(self.w):
                c = Coordinates(x, y)
                self.neighbors[c] = [
                    n for n in c.get_neighboring_coordinates()
                    if game_map.is_valid_coordinates(n) and not game_map.is_wall(c, n)
                ]
        self.pickups = {}   # coord -> CellContents for items
        self.gems = []
        self.shrines = []
        self.seals = []
        for y in range(self.h):
            for x in range(self.w):
                c = Coordinates(x, y)
                content = game_map.get_cell_contents(x, y)
                if content in ITEMS:
                    self.pickups[c] = content
                elif content == CellContents.GEM:
                    self.gems.append(c)
                elif content == CellContents.SHRINE:
                    self.shrines.append(c)
                elif content == CellContents.SEAL:
                    self.seals.append(c)
        self.gems_needed = GEMS_PER_SEAL * len(self.seals)
        self._cache = {}

        # Lava snakes: edges and tiles that block you unless you have the Bow.
        self.snakes = [Coordinates(x, y) for y in range(self.h) for x in range(self.w)
                       if game_map.get_cell_contents(x, y) == CellContents.DRAGON]
        self.snake_edges = set()
        for snake in self.snakes:
            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                b = Coordinates(snake.x + dx, snake.y + dy)
                a = Coordinates(snake.x + 2 * dx, snake.y + 2 * dy)
                self.snake_edges.add((a, b))
                self.snake_edges.add((b, a))
        self.snake_tiles = set(self.snakes)

    def _passable(self, c, items):
        need = TERRAIN_NEEDS.get(self.map.get_cell(c.x, c.y))
        return need is None or need in items

    def reachable(self, items):
        """Set of tiles reachable while holding `items` (a frozenset)."""
        items = frozenset(items)
        if items in self._cache:
            return self._cache[items]
        cloak = CellContents.DESERT_CLOAK in items
        snakes_block = CellContents.BOW not in items and bool(self.snakes)
        seeds = [START]
        if CellContents.BLESSING in items:
            # Warp works from any shrine you can reach; if you can reach none
            # except spawn (spawn is a shrine) you can still warp from spawn.
            seeds += self.shrines
        best_run = {}   # coord -> smallest desert run we've arrived with
        queue = deque()
        for s in seeds:
            if self._passable(s, items):
                run = 1 if (self.map.get_cell(s.x, s.y) == TerrType.DESERT and not cloak) else 0
                best_run[s] = run
                queue.append((s, run))
        while queue:
            c, run = queue.popleft()
            if best_run.get(c, 99) < run:
                continue
            for n in self.neighbors[c]:
                if not self._passable(n, items):
                    continue
                if snakes_block and (n in self.snake_tiles or (c, n) in self.snake_edges):
                    continue
                if self.map.get_cell(n.x, n.y) == TerrType.DESERT and not cloak:
                    nrun = run + 1
                    if nrun > DESERT_MAX_RUN:
                        continue
                else:
                    nrun = 0
                if nrun < best_run.get(n, 99):
                    best_run[n] = nrun
                    queue.append((n, nrun))
        result = frozenset(best_run)
        self._cache[items] = result
        return result

    def can_win(self, reach):
        gems = sum(1 for g in self.gems if g in reach)
        return gems >= self.gems_needed and all(s in reach for s in self.seals)

    def progression(self, allowed=None):
        """Greedy item collection from nothing. Returns list of spheres; each
        sphere is the set of items newly obtainable at that step. `allowed`
        restricts which items you are willing to pick up."""
        held = set()
        spheres = []
        while True:
            reach = self.reachable(frozenset(held))
            new = {item for c, item in self.pickups.items()
                   if c in reach and item not in held and (allowed is None or item in allowed)}
            if not new:
                return spheres, frozenset(held), reach
            spheres.append(new)
            held |= new

    def min_requirements(self, target, exclude=None):
        """Minimal item sets (ignoring how you'd get them) that make `target`
        reachable. `exclude` is an item that can't be used (the target itself)."""
        pool = [i for i in TRAVERSAL_ITEMS if i != exclude]
        found = []
        for r in range(len(pool) + 1):
            for subset in itertools.combinations(pool, r):
                s = frozenset(subset)
                if any(f <= s for f in found):
                    continue
                if target in self.reachable(s):
                    found.append(s)
        return found

    def min_items_to_win(self):
        """Smallest set of items that is actually collectable (in some order)
        and lets you win. This is roughly 'how many items a run must get'."""
        for r in range(len(TRAVERSAL_ITEMS) + 1):
            for subset in itertools.combinations(TRAVERSAL_ITEMS, r):
                s = frozenset(subset)
                _, held, reach = self.progression(allowed=s)
                if held == s and self.can_win(reach):
                    return s
        return None


class VerificationReport:
    def __init__(self, v):
        spheres, held, final_reach = v.progression()
        self.spheres = spheres
        self.items_obtainable = held
        self.unobtainable_items = [item for item in ITEMS if item not in held]
        self.gems_total = len(v.gems)
        self.gems_needed = v.gems_needed
        self.gems_reachable = sum(1 for g in v.gems if g in final_reach)
        self.seals_reachable = sum(1 for s in v.seals if s in final_reach)
        self.seals_total = len(v.seals)
        self.beatable = v.can_win(final_reach)
        self.unreachable_shrines = [s for s in v.shrines if s not in final_reach]

        start_reach = v.reachable(frozenset())
        self.items_free = [item for c, item in v.pickups.items() if c in start_reach]
        self.gems_free = sum(1 for g in v.gems if g in start_reach)
        self.beatable_with_no_items = v.can_win(start_reach)

        # For each item: minimal sets of *other* items needed to reach it.
        self.item_requirements = {}
        for c, item in v.pickups.items():
            self.item_requirements[item] = v.min_requirements(c, exclude=item)
        # An item is 'gated' if every way to reach it needs some item.
        self.gated_items = [i for i, reqs in self.item_requirements.items()
                            if reqs and all(len(r) > 0 for r in reqs)]
        # Chains: item A needs B which needs C... longest sphere count is a proxy.
        self.num_spheres = len(spheres)
        self.min_win_set = v.min_items_to_win() if self.beatable else None

        # Gems by requirement, for spotting 'all gems are free' maps.
        self.gems_by_requirement = {}
        for g in v.gems:
            reqs = v.min_requirements(g)
            key = _short(min(reqs, key=len)) if reqs else 'UNREACHABLE'
            self.gems_by_requirement[key] = self.gems_by_requirement.get(key, 0) + 1

    def summary(self):
        lines = []
        lines.append('Beatable: {}  (gems {}/{} reachable, need {}; seals {}/{})'.format(
            self.beatable, self.gems_reachable, self.gems_total, self.gems_needed,
            self.seals_reachable, self.seals_total))
        if self.unobtainable_items:
            lines.append('Unobtainable items: ' + ', '.join(i.label for i in self.unobtainable_items))
        if self.unreachable_shrines:
            lines.append('Unreachable shrines: {}'.format(self.unreachable_shrines))
        lines.append('Free from spawn: items {}, gems {}'.format(
            _short(self.items_free), self.gems_free))
        for n, sphere in enumerate(self.spheres):
            lines.append('  Sphere {}: {}'.format(n, _short(sphere)))
        lines.append('Item requirements (minimal sets, any one suffices):')
        for item in ITEMS:
            reqs = self.item_requirements.get(item)
            if reqs is None:
                continue
            txt = ' or '.join(_short(r) for r in reqs) if reqs else 'UNREACHABLE even with everything'
            lines.append('  {:8s} <- {}'.format(item.label, txt))
        lines.append('Gems by cheapest requirement: {}'.format(self.gems_by_requirement))
        lines.append('Smallest winning item set: {}'.format(
            _short(self.min_win_set) if self.min_win_set is not None else 'n/a'))
        return '\n'.join(lines)


def verify_map(game_map):
    return VerificationReport(Verifier(game_map))


DEFAULT_CRITERIA = {
    'beatable': True,
    'all_items_obtainable': True,
    'min_spheres': 3,            # at least one item behind another item behind another
    'min_gated_items': 2,        # at least two items need some other item first
    'max_free_items': 3,         # at most this many items grabbable with nothing
    'min_items_to_win': 2,       # a run must collect at least this many items
    'not_beatable_with_no_items': True,
}


def check_criteria(report, criteria=None):
    """Returns a list of failed criteria (empty list = map accepted)."""
    c = dict(DEFAULT_CRITERIA)
    if criteria:
        c.update(criteria)
    fails = []
    if c.get('beatable') and not report.beatable:
        fails.append('not beatable')
    if c.get('all_items_obtainable') and report.unobtainable_items:
        fails.append('unobtainable items')
    if report.num_spheres < c.get('min_spheres', 0):
        fails.append('only {} spheres'.format(report.num_spheres))
    if len(report.gated_items) < c.get('min_gated_items', 0):
        fails.append('only {} gated items'.format(len(report.gated_items)))
    if len(report.items_free) > c.get('max_free_items', 99):
        fails.append('{} free items'.format(len(report.items_free)))
    if report.min_win_set is not None and len(report.min_win_set) < c.get('min_items_to_win', 0):
        fails.append('winnable with {} items'.format(len(report.min_win_set)))
    if c.get('not_beatable_with_no_items') and report.beatable_with_no_items:
        fails.append('beatable with no items')
    return fails


def generate_verified_map(width=50, height=50, seed=None, criteria=None, max_tries=200, quiet=True):
    """Re-roll seeds (seed, seed+1, ...) until a map passes the criteria."""
    from map import Map
    base = seed if seed is not None else random.randrange(10**9)
    for i in range(max_tries):
        s = base + i
        random.seed(s)
        m = Map(width, height)
        try:
            if quiet:
                with contextlib.redirect_stdout(io.StringIO()):
                    m.generate_map()
            else:
                m.generate_map()
        except Exception as e:  # generator occasionally fails outright
            if not quiet:
                print('seed {}: generation failed: {!r}'.format(s, e))
            continue
        report = verify_map(m)
        fails = check_criteria(report, criteria)
        if not fails:
            return m, report, s
        if not quiet:
            print('seed {} rejected: {}'.format(s, '; '.join(fails)))
    raise RuntimeError('No acceptable map in {} tries'.format(max_tries))


if __name__ == '__main__':
    # python verify.py              -> report on seeds 42 43 44
    # python verify.py 7 8 9        -> report on those seeds
    # python verify.py --find 3 100 -> find 3 accepted maps starting at seed 100,
    #                                  print reports and export verified_map_<seed>.xlsx
    import sys
    from map import Map
    if len(sys.argv) > 1 and sys.argv[1] == '--find':
        count = int(sys.argv[2]) if len(sys.argv) > 2 else 1
        seed = int(sys.argv[3]) if len(sys.argv) > 3 else 0
        for _ in range(count):
            m, r, seed = generate_verified_map(50, 50, seed=seed, quiet=False)
            print('=== accepted seed {} ==='.format(seed))
            print(r.summary())
            m.export_to_excel('verified_map_{}.xlsx'.format(seed))
            print()
            seed += 1
        sys.exit(0)
    seeds = [int(a) for a in sys.argv[1:]] or [42, 43, 44]
    for s in seeds:
        random.seed(s)
        m = Map(50, 50)
        with contextlib.redirect_stdout(io.StringIO()):
            m.generate_map()
        r = verify_map(m)
        print('=== seed {} ==='.format(s))
        print(r.summary())
        fails = check_criteria(r)
        print('ACCEPTED' if not fails else 'REJECTED: ' + '; '.join(fails))
        print()
