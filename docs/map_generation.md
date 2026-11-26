# Map generation pipeline

`Map.generate_map()` runs these steps in order on a grass-filled grid (default 50x50). Later steps overwrite earlier ones, so order matters. Percentages below are of width/height.

## 1. Rivers (`generate_rivers`)
- Main river: random-walk segments through 4 checkpoints, from the **top edge** (x 20-30%) → (x 30-40%, y 50-70%) → (x 50-70%, y 20-30%) → **right edge** (y 10-30%). Meander 0.5, widened twice at 15%.
- Tributary: **left edge** (y 70-90%) → (x 10-20%, y 40-50%) → joins the main river's third checkpoint. Widened at 8%.
- Any 3x3 all-water block seeds a grass island: grows outward through tiles ≥3 from grass with 80% chance per step.
- Net effect: water roughly splits the map into a bottom-left region (spawn), an upper-left region and a right/top-right region.

## 2. Deserts (`generate_deserts`)
- One big desert (spread 14-16 iterations at 0.8, plus 1-3 sub-blobs) centred near one of four edge bands, chosen to avoid the top-right/bottom-left corners.
- 1-3 small deserts (9-11 iterations, 0-1 sub-blob) anywhere ≥10 from spawn.
- Only converts GRASS.

## 3. Bridges (`generate_bridges`)
- Split map into non-water islands, randomly drop small ones (keep chance ~ size/20).
- Place 1-3 ROAD bridges between two islands whose closest gap is 2-5 tiles, each ≥20 from other bridges. Gives up after 100 tries. These are the "no Water Boots needed" crossings.

## 4. Castle (`generate_castle`)
- Rectangle ~28-33% of each dimension, origin at 60-65%, so it sits in the **top-right**. Midpoints of all four sides are indented 1-2 tiles to make corner towers.
- Gate (2 or 3 tiles wide, centred) on the **bottom** or **left** side, 50/50.
- **Boss room**: 5x5, on the far side of the castle from the gate, aligned with it. Exactly one door, centred on the side facing the gate; every other edge is a forced wall (the code prints whether the door count is 1). Seals in the four corners, Boss in the centre.
- Rest of the castle becomes one CASTLE room, then recursively split into sub-rooms (see buildings).

## 5. Buildings (`generate_buildings`)
- Keep adding buildings until 5-10% of tiles are buildings.
- Each: random 1-8 x 1-8 rectangle in a spot with no building/castle/water; sometimes 1-4 corner "bites" removed. 1-4 exterior doors depending on shape (never onto water, one per side).
- `split_building_into_rooms` recursively splits by a random x-cut, y-cut or flood-fill blob, linking each new piece to its neighbours with (usually) one door. Small rooms are left alone; big rooms are possible but rare.
- `open_unreachable_rooms` exists (adds a door to rooms unreachable from spawn) but is **commented out**.

## 6. Lava (`generate_lava`)
- Until 3-4% of the map is lava: draw short meandering lava streams starting in the **top-right quadrant** (skipping water/lava/buildings/castle), and on every iteration also sprinkle 2% of grass/desert in that quadrant with lava plus short "streaks".
- Result: the top-right (castle approach) is dotted with lava. This is where the Flame Shield / knockback-over-hazard decisions live.

## 7. Forests (`generate_forests`, `scatter_trees`)
- 3-5 forests at grass centres in the 10-90% box, density falling off with distance (radius 2x base 3-6), plus optional sub-clumps.
- Then 1% of remaining grass becomes lone trees.

> **Update 2026-11-21:** steps 7b-9 changed. After the trees, `clear_spawn_area` turns desert/trees/lava within 3 of spawn into grass. `place_vaults` now runs a fixed list of seven vaults in order, and `place_items` places shrines and then items with forward fill into hiding places. See [item_placement.md](item_placement.md). The text below describes the older behaviour.

## 8. Vaults (`place_vaults`)
Only the **Desert Pyramid** (probability 1.0, but only if a spot exists):
- Needs a 9x9 square whose *border* is all desert. Centre is chosen at random from valid spots.
- Builds 4 concentric rooms (centre tile, 3x3 ring, 5x5 ring, 7x7 ring), BUILDING terrain. One door per ring, never in the same direction twice in a row, so you spiral in.
- In each of the 3 outer rings, one random adjacent pair gets a forced wall, creating dead ends. Each of the 6 dead-end tiles gets: Gem 10%, else Shrine 10% (max one), else Ogre 50%, else lava-or-water (one type for the whole pyramid).
- Centre tile holds an ITEM placeholder, later replaced by a random real item.

## 9. Items (`place_items`)
- Counts gems and ITEM placeholders already placed (by vaults).
- Spawn **Shrine at (0,0)**.
- Places, on clear, empty tiles at least `(w+h)//11` (= 9 on 50x50) from every other placed thing: gems up to **20 total**, **5 more shrines**, and enough ITEMs to make **6 items** total.
- Shuffles all ITEM locations and assigns Desert Cloak, Water Boots, Flame Shield, Axe, Bow, Shrine Maiden's Blessing.
- No check that anything is reachable or that the game is beatable.

## 10. Export
`export_to_excel`: one 3-wide column per x, background = terrain colour, symbol/font colour = contents, thick borders = walls. `gen_name()` makes a title like "Assail the Blighted Citadel of Dread Exarch Festin" (initials always A-B-C-D-E-F) but isn't called anywhere.

## What a seed looks like (seeds 42/43 at 50x50, measured)
~1000 grass, 300-400 desert, ~350 water, 200-260 trees, ~230-260 building, ~200 castle, 120-130 lava, 8-13 road. 20 gems, 6 shrines, 6 items, 4 seals, boss; ogres only come from the pyramid (0 to 6). With no items, 200-600 tiles are reachable from spawn (by the code's strict measure).
