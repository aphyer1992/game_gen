"""Tests for the turn simulator (game.py) on small hand-built maps.

    python test_game.py
"""
import unittest

import game
from game import Simulator, parse_commands
from map import Map
from support_classes import Coordinates as C, TerrType as T, CellContents as K


def blank(w=12, h=12):
    m = Map(w, h)
    m.set_cell_contents(0, 0, K.SHRINE)
    return m


def run(m, route):
    cmds, errs = parse_commands(route)
    assert not errs, errs
    sim = Simulator(m)
    return sim, sim.run(cmds)


class TestParse(unittest.TestCase):
    def test_vocabulary(self):
        cmds, errs = parse_commands('ww wa a. d xa e. e3 .. dd*3 # comment\nddww')
        self.assertEqual(errs, [])
        self.assertEqual([c.kind for c in cmds],
                         ['move', 'move', 'move', 'move', 'attack', 'interact', 'warp', 'wait',
                          'move', 'move', 'move', 'move', 'move'])
        self.assertEqual(cmds[2].dirs, ['a'])
        self.assertEqual(cmds[6].target, 3)

    def test_unfinished_run_keeps_complete_turns(self):
        cmds, errs = parse_commands('dd' * 100 + 'd')
        self.assertEqual(len(cmds), 100)
        self.assertTrue(errs[0][1].startswith(game.UNFINISHED))

    def test_error_stops_route(self):
        cmds, errs = parse_commands('dd qq dd')
        self.assertEqual(len(cmds), 1)
        self.assertEqual(errs[0][0], 1)


class TestMovement(unittest.TestCase):
    def test_move_and_tree(self):
        m = blank()
        m.set_cell(3, 0, T.TREE)
        sim, st = run(m, 'dd dd')
        self.assertEqual(st[1].pos, C(2, 0))
        self.assertEqual(st[2].pos, C(2, 0))        # tree blocks
        self.assertEqual(st[2].turn, 2)

    def test_water_kills_without_boots(self):
        m = blank()
        m.set_cell(1, 0, T.WATER)
        m.set_cell_contents(0, 2, K.SHRINE)
        sim, st = run(m, 'ww e. ss d.')
        self.assertEqual(st[4].pos, C(0, 2))         # respawned at last shrine
        self.assertEqual(st[4].deaths, 1)

    def test_desert(self):
        m = blank()
        for x in range(1, 6):
            m.set_cell(x, 0, T.DESERT)
        sim, st = run(m, 'd. dd dd')
        self.assertEqual(st[1].pos, C(1, 0))
        self.assertEqual(st[2].pos, C(2, 0))         # only 1 tile from desert
        self.assertEqual(st[2].life, 2)
        self.assertEqual(st[3].life, 1)

    def test_wall(self):
        m = blank()
        m.add_room([C(x, y) for x in range(3, 6) for y in range(0, 3)])
        sim, st = run(m, 'dd d.')
        self.assertEqual(st[2].pos, C(2, 0))
        m.add_door(C(2, 0), C(3, 0))
        sim, st = run(m, 'dd d.')
        self.assertEqual(st[2].pos, C(3, 0))


class TestCastleGate(unittest.TestCase):
    def _gated(self, gems_on_map):
        m = blank()
        m.add_room([C(x, y) for x in range(3, 6) for y in range(0, 3)], terr_type=T.CASTLE)
        m.add_door(C(3, 0), C(2, 0))
        m.castle_gate = [(C(3, 0), C(2, 0))]
        m.gate_gems = 2
        m.set_cell_contents(2, 0, K.GATE)
        for x in range(gems_on_map):
            m.set_cell_contents(0, 2 + x, K.GEM)
        return m

    def test_gate_stays_shut_without_gems(self):
        m = self._gated(0)
        sim, st = run(m, 'dd e. d.')
        self.assertFalse(st[2].gate_open)
        self.assertEqual(st[3].pos, C(2, 0))           # bumped into the shut gate

    def test_gate_opens_with_gems(self):
        m = self._gated(2)
        sim, st = run(m, 'ww e. w. e. ss ss dd e. d.')
        self.assertEqual(st[5].gems, 2)
        self.assertTrue(st[8].gate_open)
        self.assertEqual(st[8].gems, 2)                # showing the gems doesn't spend them
        self.assertEqual(st[9].pos, C(3, 0))           # walked into the castle


