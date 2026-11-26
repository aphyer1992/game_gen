"""
Turn simulator: runs a list of commands on a generated map and records the
game state after every turn.

    from game import load_map, parse_commands, simulate
    m = load_map(seed=5)
    cmds, errors = parse_commands("dd dd ww e.")
    states = simulate(m, cmds)     # states[0] = start, states[i] = after turn i
    print(states[-1].describe())

Command vocabulary (two characters per turn, as in `rules`; case and spacing
don't matter, so "ddddww" is the same as "dd dd ww"):

    ww, wa, sd ...   move up to two tiles (w=north/up, a=west, s=south, d=east)
    w.  (or just w)  move one tile
    xw, xa, xs, xd   attack in that direction
    e.  (or just e)  interact with your tile (shrine, pickup, seal); i. works too
    ew, ea, es, ed   interact with the neighbouring tile (iw/ia/is/id work too):
                     with the Boat, facing water: get into the boat (you move onto
                     that water tile); in the boat, facing land: get out onto it.
                     In the boat you move through water normally but can't
                     walk onto land; out of it, water still drowns you.
    e0 .. e9         with the Blessing, at a shrine: warp to shrine N, if you've
                     interacted with it before (the spawn shrine counts). Takes 4 turns;
                     the 3 travel turns are added automatically (no command needed)
    ..               wait a turn
    dd*5             repeat a command 5 times
    # ...            comment to the end of the line

Turn order: the player acts, then every enemy acts (lowest y, then lowest x).

Readings of the rules where they were ambiguous (see docs/simulator.md):
  * Moving into a tree, a wall or an enemy stops you; the turn is still used.
    Only a Sawblade hurts when you walk into it (none are placed yet).
  * Desert without the Cloak: damage happens at the start of your turn,
    before you act. A 2-tile move made from desert only goes 1 tile.
  * Dying (Life 0) respawns you at the end of that turn at your last shrine
    with full Life. It costs no extra time. Enemies keep their state.
  * Interacting with a shrine heals you and sets it as your respawn point.
    Warping (eN) does not heal; interact at the destination if you want that.
  * During the 3 warp-travel turns you are off the map: enemies can't hit you.
  * Attacks don't go through walls. The Bow's arrow flies over water/lava and
    stops at a wall, a tree or the map edge. The Axe only cuts an adjacent
    tree: an arrow that reaches a tree further away just stops there.
  * Ogres (and the boss) attack only an orthogonally adjacent player with no
    wall between. They chase only if they could walk to you in 5 steps or
    fewer (not as the crow flies), stepping along a shortest walkable path
    (tie-break lowest y then x). Otherwise they stay put.
  * Lava snakes follow the rules literally: turn A aim (if collinear, within
    5, no wall or tree between), turn B breathe down that line (range 5,
    hits if you are still on it). A tree cut in between opens the line. The breathing turn is the snake's whole turn.
  * Stun: an enemy you hit (and don't kill) is stunned and skips its next
    turn, so a knocked-back Ogre doesn't immediately walk back at you.
  * Boss: hits you whenever you're in melee range (even standing outside
    its door). It only chases while you are in its room (within 5);
    otherwise it walks back toward the room centre. It never leaves its room by walking.
    Each seal costs 4 gems. With all seals broken, any hit kills it: victory.
  * Knockback: 2 tiles. If the first tile is blocked (wall, edge, tree,
    another figure), no movement. If only the second is blocked, 1 tile.
    Hazards (water/lava) only matter on the tile you land on.

Castle gate (map.setup_castle_gate): the castle's gate doorway is shut
until you stand on a Gate tile just outside it and interact (e.) holding at
least map.gate_gems gems. Gems aren't spent; the gate stays open.

Ghosts (2026-11-23): roam and hit like Ogres (HP 2), but attacks pass
through them unless you hold the Silver Sword (then they take damage, are
knocked back and stunned as usual). Water and lava don't kill them.

Horse (redesigned 2026-11-24 after Andrew's playtest: the old 4-tile
gallop was far too easy). h. mounts the Horse, which takes the turn and
needs solid open ground (grass or road, outdoors, not from the boat). While
mounted, every direction letter of a move is worth 2 tiles: dd = 4 east,
dw = 2 east then 2 north, d. = 2 east. You come off the horse (and stop) when
you bump into anything (wall, tree, enemy, map edge), when the next tile is a
building/castle floor, water, lava or desert (you stop before it), when you
are hit, and when you warp. Waiting and interacting keep you mounted.

Glitches are not implemented. `Simulator.glitches` is a set of names that
command handlers can check; see GLITCH HOOKS below.
"""
import contextlib
import copy
import io
import random
import re
from collections import deque
import sys
import types

