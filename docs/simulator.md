# Simulator and play UI

Added 2026-11-21. The first version of the actual game: you type a route and see the game state after every turn, ending in a time to victory.

## Running it
```
python play.py           # opens the UI on seed 1 (Tkinter, ships with Windows Python)
python play.py 40        # a given seed
python game.py 40 "dd dd ww e."   # same thing in the terminal: prints the state after each turn
python autoroute.py 40   # prints a rough winning route for seed 40
python test_game.py      # 20 tests
```

**The UI.** Left is the map at the selected turn: you are the white circle, your path so far is the white line, and this turn's movement is the pink arrow. Shrines are numbered (for warps), seals turn grey when broken, picked-up items and gems disappear, cut trees turn to grass, ogres are red O, the boss is a purple B, and lava snakes are green triangles with a yellow arrow while they're aiming. On the right, the route box re-runs about 0.3 s after you stop typing. The turn list shows each turn's command, your position and Life (orange = you got hit, red = you died). Click a turn, or use the arrow keys, to see the full state after it: turn, position, Life, items, gems, seals, respawn shrine, what happened that turn, and enemies nearby. Hovering the map shows a tile's coordinates and contents. "Verified maps only" re-rolls the seed upward until `verify.py` accepts the map. "Fill in a rough auto-route" loads the greedy route below as a starting point (it stops in the boss room; the fight is yours).

## Command vocabulary (2 characters per turn, from `rules`)
| Command | Meaning |
|---|---|
| `ww`, `wa`, `sd` … | move up to 2 tiles (w = north/up, a = west, s = south, d = east), turning allowed |
| `w.` or `w` | move 1 tile |
| `xw` `xa` `xs` `xd` | attack in that direction |
| `e.` or `e` | interact with your tile: shrine (heal + respawn point), pick up gem/item, break a seal |
| `ew` `ea` `es` `ed` | interact with the neighbouring tile: with the Boat, facing water, get into the boat (you move onto that tile); in the boat, facing land, get out onto it. `i` works in place of `e` everywhere (`id`, `i.`, `i3`) |
| `e0` … `e9` | with the Blessing, standing on a shrine: warp to shrine N, if you've interacted with it before. Takes 4 turns; the 3 travel turns are added for you |
| `..` | wait |
| `dd*5` | repeat a command |
| `# text` | comment |

Spaces, commas and case don't matter, and runs split into pairs (`ddddww` = `dd dd ww`). A typo stops the route at that point with a red message, so it never silently shifts everything after it. A half-typed last command (`ddd`) just shows a grey note, and the turns before it still run. The turn list follows the end of the route as you type, unless you've clicked an earlier turn; then it stays on that turn.

## Turn order
1. If you start the turn in desert without the Cloak: 1 damage, and this turn's move is cut to 1 tile.
2. Your action.
3. Every enemy acts, lowest y then lowest x.

Score = the turn on which you land the killing blow on the boss.

## The Boat (the water item, Andrew 2026-11-22)
The water item is a Boat instead of boots, so water stays a real obstacle. Facing water, `eX` gets you into the boat, which takes a turn. In the boat you move through water normally, 2 tiles a turn, but bump into the shore. Facing land, `eX` gets you out, which takes another turn. Out of the boat, walking into water just stops you if you own the Boat, and drowns you if you don't. Knockback into water drowns you unless you're in the boat. Knockback onto land throws you out of it. Dying puts you back on land. The map code still calls the item `WATER_BOOTS`; only the name shown changed. Reachability is unchanged, since every water tile next to land is still reachable, so verify.py needs no change. It only costs turns.

