import unittest

from src.alg import astar, bfs
from src.cfg import (
    FIXED_DT,
    FLOOR,
    KEY_KINDS,
    MAX_LEVEL,
    SPARKS_NEEDED,
    SPARKS_ON_MAP,
    GUN_MAX,
    WALL,
    WEAPON_KINDS,
)
from src.level import make_level


class TestGrid:
    def __init__(self, grid):
        self.grid = grid
        self.h = len(grid)
        self.w = len(grid[0])

    def walk(self, c, r):
        return 0 <= c < self.w and 0 <= r < self.h and self.grid[r][c] == FLOOR

    def is_wall(self, c, r):
        return not self.walk(c, r)


class AlgTests(unittest.TestCase):
    def test_astar_gap(self):
        grid = [
            [FLOOR, FLOOR, FLOOR, FLOOR, FLOOR],
            [FLOOR, WALL, WALL, WALL, FLOOR],
            [FLOOR, FLOOR, FLOOR, WALL, FLOOR],
            [WALL, WALL, FLOOR, FLOOR, FLOOR],
            [FLOOR, FLOOR, FLOOR, WALL, FLOOR],
        ]
        path = astar(TestGrid(grid), (0, 0), (4, 4))
        self.assertTrue(path)
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (4, 4))

    def test_no_path(self):
        grid = [
            [FLOOR, WALL, FLOOR],
            [FLOOR, WALL, FLOOR],
            [FLOOR, WALL, FLOOR],
        ]
        path = astar(TestGrid(grid), (0, 0), (2, 0))
        self.assertEqual(path, [])

    def test_exit_reach(self):
        lvl = make_level(seed=123456, w=32, h=24)
        seen = bfs(lvl, lvl.start)
        self.assertIn(lvl.exit, seen)
        self.assertGreater(len(seen), 32 * 24 // 5)

    def test_not_box(self):
        lvl = make_level(seed=777777, w=32, h=24)
        seen = bfs(lvl, lvl.start)
        total = lvl.w * lvl.h
        self.assertGreater(len(seen), total * 0.35)
        self.assertLess(len(seen), total * 0.65)

    def test_wide_roads(self):
        lvl = make_level(seed=888888, w=32, h=24)
        blocks = 0
        for r in range(1, lvl.h - 1):
            for c in range(1, lvl.w - 1):
                if all(lvl.walk(c + dc, r + dr) for dc in (-1, 0, 1) for dr in (-1, 0, 1)):
                    blocks += 1
        self.assertGreater(blocks, 70)

    def test_straights(self):
        lvl = make_level(seed=999999, w=32, h=24)
        runs = 0
        for row in lvl.grid:
            n = 0
            for v in [*row, WALL]:
                if v == FLOOR:
                    n += 1
                else:
                    if n >= 6:
                        runs += 1
                    n = 0
        for c in range(lvl.w):
            n = 0
            for r in range(lvl.h + 1):
                v = lvl.grid[r][c] if r < lvl.h else WALL
                if v == FLOOR:
                    n += 1
                else:
                    if n >= 6:
                        runs += 1
                    n = 0
        self.assertGreater(runs, 18)


class GameplayTests(unittest.TestCase):
    def test_spawn_pack(self):
        from src.world import World

        w = World.new(seed=123456)
        keys = {it.kind for it in w.items if it.kind.startswith("key_") and it.alive}
        weapons = {it.kind for it in w.items if it.kind in WEAPON_KINDS and it.alive}
        sparks = [it for it in w.items if it.kind == "spark" and it.alive]
        self.assertEqual(keys, {f"key_{k}" for k in KEY_KINDS})
        self.assertEqual(weapons, set(WEAPON_KINDS))
        self.assertEqual(len(sparks), SPARKS_ON_MAP)

    def test_key_pickup(self):
        from src.systems import logic_sys
        from src.world import World

        w = World.new(seed=123456)
        key = next(it for it in w.items if it.kind.startswith("key_"))
        name = key.kind.split("_", 1)[1]
        w.player.x = key.x
        w.player.y = key.y
        logic_sys(w, FIXED_DT)
        self.assertFalse(key.alive)
        self.assertIn(name, w.player.keys)

    def test_wp_pickup(self):
        from src.systems import logic_sys
        from src.world import World

        w = World.new(seed=123456)
        wp = next(it for it in w.items if it.kind in WEAPON_KINDS)
        w.player.x = wp.x
        w.player.y = wp.y
        logic_sys(w, FIXED_DT)
        self.assertFalse(wp.alive)
        self.assertIn(w.player.wp, WEAPON_KINDS)
        self.assertIn(w.player.wp, WEAPON_KINDS)
        self.assertGreater(w.player.inv[w.player.wp], 0)

    def test_auto_hit(self):
        from src.systems import use_weapon
        from src.world import World

        w = World.new(seed=123456)
        p = w.player
        e = w.enemies[0]
        e.x = p.x - 42
        e.y = p.y
        e.alive = True
        p.wp = "blade"
        p.inv = {"blade": 1}
        p.face_x = 1.0
        p.face_y = 0.0
        self.assertTrue(use_weapon(w))
        self.assertFalse(e.alive)
        self.assertEqual(p.inv.get("blade", 0), 0)

    def test_blade(self):
        from src.systems import use_blade
        from src.world import World

        w = World.new(seed=123456)
        p = w.player
        e = w.enemies[0]
        e.x = p.x + 42
        e.y = p.y
        e.alive = True
        p.wp = "blade"
        p.inv = {"blade": 1}
        self.assertTrue(use_blade(w))
        self.assertFalse(e.alive)
        self.assertGreater(w.wp_cd, 0)

    def test_gun_breaks(self):
        from src.systems import use_weapon
        from src.world import World

        w = World.new(seed=123456)
        p = w.player
        p.wp = "gun"
        p.inv = {"gun": GUN_MAX}
        p.gems = GUN_MAX

        for i, e in enumerate(w.enemies[:GUN_MAX]):
            e.x = p.x + 38 + i * 2
            e.y = p.y
            e.alive = True
            e.path.clear()

        for _ in range(GUN_MAX):
            p.atk_t = 0.0
            self.assertTrue(use_weapon(w))

        self.assertEqual(p.gems, 0)
        self.assertNotIn("gun", p.inv)
        self.assertEqual(w.wp_wait, "gun")
        self.assertGreater(w.wp_cd, 0)

    def test_gun_need(self):
        from src.systems import use_weapon
        from src.world import World

        w = World.new(seed=123456)
        p = w.player
        e = w.enemies[0]
        e.x = p.x + 38
        e.y = p.y
        e.alive = True
        p.wp = "gun"
        p.inv = {"gun": GUN_MAX}
        p.gems = 0
        self.assertFalse(use_weapon(w))
        self.assertTrue(e.alive)
        self.assertEqual(p.inv["gun"], GUN_MAX)

    def test_wp_respawn(self):
        from src.systems import logic_sys
        from src.world import World

        w = World.new(seed=777777)
        for it in w.items:
            if it.kind in WEAPON_KINDS:
                it.alive = False
        w.player.wp = ""
        w.player.inv.clear()
        w.wp_cd = 0.0
        logic_sys(w, FIXED_DT)
        self.assertTrue(any(it.kind in WEAPON_KINDS and it.alive for it in w.items))

    def test_heal(self):
        from src.systems import logic_sys
        from src.world import World

        w = World.new(seed=123456)
        heal = next(it for it in w.items if it.kind == "heal")
        w.player.hp = 40
        w.player.x = heal.x
        w.player.y = heal.y
        logic_sys(w, FIXED_DT)
        self.assertFalse(heal.alive)
        self.assertGreater(w.player.hp, 40)

    def test_armor(self):
        from src.systems import hit_player
        from src.world import World

        w = World.new(seed=123456)
        w.player.hp = 100
        w.player.armor = 20
        hit_player(w, 12)
        self.assertEqual(w.player.hp, 100)
        self.assertEqual(w.player.armor, 8)

    def test_next_level(self):
        from src.systems import logic_sys
        from src.world import World

        w = World.new(seed=123456)
        exit_item = next(it for it in w.items if it.kind == "exit")
        w.state = w.state.PLAY
        w.player.gems = SPARKS_NEEDED
        w.player.keys = set(KEY_KINDS)
        w.player.x = exit_item.x
        w.player.y = exit_item.y
        old_no = w.level_no
        logic_sys(w, FIXED_DT)
        self.assertEqual(w.level_no, old_no + 1)
        self.assertEqual(w.state.name, "PLAY")
        self.assertEqual(w.player.gems, 0)

    def test_final_win(self):
        from src.systems import logic_sys
        from src.world import World

        w = World.new(seed=123456, level_no=MAX_LEVEL)
        exit_item = next(it for it in w.items if it.kind == "exit")
        w.state = w.state.PLAY
        w.player.gems = SPARKS_NEEDED
        w.player.keys = set(KEY_KINDS)
        w.player.x = exit_item.x
        w.player.y = exit_item.y
        logic_sys(w, FIXED_DT)
        self.assertEqual(w.level_no, MAX_LEVEL)
        self.assertEqual(w.state.name, "WIN")

    def test_scale(self):
        from src.world import World

        w1 = World.new(seed=123456, level_no=1)
        w10 = World.new(seed=123456, level_no=MAX_LEVEL)
        self.assertLess(w1.enemies[0].speed, w10.enemies[0].speed)
        self.assertLess(w1.enemies[0].dmg, w10.enemies[0].dmg)

    def test_smooth(self):
        from src.systems import input_sys
        from src.world import World

        class Inp:
            def down(self, *names):
                return "d" in names

            def take(self, *names):
                return False

        w = World.new(seed=123456)
        input_sys(w, Inp(), FIXED_DT)
        self.assertGreater(w.player.vx, 0)
        self.assertLess(w.player.vx, w.player.speed)

    def test_xp_drop(self):
        from src.systems import kill_enemy, logic_sys
        from src.world import World

        w = World.new(seed=123456)
        e = w.enemies[0]
        old_xp = w.player.xp
        kill_enemy(w, e, "blade")
        xp = next(it for it in w.items if it.kind == "xp" and it.alive)
        w.player.x = xp.x
        w.player.y = xp.y
        logic_sys(w, FIXED_DT)
        self.assertFalse(xp.alive)
        self.assertGreater(w.player.xp, old_xp)

    def test_buy_speed(self):
        from src.cfg import SKILL_COST
        from src.systems import buy_skill, player_speed
        from src.world import World

        w = World.new(seed=123456)
        w.player.xp = SKILL_COST["spd"]
        old = player_speed(w.player)
        self.assertTrue(buy_skill(w, "spd"))
        self.assertEqual(w.player.xp, 0)
        self.assertGreater(player_speed(w.player), old)

    def test_skills(self):
        from src.systems import use_dash, use_rage
        from src.world import World

        w = World.new(seed=123456)
        self.assertFalse(use_dash(w))
        self.assertFalse(use_rage(w))
        w.player.skills["dash"] = 1
        w.player.skills["rage"] = 1
        self.assertTrue(use_dash(w))
        self.assertGreater(w.player.dash_t, 0)
        self.assertTrue(use_rage(w))
        self.assertGreater(w.player.rage_t, 0)

    def test_alert_wave(self):
        from src.systems import logic_sys
        from src.world import World

        w = World.new(seed=123456)
        w.state = w.state.PLAY
        w.player.gems = SPARKS_NEEDED
        w.player.keys = set(KEY_KINDS)
        old_count = len(w.enemies)
        logic_sys(w, FIXED_DT)
        self.assertTrue(w.alert)
        self.assertGreater(w.alert_n, 0)
        self.assertGreater(len(w.enemies), old_count)

    def test_shoot(self):
        from src.systems import _fire_bolt
        from src.world import World

        w = World.new(seed=123456, level_no=3)
        shooter = next(e for e in w.enemies if e.kind == "shooter")
        old = len(w.shots)
        _fire_bolt(w, shooter)
        self.assertEqual(len(w.shots), old + 1)
        self.assertTrue(w.shots[-1].alive)

    def test_tank_spawn(self):
        from src.world import World

        w = World.new(seed=123456, level_no=4)
        tanks = [e for e in w.enemies if e.kind == "tank"]
        self.assertTrue(tanks)
        self.assertGreater(tanks[0].max_hp, w.enemies[0].max_hp)

    def test_render(self):
        from src.cfg import ALERT_LIGHT_R, LIGHT_R
        from src.render import Renderer

        self.assertTrue(hasattr(Renderer, "_inventory"))
        self.assertLess(ALERT_LIGHT_R, LIGHT_R)


if __name__ == "__main__":
    unittest.main()