class TestGhostAndHorse(unittest.TestCase):
    def test_ghost_immune_without_sword(self):
        m = blank()
        m.set_cell_contents(1, 0, K.GHOST)
        sim, st = run(m, 'xd')
        g = st[1].enemies[0]
        self.assertEqual(g.hp, 2)
        self.assertTrue(g.alive)

    def test_sword_hurts_ghost(self):
        m = blank()
        m.set_cell_contents(1, 0, K.GHOST)
        sim = Simulator(m)
        st = sim.initial_state()
        st.items.add(K.SILVER_SWORD)
        after = sim.step(st, parse_commands('xd')[0][0])
        g = after.enemies[0]
        self.assertEqual(g.hp, 1)
        self.assertNotEqual(g.pos, C(1, 0))          # knocked back

    def _horse_map(self):
        m = blank(16, 12)
        m.set_cell_contents(0, 1, K.HORSE)
        return m

    def test_mount_then_double_moves(self):
        sim, st = run(self._horse_map(), 'w. e. h. dd dw')
        self.assertTrue(st[3].mounted)
        self.assertEqual(st[3].pos, C(0, 1))          # mounting takes the turn
        self.assertEqual(st[4].pos, C(4, 1))          # dd = 4 east
        self.assertEqual(st[5].pos, C(6, 3))          # dw = 2 east, 2 north

    def test_dismount_before_rough_ground(self):
        m = self._horse_map()
        m.set_cell(3, 1, T.DESERT)
        sim, st = run(m, 'w. e. h. dd')
        self.assertFalse(st[4].mounted)
        self.assertEqual(st[4].pos, C(2, 1))          # stopped before the sand

    def test_dismount_on_bump(self):
        m = self._horse_map()
        m.set_cell(2, 1, T.TREE)
        sim, st = run(m, 'w. e. h. d.')
        self.assertFalse(st[4].mounted)
        self.assertEqual(st[4].pos, C(1, 1))

    def test_mount_needs_horse(self):
        sim, st = run(blank(), 'h. dd')
        self.assertFalse(st[1].mounted)
        self.assertEqual(st[2].pos, C(2, 0))          # ordinary move


class TestPickups(unittest.TestCase):
    def test_seals_and_boss(self):
        m = blank(14, 14)
        for x in range(1, 9):
            m.set_cell_contents(x, 0, K.GEM) if x <= 8 else None
        # boss room 5x5 at (4..8, 4..8), door from (6,3)
        room = [C(x, y) for x in range(4, 9) for y in range(4, 9)]
        m.add_room(room, T.CASTLE)
        m.add_door(C(6, 3), C(6, 4))
        for c in (C(4, 4), C(8, 4)):
            m.set_cell_contents(c.x, c.y, K.SEAL)
        m.set_cell_contents(6, 6, K.BOSS)
        route = ' '.join(['d. e.'] * 8)
        sim, st = run(m, route)
        self.assertEqual(st[-1].gems, 8)
        sim2 = Simulator(m)
        s = st[-1]
        self.assertEqual(len(sim2.seals), 2)
        self.assertEqual(s.pos, C(8, 0))