## Rule readings I had to choose (easy to change, all in `game.py`)
1. **Bumping.** Walking into a tree, wall, map edge or enemy stops you there; the turn is still used, and it doesn't hurt (only Sawblades hurt to walk into, and none are placed yet).
2. **Desert.** The damage happens before you act, so it can kill you before you move. A 2-tile move from desert only goes 1 tile.
3. **Death.** Respawn at the end of that turn at your last shrine, full Life, no extra time. Enemies keep their positions and HP; snakes forget their aim.
4. **Shrines.** Interacting heals and sets respawn. Warps only go to shrines you've visited (Andrew). A shrine counts as visited once you've interacted with it (Andrew); just walking over it doesn't count. The spawn shrine counts from the start. In the UI, unvisited shrines are drawn dark blue, and the state panel lists your warp targets once you hold the Blessing. Warping does not heal at either end; you're off the map during travel, so nothing can hit you.
5. **Attacks** don't go through walls. The Bow's arrow flies over water and lava but stops at walls, trees and the map edge. The Axe only cuts an adjacent tree; an arrow that reaches a tree further away just stops (Andrew: cutting at range could be a glitch later).
6. **Ogres** attack only when orthogonally adjacent with no wall between. They react only if they could walk to you in 5 steps or fewer (Andrew), so an ogre just across a river, or behind a wall with a long way round, ignores you. To approach, they take one step along a shortest walkable path to you, so they never walk into a dead end that doesn't lead to you (Andrew). Ties go to the lowest y, then x. If there's no path at all (e.g. across a river), they stay put. They won't step into water, lava or trees. The boss uses the same pathing, kept inside its room.
7. **Lava snakes** follow `rules` literally: one turn aim (collinear, within 5, no wall or tree between), next turn breathe down that line (range 5). Trees block both the aim and the fire (Andrew); cutting the tree opens the line. Breathing is that whole turn, so a snake can't aim and breathe in the same turn. verify.py still only lets walls block snakes, and it lets a snake re-aim right after breathing. Both are stricter than the game, so the verifier stays on the safe side. Leaving it alone also means each seed still generates the same map.
8. **Boss.** Hits you whenever you're in melee range, even from outside its door. It chases only while you're inside its room and within 5; otherwise it walks back toward the centre, so waiting outside lets you slip in. It never walks out of its room. Each seal costs 4 gems; once all 4 are broken any hit kills it. Hitting any enemy (Ogre or boss) **stuns** it: it skips its next turn, so a knocked-back Ogre or boss doesn't walk straight back at you.
9. **Knockback** (player and enemies): 2 tiles. If the first tile is blocked (wall, edge, tree or another figure) nothing moves; if only the second is, 1 tile. Only the landing tile's hazard counts, so you can be knocked over a 1-wide river. An ogre that lands in water or lava dies.
10. **Seals vs. "three"**: `rules` says "once all three are broken"; the code places 4 seals and needs all of them.

## Code
- `game.py`: `parse_commands(text)` → `(commands, errors)`; `Simulator(map).run(commands)` → list of `GameState` (index 0 = start, then one per turn); `load_map(seed, verified)`. `GameState.describe()` gives the text summary.
- `play.py`: the Tkinter UI, ~300 lines, no dependencies beyond the generator.
- `autoroute.py`: greedy player (nearest item, then gems, then the boss room, re-planned every turn). It cuts trees, gets into and out of the boat, attacks ogres in its way, and tries to path around ogres' reach. By default it stops once it's in the boss room holding 16 gems (Andrew's call). `--fight` makes it try the fight too, which often fails. It's a test, not a par time, and its success rate moves around as the map generator changes.
- `test_game.py`: unit tests on small hand-built maps (parser, movement, desert, walls, the Boat, death and respawn, ogres, knockback, snakes, Bow, warps, stun, seals and boss kill). Two end-to-end tests run on real maps: a route's text replays to the identical state, and the auto-route reaches the boss room on at least half of 4 seeds.

## Extension points
- **Glitches:** `Simulator(map, glitches={'corner_clip', ...})` stores the set; nothing checks it yet. Each glitch would be a new command kind (e.g. a `do_clip` handler) or a check inside an existing handler.
- **Sawblades:** add an `Enemy` kind with a patrol list and a branch in `enemy_phase`. Walking into one should cost 1 Life in `do_move`. The hard part is knowing whether an arrangement can be passed at all. Andrew's idea: only place them in vaults, as hand-checked set pieces, e.g. a narrow corridor with side exits at both ends and a sawblade going up and down it, with enough room at the ends for the blade to wait while you slip past.

## Glitch ideas collected so far (not implemented)
- **Ranged tree cutting:** Axe + Bow cuts a tree at range.
- **Pickup cancel** (from Hollow Knight): if picking things up later costs extra time (a cutscene), getting hit while picking up cancels it and saves that time.
