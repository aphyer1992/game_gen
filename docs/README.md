# game_gen notes (index)

Notes written by Claude after reading the repo on 2026-11-21, for future sessions. Code was not changed.

**What the project is:** a "speedrun-routing" game. A simple top-down adventure map is randomly generated; players never play it, they *route* a speedrun of it (every turn = 1 second, perfect execution assumed) and compete on time. Each round, players draw glitches that open new skips.

**Where things are**

| File | What it is |
|---|---|
| `rules` | Plain-text design doc: turn structure, items, terrain, enemies, boss, glitch/round system. No extension. |
| `map.py` | `Map` class: all procedural generation + Excel export. `__main__` builds 3 maps (seeds 42-44) at 50x50. |
| `vaults.py` | "Vaults" = hand-designed set pieces placed on the map: Desert Pyramid, Forest Temple, Lava Shrine, Island Hut, Desert Ruin, Castle Armory, Castle Moat. Most register an item hiding place. |
| `gem_placement.py` | Item placement (forward fill into hiding places, one progression step at a time) and gated gem placement. |
| `measure.py` / `render_png.py` | Batch metrics for how game-like maps are; PNG rendering of maps with a legend. |
| `verify.py` | Map verifier: item progression, beatability, gating metrics, seed re-rolling. |
| `game.py` / `play.py` | Turn simulator (runs a route, records the state every turn) and the simple Tkinter UI on top: `python play.py 40`. |
| `autoroute.py` / `test_game.py` | Greedy auto-player (a rough winning route) and the simulator tests. |
| `support_classes.py` | `Coordinates` (Manhattan distance, neighbours), `TerrType` enum (terrain + colour), `CellContents` enum (things on a tile + symbol/colour). |
| `game_map_{1,2,3}.xlsx` | Generated example maps (one cell per tile, colour = terrain, thick borders = walls). `~$game_map_1.xlsx` is just an Excel lock file. |

**Other notes in this folder**

- [architecture.md](architecture.md): data model, coordinate system, walls/rooms/doors, how to run.
- [map_generation.md](map_generation.md): the generation pipeline step by step, with the randomness knobs.
- [game_rules.md](game_rules.md): condensed rules, items, terrain, enemies, boss, glitches, and how a run is scored.
- [verification.md](verification.md): `verify.py`, the beatability / not-trivial checker, and its results.
- [item_placement.md](item_placement.md): vaults, hiding-place scores and forward fill, with before/after numbers.
- [simulator.md](simulator.md): the turn simulator and play UI, command vocabulary, and the rule readings it uses.
- [status_and_gaps.md](status_and_gaps.md): what's implemented vs. only designed, bugs and inconsistencies spotted.

**Git:** repo `aphyer1992/game_gen`, branch `main`, last commit `fdedd7a` (2025-06-03, "functionalize a spread routine"). As of this reading the working tree shows all four source files modified, but the diff is line endings only (CRLF vs LF), no content changes.