class TestBoat(unittest.TestCase):
    def _lake(self):
        m = blank()
        for x in range(2, 5):
            for y in range(0, 3):
                m.set_cell(x, y, T.WATER)
        m.set_cell_contents(0, 1, K.WATER_BOOTS)
        return m

    def test_parse(self):
        cmds, errs = parse_commands('ed id i. i3')
        self.assertEqual(errs, [])
        self.assertEqual([c.kind for c in cmds], ['interact_dir', 'interact_dir', 'interact', 'warp'])

    def test_board_sail_land(self):
        sim, st = run(self._lake(), 'w. e. sd ed dd ed')
        self.assertEqual(st[3].pos, C(1, 0))
        self.assertTrue(st[4].in_boat)
        self.assertEqual(st[4].pos, C(2, 0))
        self.assertEqual(st[5].pos, C(4, 0))
        self.assertFalse(st[6].in_boat)
        self.assertEqual(st[6].pos, C(5, 0))
        self.assertEqual(st[6].deaths, 0)

    def test_boat_cant_sail_onto_land(self):
        sim, st = run(self._lake(), 'w. e. sd ed dd dd')
        self.assertEqual(st[6].pos, C(4, 0))         # bumps the far shore
        self.assertTrue(st[6].in_boat)

    def test_walking_into_water_with_boat_stops(self):
        sim, st = run(self._lake(), 'w. e. sd dd')
        self.assertEqual(st[4].pos, C(1, 0))
        self.assertEqual(st[4].deaths, 0)

    def test_walking_into_water_without_boat_drowns(self):
        sim, st = run(self._lake(), 'dd')
        self.assertEqual(st[1].deaths, 1)

    def test_need_boat_to_board(self):
        sim, st = run(self._lake(), 'd. ed')
        self.assertFalse(st[2].in_boat)
        self.assertEqual(st[2].pos, C(1, 0))