if 'xlsxwriter' not in sys.modules:          # map.py imports it for Excel export only
    try:
        import xlsxwriter  # noqa: F401
    except ImportError:
        sys.modules['xlsxwriter'] = types.ModuleType('xlsxwriter')

from support_classes import Coordinates, TerrType, CellContents

MAX_LIFE = 3
GEMS_PER_SEAL = 4
OGRE_HP = 3
OGRE_RANGE = 5
SNAKE_RANGE = 5
GHOST_HP = 2
MOUNTED_STRIDE = 2   # tiles per direction letter while riding
KNOCKBACK = 2
WARP_TURNS = 4

DIRS = {'w': (0, 1), 'a': (-1, 0), 's': (0, -1), 'd': (1, 0)}
DIR_NAMES = {(0, 1): 'north', (-1, 0): 'west', (0, -1): 'south', (1, 0): 'east'}

def item_name(item):
    """Display name. The water item (WATER_BOOTS in the map code) is a Boat."""
    return 'Boat' if item == CellContents.WATER_BOOTS else item.label


ITEMS = (CellContents.WATER_BOOTS, CellContents.FIRE_SHIELD, CellContents.AXE,
         CellContents.DESERT_CLOAK, CellContents.BOW, CellContents.BLESSING,
         CellContents.SILVER_SWORD, CellContents.HORSE)


# ----------------------------------------------------------------------------
# Map loading
# ----------------------------------------------------------------------------
def load_map(seed, verified=True, width=50, height=50):
    """Build a map for `seed`. With verified=True, re-rolls upward from the seed
    until verify.py accepts the map. Returns (map, actual_seed)."""
    if verified:
        from verify import generate_verified_map
        m, _, s = generate_verified_map(width, height, seed=seed)
        return m, s
    from map import Map
    random.seed(seed)
    m = Map(width, height)
    with contextlib.redirect_stdout(io.StringIO()):
        m.generate_map()
    return m, seed


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------
class Command:
    """One turn. kind: 'move' (dirs = list of 1-2 direction letters),
    'attack' (dirs = [d]), 'interact', 'warp' (target = shrine number), 'wait',
    'mount' (h., needs the Horse)."""
    def __init__(self, text, kind, dirs=(), target=None, line=None):
        self.text, self.kind, self.dirs, self.target, self.line = text, kind, list(dirs), target, line

    def __repr__(self):
        return 'Command({!r})'.format(self.text)


def _parse_token(tok):
    t = tok.lower()
    if t in ('..', '.'):
        return Command(t, 'wait')
    if t in ('e', 'e.', 'ee', 'i', 'i.'):
        return Command(t, 'interact')
    if len(t) == 2 and t[0] in 'ei' and t[1].isdigit():
        return Command(t, 'warp', target=int(t[1]))
    if len(t) == 2 and t[0] in 'ei' and t[1] in DIRS:
        return Command(t, 'interact_dir', [t[1]])
    if len(t) == 2 and t[0] == 'x' and t[1] in DIRS:
        return Command(t, 'attack', [t[1]])
    if t in ('h', 'h.'):
        return Command(t, 'mount')
    if len(t) in (1, 2) and t[0] in DIRS and (len(t) == 1 or t[1] in DIRS or t[1] == '.'):
        return Command(t, 'move', [ch for ch in t if ch in DIRS])
    return None


UNFINISHED = 'unfinished command'


def parse_commands(text):
    """Parse route text into a list of Commands. Returns (commands, errors);
    errors is a list of (line_number, message). Commands after the first
    error are dropped, so a typo never silently shifts the rest of the route."""
    cmds, errors = [], []
    for ln, raw in enumerate(text.splitlines(), 1):
        line = raw.split('#', 1)[0]
        for word in line.replace(',', ' ').split():
            rep = 1
            m = re.fullmatch(r'(.+?)\*(\d+)', word)
            if m:
                word, rep = m.group(1), int(m.group(2))
            # split a run like "ddddww" into 2-char turns
            pieces = [word] if len(word) <= 2 else [word[i:i + 2] for i in range(0, len(word), 2)]
            for p in pieces:
                if len(p) == 1 and len(word) > 2:
                    # odd run: keep the complete turns before the dangling character
                    errors.append((ln, UNFINISHED + ' "{}"'.format(p)))
                    break
                c = _parse_token(p)
                if c is None:
                    errors.append((ln, 'unknown command "{}"'.format(p)))
                    break
                c.line = ln
                if not errors:
                    cmds.extend(copy.copy(c) for _ in range(rep))
    return cmds, errors


