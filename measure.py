"""
Measure how "game-like" a batch of generated maps is.

    python measure.py 0 60            # seeds 0..59, prints a summary table
    python measure.py 0 60 --csv out.csv

Per map it records (traversal items = Boots, Shield, Axe, Cloak, Bow):
  * verifier pass/fail and beatability (verify.py's DEFAULT_CRITERIA)
  * items in the open: on outdoor terrain AND reachable with no items
  * items near spawn: within NEAR tiles (Manhattan) of the spawn shrine
  * hidden items: inside a building/castle/vault room, or behind some item
  * spread: the smallest distance between any two items
  * progression shape: traversal items per sphere; "1-2 per step" holds when
    every sphere has 1 or 2 traversal items
"""
import contextlib
import io
import itertools
import random
import sys
import time
import types

if 'xlsxwriter' not in sys.modules:   # only needed for export; don't require it here
    try:
        import xlsxwriter  # noqa: F401
    except ImportError:
        sys.modules['xlsxwriter'] = types.ModuleType('xlsxwriter')

from support_classes import Coordinates
import verify

NEAR = 12


def item_spots(m):
    out = {}
    for y in range(m.height):
        for x in range(m.width):
            c = m.get_cell_contents(x, y)
            if c in verify.ITEMS:
                out[Coordinates(x, y)] = c
    return out


def interesting(m, c):
    """In a room, under tree cover (4+ trees within 2), or right by water/lava."""
    if m.get_room_number(c.x, c.y) != 0:
        return True
    trees = hazard = 0
    for t in c.get_coordinates_in_range(2):
        if t != c and m.is_valid_coordinates(t):
            terr = m.get_cell(t.x, t.y)
            trees += terr.label == 'Tree'
            hazard += terr.label in ('Water', 'Lava') and t.get_distance(c) == 1
    return trees >= 4 or hazard > 0


def contents_at(m, kind):
    return [Coordinates(x, y) for y in range(m.height) for x in range(m.width)
            if m.get_cell_contents(x, y) == kind]