class TestEnemies(unittest.TestCase):
    def test_ogre_hits_and_knocks_back(self):
        m = blank()
        m.set_cell_contents(4, 0, K.OGRE)
        sim, st = run(m, 'dd')
        # player at (2,0); ogre within 5 steps to (3,0) (adjacent now)
        self.assertEqual(st[1].pos, C(2, 0))
        self.assertEqual(st[1].enemies[0].pos, C(3, 0))
        sim, st = run(m, 'dd ..')
        self.assertEqual(st[2].life, 2)
        self.assertEqual(st[2].pos, C(0, 0))         # knocked west 2

    def test_ogre_avoids_dead_end(self):
        # Andrew's example (flipped so plain greedy would pick the dead end):
        #   . . Y
        #   . T T
        #   O . T
        m = blank(3, 3)
        for c in (C(1, 1), C(2, 1), C(2, 0)):
            m.set_cell(c.x, c.y, T.TREE)
        m.set_cell_contents(0, 0, K.OGRE)
        sim = Simulator(m)
        st = sim.initial_state()
        st.pos = C(2, 2)
        s1 = sim.step(st, parse_commands('..')[0][0])
        self.assertEqual(s1.enemies[0].pos, C(0, 1))   # not into the (1,0) pocket

    def test_ogre_ignores_you_across_a_river(self):
        m = blank()
        for y in range(11):
            m.set_cell(3, y, T.WATER)             # river with a crossing far away at y=11
        m.set_cell_contents(2, 2, K.OGRE)
        sim = Simulator(m)
        st = sim.initial_state()
        st.pos = C(4, 2)                         # 2 tiles away as the crow flies
        s1 = sim.step(st, parse_commands('..')[0][0])
        self.assertEqual(s1.enemies[0].pos, C(2, 2))

    def test_ogre_with_no_path_stays(self):
        m = blank()
        for x in range(12):
            m.set_cell(x, 2, T.WATER)
        m.set_cell_contents(1, 3, K.OGRE)
        sim = Simulator(m)
        st = sim.initial_state()
        st.pos = C(1, 0)
        s1 = sim.step(st, parse_commands('..')[0][0])
        self.assertEqual(s1.enemies[0].pos, C(1, 3))

    def _ogre_hit(self, middle_terrain):
        m = blank()
        for y in range(12):
            m.set_cell(3, y, middle_terrain)
        m.set_cell_contents(1, 2, K.OGRE)
        sim = Simulator(m)
        st = sim.initial_state()
        st.pos = C(2, 2)                 # ogre is adjacent to the west
        return sim.step(st, parse_commands('..')[0][0])

    def test_knockback_over_water(self):
        s = self._ogre_hit(T.WATER)      # 1-wide river: flown over, no Boots needed
        self.assertEqual(s.pos, C(4, 2))
        self.assertEqual((s.life, s.deaths), (2, 0))

    def test_knockback_bounces_off_tree(self):
        s = self._ogre_hit(T.TREE)
        self.assertEqual(s.pos, C(2, 2))
        self.assertEqual(s.life, 2)

    def test_attack_kills_ogre_into_lava(self):
        m = blank()
        m.set_cell(3, 0, T.LAVA)
        m.set_cell_contents(1, 0, K.OGRE)
        sim, st = run(m, 'xd')
        e = st[1].enemies[0]
        self.assertEqual(e.hp, 2)
        self.assertFalse(e.alive)                    # knocked 2 east into lava (3,0)

    def test_snake_aims_then_breathes(self):
        m = blank()
        m.set_cell(5, 3, T.LAVA)
        m.set_cell_contents(5, 3, K.DRAGON)
        sim, st = run(m, 'ww w. ..')
        # (0,2) then (0,3): collinear with snake at distance 5 -> aims; next turn breathes
        self.assertEqual(st[2].pos, C(0, 3))
        self.assertEqual(st[2].enemies[0].aim, (-1, 0))
        self.assertEqual(st[3].life, 2)

    def test_snake_dodge(self):
        m = blank()
        m.set_cell(5, 3, T.LAVA)
        m.set_cell_contents(5, 3, K.DRAGON)
        sim, st = run(m, 'ww w. w.')
        self.assertEqual(st[3].life, 3)

    def test_tree_blocks_snake(self):
        m = blank()
        m.set_cell(5, 3, T.LAVA)
        m.set_cell(3, 3, T.TREE)
        m.set_cell_contents(5, 3, K.DRAGON)
        sim, st = run(m, 'ww w. ..')
        self.assertIsNone(st[2].enemies[0].aim)       # can't see us past the tree
        self.assertEqual(st[3].life, 3)
        # cut the tree and the line opens again
        sim = Simulator(m)
        s0 = sim.initial_state()
        s0.cut_trees = {C(3, 3)}
        s0.pos = C(0, 3)
        s1 = sim.step(s0, parse_commands('..')[0][0])
        self.assertEqual(s1.enemies[0].aim, (-1, 0))

    def test_bow_kills_snake(self):
        m = blank()
        m.set_cell(5, 3, T.LAVA)
        m.set_cell(2, 3, T.WATER)
        m.set_cell_contents(5, 3, K.DRAGON)
        m.set_cell_contents(0, 1, K.BOW)
        sim, st = run(m, 'w. e. ww xd')
        self.assertFalse(st[4].enemies[0].alive)

    def test_bow_does_not_cut_distant_tree(self):
        m = blank()
        m.set_cell(3, 0, T.TREE)
        sim = Simulator(m)
        st = sim.initial_state()
        st.items = {K.AXE, K.BOW}
        s1 = sim.step(st, parse_commands('xd')[0][0])
        self.assertNotIn(C(3, 0), s1.cut_trees)
        st.pos = C(2, 0)
        s2 = sim.step(st, parse_commands('xd')[0][0])
        self.assertIn(C(3, 0), s2.cut_trees)

    def test_hit_stuns_ogre(self):
        m = blank()
        m.set_cell_contents(1, 0, K.OGRE)
        sim, st = run(m, 'xd .. ..')
        self.assertEqual(st[1].enemies[0].pos, C(3, 0))   # knocked back...
        self.assertTrue(any('stunned' in e for e in st[1].events))
        self.assertEqual(st[1].life, 3)
        self.assertEqual(st[2].enemies[0].pos, C(2, 0))   # ...then approaches a turn later
        self.assertFalse(st[2].enemies[0].stunned)

    def test_warp_needs_visited_shrine(self):
        m = blank()
        m.set_cell_contents(0, 1, K.BLESSING)
        m.set_cell_contents(10, 10, K.SHRINE)
        sim, st = run(m, 'w. e. s. e1')
        self.assertIn("haven't visited", ' '.join(st[4].events))
        self.assertIsNone(st[4].warp)
        self.assertEqual(st[4].pos, C(0, 0))

    def test_only_interacting_visits_a_shrine(self):
        m = blank()
        m.set_cell_contents(1, 0, K.SHRINE)
        sim, st = run(m, 'd. e.')
        self.assertNotIn(C(1, 0), st[1].visited_shrines)   # standing on it isn't enough
        self.assertIn(C(1, 0), st[2].visited_shrines)

    def test_warp(self):
        m = blank()
        m.set_cell_contents(0, 1, K.BLESSING)
        m.set_cell_contents(2, 0, K.SHRINE)            # shrine 1
        sim, st = run(m, 'w. e. sd d. e. e0 d.')
        self.assertEqual(st[6].command.text, 'e0')     # back to the spawn shrine
        self.assertEqual([s.command.text for s in st[7:10]], ['~~', '~~', '~~'])
        self.assertEqual(st[9].pos, C(0, 0))
        self.assertEqual(st[9].turn, 9)
        self.assertEqual(st[10].pos, C(1, 0))


