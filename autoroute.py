"""
Greedy auto-router: plays a map with the simulator to produce SOME winning
route (far from optimal). Used as an end-to-end test of game.py, and to give
a starting route to paste into play.py.

    python autoroute.py 1          -> route for seed 1, up to the boss room
    python autoroute.py 1 --fight  -> also try the boss fight (often fails)

By default the route counts as done once you're in the boss room holding
enough gems for every seal (Andrew's call: the boss fight needs luring him
off seals, which this greedy player can't plan).

Strategy: repeatedly walk (BFS, 2 tiles per turn) to the nearest reachable
item, then gems until it can afford every seal, then the seals, then hit
the boss. It re-plans from the real simulated state after every turn, so
enemy hits and deaths are handled. It gets into and out of the boat at
shores. With the Axe it cuts through trees, and
it attacks ogres that stand in its way or next to it, and waits for an
ogre to come to it rather than walking into its reach. It
never tanks desert damage or uses knockback skips.
"""
import sys
from collections import deque

import game
from game import Command, Simulator, DIRS
from support_classes import Coordinates, TerrType, CellContents

NAMES = {v: k for k, v in DIRS.items()}


def passable(sim, st, c, desert_ok=False):
    t = sim.terrain(st, c)
    if t == TerrType.DESERT and CellContents.DESERT_CLOAK not in st.items and not desert_ok:
        return False
    if t == TerrType.TREE:
        return CellContents.AXE in st.items      # we'll cut it on the way
    if t == TerrType.WATER and CellContents.WATER_BOOTS not in st.items:
        return False
    if t == TerrType.LAVA and CellContents.FIRE_SHIELD not in st.items:
        return False
    e = sim.enemy_at(st, c)
    if e is not None and e.kind == 'ghost' and CellContents.SILVER_SWORD not in st.items:
        return False                          # can't hurt it: treat it as a wall
    return e is None or e.kind != 'snake'    # an ogre or the boss in the way gets attacked


def bfs(sim, st, goal_fn):
    """Tile BFS from the player to the nearest goal, avoiding desert (without
    the Cloak) unless there's no other way."""
    # First try to keep out of ogres' reach too (an ogre on a shore can hit
    # you in your boat but can't come to you, so waiting for it doesn't help).
    first = [] if _no_avoid > 0 else [_bfs(sim, st, goal_fn, False, avoid_ogres=True)]
    return (next((p for p in first if p), None)
            or _bfs(sim, st, goal_fn, False) or _bfs(sim, st, goal_fn, True))


_no_avoid = 0     # turns left with ogre avoidance switched off (loop breaker)


def _bfs(sim, st, goal_fn, desert_ok, avoid_ogres=False):
    start = st.pos
    prev = {start: None}
    q = deque([start])
    while q:
        c = q.popleft()
        if goal_fn(c) and c != start:
            path = []
            while c is not None:
                path.append(c)
                c = prev[c]
            return path[::-1]
        for n in sorted(sim.neighbors(st, c), key=lambda n: (n.y, n.x)):
            if n not in prev and (goal_fn(n) or (passable(sim, st, n, desert_ok)
                                                 and not (avoid_ogres and _exposed(sim, st, n)))):
                prev[n] = c
                q.append(n)
    return None


MAX_WAITS = 3     # give up waiting for an ogre that can't reach us


def _threats(sim, st):
    """Enemies we fight when they come close: ogres, and ghosts once we hold the Silver Sword."""
    sword = CellContents.SILVER_SWORD in st.items
    return [e for e in st.enemies if e.alive and (e.kind == 'ogre' or (e.kind == 'ghost' and sword))]


def _exposed(sim, st, c):
    """Ending a turn on c lets an awake ogre hit us (adjacent, no wall)."""
    return any(not e.stunned and e.pos.get_distance(c) == 1 and sim.can_step(c, e.pos)
               for e in _threats(sim, st))


