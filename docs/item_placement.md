# Item placement: making maps look like a real game

Added 2026-11-21, after Andrew's feedback that items were "just lying around out in the open in one desert near the start of the map". The goal is a base game that could pass for a real one: you travel around the map, finding each item somewhere that feels deliberate, and each new item opens up the next part of the map.

## Ideas considered (Andrew's menu plus a few more)
| Idea | Done? | How |
|---|---|---|
| 1. Spread items out | Yes | Items try to stay 12+ tiles apart (relaxed to 9, 6, 4... only if needed). |
| 2. 1-2 new gating items available at each step | Yes | Forward fill, below. Each step is exactly one verifier sphere. |
| 3. Item spots inside buildings, ringed by trees, on islands | Yes | Every candidate tile gets a "hiddenness" score; see below. |
| 4. More vaults | Yes | Six new set pieces in `vaults.py`. |
| 5a. Castle blocked by lava | Yes, 40% of maps | `Castle Moat` vault: a 1- or 2-wide lava ring around the castle. |
| 5b. Castle holds an item, lava gems elsewhere | Partly | `Castle Armory` always offers the castle's deepest room as an item spot. Gem placement already puts 5+ gems behind lava whenever it can. I didn't force the Shield specifically into the castle. |
| Fewer gems right by spawn | Small tweak | Filler gems avoid an 8-tile radius around spawn when they can. |
| Not done | | Ogres guarding vaults, sawblade corridors, themed names for vaults in the xlsx. |

## Vaults (`vaults.py`), in the order they're placed
Each vault registers an **item spot** (`register_item_spot`). Forward fill puts items in vault spots first. A spot that doesn't get an item gets a gem when the gem rules allow it.

| Vault | Chance | What it builds | Usually needs |
|---|---|---|---|
| Castle Moat | 40% | Lava ring, width 1-2, around the castle (outdoor tiles only) | Shield for the boss (1-wide moat = knockback skip) |
| Castle Armory | 100% | Item spot in the castle room that's behind the most doors | whatever the castle needs |
| Desert Pyramid | 100% if a site exists | Unchanged, except the centre is now an item spot rather than a forced item | Cloak |
| Forest Temple | 90% (+35% for a second one) | 1x1 or 2x2 hut in a dense forest, a clearing around it, then a ring of trees. 45% of the time the clearing is **lava** instead ("behind a lava pit in the deep forest temple") | Axe, or Axe + Shield |
| Lava Shrine | 70% | A plus-shaped patch of grass ringed by a diamond of lava, width 1-2 | Shield (1-wide = skip) |
| Island Hut | 60% | A hut on one of the small islands the river generator makes (no bridge, up to 30 tiles), or in open water if any is wide enough | Boots |
| Desert Ruin | 50% | A hut 3+ tiles into the desert | Cloak |

Vaults keep 15+ tiles from spawn (12 for the island hut, 18 for the lava shrine) and 10+ from each other's item spots. They only build on outdoor, empty tiles that aren't next to a door, so they never cut into a building.

## Forward fill (`gem_placement.place_items_forward_fill`)
This replaces assumed fill for items (set `map.ITEM_PLACEMENT = 'assumed'` to get the old behaviour back).

1. Step 0: R0 = everything reachable with no items. Pick 1 traversal item (55%) or 2 (45%), and put each in the best hiding place in R0.
2. Step s: Rs = reachable with every item placed so far. Pick 1-2 more and put them in the best hiding places in Rs minus R(s-1), the area the last step's items opened up. A vault there always gets an item first.
3. Which items a step offers is chosen so that, together with what you hold, they open new hiding places for what's left. A step only grows past 2 items if no 1- or 2-item choice opens anything.
4. The Blessing never gates anything, so it goes into some step after the first (a leftover vault there 70% of the time), never behind every item where it would be useless.

Because items for step s sit only in the area step s-1 opened, the verifier's spheres come out exactly as the steps.

**Hiddenness score** for a tile (`spot_scores`): +10 for a vault spot; +3 for being inside a building or castle room, +1 or +2 more for rooms behind more doors; +0.4 for each nearby tree (or +0.2 per water/lava tile) within 2, up to +3.2; -6 within 12 of spawn, -2 within 20. The best-scoring spot wins, with a little randomness (+0 to 2.5).

