"""
Map verification: is a generated map beatable, and is it interesting?

Model (glitchless, deliberately simple):
  * Movement is 4-way, blocked by walls (Map.is_wall) and the map edge.
  * Water needs Water Boots, Lava needs the Flame Shield, Trees need the Axe
    (you cut them). Grass/Road/Building/Castle floors are always fine.
  * The verifier thinks in turns: each turn you move up to 2 tiles, and it
    allows no damage at all (taking hits is how skips work). To pick
    something up you must end a turn on it and then spend a turn there.
  * Desert without the Cloak: if you begin a turn in the desert you take 1
    damage, so the verifier never lets you END a turn on desert. A 1-wide
    strip can be crossed in one 2-tile move; anything 2+ wide needs the
    Cloak (a runner can tank the damage instead; that's a skip). A pickup ON
    a desert tile needs the Cloak for the same reason.
  * The Shrine Maiden's Blessing only warps you to shrines you've already
    visited, so it's pure convenience and never affects reachability.
  * Lava snakes (CellContents.DRAGON), Andrew's rules: on its turn a snake
    first breathes fire if it was aiming (hitting you if you're still on that
    line), then aims at you if you're collinear and within SNAKE_RANGE (5).
    So without the Bow:
      - you may not end two turns in a row on the same line of the same
        snake within range (the second one gets you hit), and
      - you can't pick anything up on a snake's line (you'd stand there for
        two turns).
    Crossing a snake's line is fine (enter, it aims, you leave). Walking
    along its line for more than one turn is not. Walls block the line of
    fire; nothing else does (the conservative choice). The snake's own tile
    is impassable. With the Bow, snakes don't block.
  * Skips are deliberately NOT modelled: beatability must never depend on
    knockback over hazards, tanking damage, glitches, etc. Other enemies
    don't block.

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
    CellContents.SILVER_SWORD,
    CellContents.HORSE,
]
# Items that can change what is reachable.
# Bow matters because of lava snakes; Blessing never changes reachability.
# The Horse only makes you faster, so like the Blessing it never changes
# reachability. The Silver Sword gets you past Ghosts.
TRAVERSAL_ITEMS = [i for i in ITEMS if i not in (CellContents.BLESSING, CellContents.HORSE)]

TERRAIN_NEEDS = {
    TerrType.WATER: CellContents.WATER_BOOTS,
    TerrType.LAVA: CellContents.FIRE_SHIELD,
    TerrType.TREE: CellContents.AXE,
}

SNAKE_RANGE = 5
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
GEMS_PER_SEAL = 4
START = Coordinates(0, 0)


def _short(items):
    return '{' + ', '.join(sorted(i.label for i in items)) + '}' if items else '{}'


class Verifier:
    def __init__(self, game_map):
        self.map = game_map
        self.w, self.h = game_map.width, game_map.height
        # Precompute open edges once. Same rule as Map.is_wall (forced wall ->
        # wall; same room -> open; door -> open; else wall), with sets instead
        # of Map's list scans.
        doors = {frozenset(p) for p in game_map.doors}
        forced = {frozenset(p) for p in game_map.forced_walls}
        rooms = game_map.room_numbers
        self.neighbors = {}
        for y in range(self.h):
            for x in range(self.w):
                c = Coordinates(x, y)
                out = []
                for n in c.get_neighboring_coordinates():
                    if not (0 <= n.x < self.w and 0 <= n.y < self.h):
                        continue
                    pair = frozenset((c, n))
                    if pair in forced:
                        continue
                    if rooms[y][x] == rooms[n.y][n.x] or pair in doors:
                        out.append(n)
                self.neighbors[c] = out
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
        # Ghosts roam, but "as intended" play treats each one as blocking the
        # tile it starts on until you have the Silver Sword (Andrew, 2026-11-23).
        # Luring one away is speedrun tech, deliberately not modelled.
        self.ghosts = [Coordinates(x, y) for y in range(self.h) for x in range(self.w)
                       if game_map.get_cell_contents(x, y) == CellContents.GHOST]
        # Castle gem gate (map.setup_castle_gate). gate_mode 'gems' needs the
        # gems; 'open' pretends you have them (used while placing items,
        # before any gems exist).
        self.gate_gems = getattr(game_map, 'gate_gems', 0)
        self.gate_edges = set()
        self.gate_tiles = []
        if self.gate_gems:
            for a, b in getattr(game_map, 'castle_gate', []):
                self.gate_edges |= {(a, b), (b, a)}
                self.gate_tiles.append(b)
        self.gate_mode = 'gems'
        self._cache = {}

        # Lava snakes: edges and tiles that block you unless you have the Bow.
        self.set_snakes([Coordinates(x, y) for y in range(self.h) for x in range(self.w)
                         if game_map.get_cell_contents(x, y) == CellContents.DRAGON])

    def set_snakes(self, snakes):
        """(Re)build the snakes' walls and drop cached reach. Lets snake
        placement try candidates without a new Verifier.

        Andrew's model (2026-11-23): without the Bow, each snake S puts a wall
        between A and B on each of its four sides (B next to S, A one further
        out), and S itself is impassable:

            . . A . .
            . . B . .
            A B S B A
            . . B . .
            . . A . .

        Walking straight down a snake's line at it gets you breathed on, but
        you can step past it sideways, and once you stand on a B you can kill
        it in melee (stand_tiles then drops its walls). So only a snake that
        blocks a hallway, where the only way on is along its line, needs the
        Bow."""
        self.snakes = list(snakes)
        self.snake_tiles = set(self.snakes)
        self.snake_walls = {}   # snake -> set of blocked (tile, tile) steps, both ways
        self.snake_b = {}       # snake -> B tiles you could melee it from
        for snake in self.snakes:
            walls, bs = set(), []
            for d in DIRS:
                b = Coordinates(snake.x + d[0], snake.y + d[1])
                a = Coordinates(snake.x + 2 * d[0], snake.y + 2 * d[1])
                if b in self.neighbors.get(snake, ()):   # no wall between snake and B
                    bs.append(b)
                if a in self.neighbors.get(b, ()):
                    walls |= {(a, b), (b, a)}
            self.snake_walls[snake] = walls
            self.snake_b[snake] = bs
        # Kept for callers that ask "is this tile next to a snake?"
        self.snake_lines = {b: frozenset([s]) for s, bs in self.snake_b.items() for b in bs}
        self._cache = {}

    def line_tiles(self, snake):
        """The B tiles of this snake (next to it, where you could melee it)."""
        return set(self.snake_b.get(snake, ()))

    def _passable(self, c, items):
        need = TERRAIN_NEEDS.get(self.map.get_cell(c.x, c.y))
        return need is None or need in items

    def reachable(self, items):
        """Tiles where you can pick something up while holding `items` (a
        frozenset): you can end a turn there safely and stay a turn."""
        items = frozenset(items)
        if items in self._cache:
            return self._cache[items]
        result = self.stand_tiles(items)
        self._cache[items] = result
        return result

    def _index(self):
        """Integer-indexed copies of the map for the hot BFS loop."""
        if getattr(self, '_idx_ready', False):
            return
        w = self.w
        self._coords = [Coordinates(i % w, i // w) for i in range(w * self.h)]
        self._nbr = [[n.y * w + n.x for n in self.neighbors[c]] for c in self._coords]
        # The same without the castle gate's doorway (gate still locked).
        self._nbr_closed = [[n.y * w + n.x for n in self.neighbors[c] if (c, n) not in self.gate_edges]
                            for c in self._coords]
        self._terr = [self.map.get_cell(c.x, c.y) for c in self._coords]
        self._idx_ready = True

    def _bfs(self, nbr, walk, blocked, can_end):
        """Turn-based flood fill: each turn is up to 2 steps and must end on a
        tile where you can end a turn. `blocked` holds (from, to) index pairs
        you can't step across (snake walls)."""
        w = self.w
        size = len(walk)
        start = START.y * w + START.x
        seen = [False] * size
        seen[start] = True
        queue = deque([start])
        pop, push = queue.popleft, queue.append
        bl = {a * size + b for a, b in blocked} if blocked else None
        while queue:
            c = pop()
            for n in nbr[c]:
                if not walk[n] or (bl is not None and c * size + n in bl):
                    continue
                if not seen[n] and can_end[n]:
                    seen[n] = True
                    push(n)
                for m in nbr[n]:
                    if (m != c and not seen[m] and walk[m] and can_end[m]
                            and (bl is None or n * size + m not in bl)):
                        seen[m] = True
                        push(m)
        return seen

    def _gate_opens(self, seen, snakes_on):
        """Locked castle gate: it opens if you can stand on a Gate tile (long
        enough to interact) holding gate_gems gems, all collected outside."""
        w = self.w
        def pickup(c):
            return seen[c.y * w + c.x]
        if not any(pickup(g) for g in self.gate_tiles):
            return False
        if self.gate_mode == 'open':
            return True
        return sum(1 for g in self.gems if pickup(g)) >= self.gate_gems

    def stand_tiles(self, items):
        """Tiles where you can end a turn (BFS over turns of up to 2 steps)."""
        key = ('stand', frozenset(items))
        if key in self._cache:
            return self._cache[key]
        self._index()
        w = self.w
        cloak = CellContents.DESERT_CLOAK in items
        snakes_on = CellContents.BOW not in items and bool(self.snakes)
        terr = self._terr
        walk = [TERRAIN_NEEDS.get(t) is None or TERRAIN_NEEDS[t] in items for t in terr]
        can_end = [cloak or t != TerrType.DESERT for t in terr]
        idx = lambda c: c.y * w + c.x
        if CellContents.SILVER_SWORD not in items:
            for g in self.ghosts:
                walk[idx(g)] = False
        alive = set(self.snakes) if snakes_on else set()
        while True:
            blocked = set()
            for sn in alive:
                walk[idx(sn)] = False
                blocked |= {(idx(a), idx(b)) for a, b in self.snake_walls[sn]}
            if self.gate_edges:
                seen = self._bfs(self._nbr_closed, walk, blocked, can_end)
                if self._gate_opens(seen, snakes_on):
                    seen = self._bfs(self._nbr, walk, blocked, can_end)
            else:
                seen = self._bfs(self._nbr, walk, blocked, can_end)
            # A snake you can stand next to (on a B) you can kill in melee.
            killed = {sn for sn in alive if any(seen[idx(b)] for b in self.snake_b[sn])}
            if not killed:
                break
            alive -= killed
            for sn in killed:
                walk[idx(sn)] = TERRAIN_NEEDS.get(terr[idx(sn)]) is None or TERRAIN_NEEDS[terr[idx(sn)]] in items
        coords = self._coords
        result = frozenset(coords[i] for i in range(len(seen)) if seen[i])
        self._cache[key] = result
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

        # Castle gem gate and the item kept in the castle (map.setup_castle_gate,
        # gem_placement.choose_castle_item): can you win without that item, and
        # how many gems does it guard?
        self.gate_gems = v.gate_gems
        self.castle_item = getattr(v.map, 'castle_item', None)
        self.castle_item_optional = None
        self.castle_item_gems = 0
        if self.castle_item is not None:
            _, _, reach = v.progression(allowed=set(ITEMS) - {self.castle_item})
            self.castle_item_optional = v.can_win(reach)
            without = v.reachable(frozenset(i for i in TRAVERSAL_ITEMS if i != self.castle_item))
            self.castle_item_gems = sum(1 for g in v.gems if g not in without)

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
        if self.gate_gems:
            lines.append('Castle gate: needs {} gems held'.format(self.gate_gems))
        if self.castle_item is not None:
            lines.append('Castle item: {} (guards {} gems; {})'.format(
                self.castle_item.label, self.castle_item_gems,
                'optional, you can win without it' if self.castle_item_optional else 'needed to win'))
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
    'min_items_to_win': 4,       # a run must collect at least this many items (Andrew 2026-11-23: 4 once a 6th access item exists; the Silver Sword is it)
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