# ----------------------------------------------------------------------------
# State
# ----------------------------------------------------------------------------
class Enemy:
    def __init__(self, kind, pos, hp):
        self.kind = kind          # 'ogre', 'snake', 'boss', 'ghost'
        self.pos = pos
        self.hp = hp
        self.alive = True
        self.aim = None           # snakes: direction (dx, dy) they're aiming
        self.stunned = False      # hit by the player: skips its next turn

    @property
    def label(self):
        return {'ogre': 'Ogre', 'snake': 'Lava snake', 'boss': 'Boss', 'ghost': 'Ghost'}[self.kind]

    def describe(self):
        s = '{} at ({}, {})'.format(self.label, self.pos.x, self.pos.y)
        if self.kind in ('ogre', 'ghost'):
            s += ', HP {}'.format(self.hp)
        if self.kind == 'snake' and self.aim:
            s += ', AIMING {}'.format(DIR_NAMES[self.aim])
        if self.stunned:
            s += ', STUNNED'
        if not self.alive:
            s += ' (dead)'
        return s


class GameState:
    def __init__(self):
        self.turn = 0
        self.pos = Coordinates(0, 0)
        self.life = MAX_LIFE
        self.items = set()             # CellContents
        self.gems = 0                  # gems held (unspent)
        self.gems_collected = 0
        self.seals_broken = set()      # Coordinates
        self.collected = set()         # Coordinates of picked-up gems/items
        self.cut_trees = set()         # Coordinates turned to grass
        self.respawn = Coordinates(0, 0)
        self.visited_shrines = set()   # shrines you've interacted with (warp targets); spawn counts
        self.deaths = 0
        self.enemies = []
        self.warp = None               # (target Coordinates, turns left) while travelling
        self.won = False
        self.in_boat = False           # sailing (the water item is a boat)
        self.gate_open = False         # castle gate opened (needs gems, see do_interact)
        self.mounted = False           # riding the Horse (h.): moves count double
        self.command = None            # the Command that produced this state
        self.events = []               # what happened this turn
        self.trail = []                # tiles the player passed through this turn

    def copy(self):
        s = copy.copy(self)
        s.items = set(self.items)
        s.seals_broken = set(self.seals_broken)
        s.collected = set(self.collected)
        s.cut_trees = set(self.cut_trees)
        s.visited_shrines = set(self.visited_shrines)
        s.enemies = [copy.copy(e) for e in self.enemies]
        s.events = []
        s.trail = []
        return s

    def describe(self, seals_total=4, shrines=None):
        """shrines: the Simulator's numbered shrine list, to show warp targets."""
        lines = [
            'Turn {}  ({} s)'.format(self.turn, self.turn),
            'Position: ({}, {})'.format(self.pos.x, self.pos.y) + ('  [warping]' if self.warp else '')
            + ('  [in the boat]' if self.in_boat else '') + ('  [riding]' if self.mounted else ''),
            'Life: {}/{}'.format(self.life, MAX_LIFE) + ('   deaths: {}'.format(self.deaths) if self.deaths else ''),
            'Items: ' + (', '.join(sorted(item_name(i) for i in self.items)) or 'none'),
            'Gems: {} held ({} collected)'.format(self.gems, self.gems_collected),
            'Seals broken: {}/{}'.format(len(self.seals_broken), seals_total),
            'Respawn shrine: ({}, {})'.format(self.respawn.x, self.respawn.y),
        ]
        if self.gate_open:
            lines.append('Castle gate: open')
        if shrines is not None and CellContents.BLESSING in self.items:
            ids = [str(i) for i, c in enumerate(shrines) if c in self.visited_shrines]
            lines.append('Warp targets (visited shrines): ' + ', '.join(ids))
        if self.won:
            lines.insert(0, '*** VICTORY in {} turns ***'.format(self.turn))
        return '\n'.join(lines)


