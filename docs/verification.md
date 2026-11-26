# Map verification (`verify.py`)

Added 2026-11-21. Answers two questions about a generated map: **can it be beaten** (no chicken-and-egg item locks, enough gems, seals reachable) and **is it interesting** (items gated behind other items, not everything free from spawn).

## Usage
```
python verify.py                 # reports for seeds 42 43 44
python verify.py 7 8 9           # reports for chosen seeds
python verify.py --find 3 100    # find 3 accepted maps from seed 100 up, export verified_map_<seed>.xlsx
```
From code: `verify_map(m)` returns a `VerificationReport` (`.summary()` prints it); `check_criteria(report, overrides)` returns the list of failed criteria; `generate_verified_map(w, h, seed, criteria)` re-rolls seeds until one passes.

## Movement model (glitchless)
- 4-way movement, blocked by walls (`Map.is_wall`, i.e. room borders without doors, plus forced walls) and the map edge.
- Water needs Boots, Lava needs Shield, Tree needs Axe. Everything else is walkable.
- **Turns, and no damage.** The verifier works in turns: each turn you move up to 2 tiles. It never lets you take damage, since taking hits is how skips work. To pick something up (gem, item, seal) you have to end a turn on it and then spend a turn there.
- **Desert without the Cloak:** starting a turn in desert costs 1 damage, so you may never *end* a turn on desert. A 1-wide strip can be crossed in one 2-tile move. Anything 2+ wide needs the Cloak. That's the same as Andrew's "1-wide is free" rule, now in the same turn model. One new consequence: a pickup sitting *on* a desert tile needs the Cloak.
- **Blessing:** it only warps you to shrines you've already visited, so it's pure convenience and never affects reachability. It is never needed to win.
- **Lava snakes (superseded 2026-11-23: now Andrew's four-walls model, see item_placement.md)** (`CellContents.DRAGON`, Andrew's rules). On its turn a snake first breathes fire if it was aiming, hitting you if you're still on that line. Then it aims at you if you're collinear and within 5. So, without the Bow:
  - You may not end two turns in a row on the same line of the same snake within range of it. Crossing a line is fine (you step on, it aims, you step off). Walking *along* a line for more than one turn gets you hit.
  - You can't pick anything up on a snake's line, because you'd stand there for two turns.
  - Walls block the line of fire. Nothing else does: trees, water and lava don't. That's the cautious choice.
  - With the Bow, snakes don't block.

  The two layouts Andrew described are unit-tested. A snake beside a 1-wide corridor doesn't stop you. A corridor running down a snake's line for 5 tiles does. Snakes are only placed in lava, as the rules say.
- **No skips, by design.** Beatability must never depend on a skip: no knockback over hazards and no glitches. Ogres and other enemies are ignored, so they neither help nor block.

## What it computes
- **Progression ("spheres")**: start with nothing, collect every item you can reach, repeat until nothing changes. Sphere 0 holds the items that are free from spawn, sphere 1 the items those unlock, and so on. If you get stuck before you have 16 gems and all 4 seals, the map can't be beaten.
- **Item requirements**: for each item, the minimal sets of *other* items that make it reachable, e.g. `Shield <- {Cloak}` or `Boots <- {Axe, Blessing}`.
- **Gems by cheapest requirement**: how many gems are free and how many need Boots, etc.
- **Smallest winning item set**: the fewest items that can actually be collected in some order and still win. This is roughly the minimum a speedrun has to pick up.

## Acceptance criteria (`DEFAULT_CRITERIA`, all tweakable)
| Criterion | Default |
|---|---|
| beatable | required |
| all 6 items obtainable | required |
| min spheres | 3 (at least one item behind an item behind an item) |
| min gated items | 2 |
| max items free from spawn | 3 |
| min items needed to win | 4 (counting Boots, Shield, Axe, Cloak and Bow) |
| not beatable with zero items | required |