## Measuring it
`python measure.py 0 60` generates seeds 0-59 and prints the summary. `python render_png.py --out DIR 4 7 11` draws maps as PNGs with a legend listing each item's spot and the progression. Both work without xlsxwriter installed.

## Results (seeds 0-59, 50x50, same seeds before and after)
| Metric | Before | After |
|---|---|---|
| Accepted by the verifier's default criteria | 48% | **100%** |
| Beatable | 95% | 100% |
| Items lying in the open (outdoors and free from spawn), per map | 2.18 | **0.25** (78% of maps have none) |
| Items within 12 tiles of spawn | 0.50 | 0.08 |
| Items free from spawn | 2.53 | 1.38 |
| Items hidden (in a room, or behind some item), of 6 | 3.82 | 5.75 |
| Closest pair of items | 10.2 tiles | 12.1 tiles |
| Maps with two items under 8 tiles apart | 12% | 10% |
| Spheres (3+ / 4+) | 2.48 (48% / 10%) | 3.68 (100% / 63%) |
| Every step offers 1-2 traversal items | 28% | **100%** |
| Generation time | 3.4 s/map | 3.4 s/map |

Common step patterns: 1-1-2-1, 2-2-1, 1-2-1-1, 2-1-1-1, 2-1-2. About 2.4 of the 6 items sit in a vault on an average map; most of the rest are in buildings or castle rooms. In 30 maps, the Castle Armory held an item 25 times, Forest Temples 19 of 39, Lava Shrines 12 of 21, Desert Ruins 8 of 12, the Pyramid 7 of 9, and Island Huts (when built) almost always.

Spawn fix: seeds 10, 20 and 37 put spawn inside a big desert, so nothing was reachable at all. `clear_spawn_area` now gives spawn a radius-3 grass clearing.

## Ideas for later
- Ogres guarding vault entrances (also handy as knockback launchers over the 1-wide lava rings).
- Name vaults in the xlsx export (e.g. a note on the cell) so players see "Forest Temple".
- A vault for the Bow behind lava snakes (a snake-guarded corridor), now that snakes exist.
- A criterion in `verify.py` for "items in the open", if we want to reject the remaining 22% of maps with one.

## Shrines, gems and ogres (2026-11-22)
Andrew asked for shrines spread across the map like items, shrines and gems more often in interesting places, and ogres (some random, some in buildings near items and gems).

- **Shrines** (`gem_placement.place_shrines_spread`, `map.SHRINE_PLACEMENT = 'spread'`): farthest-point sampling. Each shrine goes among the tiles at least 80% as far from spawn and the earlier shrines as the farthest tile is, and within those on the best `spot_scores` tile (rooms, tree cover). Only tiles reachable with every item, off snake lines, 3+ from vault spots. Placed before items, so items avoid them.
- **Gems** (`GEM_TOURNAMENT = 3`): every gem pick is the best-hidden of 3 random tiles that pass the gating rules, so the gating quotas are unchanged.
- **Ogres** (`ogre_placement.py`, `map.PLACE_OGRES`): 3-5 guards in the same room as an item (then gems), 2-3 tiles from it, or just outside the door of a room too small for that. Plus 3-6 wanderers outdoors, about half on "launcher" tiles two steps from a 1-wide strip of water or lava, so an ogre hit can knock you over it. Pyramid ogres are kept. None within 10 of spawn, next to a shrine or in the boss room. The verifier ignores ogres, so beatability is unaffected.
- **autoroute.py** (test helper) used to walk into ogres' reach and get knocked back forever. It now hits an adjacent ogre first, and stops short or waits (up to 3 turns) so the ogre steps up to it. All 24 tests in `test_game.py` pass.

`python measure.py 0 60 --old-extras` measures with all three switched back to the old behaviour.

| Metric (seeds 0-59) | Before | After |
|---|---|---|
| Farthest any reachable tile is from a shrine | 38.6 | **25.7** |
| Map sectors (of 9) with a shrine, spawn included | 4.9 | 5.9 |
| Shrines (of 5) in interesting spots* | 2.1 | **5.0** |
| Gems (of 20) in interesting spots* | 12.3 | 14.8 |
| Gems within 12 of spawn | 0.25 | 0.10 |
| Ogres per map (in rooms) | 0.7 (0.7, pyramid only) | 9.1 (3.9) |
| Verifier acceptance | 100% | 100% |
| Generation time | 4.5 s | 4.8 s |