def map_metrics(m):
    v = verify.Verifier(m)
    rep = verify.VerificationReport(v)
    fails = verify.check_criteria(rep)
    spots = item_spots(m)
    start = v.reachable(frozenset())
    open_items = [c for c in spots if m.get_room_number(c.x, c.y) == 0 and c in start]
    near = [c for c in spots if c.get_distance(verify.START) <= NEAR]
    hidden = [c for c in spots if m.get_room_number(c.x, c.y) != 0 or c not in start]
    coords = list(spots)
    min_gap = min((a.get_distance(b) for a, b in itertools.combinations(coords, 2)), default=0)
    trav_per_sphere = [sum(1 for i in s if i in verify.TRAVERSAL_ITEMS) for s in rep.spheres]
    trav_per_sphere = [n for n in trav_per_sphere if n] or [0]
    from support_classes import CellContents
    shrines = contents_at(m, CellContents.SHRINE)
    gems = contents_at(m, CellContents.GEM)
    ogres = contents_at(m, CellContents.OGRE)
    every = [c for c in v.reachable(frozenset(verify.TRAVERSAL_ITEMS)) if m.get_cell(c.x, c.y).clear_terrain]
    cover = max((min(c.get_distance(s) for s in shrines) for c in every), default=0)
    sectors = {(min(2, c.x * 3 // m.width), min(2, c.y * 3 // m.height)) for c in shrines}
    import gem_placement
    trav = {i: c for c, i in spots.items() if i in verify.TRAVERSAL_ITEMS}
    moments, forced, start_opts = gem_placement.choice_profile(v, trav)
    full = len(v.stand_tiles(frozenset(verify.TRAVERSAL_ITEMS)))
    from support_classes import CellContents as _K
    _, _, reach_nobow = v.progression(allowed=set(verify.ITEMS) - {_K.BOW})
    bow_needed = rep.beatable and not v.can_win(reach_nobow)
    no_bow = frozenset(i for i in verify.TRAVERSAL_ITEMS if i != _K.BOW)
    reach_nb = v.reachable(no_bow)
    bow_gems = sum(1 for g in v.gems if g not in reach_nb)
    bow_items = sum(1 for c, i in v.pickups.items() if c not in reach_nb)
    from buildings import building_blocks, BIG
    br = getattr(m, 'building_report', {})
    castle_tiles = [c for c in [Coordinates(x, y) for y in range(m.height) for x in range(m.width)]
                    if m.get_cell(c.x, c.y).label == 'Castle']
    import fill_empty
    far = fill_empty._distance_to_stuff(m)
    empty_land = sum(1 for c, d in far.items() if d >= fill_empty.EMPTY_DIST
                     and m.get_cell(c.x, c.y).label in ('Grass', 'Desert', 'Road'))
    return {
        'empty_land': empty_land,
        'idle_buildings': br.get('left', 0),
        'big_buildings': br.get('big', 0),
        'castle_gems': len(getattr(m, 'castle_gems', [])),
        'castle_ogres': sum(1 for c in castle_tiles if m.get_cell_contents(c.x, c.y) == _K.OGRE),
        'bow_needed': bow_needed,
        'bow_gems': bow_gems,
        'bow_items': bow_items,
        'snakes': len(v.snakes),
        'castle_item': rep.castle_item.label if rep.castle_item else '',
        'castle_optional': rep.castle_item_optional,
        'castle_item_gems': rep.castle_item_gems,
        'start_share': len(v.stand_tiles(frozenset())) / full if full else 0,
        'vault_types': len({n.split(' (')[0] for n in getattr(m, 'vault_spot_names', {}).values()}),
        'choice_moments': moments,
        'forced': forced,
        'forced_share': forced / moments if moments else 0,
        'start_options': start_opts,
        'shrine_cover': cover,
        'shrine_sectors': len(sectors),
        'shrine_interest': sum(interesting(m, c) for c in shrines if c != verify.START),
        'gem_count': len(gems),
        'gem_close_pairs': sum(1 for a, b in itertools.combinations(gems, 2) if a.get_distance(b) <= 3),
        'gem_interest': sum(interesting(m, c) for c in gems),
        'gems_near': sum(1 for c in gems if c.get_distance(verify.START) <= NEAR),
        'ogres': len(ogres),
        'ogres_in_rooms': sum(1 for c in ogres if m.get_room_number(c.x, c.y) != 0),
        'accepted': not fails,
        'beatable': rep.beatable,
        'fails': fails,
        'open': len(open_items),
        'near': len(near),
        'hidden': len(hidden),
        'free': len(rep.items_free),
        'min_gap': min_gap,
        'spheres': rep.num_spheres,
        'trav_per_sphere': trav_per_sphere,
        'one_two': all(1 <= n <= 2 for n in trav_per_sphere),
        'max_sphere': max(trav_per_sphere),
        'gems_free': rep.gems_free,
        'win_set': len(rep.min_win_set) if rep.min_win_set is not None else None,
    }


def generate(seed, w=50, h=50):
    from map import Map
    random.seed(seed)
    m = Map(w, h)
    with contextlib.redirect_stdout(io.StringIO()):
        m.generate_map()
    return m


def run(seeds):
    rows = []
    t0 = time.time()
    for s in seeds:
        try:
            m = generate(s)
        except Exception as e:
            rows.append({'seed': s, 'error': repr(e)})
            continue
        r = map_metrics(m)
        r['seed'] = s
        rows.append(r)
    return rows, time.time() - t0


def summarize(rows, elapsed):
    ok = [r for r in rows if 'error' not in r]
    n = len(ok)
    if not n:
        return 'no maps'
    def avg(k):
        return sum(r[k] for r in ok) / n
    def pct(pred):
        return 100.0 * sum(1 for r in ok if pred(r)) / n
    lines = [
        'maps: {} (+{} generator errors), {:.1f} s/map'.format(n, len(rows) - n, elapsed / max(1, len(rows))),
        'accepted by verifier: {:.0f}%   beatable: {:.0f}%'.format(pct(lambda r: r['accepted']), pct(lambda r: r['beatable'])),
        'items in the open (outdoors, free from spawn): avg {:.2f}, maps with 0: {:.0f}%'.format(avg('open'), pct(lambda r: r['open'] == 0)),
        'items within {} of spawn: avg {:.2f}'.format(NEAR, avg('near')),
        'items free from spawn: avg {:.2f}'.format(avg('free')),
        'hidden items (room or gated) of 6: avg {:.2f}'.format(avg('hidden')),
        'closest pair of items: avg {:.1f} tiles, maps with a pair < 8 apart: {:.0f}%'.format(avg('min_gap'), pct(lambda r: r['min_gap'] < 8)),
        'spheres: avg {:.2f} (3+: {:.0f}%, 4+: {:.0f}%)'.format(avg('spheres'), pct(lambda r: r['spheres'] >= 3), pct(lambda r: r['spheres'] >= 4)),
        'every step opens 1-2 traversal items: {:.0f}%   biggest step avg {:.2f}'.format(pct(lambda r: r['one_two']), avg('max_sphere')),
        'gems free from spawn: avg {:.1f}'.format(avg('gems_free')),
        'choices (over every collection order, moments with 2+ items left): forced to 1 option {:.0f}% of the time; maps never forced {:.0f}%'.format(100 * avg('forced_share'), pct(lambda r: r['forced'] == 0)),
        'map open with no items: avg {:.0f}% (maps under 20%: {:.0f}%); distinct vault types per map: {:.1f}'.format(100 * avg('start_share'), pct(lambda r: r['start_share'] < 0.2), avg('vault_types')),
        'castle item: present {:.0f}%, optional to win {:.0f}% of those, gems it guards avg {:.1f}; which: {}'.format(
            pct(lambda r: r['castle_item']), 100 * sum(1 for r in ok if r['castle_item'] and r['castle_optional']) / max(1, sum(1 for r in ok if r['castle_item'])),
            sum(r['castle_item_gems'] for r in ok if r['castle_item']) / max(1, sum(1 for r in ok if r['castle_item'])),
            dict(__import__('collections').Counter(r['castle_item'] for r in ok if r['castle_item']))),
        'Bow: needed to win {:.0f}%; gems behind it avg {:.1f}; items behind it avg {:.2f}; snakes per map {:.1f}'.format(
            pct(lambda r: r['bow_needed']), avg('bow_gems'), avg('bow_items'), avg('snakes')),
        'empty land (tiles 8+ from anything built or placed): avg {:.0f}; maps with 0: {:.0f}%'.format(avg('empty_land'), pct(lambda r: r['empty_land'] == 0)),
        'big buildings (12+ tiles) per map {:.1f}, still idle {:.2f}; castle gems avg {:.1f} (4 in {:.0f}% of maps), castle ogres avg {:.1f}'.format(
            avg('big_buildings'), avg('idle_buildings'), avg('castle_gems'), pct(lambda r: r['castle_gems'] == 4), avg('castle_ogres')),
        'access items reachable at the start: avg {:.2f}; maps with 2+: {:.0f}%'.format(avg('start_options'), pct(lambda r: r['start_options'] >= 2)),
        'shrines: farthest any tile is from a shrine avg {:.1f}; of 9 map sectors, avg {:.1f} have one (spawn counts)'.format(avg('shrine_cover'), avg('shrine_sectors')),
        'shrines (of 5, not counting spawn) in interesting spots: avg {:.2f}'.format(avg('shrine_interest')),
        'gem count: maps with fewer than 20: {}; gem pairs 3 or fewer tiles apart: avg {:.1f}'.format(
            sum(1 for r in ok if r['gem_count'] < 20), avg('gem_close_pairs')),
        'gems (of 20) in interesting spots: avg {:.1f}; within {} of spawn: avg {:.2f}'.format(avg('gem_interest'), NEAR, avg('gems_near')),
        'ogres: avg {:.1f}, of which in rooms {:.1f}'.format(avg('ogres'), avg('ogres_in_rooms')),
    ]
    fails = {}
    for r in ok:
        for f in r['fails']:
            key = f.split(' ', 1)[-1] if f[0].isdigit() else f
            key = 'only N spheres' if 'spheres' in f else key
            fails[key] = fails.get(key, 0) + 1
    lines.append('rejection reasons: {}'.format(fails))
    return '\n'.join(lines)


if __name__ == '__main__':
    # --old-extras: shrines, gems and ogres as before the 2026-11-22 changes
    if '--old-extras' in sys.argv:
        import map as _map
        import gem_placement as _gp
        _map.SHRINE_PLACEMENT = 'random'
        _map.PLACE_OGRES = False
        _gp.GEM_TOURNAMENT = 1
    if '--no-fill' in sys.argv:
        import map as _map
        _map.FILL_EMPTY = False
    if '--no-trails' in sys.argv:
        import map as _map
        _map.CARVE_TRAILS = False
    if '--forward' in sys.argv:   # item placement as before 2026-11-22 (one step at a time)
        import map as _map
        _map.ITEM_PLACEMENT = 'forward'
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    rows, el = run(range(a, b))
    print(summarize(rows, el))
    if '--csv' in sys.argv:
        import csv
        path = sys.argv[sys.argv.index('--csv') + 1]
        keys = ['seed', 'accepted', 'beatable', 'open', 'near', 'hidden', 'free', 'min_gap',
                'spheres', 'trav_per_sphere', 'one_two', 'gems_free', 'win_set', 'shrine_cover', 'forced', 'choice_moments', 'start_options',
                'shrine_sectors', 'shrine_interest', 'gem_interest', 'gems_near', 'ogres', 'ogres_in_rooms', 'fails', 'error']
        with open(path, 'w', newline='') as f:
            wr = csv.DictWriter(f, keys, extrasaction='ignore')
            wr.writeheader()
            for r in rows:
                wr.writerow(r)
