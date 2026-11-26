# Status and gaps (as of 2026-11-21)

> Update: `verify.py` now checks beatability and gating. See [verification.md](verification.md). Generator bugs fixed there: the slow `split_map_by_terrain`, the door-placement hang, the pyramid door/wall crash, `raise("...")`, and the xlsx font_color crash.

## Implemented
- Full terrain generation (rivers, islands, deserts, bridges, castle, buildings with rooms/doors, lava, forests).
- Boss room with single door, 4 seals, boss.
- Desert Pyramid vault with dead ends, an item at the centre, optional ogres/gem/shrine.
- Placement of 20 gems, 6 shrines (incl. spawn), 6 items, spread apart.
- Excel export.
- Reachability-by-item-set analysis (`reachable_coordinates`, `evaluate_item_usefulness`), not wired in. It works as a flood fill but treats desert as impassable, ignores the Blessing, and doesn't chain items, so it can't detect locks. Superseded by `verify.py`.

## Designed in `rules` but not in code
- **No game engine / simulator**: no movement, turn resolution, damage, knockback, enemy AI, route parser or timer. Nothing can validate a route or compute its time.
- **No solver / par time**: no shortest-route search, so no way to know if a map is interesting or what the vanilla time is.
- **Enemies**: Lava Snakes (`DRAGON` enum exists but is never placed), Sawblades (no enum, no patrol data), Ogres only appear inside the pyramid. No general enemy placement.
- **Glitches**: none implemented; Superslide text is unfinished.
- `gen_name()` is never called.

## Beatability is not guaranteed
- `open_unreachable_rooms()` and `evaluate_item_usefulness()` are commented out.
- Items/gems/shrines are placed without checking reachability, so a building room, a forest pocket or an island can hold something you can't get to, or the needed 16 gems might be locked behind items you can't reach first.
- Building doors are placed before lava/forests/pyramid, which can later block or overwrite them.
- The castle gate can face lava/trees; nothing checks the gate is reachable.

## Bugs / inconsistencies spotted
- `rules`: boss section says "four Seals" then "Once all three are broken". Code places 4 seals; 4 x 4 = 16 of 20 gems.
- `place_items`: `raise("Too many tries...")` raises a string, which is itself a `TypeError` in Python 3. Should be `raise RuntimeError(...)`.
- `place_items` can loop until that error if the map is crowded (fixed 1000 tries, min spread 9).
- Desert Pyramid: its interior isn't checked, so `add_room` can overwrite part of an existing building (re-numbering its tiles and possibly orphaning doors). Its search range can also include the spawn corner if the border there is desert; `place_items` would then force the spawn shrine onto `(0,0)` regardless.
- Pyramid dead ends can be turned into lava/water *inside* a building; fine as design, but they ignore the "ogre dies in water/lava" interplay.
- `generate_lava`'s 2% sprinkle runs inside the `while` loop, so it repeats every iteration; lava ends up mostly as scattered single tiles/streaks rather than streams.
- `reachable_coordinates` treats desert as impassable without the Cloak; the real rule only slows/damages, so it understates reachability.
- `get_coordinates_in_range` relies on operator precedence (`not exact and a or b`); it happens to give the right answer but is fragile.
- `os.startfile` makes `__main__` Windows-only.
- `~$game_map_1.xlsx` is an Excel lock file in the repo folder (probably should be gitignored).
- Working tree shows all files modified, but it's only CRLF/LF line endings.

## Likely next steps (my suggestions, not decided)
1. Reachability/beatability pass (use the existing flood fill with items as keys; reject or repair seeds).
2. A minimal simulator: state = position, life, items, gems, seals, last shrine; apply the 2-char commands; enemies later.
3. A shortest-time solver (BFS/Dijkstra over that state, or over a graph of points of interest) to compute par times and check that items matter.
4. Enemy placement (ogres near rivers as knockback launchers, lava snakes in the lava field, sawblades in castle corridors).
5. Glitches as toggleable rule modules in the simulator/solver.
