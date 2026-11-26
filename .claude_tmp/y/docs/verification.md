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
- **Desert without the Cloak:** at most 3 desert tiles in a row. With 3 Life, from outside you can step 2 tiles in, take 1 damage and step 1 more, take 1 damage and step out on 1 Life. So a 3-wide desert strip can be crossed and a pickup up to 3 deep can be grabbed (you can die afterwards, since progress is kept). This assumes you enter at full Life.
- **Blessing:** every shrine counts as a starting point, since you can warp from spawn to any shrine.
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
| min items needed to win | 2 |
| not beatable with zero items | required |

## Results over 300 seeds (50x50, after the generator fixes below)
- 46% beatable, **21% accepted** by the defaults. Generating plus verifying takes about 0.4 s per seed, so `--find` usually returns a map within a few seconds.
- Most failures are real item locks, because items are placed at random. For example, the spawn area is fenced in by water and trees and holds neither the Boots nor the Axe (22% of seeds can't reach any item at all). About 1 seed in 80 is impossible even with every item, with seals or gems that are walled off.
- Number of spheres: 0 in 66 seeds, 1 in 76, 2 in 73, 3 in 68, 4 in 14, 5 in 3.

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