# ----------------------------------------------------------------------------
# Simulator
# ----------------------------------------------------------------------------
class Simulator:
    def __init__(self, game_map, glitches=()):
        self.map = game_map
        self.w, self.h = game_map.width, game_map.height
        self.glitches = set(glitches)   # GLITCH HOOKS: e.g. {'corner_clip'}; nothing checks these yet
        # Precompute open edges (Map.is_wall does list scans).
        self.open = {}
        for y in range(self.h):
            for x in range(self.w):
                c = Coordinates(x, y)
                self.open[c] = {n for n in c.get_neighboring_coordinates()
                                if game_map.is_valid_coordinates(n) and not game_map.is_wall(c, n)}
        # Castle gate: its doorway is closed until a state has gate_open.
        self.gate_gems = getattr(game_map, 'gate_gems', 0)
        self.gate_edges = set()
        if self.gate_gems:
            for a, b in getattr(game_map, 'castle_gate', []):
                self.gate_edges |= {(a, b), (b, a)}
                self.open[a].discard(b)
                self.open[b].discard(a)
        self.shrines = sorted((Coordinates(x, y) for y in range(self.h) for x in range(self.w)
                               if game_map.get_cell_contents(x, y) == CellContents.SHRINE),
                              key=lambda c: (c.y, c.x))
        self.seals = [Coordinates(x, y) for y in range(self.h) for x in range(self.w)
                      if game_map.get_cell_contents(x, y) == CellContents.SEAL]
        self.boss_room = None
        self.boss_center = None

    # --- map queries ---------------------------------------------------------
    def terrain(self, state, c):
        if c in state.cut_trees:
            return TerrType.GRASS
        return self.map.get_cell(c.x, c.y)

    def contents(self, state, c):
        """Static contents still on the tile (pickups vanish once collected)."""
        cont = self.map.get_cell_contents(c.x, c.y)
        if cont in (CellContents.OGRE, CellContents.BOSS, CellContents.DRAGON, CellContents.GHOST):
            return CellContents.EMPTY
        if c in state.collected:
            return CellContents.EMPTY
        return cont

    def can_step(self, a, b, state=None):
        """Open edge a->b. Pass the state so an opened castle gate counts."""
        if b in self.open.get(a, ()):
            return True
        return state is not None and state.gate_open and (a, b) in self.gate_edges

    def neighbors(self, state, c):
        """Tiles you can step to from c in this state (gate included once open)."""
        out = set(self.open.get(c, ()))
        if state.gate_open:
            out |= {b for a, b in self.gate_edges if a == c}
        return out

    def enemy_at(self, state, c):
        for e in state.enemies:
            if e.alive and e.pos == c:
                return e
        return None

    def room(self, c):
        return self.map.get_room_number(c.x, c.y)

    # --- setup --------------------------------------------------------------
    def initial_state(self):
        s = GameState()
        s.pos = self.shrines[0] if self.shrines else Coordinates(0, 0)
        s.respawn = s.pos
        s.visited_shrines = {s.pos}
        kinds = {CellContents.OGRE: ('ogre', OGRE_HP), CellContents.DRAGON: ('snake', 1),
                 CellContents.GHOST: ('ghost', GHOST_HP),
                 CellContents.BOSS: ('boss', None)}
        for y in range(self.h):
            for x in range(self.w):
                k = kinds.get(self.map.get_cell_contents(x, y))
                if k:
                    e = Enemy(k[0], Coordinates(x, y), k[1])
                    s.enemies.append(e)
                    if k[0] == 'boss':
                        self.boss_room = self.room(e.pos)
                        self.boss_center = e.pos
        return s

    def run(self, commands):
        """Returns [initial_state, state after turn 1, ...]. Stops at victory."""
        states = [self.initial_state()]
        for cmd in commands:
            if states[-1].won:
                break
            states.append(self.step(states[-1], cmd))
            while states[-1].warp and not states[-1].won:     # warp travel turns need no command
                states.append(self.step(states[-1], Command('~~', 'travel')))
        return states

    # --- one turn -------------------------------------------------------------
    def step(self, prev, cmd):
        s = prev.copy()
        s.turn += 1
        s.command = cmd
        s.trail = [s.pos]
        ev = s.events

        if s.warp:   # travel turn (run() inserts these after a warp)
            self._continue_warp(s)
        else:
            alive = True
            moves_allowed = 2
            if self.terrain(s, s.pos) == TerrType.DESERT and CellContents.DESERT_CLOAK not in s.items:
                ev.append('Desert heat: -1 Life, only 1 tile of movement this turn')
                alive = self.damage(s, 1)
                moves_allowed = 1
            if alive:
                handler = getattr(self, 'do_' + cmd.kind)
                if cmd.kind == 'move':
                    handler(s, cmd, moves_allowed)
                else:
                    handler(s, cmd)
        if not s.won:
            self.enemy_phase(s)
        return s

    # --- player actions --------------------------------------------------------
    def do_wait(self, s, cmd):
        s.events.append('Waited')

    def do_move(self, s, cmd, moves_allowed):
        if s.mounted:
            return self._ride(s, cmd)
        dirs = cmd.dirs
        if len(dirs) > moves_allowed:
            s.events.append('Only {} tile allowed (desert), ignoring "{}"'.format(moves_allowed, ''.join(dirs[moves_allowed:])))
            dirs = dirs[:moves_allowed]
        for d in dirs:
            dx, dy = DIRS[d]
            nxt = Coordinates(s.pos.x + dx, s.pos.y + dy)
            if not self.map.is_valid_coordinates(nxt):
                s.events.append('Bumped into the map edge')
                return
            if not self.can_step(s.pos, nxt, s):
                s.events.append('Bumped into a wall')
                return
            if self.terrain(s, nxt) == TerrType.TREE:
                s.events.append('Bumped into a tree')
                return
            e = self.enemy_at(s, nxt)
            if e:
                s.events.append('Blocked by {}'.format(e.label))
                return
            water = self.terrain(s, nxt) == TerrType.WATER
            if s.in_boat and not water:
                s.events.append('The boat bumped into the shore (use e{} to get off)'.format(d))
                return
            if not s.in_boat and water and CellContents.WATER_BOOTS in s.items:
                s.events.append('Stopped at the water (use e{} to get into the boat)'.format(d))
                return
            s.pos = nxt
            s.trail.append(nxt)
            if not self.check_hazard(s):
                return
        s.events.append('Moved to ({}, {})'.format(s.pos.x, s.pos.y))

    RIDE_GROUND = (TerrType.GRASS, TerrType.ROAD)

    def do_mount(self, s, cmd):
        """h.: get on the Horse (takes the turn)."""
        if CellContents.HORSE not in s.items:
            s.events.append('You need the Horse to ride')
        elif s.mounted:
            s.events.append('Already riding')
        elif s.in_boat:
            s.events.append("You can't mount the Horse from the boat")
        elif self.terrain(s, s.pos) not in self.RIDE_GROUND or self.room(s.pos) != 0:
            s.events.append('The Horse needs open grass or road to mount')
        else:
            s.mounted = True
            s.events.append('Mounted the Horse')

    def dismount(self, s, why):
        if s.mounted:
            s.mounted = False
            s.events.append('Off the Horse ({})'.format(why))

    def _ride(self, s, cmd):
        """A move on horseback: each direction letter is MOUNTED_STRIDE tiles."""
        for d in cmd.dirs:
            dx, dy = DIRS[d]
            for _ in range(MOUNTED_STRIDE):
                nxt = Coordinates(s.pos.x + dx, s.pos.y + dy)
                if not self.map.is_valid_coordinates(nxt) or not self.can_step(s.pos, nxt, s):
                    self.dismount(s, 'bumped into a wall')
                elif self.terrain(s, nxt) == TerrType.TREE:
                    self.dismount(s, 'bumped into a tree')
                elif self.enemy_at(s, nxt):
                    self.dismount(s, 'blocked by {}'.format(self.enemy_at(s, nxt).label))
                elif self.terrain(s, nxt) not in self.RIDE_GROUND or self.room(nxt) != 0:
                    self.dismount(s, "the Horse won't go onto {}".format(
                        'that floor' if self.room(nxt) != 0 else self.terrain(s, nxt).label.lower()))
                if not s.mounted:
                    s.events.append('Moved to ({}, {})'.format(s.pos.x, s.pos.y))
                    return
                s.pos = nxt
                s.trail.append(nxt)
        s.events.append('Rode to ({}, {})'.format(s.pos.x, s.pos.y))

    def do_interact_dir(self, s, cmd):
        """eX / iX: interact with the neighbouring tile. Today that means
        getting into the boat (facing water) or out of it (facing land)."""
        d = cmd.dirs[0]
        dx, dy = DIRS[d]
        nxt = Coordinates(s.pos.x + dx, s.pos.y + dy)
        if not self.map.is_valid_coordinates(nxt) or not self.can_step(s.pos, nxt, s):
            s.events.append('Nothing to interact with that way (wall)')
            return
        water = self.terrain(s, nxt) == TerrType.WATER
        if self.enemy_at(s, nxt):
            s.events.append('Something is in the way')
            return
        if not s.in_boat and water:
            if CellContents.WATER_BOOTS not in s.items:
                s.events.append("You'd need the Boat to go out on the water")
                return
            self.dismount(s, 'getting into the boat')
            s.in_boat = True
            s.pos = nxt
            s.trail.append(nxt)
            s.events.append('Got into the boat at ({}, {})'.format(nxt.x, nxt.y))
        elif s.in_boat and not water:
            if self.terrain(s, nxt) == TerrType.TREE:
                s.events.append("Can't land on a tree")
                return
            s.in_boat = False
            s.pos = nxt
            s.trail.append(nxt)
            s.events.append('Got out of the boat at ({}, {})'.format(nxt.x, nxt.y))
            self.check_hazard(s)
        else:
            s.events.append('Nothing to interact with that way')

    def do_attack(self, s, cmd):
        dx, dy = DIRS[cmd.dirs[0]]
        bow = CellContents.BOW in s.items
        cur = s.pos
        while True:
            nxt = Coordinates(cur.x + dx, cur.y + dy)
            if not self.map.is_valid_coordinates(nxt) or not self.can_step(cur, nxt, s):
                s.events.append('Attack {} hit a wall'.format(DIR_NAMES[(dx, dy)]))
                return
            e = self.enemy_at(s, nxt)
            if e:
                self.hit_enemy(s, e, (dx, dy))
                return
            if self.terrain(s, nxt) == TerrType.TREE:
                if cur != s.pos:      # arrows stop at trees; only melee range cuts them
                    s.events.append('Arrow hit a tree at ({}, {})'.format(nxt.x, nxt.y))
                elif CellContents.AXE in s.items:
                    s.cut_trees.add(nxt)
                    s.events.append('Cut down the tree at ({}, {})'.format(nxt.x, nxt.y))
                else:
                    s.events.append('Hit a tree (no Axe)')
                return
            if not bow:
                s.events.append('Attacked {}: nothing there'.format(DIR_NAMES[(dx, dy)]))
                return
            cur = nxt

    def hit_enemy(self, s, e, d):
        if e.kind == 'boss':
            if len(s.seals_broken) >= len(self.seals):
                e.alive = False
                s.won = True
                s.events.append('Struck down the Boss! VICTORY in {} turns'.format(s.turn))
                return
            s.events.append('Hit the Boss (invulnerable until all seals are broken)')
        elif e.kind == 'ghost' and CellContents.SILVER_SWORD not in s.items:
            s.events.append('The attack passes straight through the Ghost (it needs the Silver Sword)')
            return
        else:
            e.hp -= 1
            if e.hp <= 0:
                e.alive = False
                s.events.append('Killed {} at ({}, {})'.format(e.label, e.pos.x, e.pos.y))
                return
            s.events.append('Hit {} (HP {})'.format(e.label, e.hp))
        if e.kind != 'snake':
            e.stunned = True
            self.knock_enemy(s, e, d)

    def do_interact(self, s, cmd):
        c = s.pos
        cont = self.contents(s, c)
        if cont == CellContents.SHRINE:
            s.life = MAX_LIFE
            s.respawn = c
            s.events.append('Shrine: Life restored, respawn point set')
            if c not in s.visited_shrines:
                s.visited_shrines.add(c)
                s.events.append('Shrine {} is now a warp target'.format(self.shrines.index(c)))
        elif cont == CellContents.GEM:
            s.gems += 1
            s.gems_collected += 1
            s.collected.add(c)
            s.events.append('Picked up a Power Gem ({} held)'.format(s.gems))
        elif cont in ITEMS:
            s.items.add(cont)
            s.collected.add(c)
            s.events.append('Picked up the {}'.format(item_name(cont)))
        elif cont == CellContents.GATE:
            if s.gate_open:
                s.events.append('The castle gate is already open')
            elif s.gems < self.gate_gems:
                s.events.append('The castle gate needs {} gems, you hold {}'.format(self.gate_gems, s.gems))
            else:
                s.gate_open = True
                s.events.append('The castle gate swings open ({} gems shown)'.format(s.gems))
        elif cont == CellContents.SEAL:
            if c in s.seals_broken:
                s.events.append('This seal is already broken')
            elif s.gems < GEMS_PER_SEAL:
                s.events.append('Seal needs {} gems, you hold {}'.format(GEMS_PER_SEAL, s.gems))
            else:
                s.gems -= GEMS_PER_SEAL
                s.seals_broken.add(c)
                s.events.append('Broke a seal ({}/{})'.format(len(s.seals_broken), len(self.seals)))
        else:
            s.events.append('Nothing to interact with here')

    def do_warp(self, s, cmd):
        if CellContents.BLESSING not in s.items:
            s.events.append('Warp failed: you need the Blessing')
            return
        if self.contents(s, s.pos) != CellContents.SHRINE:
            s.events.append('Warp failed: not standing on a shrine')
            return
        if cmd.target >= len(self.shrines):
            s.events.append('Warp failed: there is no shrine {}'.format(cmd.target))
            return
        target = self.shrines[cmd.target]
        self.dismount(s, 'warping') if target in s.visited_shrines else None
        if target not in s.visited_shrines:
            s.events.append("Warp failed: you haven't visited shrine {} yet".format(cmd.target))
            return
        if target == s.pos:
            s.events.append('Warp failed: already at shrine {}'.format(cmd.target))
            return
        s.warp = (target, WARP_TURNS - 1)
        s.events.append('Warping to shrine {} at ({}, {})'.format(cmd.target, target.x, target.y))

    def _continue_warp(self, s):
        target, left = s.warp
        left -= 1
        if left > 0:
            s.warp = (target, left)
            s.events.append('Warping...')
            return
        s.warp = None
        e = self.enemy_at(s, target)
        if e:   # very unlikely; land next to it
            self.knock_enemy(s, e, (0, 1))
        s.pos = target
        s.trail.append(target)
        s.events.append('Arrived at shrine ({}, {})'.format(target.x, target.y))

    # --- damage, death, hazards ---------------------------------------------
    def damage(self, s, amount):
        """Returns True if the player survives."""
        s.life -= amount
        if s.life <= 0:
            self.die(s, 'ran out of Life')
            return False
        return True

    def die(self, s, why):
        s.mounted = False
        s.deaths += 1
        s.events.append('DIED ({}). Respawned at ({}, {})'.format(why, s.respawn.x, s.respawn.y))
        s.pos = s.respawn
        s.life = MAX_LIFE
        s.warp = None
        s.in_boat = False
        s.trail.append(s.pos)
        for e in s.enemies:
            e.aim = None

    def check_hazard(self, s):
        t = self.terrain(s, s.pos)
        if t == TerrType.WATER and not s.in_boat:
            self.die(s, 'fell in the water' + ('' if CellContents.WATER_BOOTS in s.items
                                              else ' without the Boat'))
            return False
        if t != TerrType.WATER and s.in_boat:
            s.in_boat = False
            s.events.append('Thrown out of the boat onto land')
        if t == TerrType.LAVA and CellContents.FIRE_SHIELD not in s.items:
            self.die(s, 'walked into lava without the Flame Shield')
            return False
        return True

    def blocked_for_knockback(self, s, a, b, mover):
        if not self.map.is_valid_coordinates(b) or not self.can_step(a, b, s):
            return True
        if self.terrain(s, b) == TerrType.TREE:
            return True
        e = self.enemy_at(s, b)
        if e and e is not mover:
            return True
        if mover is not None and s.pos == b and not s.warp:
            return True
        return False

    def knockback_dest(self, s, start, d, mover):
        cur = start
        for _ in range(KNOCKBACK):
            nxt = Coordinates(cur.x + d[0], cur.y + d[1])
            if self.blocked_for_knockback(s, cur, nxt, mover):
                break
            cur = nxt
        return cur

    def knock_player(self, s, d):
        dest = self.knockback_dest(s, s.pos, d, None)
        if dest == s.pos:
            s.events.append('Knocked {} but bounced off'.format(DIR_NAMES[d]))
            return
        s.pos = dest
        s.trail.append(dest)
        s.events.append('Knocked {} to ({}, {})'.format(DIR_NAMES[d], dest.x, dest.y))
        self.check_hazard(s)

    def knock_enemy(self, s, e, d):
        dest = self.knockback_dest(s, e.pos, d, e)
        if dest == e.pos:
            return
        e.pos = dest
        s.events.append('{} knocked to ({}, {})'.format(e.label, dest.x, dest.y))
        if e.kind == 'ogre' and self.terrain(s, dest) in (TerrType.WATER, TerrType.LAVA):
            e.alive = False
            s.events.append('Ogre fell into {} and died'.format(self.terrain(s, dest).label.lower()))

    def player_hit(self, s, who, d):
        """1 damage + knockback in direction d."""
        s.events.append('{} hits you! -1 Life'.format(who))
        self.dismount(s, 'thrown off')
        if self.damage(s, 1):
            self.knock_player(s, d)

    # --- enemies ----------------------------------------------------------------
    def enemy_phase(self, s):
        for e in sorted(s.enemies, key=lambda e: (e.pos.y, e.pos.x)):
            if not e.alive or s.won:
                continue
            if e.stunned:
                e.stunned = False
                s.events.append('{} at ({}, {}) is stunned and loses its turn'.format(e.label, e.pos.x, e.pos.y))
                continue
            if e.kind == 'snake':
                self.snake_turn(s, e)
            else:
                self.ogre_turn(s, e)

    def _adjacent_dir(self, a, b):
        """Direction from a to b if b is an open orthogonal neighbour of a."""
        d = (b.x - a.x, b.y - a.y)
        if d in DIR_NAMES and self.can_step(a, b):
            return d
        return None

    def ogre_turn(self, s, e):
        boss = e.kind == 'boss'
        if not s.warp:
            d = self._adjacent_dir(e.pos, s.pos)
            if d:                       # in melee range: hit (the boss too, even through its door)
                self.player_hit(s, e.label, d)
                return
        # Chase only if you're within OGRE_RANGE steps of walking (not as the
        # crow flies), so an ogre across a river doesn't wander round to you.
        dist = None
        if not s.warp and (not boss or self.room(s.pos) == self.boss_room):
            dist = self._path_distances(s, s.pos, e, limit=OGRE_RANGE)
            if e.pos not in dist:
                dist = None
        if dist is None:
            if not boss or e.pos == self.boss_center:
                return
            dist = self._path_distances(s, self.boss_center, e)   # boss walks home
        # Step along a shortest path, so it never walks into a dead end.
        here = dist.get(e.pos)
        if here is None:
            return
        for n in sorted(self.open[e.pos], key=lambda c: (c.y, c.x)):
            if dist.get(n, here) < here and not self.enemy_at(s, n) and not (n == s.pos and not s.warp):
                e.pos = n
                return

    def _ogre_can_enter(self, s, c, e):
        if self.terrain(s, c) in (TerrType.WATER, TerrType.LAVA, TerrType.TREE):
            return False
        return not (e.kind == 'boss' and self.room(c) != self.boss_room)

    def _path_distances(self, s, target, e, limit=None):
        """Steps from each tile the enemy could walk on to `target` (BFS out
        from the target). Other enemies don't count as obstacles here, since
        they move; the step actually taken must be free."""
        dist = {target: 0}
        q = deque([target])
        while q:
            c = q.popleft()
            if c == e.pos or (limit is not None and dist[c] >= limit):
                if c == e.pos:
                    break
                continue
            for n in self.open[c]:
                if n not in dist and self._ogre_can_enter(s, n, e):
                    dist[n] = dist[c] + 1
                    q.append(n)
        return dist

    def _line_dir(self, s, e, p):
        """Direction from snake e to point p if p is on a clear line within range."""
        if p.x != e.pos.x and p.y != e.pos.y:
            return None
        dist = e.pos.get_distance(p)
        if dist == 0 or dist > SNAKE_RANGE:
            return None
        d = ((p.x > e.pos.x) - (p.x < e.pos.x), (p.y > e.pos.y) - (p.y < e.pos.y))
        cur = e.pos
        for k in range(dist):
            nxt = Coordinates(cur.x + d[0], cur.y + d[1])
            if not self.can_step(cur, nxt):
                return None
            if k < dist - 1 and self.terrain(s, nxt) == TerrType.TREE:
                return None          # trees block the snake's view and its fire
            cur = nxt
        return d

    def snake_turn(self, s, e):
        if e.aim:
            d, e.aim = e.aim, None
            s.events.append('Lava snake at ({}, {}) breathes fire {}'.format(e.pos.x, e.pos.y, DIR_NAMES[d]))
            if not s.warp and self._line_dir(s, e, s.pos) == d:
                self.player_hit(s, 'Fire breath', d)
            return
        if s.warp:
            return
        d = self._line_dir(s, e, s.pos)
        if d:
            e.aim = d
            s.events.append('Lava snake at ({}, {}) takes aim {} at you'.format(e.pos.x, e.pos.y, DIR_NAMES[d]))


def simulate(game_map, commands, glitches=()):
    return Simulator(game_map, glitches).run(commands)


if __name__ == '__main__':
    # python game.py SEED "route text"   -> prints the state after every turn
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    route = sys.argv[2] if len(sys.argv) > 2 else ''
    m, seed = load_map(seed)
    cmds, errs = parse_commands(route)
    for ln, msg in errs:
        print('line {}: {}'.format(ln, msg))
    sim = Simulator(m)
    for st in sim.run(cmds):
        print('--- after "{}" ---'.format(st.command.text if st.command else 'start'))
        print(st.describe(len(sim.seals), sim.shrines))
        for e in st.events:
            print('  ' + e)