*Interesting = in a room, 4+ trees within 2 tiles, or next to water/lava (`measure.interesting`). Shrine counts can go above 5 because the pyramid sometimes adds one.

## Less linear progression (2026-11-22)
Andrew: maps were sometimes fully linear (e.g. only the Cloak reachable at the start, and every later route forced too). He'd rather there usually be 2 access items to choose between.

**Metric** (`gem_placement.choice_profile`, in `measure.py`): go through every order a player could collect the 5 access items in. At each moment with 2+ items still to get, count it as *forced* if only one is reachable.

**Placement** (`gem_placement.place_items_branching`, now the default: `map.ITEM_PLACEMENT = 'branching'`): a simulated player keeps a pool of items that are placed and reachable but not collected. Whenever fewer than 2 are on offer, the next item goes into the area the last collected item opened up (else anywhere reachable), choosing an item that opens somewhere new once you have it. Then a random offered item is collected, and so on. It makes 10 attempts and keeps the best: all items obtainable, at least 3 spheres, then fewest forced moments, then 2+ items at the start, then best-hidden spots. Hiding-place scores, vault preference, spacing and the Blessing rule are the same as forward fill. `'forward'` still selects the old step-by-step placement (`python measure.py 0 60 --forward`).

| Metric (seeds 0-59) | Forward fill | Branching |
|---|---|---|
| Moments forced to a single option | 51% | **24%** |
| Maps with 2+ access items reachable at the start | 33% | **100%** |
| Spheres (3+ / 4+) | 3.65 (100% / 58%) | 3.07 (100% / 7%) |
| Items free from spawn | 1.33 | 2.13 |
| Items in the open (outdoors, free from spawn) | 0.23 | 0.50 |
| Verifier acceptance | 100% | 100% |

Trade-offs: offering 2 items at once means a wider, shallower progression (fewer 4-sphere maps), and the 2 starting items sit in the start area, so slightly more items are in the open. No map is *never* forced: once you go deep down one branch, the last item of the other branch can still be the only option. That's built into having 5 items.

## More open start, more vaults, varied boss room (2026-11-22, later)

**Seed 41 had 18 gems.** `place_gated_gems` places gems so each access item guards at least 5 of the 20. On seed 41, after 18 gems, the next one would have had to need Boots, Shield and Bow all at once, and no tile does, so it stopped. Now, when it gets stuck short of 20, it drops the strict quota of the item furthest from meeting it and carries on. `measure.py` reports maps with fewer than 20 gems (none in seeds 0-59).

**Winding trails** (`trails.py`, `map.CARVE_TRAILS`), run after terrain and before vaults:
1. *Connecting trails*: while less than 30-45% of the map is open with no items (up to 4 trails), a Dijkstra search from the start area through trees, lava, desert and up to 3 water tiles (a ford) finds a route to a patch of open ground. The patch is picked at random, weighted by size. A smooth random field makes the route meander. Obstacles on it become grass (road for desert and water).
2. *Glade trails* (1-3 per map): a self-avoiding, 1-wide winding walk into a forest or lava field next to the start area, 9-26 tiles long, ending in a small clearing registered as an item spot ("Forest Glade" / "Lava Causeway"). Early items can sit at the end of a long walk instead of near spawn, and the Axe or Shield becomes a shortcut.
`render_png.py` draws carved trail tiles paler.

**New vaults** (in `vaults.py`):
| Vault | Chance | What it is |
|---|---|---|
| Snake Gallery | 50% | 1-wide corridor between tree walls, a lava snake at the end looking down it; the item sits in front of the snake (Bow) |
| Hedge Maze | 50% | 7x7 or 9x9 maze of trees, item at the dead end farthest from the entrance (walkable; Axe is a shortcut) |
| Oasis | 50% | Pond ringed by grass and palms, 3+ tiles into the desert (Cloak) |
| Ogre Camp | 60% | Tree palisade with one gap, 2-3 ogres inside, item spot in the middle |

**Boss room** (`map.BOSS_ROOM_6X6 = 0.4`, `map.BOSS_ROOM_LAVA = 0.35`): 6x6 when it fits (door and boss offset 2 or 3), and sometimes 1-3 lava tiles, never on a seal, the boss, or next to the door, and never cutting a seal off from the door. Lava snakes are no longer placed inside rooms. Buildings now keep one tile clear of the castle: on seed 4 a building had sealed the castle gate.

