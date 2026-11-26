# Architecture

## Running it
`python map.py` (needs `xlsxwriter`). For seeds 42, 43, 44 it builds a 50x50 `Map`, calls `generate_map()`, writes `game_map_N.xlsx` and opens it with `os.startfile` (Windows-only). Lots of debug `print`s (castle size, gate, bridges, item placements).

There is no game engine, simulator, route checker or UI. The "game" today is the generated spreadsheet plus the `rules` text.

## Coordinates
- `Coordinates(x, y)`: hashable, supports `+`/`-`, `get_distance` (Manhattan), `get_neighboring_coordinates` (4-way), `get_coordinates_in_range(d, exact)` (diamond of radius d, or just its rim when `exact=True`).
- **y = 0 is the bottom row.** `export_to_excel` flips rows so low y renders at the bottom. Spawn shrine is `(0, 0)` = bottom-left, matching the rules.
- Grids are stored row-major as `self.cells[y][x]`.

## Map state (`Map` in map.py)
| Field | Meaning |
|---|---|
| `cells[y][x]` | `TerrType`: GRASS, TREE, WATER, BUILDING, CASTLE, DESERT, LAVA, ROAD |
| `cell_contents[y][x]` | `CellContents`: EMPTY, SHRINE, SEAL, OGRE, BOSS, DRAGON, GEM, the six items, ITEM (placeholder for "some item, decided later"), FORCE_EMPTY |
| `room_numbers[y][x]` | 0 = outdoors; every building room / castle room / pyramid ring gets a unique number |
| `doors` | list of `(coordA, coordB)` adjacent pairs that are open despite a room boundary |
| `forced_walls` | list of pairs that are walls even inside one room (used for the boss room and pyramid dead ends) |

`TerrType.clear_terrain` is True for GRASS, DESERT, BUILDING, ROAD; these are the tiles pickups/shrines can be placed on. CASTLE is *not* clear, so nothing random spawns in the castle.

## Walls (important for routing and for the Corner Clip glitch)
Walls live on the **edges between tiles**, not on tiles. `is_wall(a, b)`:
1. forced wall → wall
2. same room number → open
3. door between them → open
4. otherwise → wall

So every boundary between different rooms (including indoor/outdoor) is a wall unless a door is listed. Outdoors is one big "room 0", so outdoor tiles never have walls between them. The map edge is implicitly a wall. The Excel export draws walls as thick cell borders.

## Helpers worth knowing
- `flood_fill(start, blocking_terrains, blocked_walls)`: 4-way reachability.
- `reachable_coordinates()`: from `(0,0)`, for every subset of {LAVA, WATER, TREE, DESERT} treated as passable, counts reachable / clear tiles. The dict key is the tuple of terrain types you can cross (i.e. the items you hold). Note it treats DESERT as impassable without the cloak, which is harsher than the actual rule (desert just hurts and slows).
- `evaluate_item_usefulness()`: averages the above per terrain to see how much each item opens up. Currently commented out of `generate_map`.
- `split_map_by_terrain`, `split_into_continuous_regions`, `find_closest_distance`, `draw_random_spread`, `draw_river` (random walk toward a target, optionally widened; reused for lava streams and bridges).

## Vault framework (vaults.py)
`Vault(name, probability, find_location_func, place_func)`. `place_vaults()` rolls each vault against its probability, shuffles, and for each calls `find_location_func(map)` → a centre or `None`, then `place_func(map, location)`. Designed to be extended with more set pieces.
