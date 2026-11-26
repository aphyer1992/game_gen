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
- **Desert without the Cloak:** at most **1** desert tile in a row (Andrew's design rule). Any player can dash across a 1-wide strip, so it's not an obstacle, but anything 2+ wide counts as needing the Cloak. A speedrunner can actually cross 3 wide on full Life by taking 2 damage. That's deliberately left as a skip players can find.
- **Blessing:** it only warps you to shrines you've already visited, so it's pure convenience and never affects reachability. It is never needed to win.
- **Lava snakes** (`CellContents.DRAGON`, Andrew's rule): without the Bow, each snake adds four walls, on the edge between the tiles 1 and 2 away from it along each of its four lines, and its own tile is impassable:
  ```
  . . A . .
  . . B . .
  A B S B A      (wall between each A and B)
  . . B . .
  . . A . .
  ```
  You can't walk up a line towards a snake, but you can step in beside it from the side. So a snake at the end of a 1-wide corridor that's 2+ tiles long blocks it, and a snake in the open can be walked around. With the Bow, snakes don't block: you step into line, it aims, and you shoot it before it breathes. Because of this the Bow now counts in the item-requirement searches.
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

## Results (50x50, current rules, 100 seeds)
- **95% beatable, 43% pass** the default checks. Generating plus verifying takes about 0.9 s per seed.
- Winning needs at least 4 items in 81 seeds and 3 items in 14. In practice that means Boots + Shield + Axe + Cloak, because the Bow can't gate anything until lava snakes are placed.
- Number of spheres: 2 in 47 seeds, 3 in 44, 4 in 7. "Only 2 spheres" is the most common reason a map gets rejected.

## Not modelled yet (known gaps)
- **Knockback over 1-wide hazards** is deliberately left out of beatability (it's a skip). It might be worth a separate report later, like "this lock can be skipped with the ogre at (x, y)", to help with designing skips.
- **Placing lava snakes / sawblades.** The verifier handles snakes (see above), but the generator doesn't place any yet, so for now the snake rule only matters on hand-edited maps.
- Enemies blocking corridors, Life carried between desert crossings, and glitches.

## Generator fixes made alongside (map.py / vaults.py)
1. `split_map_by_terrain` never checked `visited`, so it flood-filled from every tile. That made generation about 30x slower (7 s down to 0.25 s per map) and listed each island once per tile it contains, which skewed bridge placement toward big islands. **Fixing it changes which map each seed produces**, so seeds 42-44 no longer give the old `game_map_*.xlsx`.
2. `generate_building` could loop forever when a building had no valid door side (on the map edge or against water). It now gives up on a side after 10 failed tries. Seed 40 used to hang.
3. The Desert Pyramid could pick a dead-end wall on top of a ring door, which crashed the `add_forced_wall` assert (seed 20). It now re-picks.
4. `raise("...")` became `raise RuntimeError(...)`.
5. `export_to_excel` no longer passes `font_color=None`, which current xlsxwriter rejects.

## Suggested next steps
- Replace random item placement with a randomizer-style "assumed fill": place items so that each one is reachable using only items placed before it. Then (almost) every map is beatable and the gating can be steered, e.g. "Shield always behind Axe". This would also stop us throwing away 80% of seeds.
- Model knockback skips (and later glitches) as optional movement rules, so the verifier can say "this lock is skippable with an ogre".