def next_command(sim, st):
    n_seals = len(sim.seals)
    # An ogre right next to us gets hit first (it is knocked back and stunned).
    for e in _threats(sim, st):
        d = (e.pos.x - st.pos.x, e.pos.y - st.pos.y)
        if d in NAMES and sim.can_step(st.pos, e.pos):
            return Command('x' + NAMES[d], 'attack', [NAMES[d]])
    # Down to 1 Life? Heal at a shrine if one is close (also moves the respawn point).
    if st.life == 1:
        if sim.contents(st, st.pos) == CellContents.SHRINE:
            return Command('e.', 'interact')
        path = bfs(sim, st, lambda c: sim.contents(st, c) == CellContents.SHRINE)
        if path and len(path) <= 12:
            return _walk(sim, st, path)
    boss = next((e for e in st.enemies if e.kind == 'boss' and e.alive), None)
    if len(st.seals_broken) == n_seals and boss:
        d = (boss.pos.x - st.pos.x, boss.pos.y - st.pos.y)
        if d in NAMES and sim.can_step(st.pos, boss.pos):
            return Command('x' + NAMES[d], 'attack', [NAMES[d]])
        goal = lambda c: c.get_distance(boss.pos) == 1
    else:
        here = sim.contents(st, st.pos)
        need = (n_seals - len(st.seals_broken)) * game.GEMS_PER_SEAL

        def wanted(c):
            cont = sim.contents(st, c)
            if cont in game.ITEMS:
                return True
            if cont == CellContents.GEM and st.gems < need:
                return True
            if cont == CellContents.SEAL and c not in st.seals_broken and st.gems >= need:
                return True
            if cont == CellContents.GATE and not st.gate_open and st.gems >= sim.gate_gems:
                return True
            return False
        if wanted(st.pos) or (here == CellContents.SEAL and st.pos not in st.seals_broken
                              and st.gems >= game.GEMS_PER_SEAL):
            return Command('e.', 'interact')
        goal = wanted
    path = bfs(sim, st, goal)
    if path is None:
        return None
    return _walk(sim, st, path)


def _walk(sim, st, path):
    global _waits
    dirs = []
    ends = []
    cur = st.pos
    for c in path[1:3]:
        d = NAMES[(c.x - cur.x, c.y - cur.y)]
        if sim.terrain(st, c) == TerrType.TREE or sim.enemy_at(st, c):
            if not dirs:
                _waits = 0
                return Command('x' + d, 'attack', [d])
            break
        if (sim.terrain(st, c) == TerrType.WATER) != st.in_boat:
            # shore crossing: get into / out of the boat (its own turn)
            if not dirs:
                _waits = 0
                return Command('e' + d, 'interact_dir', [d])
            break
        dirs.append(d)
        ends.append(c)
        cur = c
    # Don't end the turn next to an awake ogre: stop short, or wait for it
    # to step up to us so we get the first hit.
    while dirs and _exposed(sim, st, ends[len(dirs) - 1]) and _waits < MAX_WAITS:
        dirs.pop()
    if not dirs:
        _waits += 1
        return Command('..', 'wait')
    _waits = 0
    return Command(''.join(dirs) if len(dirs) == 2 else dirs[0] + '.', 'move', dirs)


_waits = 0


def reached_boss(sim, st):
    """In the boss room with enough gems for every seal."""
    need = len(sim.seals) * game.GEMS_PER_SEAL
    return (not st.warp and sim.room(st.pos) == sim.boss_room
            and st.gems + len(st.seals_broken) * game.GEMS_PER_SEAL >= need)


def autoroute(game_map, max_turns=3000, fight=False):
    """Returns (commands, final_state, done). done = won, or (unless fight)
    reached the boss room with enough gems."""
    global _waits, _no_avoid
    _waits = 0
    _no_avoid = 0
    sim = Simulator(game_map)
    st = sim.initial_state()
    cmds = []
    recent = []
    while not st.won and st.turn < max_turns:
        if not fight and reached_boss(sim, st):
            return cmds, st, True
        # Loop breaker: pacing back and forth near an ogre? Stop avoiding
        # ogres for a while and fight through.
        recent = (recent + [st.pos])[-16:]
        if _no_avoid > 0:
            _no_avoid -= 1
        elif recent.count(st.pos) >= 4:
            _no_avoid = 12
        c = next_command(sim, st)
        if c is None:
            break
        cmds.append(c.text)
        st = sim.step(st, c)
        while st.warp:
            st = sim.step(st, Command('~~', 'travel'))
    return cmds, st, st.won


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    seed = int(args[0]) if args else 1
    fight = '--fight' in sys.argv
    m, seed = game.load_map(seed)
    cmds, st, done = autoroute(m, fight=fight)
    result = 'VICTORY' if st.won else 'reached the boss room with {} gems'.format(st.gems) if done else 'stuck'
    print('# seed {}: {} in {} turns'.format(seed, result, st.turn))
    for i in range(0, len(cmds), 20):
        print(' '.join(cmds[i:i + 20]))