| Metric (seeds 0-59) | Without trails | With trails |
|---|---|---|
| Map open with no items | 16% | **33%** |
| Maps where under 20% is open | 70% | 15% |
| Distinct vault types per map | 5.6 | 6.3 |
| Forced moments (one option) | 25% | 20% |
| Items within 12 of spawn | 0.27 | 0.07 |
| Closest pair of items under 8 apart | 18% | 3% |
| Items "in the open" (outdoors and free from spawn) | 0.87 | 1.32* |
| Verifier acceptance | 100% | 98% (1 map winnable with only 3 items; the re-roller skips it) |

*These are mostly glade items: outdoors and reachable from the start, but at the end of a long winding trail. The metric can't tell the difference.

Known side effect: desert trails and oases use up desert, so the Desert Pyramid (needs a 9x9 desert border) appears less often now.

## Castle gem gate (2026-11-23)
Andrew: entering the castle needs an interact at the Gate while holding at least X gems, and an important progression item waits inside. You gather gems outside, go in for the item, and come back out to use it, unless your route can do without it.

- **X = 8 gems** (`map.GATE_GEMS`, two seals' worth; 0 turns the lock off). `map.setup_castle_gate` (right after the spawn clearing) turns the tiles just outside the gate doorway into road with a **Gate** marker (`CellContents.GATE`). The gate pairs are kept in `Map.castle_gate`, the requirement in `Map.gate_gems`.
- **Simulator** (`game.py`): the gate doorway is closed until you stand on a Gate tile and interact (`e.`) holding 8+ gems. Gems aren't spent, and the gate stays open (`GameState.gate_open`). `Simulator.can_step(a, b, state)` and `Simulator.neighbors(state, c)` include the gate once it's open. `autoroute.py` heads for the gate once it holds enough gems. Tests: `TestCastleGate` in `test_game.py`.
- **Verifier**: with the gate shut, it floods everything outside. The gate opens if a Gate tile is reachable (long enough to interact) and 8+ gems are collectable outside; then it floods again with the doorway open. `Verifier.gate_mode = 'open'` pretends you have the gems (used during placement, before gems exist).
- **Castle item** (`map.CASTLE_ITEM`, `gem_placement.choose_castle_item`): one access item goes in the Castle Armory. It's chosen so the armory and every seal are reachable without it (so it never locks itself and is never needed to finish), weighted toward items that open more of the map. Gem placement puts 3 gems behind it, and never more than 4, so 16 are always reachable without it: useful, but optional. The report says e.g. `Castle item: Boots (guards 3 gems; optional, you can win without it)`.
- Room for what's next: bombs/cracked walls, a one-shot Bow, keys and coins can follow the same pattern: a map field for the gate/lock, a `GameState` flag or counter, a verifier rule in `stand_tiles`, and a placement hook.

## Snakes in hallways: making the Bow matter (2026-11-23)
Andrew: snakes out in the open don't need the Bow (you walk round them, or walk up and melee them; one hand route of seed 42 skipped the Bow entirely). Only a snake blocking a narrow hallway should.

**Verifier model** (`verify.Verifier.set_snakes`, Andrew's "four walls"): without the Bow, each snake S walls off the step between A and B on each of its four sides (B next to S, A one further out), and S is impassable:
```
. . A . .
. . B . .
A B S B A
. . B . .
. . A . .
```
If you can stand on any B without crossing its walls, you can kill it in melee, so its walls drop (repeated until nothing changes). The old "you can't stand on a snake's line for two turns or pick anything up there" rule is gone. `test_snakes.py` covers: passing beside a snake, walking down its line, an L-bend hallway (blocked; open with the Bow), and side access to B (melee opens it).

**Placement** (`snake_placement.py`): gating snakes (2-3) are chosen by what they cut off while you hold every item but the Bow, so only real walls count. Candidates are lava tiles plus *hallway spots*: the tile straight ahead of a bend in a 1-wide path, where the path comes along A->B and turns at B. It can be a tree outdoors (trails, mazes; the Axe gets round these, so the Bow is one option) or a floor tile in a building or castle corridor, which becomes a lava pit (only the Bow gets past). Hallway spots are preferred. The castle counts as open during this step. 1-3 decorative snakes in lava cut off (almost) nothing. Speed: one tile is patched in the verifier's index per candidate instead of rebuilding it.

**Snake Gallery** is now a walled 1-wide building: door at the near end, lava pit and snake at the far end, item spot in front of the snake. Only the Bow gets you to it.

**Acceptance criterion (2026-11-23):** `min_items_to_win` is now 3 (was 4), on Andrew's call, since the castle item is optional by design. **Go back to 4 once Bombs are added** as another access item. With 3, 59 of 60 seeds pass (was 50).

## Purposeful buildings, a dangerous castle, Ghosts and the Horse (2026-11-23)

**Buildings** (`buildings.py`, `map.PURPOSEFUL_BUILDINGS`): every building block of 12+ tiles should hold an access item or a gem, or be a connector (walking through it opens 15+ tiles you couldn't otherwise reach, for no items, any single item, or all items). Gem placement now sends a gem into an empty big building 80% of the time when the gating rules allow it. After gems, any still-idle big building:
1. gets an outdoor gem with exactly the same requirement moved in;
2. or one whose requirement is one item smaller (never the castle item);
3. or gets a flooded or burning inner room: the floor just inside the door(s) becomes water or lava, and an outdoor gem needing exactly that room's new requirement moves in.
Idle big buildings went from about 3 per map to 0.6 (of 6.2).

**Castle** (`castle.py`, `map.FURNISH_CASTLE`): castle gems are part of the 20. On 60% of maps there's one per corner tower; on 25%, 2-3 in random castle rooms; otherwise 1. They can't help open the gate. 3-6 lava traps go on castle floor, never next to a door and never cutting any castle tile off from the gate (ogre knockback can still throw you in). `ogre_placement` adds a garrison of 3-5 castle ogres (5.5 on average, counting guards). Gem placement treats the gate as open when working out requirements, so castle gems count properly.

**Ghosts + Silver Sword** (`ghost_placement.py`, `map.PLACE_GHOSTS`):
- *Simulator*: a Ghost (HP 2) roams and hits like an Ogre, but attacks pass through it unless you hold the Silver Sword. Water and lava don't kill it.
- *Verifier*: play "as intended", so each ghost blocks the tile it starts on until you have the Sword. Luring one away is speedrun tech, deliberately not modelled.
- *Placement*: 2-3 gating ghosts on chokepoints (a tile just inside a building door, or a 1-wide corridor or trail tile) that cut off 12+ clear tiles (falling back to 5+) while you hold every other item. Plus 1-2 wandering ghosts in the open.
- The Silver Sword is the 6th access item, so `min_items_to_win` is back to 4.

**Horse** (`map.HORSE_ITEM`): `hX` gallops up to 4 tiles in a straight line, stopping before anything you couldn't walk onto plus water, lava and desert. It can't start from the boat or from desert, and picks nothing up on the way. Speed only: like the Blessing, it never changes reachability, and it's placed by the same rule. A later slide glitch should differ from it (e.g. through hazards, or backwards). Tests: `TestGhostAndHorse`.

**Speed**: the Verifier builds its wall table from sets instead of `Map.is_wall` list scans, and the flood fill's inner loop no longer builds lists. Together that's about 2x faster.

## Horse redesign and playtest fixes (2026-11-24)

**Horse** (`game.py`): Andrew's playtest of seed 45 found the 4-tile gallop far too easy ("I use it constantly"). New rules, following his suggestion:
- `h.` mounts, which takes the turn. It needs open grass or road, outdoors, and not from the boat.
- While mounted, each direction letter of a move is 2 tiles: `dd` = 4 east, `dw` = 2 east then 2 north, `d.` = 2 east.
- You come off (and stop) when you bump into anything (wall, tree, enemy, edge), when the next tile is building or castle floor, water, lava or desert (you stop before it), when you're hit, when you warp, board the boat or die.
- Waiting and interacting keep you mounted.
- `hX` is gone. Tests: `TestGhostAndHorse`.

**Empty vaults** (`buildings.ensure_vaults_filled`, runs just before the building pass): a snake gallery or ogre camp guarding nothing looks broken. A leftover vault spot first gets a gem moved in whose requirement matches, or is a subset of, the spot's (it only gets harder to reach; never adding the castle item). Gem quotas are usually exactly tight (each required item has exactly 15 gems reachable without it), so that rarely works. So the nearest shrine (within 15 tiles, not spawn) moves in instead. Failing that, an empty ogre camp or snake gallery loses its guards. Across 8 maps, empty vault spots went from 11 to 3 (the rest are Forest Glades, which read as plain clearings).

## Gem spacing and wandering ogres (2026-11-24, after playtest)

**Gem clumps.** Seed 13 had 5 gems within a few tiles across neighbouring buildings. They came from the gated gem placement: when an item gates only a small pocket but still has to guard 5 gems, they all land there. Changes in `gem_placement.place_gated_gems`:
- Spacing relaxes one step at a time (`SPACING_STEPS = 6, 5, 4, 3, 2, 1`) instead of jumping from 4 to 2 to 1.
- *No clumps*: a gem may not go within 3 tiles of another (`CLUMP_RADIUS`).
- When stuck, the last resorts run in this order: drop a target item's strict quota, then allow close gems (choosing the tile farthest from other gems), then let the castle item become needed.
- Gems steered into empty buildings, and gems moved by `buildings.py`, keep `GEM_SPREAD = 5` from other gems.
Close gem pairs (3 or fewer tiles apart) went from 3.9 per map to 0.1. The cost is that, on a few maps, an item that only gated a small pocket stops being strictly required.

**Wandering ogres** (`ogre_placement.RANDOM_OGRES = (2, 2)`, `LAUNCHER_SHARE = 1.0`). Playtested 0, 2, 4 and 6 wanderers on seeds 45, 7 and 21 (identical maps apart from the wanderers). Nearly every wanderer ends up within aggro range of the important routes (spawn, items, shrines, gate), but they barely change a route: the test router took 0-2 ogre hits whatever the count, and its turn counts didn't trend. Ogres are low-threat (3 HP, and waiting lets you hit first), so a wanderer in an open field is a small time tax with no decision attached. The ones worth having are guards (by items), the castle garrison, and *launchers* by a 1-wide river or lava strip, which create knockback-skip options. So: 2 wanderers, always on launcher spots when one exists.

**Test router**: `autoroute.py` now has a loop breaker. If it revisits a tile 4 times in 16 turns, it stops avoiding ogres for 12 turns and fights through. That fixed the endless pacing on seed 45, which it now beats in 585 turns (Andrew: 242).

## Icons (2026-11-24)
`icons.py` defines small vector icons, shared by `play.py` (tkinter) and `render_png.py` (Pillow):
- items on a cream badge: Boat, Shield, Axe, Cloak, Bow, Blessing (compass star), Silver Sword, Horse;
- gem, shrine (temple, number in the corner, dark until visited), seal (rune star; grey and cracked once broken), castle gate (portcullis, hidden once open);
- ogre, ghost, lava snake, boss.
To add one, append its shapes in unit-box coordinates and both front ends pick it up. Tiles in `play.py` went from 13 to 16 px so the icons stay readable.

## Filling empty plains; Winding Wood (2026-11-24)
Andrew: seed 47 had large empty areas; any empty 5x5 block of plains should contain something; and he wants winding forest paths, walkable with no items but quicker with the Axe.

`fill_empty.py` (`map.FILL_EMPTY`):
1. **`place_area_vaults`**, after vaults and castle, before snakes and items. "Empty" means EMPTY_DIST (8)+ tiles from anything built: building or castle floor, a vault's item spot, anything on a tile, or the map edge (counted as 3 tiles beyond). Up to 4 set pieces go to the emptiest spots, each allowed to shift up to 4 tiles to fit, and at most 2 of a kind per map:
   - **Winding Wood** (most often): a 7x7 to 11x9 block of forest with a serpentine 1-wide path, in at one end and out at the other, and a dead-end nook part way along with the item spot. Walkable with nothing; the Axe cuts straight through.
   - **Pond Islet**: a one-tile islet in a 2-wide pond (Boots).
   - **Lava Shrine** (as before).
   Each registers an item spot, so items, gems or a shrine end up there.
2. **`decorate_empty`**, at the very end: every 5x5 block of plain empty grass gets a copse of trees (75%) or a small pond in its middle 3x3. The block's outer ring stays grass, so it can never cut a path.

Results (40 seeds, with vs without): empty land (tiles 8+ from anything) 43 -> 26 per map; distinct vault types per map 6.2 -> 7.3. Verifier acceptance 88% -> 82% (two maps became winnable with only 2 items; the re-roller skips them). Seed 46, previously rejected, is now accepted.