## Generation now builds maps to pass (gem_placement.py)
Added after Andrew reviewed the first sample maps:
1. **Spawn shrine fix.** `place_items` used to shuffle `(0,0)` in with the other spots, so the spawn shrine was often overwritten by a gem or item. It no longer is.
2. **Assumed-fill item placement** (`assign_items_assumed_fill`), the technique game randomizers use. Items are taken in random order. Each one goes on a clear tile that is reachable while holding all the items not yet placed, so the last item placed is always reachable from spawn and nothing is locked behind itself. 80% of the time it picks a tile that is *not* reachable from spawn with no items, which pushes items behind other items. The Desert Pyramid's centre always gets an item.
3. **Gated gem placement** (`place_gated_gems`). The boss needs 16 of 20 gems, so for an item to be required, at least 5 gems must need it. For each tile, the generator works out which items every route to it needs: island means Boots, behind lava means Shield, in a forest means Axe, 2+ deep in desert means Cloak, behind a lava snake means Bow. Combinations count for every item involved. It then places gems until each gating item has its 5, preferring combo tiles about a third of the time. It never lets 16 gems become reachable without one of those items. An item that can't gate anything on a given map is skipped, for example the Bow when no snakes are placed.

4. **Lava snake placement** (`snake_placement.py`, runs after vaults and before items). Snakes go on lava tiles at least 8 from spawn whose lines cover at least 2 tiles you can stand on. 1-2 are *gating* snakes: placed where, holding every item but the Bow, the snake cuts off a pocket beyond its own lines of 10+ clear tiles (falling back to 3+), but never more than 35% of the reachable map. 2-4 more are *decorative*: they cut off at most 2 tiles beyond their lines, though anything sitting on their lines still needs the Bow.
5. **Bow gems.** Snake pockets are often too small to hold the 5 gems needed to make the Bow strictly required. Per Andrew, that's fine: any item that gates something but can't reach the full quota still gets 2 gems behind it (`SOFT_QUOTA`). Assumed fill can also put an item behind a snake, which makes the Bow required that way.

## Results (50x50, current rules, 60 seeds, turn-based snake model)
- **95% beatable, 48% pass** the default checks. Generating plus verifying takes about 1.6 s per seed.
- The Bow is needed to win in 57 of 60 maps. Winning needs all 5 traversal items in 46 seeds and 4 in 11.
- Number of spheres: 2 in 28 seeds, 3 in 23, 4 in 6. "Only 2 spheres" is still the most common reason a map gets rejected, and it has nothing to do with snakes.

## Snake model: remaining assumptions
1. **Fire range.** The rules say the snake aims within 5. I assume the breath also only reaches 5 tiles, so a player who aimed it at range 5 and then walks *away* along the line is safe.
2. **Line of fire.** Only walls block it. If trees or buildings should block it too, snakes block less than the verifier thinks, so it errs on the cautious side.
3. **No damage at all** in the beatability check. Tanking a breath and getting knocked back 2, tanking desert damage, and knockback over hazards are all skips for players to find.
4. **Ogres** are ignored. One that parks in a 1-wide corridor is a soft block the verifier doesn't know about.

## Not modelled yet (known gaps)
- **Knockback over 1-wide hazards** is deliberately left out of beatability (it's a skip). It might be worth a separate report later, like "this lock can be skipped with the ogre at (x, y)", to help with designing skips.
- **Sawblades** aren't placed or modelled.
- Enemies blocking corridors, Life carried between desert crossings, and glitches.

## Generator fixes made alongside (map.py / vaults.py)
1. `split_map_by_terrain` never checked `visited`, so it flood-filled from every tile. That made generation about 30x slower (7 s down to 0.25 s per map) and listed each island once per tile it contains, which skewed bridge placement toward big islands. **Fixing it changes which map each seed produces**, so seeds 42-44 no longer give the old `game_map_*.xlsx`.
2. `generate_building` could loop forever when a building had no valid door side (on the map edge or against water). It now gives up on a side after 10 failed tries. Seed 40 used to hang.
3. The Desert Pyramid could pick a dead-end wall on top of a ring door, which crashed the `add_forced_wall` assert (seed 20). It now re-picks.
4. `raise("...")` became `raise RuntimeError(...)`.
5. `export_to_excel` no longer passes `font_color=None`, which current xlsxwriter rejects.

## Suggested next steps
- Push assumed fill toward 3+ spheres, which is the main reason maps get rejected now.
- Speed up gem placement's subset search (only test the subsets that matter), since generation is now ~2.7 s per map.
- Model knockback skips (and later glitches) as optional movement rules, so the verifier can say "this lock is skippable with an ogre".
