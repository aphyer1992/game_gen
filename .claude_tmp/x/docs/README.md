# game_gen notes (index)

Notes written by Claude after reading the repo on 2026-11-21, for future sessions. Code was not changed.

**What the project is:** a "speedrun-routing" game. A simple top-down adventure map is randomly generated; players never play it, they *route* a speedrun of it (every turn = 1 second, perfect execution assumed) and compete on time. Each round, players draw glitches that open new skips.

**Where things are**

| File | What it is |
|---|---|
| `rules` | Plain-text design doc: turn structure, items, terrain, enemies, boss, glitch/round system. No extension. |
| `map.py` | `Map` class: all procedural generation + Excel export. `__main__` builds 3 maps (seeds 42-44) at 50x50. |
| `vaults.py` | "Vaults" = hand-designed set pieces placed on the map. Only one exists: the Desert Pyramid. |
| `verify.py` | Map verifier: item progression, beatability, gating metrics, seed re-rolling. |
| `support_classes.py` | `Coordinates` (Manhattan distance, neighbours), `TerrType` enum (terrain + colour), `CellContents` enum (things on a tile + symbol/colour). |
| `game_map_{1,2,3}.xlsx` | Generated example maps (one cell per tile, colour = terrain, thick borders = walls). `~$game_map_1.xlsx` is just an Excel lock file. |

**Other notes in this folder**

- [architecture.md](architecture.md): data model, coordinate system, walls/rooms/doors, how to run.
- [map_generation.md](map_generation.md): the generation pipeline step by step, with the randomness knobs.
- [game_rules.md](game_rules.md): condensed rules, items, terrain, enemies, boss, glitches, and how a run is scored.
- [verification.md](verification.md): `verify.py`, the beatability / not-trivial checker, and its results.
- [status_and_gaps.md](status_and_gaps.md): what's implemented vs. only designed, bugs and inconsistencies spotted.

**Git:** repo `aphyer1992/game_gen`, branch `main`, last commit `fdedd7a` (2025-06-03, "functionalize a spread routine"). As of this reading the working tree shows all four source files modified, but the diff is line endings only (CRLF vs LF), no content changes.
