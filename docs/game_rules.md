# Game rules (condensed from `rules`)

## Core loop
- Deterministic, effectively turn-based: **1 turn = 1 second**. Final score = turns to defeat the boss. Lower is better.
- Spawn at the Shrine in the bottom-left. 3 Life. At 0 you respawn with full life and all progress kept, at the last shrine you interacted with (dying can be a deliberate movement tech).
- Tie-break rule for any ambiguity (e.g. enemy choosing between equal squares): lowest y, then lowest x.
- Each turn, one of:
  1. **Move** up to 2 tiles orthogonally (may turn between the two steps).
  2. **Attack** an adjacent tile: enemy takes 1 damage and is knocked back 2.
  3. **Interact** with what's on your tile.
- Route notation: two characters per turn. `ww` = north twice, `wa` = north then west, `a.` = west once and stop, `xa` = attack west.

## Items (6 per map)
| Item | Effect |
|---|---|
| Water Boots | Can enter water (otherwise instant death) |
| Flame Shield | Can enter lava (otherwise instant death) |
| Woodcutter's Axe | Attack a Tree to turn it to grass (trees otherwise impassable) |
| Desert Cloak | Ignore desert penalty |
| Bow | Attacks travel in a straight line until they hit an enemy |
| Shrine Maiden's Blessing | Interact at a shrine to warp to any other shrine: 4 turns total |

Plus **20 Power Gems**; the boss needs 16 (4 seals x 4).

## Terrain
- Water / Lava: entering without the item kills you.
- Tree: impassable (Axe can cut).
- Desert: if you *start* your turn there without the Cloak, take 1 damage and can move only 1.
- Wall: impassable edge between tiles (buildings, rooms, castle, pyramid).
- Road / Grass / Building floor / Castle floor: normal.

## Knockback (the main glitchless skip)
Many hits knock the player 2 tiles. If the middle tile is impassable (wall/tree), you bounce and don't move. If the middle tile is only *hazardous* (water, lava), you fly over it safely. So taking a hit next to a 1-wide river can replace the Boots. A figure stuck inside impassable terrain is pushed to an adjacent empty tile, or dies if there is none.

## Locations
- Shrine: interact to heal to full and set respawn. With Blessing, warp hub.
- Pickups: interact to collect a gem or item.
- Seals: in the boss room corners; interact to spend 4 gems and break one.

## Enemies
- **Ogre** (HP 3): adjacent → hits you (1 dmg + knockback 2); else within 5 → steps 1 toward you; else idle. Can't enter water/lava and dies if knocked into them. Useful as a knockback launcher.
- **Lava Snake** (HP 1, stationary in lava): if collinear within 5, aims; next turn breathes fire down that line (1 dmg + knockback) if you're still in it. (Probably the `DRAGON` content in code.)
- **Sawblade**: follows a fixed patrol, 1 tile/turn. Walking into it fails and costs 1 damage; it moving into you does 1 damage + knockback in its direction (can push you into a wall).
- **Boss "D.E.F."** (Dark Emperor Festin, etc.): in a 5x5 room with a seal in each corner. Acts like an Ogre but only aggros while you're in the room (otherwise drifts back to centre), has infinite HP but still takes knockback. Break all four seals (16 gems), then he dies in one hit.

## Rounds and glitches
- Round 0: everyone routes the vanilla map.
- Each later round: each player draws a random glitch only they may use that round; from the next round on, everyone may use it. Times drop as the glitch pool grows.
- Glitches the designer likes:
  - **Corner Clip**: standing at the outside corner of a wall, spend a turn to move diagonally through it into the inside corner tile (if free and passable).
  - **Shrinewarp Momentum**: enter a move during the warp to land 3 tiles offset from the destination shrine in a chosen direction.
  - **Superslide**: placeholder, text stops at "By".
- Less sure:
  - **Infinite Sword Glitch**: after one attack you keep attacking that direction every turn, even while moving, until you die.
  - **Spawning Savestate**: start the run at any shrine.
  - **Respawn Exploit**: die on the same turn as collecting an item and it stays on the map (designer worries about gem farming).

## Scoring today
Score = number of turns. There is no code that computes or checks a route; routes are presumably worked out by hand against the spreadsheet.