class TestVictory(unittest.TestCase):
    def test_full_boss_fight(self):
        m = blank(12, 12)
        for i, x in enumerate(range(1, 9)):
            m.set_cell_contents(x, 1, K.GEM)
        room = [C(x, y) for x in range(2, 7) for y in range(4, 9)]
        m.add_room(room, T.CASTLE)
        m.add_door(C(2, 3), C(2, 4))
        m.set_cell_contents(2, 4, K.SEAL)
        m.set_cell_contents(6, 4, K.SEAL)
        m.set_cell_contents(4, 6, K.BOSS)
        sim = Simulator(m)
        st = sim.initial_state()
        st.gems = 8
        # enter the room and break the near seal; boss will come at us
        cmds, _ = parse_commands('ww dd ww e.')
        states = [st]
        for c in cmds:
            states.append(sim.step(states[-1], c))
        self.assertTrue(any('Broke a seal' in e for s in states for e in s.events))
        # force second seal and check one hit wins
        s = states[-1].copy()
        s.seals_broken = set(sim.seals)
        boss = [e for e in s.enemies if e.kind == 'boss'][0]
        boss.pos = C(s.pos.x + 1, s.pos.y) if s.pos.x < 6 else C(s.pos.x - 1, s.pos.y)
        d = 'd' if boss.pos.x > s.pos.x else 'a'
        won = sim.step(s, parse_commands('x' + d)[0][0])
        self.assertTrue(won.won)


class TestEndToEnd(unittest.TestCase):
    # These play real generated maps, so they use several seeds and ask for
    # most of them to work: the map generator keeps changing which map a seed
    # gives, and the greedy auto-route is only a rough player.
    SEEDS = (3, 21, 40, 43)

    def test_route_text_replays_identically(self):
        import autoroute
        m, seed = game.load_map(40)
        cmds, st, done = autoroute.autoroute(m, max_turns=400)
        parsed, errs = parse_commands(' '.join(cmds))
        self.assertEqual(errs, [])
        final = Simulator(m).run(parsed)[-1]
        self.assertEqual((final.turn, final.pos, final.gems, final.items),
                         (st.turn, st.pos, st.gems, st.items))

    def test_greedy_route_reaches_boss_room(self):
        import autoroute
        reached = []
        for seed in self.SEEDS:
            m, _ = game.load_map(seed)
            cmds, st, done = autoroute.autoroute(m)
            if done:
                self.assertGreaterEqual(st.gems, 16)
                reached.append(seed)
        self.assertGreaterEqual(len(reached), len(self.SEEDS) // 2, reached)


if __name__ == '__main__':
    unittest.main()
