import math
import tkinter as tk

from .cfg import (
    ALERT_LIGHT_R,
    BLADE_COOLDOWN,
    BLADE_RANGE,
    COL,
    ENEMY_SEE,
    FLOOR_LIGHT_MIN,
    KEY_KINDS,
    LIGHT_MIN,
    LIGHT_R,
    ARMOR_MAX,
    MAX_LEVEL,
    VIEW_LERP,
    PLAYER_HP,
    SCREEN_H,
    SCREEN_W,
    SKILL_COST,
    SKILL_KINDS,
    SKILL_DESC,
    SKILL_MAX,
    SKILL_NAMES,
    SPARKS_NEEDED,
    GUN_MAX,
    SPRITE_MIN,
    TILE,
    WALL_LIGHT_MIN,
    WEAPON_KINDS,
    WEAPON_NAMES,
    WEAPON_DMG,
    WEAPON_RANGE,
)
from .entities import EnemyState, GameState, Item
from .vec import clamp, dist
from .world import World


class Camera:
    def __init__(self, sw: int, sh: int) -> None:
        self.x = 0.0
        self.y = 0.0
        self.sw = sw
        self.sh = sh

    def update(self, w: World, dt: float) -> None:
        p = w.player
        px = p.view_x + p.w / 2
        py = p.view_y + p.h / 2
        tx = px - self.sw / 2
        ty = py - self.sh / 2
        k = min(1.0, 7.5 * dt)
        self.x += (tx - self.x) * k
        self.y += (ty - self.y) * k
        self.x = clamp(self.x, 0.0, max(0.0, w.lvl.px_w - self.sw))
        self.y = clamp(self.y, 0.0, max(0.0, w.lvl.px_h - self.sh))

    def apply(self, x: float, y: float) -> tuple[float, float]:
        return x - self.x, y - self.y

    def visible(self, x: float, y: float, pad: float = 80.0) -> bool:
        return -pad <= x - self.x <= self.sw + pad and -pad <= y - self.y <= self.sh + pad


class Renderer:
    def __init__(self, canvas: tk.Canvas) -> None:
        self.cv = canvas
        self.cam = Camera(SCREEN_W, SCREEN_H)
        self.px: float | None = None
        self.py: float | None = None
        self.frame_dt = 0.0


    def _smooth_views(self, w: World, dt: float) -> None:
        k = min(1.0, VIEW_LERP * dt)
        for a in [w.player, *w.enemies]:
            if abs(a.x - a.view_x) > TILE * 4 or abs(a.y - a.view_y) > TILE * 4:
                a.view_x = a.x
                a.view_y = a.y
            else:
                a.view_x += (a.x - a.view_x) * k
                a.view_y += (a.y - a.view_y) * k

    def draw(self, w: World, dt: float) -> None:
        self.frame_dt = dt
        self._smooth_views(w, dt)
        self.cam.update(w, dt)
        self.cv.delete("all")
        if w.state is GameState.MENU:
            self._menu(w)
            return

        self._world(w)
        self._items(w)
        self._enemies(w)
        self._shots(w)
        self._player(w)
        self._parts(w)
        self._hud(w)
        if w.debug:
            self._debug(w)
        if w.state is GameState.INV:
            self._inventory(w)
        elif w.state is GameState.PAUSE:
            self._overlay("ПАУЗА", "P или Esc — продолжить    R — новый уровень")
        elif w.state is GameState.WIN:
            self._overlay("ПОБЕДА", "Enter — новый забег    Esc — меню")
        elif w.state is GameState.LOSE:
            self._overlay("ПОРАЖЕНИЕ", "Enter — новый забег    Esc — меню")

    def _world(self, w: World) -> None:
        c0 = max(0, int(self.cam.x // TILE) - 1)
        r0 = max(0, int(self.cam.y // TILE) - 1)
        c1 = min(w.lvl.w, int((self.cam.x + SCREEN_W) // TILE) + 2)
        r1 = min(w.lvl.h, int((self.cam.y + SCREEN_H) // TILE) + 2)
        for r in range(r0, r1):
            for c in range(c0, c1):
                x, y = self.cam.apply(c * TILE, r * TILE)
                cx = c * TILE + TILE / 2
                cy = r * TILE + TILE / 2
                if w.lvl.is_wall(c, r):
                    base = COL["wall2"] if (c + r) % 2 else COL["wall"]
                    col = self._lit(base, cx, cy, w, WALL_LIGHT_MIN)
                    edge = self._lit(COL["wall_edge"], cx, cy, w, WALL_LIGHT_MIN + 0.035)
                    hi = self._lit(COL["wall_hi"], cx, cy, w, WALL_LIGHT_MIN + 0.055)
                    self.cv.create_rectangle(x, y, x + TILE + 1, y + TILE + 1, fill=col, outline=edge)
                    self.cv.create_line(x + 2, y + 2, x + TILE - 2, y + 2, fill=hi)
                    self.cv.create_line(x + 2, y + 2, x + 2, y + TILE - 2, fill=hi)
                else:
                    base = COL["floor2"] if (c + r) % 2 else COL["floor"]
                    col = self._lit(base, cx, cy, w, FLOOR_LIGHT_MIN)
                    edge = self._lit(COL["floor_grid"], cx, cy, w, FLOOR_LIGHT_MIN * 0.7)
                    self.cv.create_rectangle(x, y, x + TILE + 1, y + TILE + 1, fill=col, outline=edge)

    def _items(self, w: World) -> None:
        for it in w.items:
            if not it.alive and it.kind != "exit":
                continue
            if not self.cam.visible(it.cx, it.cy):
                continue
            sx, sy = self.cam.apply(it.x, it.y)
            pulse = 2 + math.sin(it.anim_i * 1.1) * 2
            if it.kind == "exit":
                self._exit_item(it, sx, sy, w)
            elif it.kind in KEY_KINDS or it.kind.startswith("key_"):
                self._key_item(it, sx, sy, pulse, w)
            elif it.kind in WEAPON_KINDS:
                self._weapon_item(it, sx, sy, pulse, w)
            elif it.kind in ("heal", "armor"):
                self._boost_item(it, sx, sy, pulse, w)
            elif it.kind == "xp":
                self._xp_item(it, sx, sy, pulse, w)
            else:
                self._spark_item(it, sx, sy, pulse, w)

    def _exit_item(self, it: Item, sx: float, sy: float, w: World) -> None:
        ready = w.player.gems >= SPARKS_NEEDED and all(k in w.player.keys for k in KEY_KINDS)
        base = COL["exit"] if ready else COL["exit_lock"]
        col = self._lit(base, it.cx, it.cy, w, SPRITE_MIN)
        glow = self._lit(COL["exit"], it.cx, it.cy, w, 0.34 if ready else 0.18)
        self.cv.create_oval(sx - 9, sy - 9, sx + it.w + 9, sy + it.h + 9, outline=glow, width=2)
        self.cv.create_rectangle(sx - 4, sy - 4, sx + it.w + 4, sy + it.h + 4, fill="", outline=col, width=3)
        self.cv.create_rectangle(sx + 4, sy + 4, sx + it.w - 4, sy + it.h - 4, fill="", outline=col, width=1)
        for i, key in enumerate(KEY_KINDS):
            got = key in w.player.keys
            kc = self._lit(COL[f"key_{key}"] if got else COL["exit_lock"], it.cx, it.cy, w, 0.42 if got else 0.20)
            x = sx - 3 + i * 13
            y = sy - 16
            self.cv.create_oval(x, y, x + 9, y + 9, fill=kc if got else "", outline=kc, width=2)

    def _key_item(self, it: Item, sx: float, sy: float, pulse: float, w: World) -> None:
        key = it.kind.split("_", 1)[1] if it.kind.startswith("key_") else it.kind
        col = self._lit(COL[f"key_{key}"], it.cx, it.cy, w, SPRITE_MIN)
        hi = self._lit(COL["spark_core"], it.cx, it.cy, w, 0.48)
        self.cv.create_oval(sx - pulse, sy - pulse, sx + 14 + pulse, sy + 14 + pulse, fill=col, outline=hi, width=1)
        self.cv.create_rectangle(sx + 12, sy + 7, sx + 27, sy + 11, fill=col, outline="")
        self.cv.create_rectangle(sx + 21, sy + 10, sx + 25, sy + 16, fill=col, outline="")
        self.cv.create_oval(sx + 4, sy + 4, sx + 10, sy + 10, fill=COL["dark"], outline="")

    def _spark_item(self, it: Item, sx: float, sy: float, pulse: float, w: World) -> None:
        cx = sx + it.w / 2
        cy = sy + it.h / 2
        glow = self._lit(COL["spark_glow"], it.cx, it.cy, w, 0.34)
        gold = self._lit(COL["spark2"], it.cx, it.cy, w, 0.42)
        core = self._lit(COL["spark_core"], it.cx, it.cy, w, 0.58)
        r = 8 + pulse
        self.cv.create_oval(cx - r - 4, cy - r - 4, cx + r + 4, cy + r + 4, fill=glow, outline="")
        self.cv.create_polygon(
            cx, cy - r - 2,
            cx + 4, cy - 4,
            cx + r + 2, cy,
            cx + 4, cy + 4,
            cx, cy + r + 2,
            cx - 4, cy + 4,
            cx - r - 2, cy,
            cx - 4, cy - 4,
            fill=gold,
            outline="",
        )
        self.cv.create_line(cx, cy - r, cx, cy + r, fill=core, width=2)
        self.cv.create_line(cx - r, cy, cx + r, cy, fill=core, width=2)
        self.cv.create_oval(cx - 2, cy - 2, cx + 2, cy + 2, fill=core, outline="")

    def _xp_item(self, it: Item, sx: float, sy: float, pulse: float, w: World) -> None:
        cx = sx + it.w / 2
        cy = sy + it.h / 2
        col = self._lit(COL["xp"], it.cx, it.cy, w, 0.46)
        core = self._lit(COL["xp_core"], it.cx, it.cy, w, 0.58)
        r = 7 + pulse
        self.cv.create_polygon(cx, cy - r, cx + r, cy, cx, cy + r, cx - r, cy, fill=col, outline=core)
        self.cv.create_text(cx, cy + 1, text=str(max(1, it.val)), fill=core, font=("Arial", 8, "bold"))

    def _weapon_item(self, it: Item, sx: float, sy: float, pulse: float, w: World) -> None:
        if it.kind == "blade":
            self._blade_item(it, sx, sy, pulse, w)
        elif it.kind == "shuriken":
            self._shuriken_item(it, sx, sy, pulse, w)
        else:
            self._gun_item(it, sx, sy, pulse, w)

    def _blade_item(self, it: Item, sx: float, sy: float, pulse: float, w: World) -> None:
        cx = sx + it.w / 2
        cy = sy + it.h / 2
        edge = self._lit(COL["blade_edge"], it.cx, it.cy, w, 0.40)
        blade = self._lit(COL["blade"], it.cx, it.cy, w, 0.48)
        core = self._lit(COL["blade_core"], it.cx, it.cy, w, 0.60)
        hilt = self._lit(COL["key"], it.cx, it.cy, w, 0.42)
        r = 11 + pulse
        self.cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill="", outline=edge, width=2)
        self.cv.create_line(cx - 5, cy + 8, cx + 7, cy - 9, fill=blade, width=6)
        self.cv.create_line(cx - 3, cy + 7, cx + 8, cy - 8, fill=core, width=2)
        self.cv.create_line(cx - 8, cy + 5, cx - 1, cy + 12, fill=hilt, width=4)
        self.cv.create_rectangle(cx - 11, cy + 10, cx - 4, cy + 15, fill=hilt, outline="")

    def _shuriken_item(self, it: Item, sx: float, sy: float, pulse: float, w: World) -> None:
        cx = sx + it.w / 2
        cy = sy + it.h / 2
        edge = self._lit(COL["shuriken_edge"], it.cx, it.cy, w, 0.45)
        core = self._lit(COL["shuriken"], it.cx, it.cy, w, 0.55)
        r = 10 + pulse
        pts = []
        for i in range(8):
            a = -math.pi / 2 + i * math.pi / 4
            rr = r if i % 2 == 0 else 4
            pts.extend([cx + math.cos(a) * rr, cy + math.sin(a) * rr])
        self.cv.create_polygon(*pts, fill=edge, outline="")
        self.cv.create_oval(cx - 4, cy - 4, cx + 4, cy + 4, fill=core, outline=COL["dark"])

    def _gun_item(self, it: Item, sx: float, sy: float, pulse: float, w: World) -> None:
        cx = sx + it.w / 2
        cy = sy + it.h / 2
        edge = self._lit(COL["gun_edge"], it.cx, it.cy, w, 0.44)
        body = self._lit(COL["gun"], it.cx, it.cy, w, 0.52)
        core = self._lit(COL["spark_core"], it.cx, it.cy, w, 0.58)
        r = 10 + pulse
        self.cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill="", outline=edge, width=2)
        self.cv.create_rectangle(cx - 8, cy - 5, cx + 7, cy + 2, fill=body, outline=edge)
        self.cv.create_rectangle(cx + 6, cy - 4, cx + 13, cy - 1, fill=core, outline="")
        self.cv.create_polygon(cx - 4, cy + 1, cx + 3, cy + 1, cx + 0, cy + 10, cx - 6, cy + 10, fill=edge, outline="")

    def _boost_item(self, it: Item, sx: float, sy: float, pulse: float, w: World) -> None:
        cx = sx + it.w / 2
        cy = sy + it.h / 2
        if it.kind == "heal":
            col = self._lit(COL["heal"], it.cx, it.cy, w, 0.46)
            core = self._lit(COL["heal_core"], it.cx, it.cy, w, 0.58)
            r = 10 + pulse
            self.cv.create_oval(cx - r, cy - r, cx + r, cy + r, fill=col, outline=core, width=1)
            self.cv.create_rectangle(cx - 2, cy - 7, cx + 2, cy + 7, fill=core, outline="")
            self.cv.create_rectangle(cx - 7, cy - 2, cx + 7, cy + 2, fill=core, outline="")
        else:
            col = self._lit(COL["armor"], it.cx, it.cy, w, 0.46)
            core = self._lit(COL["armor_core"], it.cx, it.cy, w, 0.58)
            r = 10 + pulse
            self.cv.create_polygon(cx, cy - r, cx + r, cy - 4, cx + 7, cy + r, cx, cy + r + 4, cx - 7, cy + r, cx - r, cy - 4, fill=col, outline=core, width=1)
            self.cv.create_line(cx, cy - 5, cx, cy + 10, fill=core, width=2)

    def _shots(self, w: World) -> None:
        for b in w.shots:
            if not b.alive or not self.cam.visible(b.cx, b.cy):
                continue
            sx, sy = self.cam.apply(b.x, b.y)
            col = self._lit(COL["bolt"], b.cx, b.cy, w, 0.52)
            core = self._lit(COL["xp_core"], b.cx, b.cy, w, 0.66)
            cx = sx + b.w / 2
            cy = sy + b.h / 2
            self.cv.create_line(cx - 7, cy, cx + 7, cy, fill=col, width=2)
            self.cv.create_line(cx, cy - 7, cx, cy + 7, fill=core, width=2)
            self.cv.create_oval(cx - 3, cy - 3, cx + 3, cy + 3, fill=core, outline=col)

    def _player(self, w: World) -> None:
        p = w.player
        sx, sy = self.cam.apply(p.view_x, p.view_y)
        moving = abs(p.vx) + abs(p.vy) > 6
        bob = math.sin(p.anim_t * 18.0) * 1.2 if moving else math.sin(p.anim_t * 6.0) * 0.4
        y0 = sy - bob

        body = self._lit(COL["player_hurt"] if p.hurt_t > 0 else COL["player_body"], p.cx, p.cy, w, 0.48)
        coat = self._lit(COL["player_body2"], p.cx, p.cy, w, 0.42)
        face = self._lit(COL["player_face"], p.cx, p.cy, w, 0.56)
        eye = self._lit(COL["player_eye"], p.cx, p.cy, w, 0.62)
        scarf = self._lit(COL["player_scarf"], p.cx, p.cy, w, 0.55)
        boot = self._lit(COL["player_boot"], p.cx, p.cy, w, 0.36)
        glow = self._lit(COL["spark_glow"], p.cx, p.cy, w, 0.30)

        x0 = sx
        self.cv.create_oval(x0 - 4, y0 + p.h - 4, x0 + p.w + 4, y0 + p.h + 5, fill=self._lit(COL["dark"], p.cx, p.cy, w, 0.32), outline="")
        self.cv.create_polygon(
            x0 + 3, y0 + 11,
            x0 + p.w - 3, y0 + 11,
            x0 + p.w + 1, y0 + p.h - 2,
            x0 + p.w / 2, y0 + p.h + 3,
            x0 - 1, y0 + p.h - 2,
            fill=coat,
            outline=body,
        )
        self.cv.create_oval(x0 + 1, y0 + 1, x0 + p.w - 1, y0 + 17, fill=body, outline="")
        self.cv.create_oval(x0 + 5, y0 + 5, x0 + p.w - 5, y0 + 15, fill=face, outline="")
        eye_shift = 1 if p.face_x > 0.15 else -1 if p.face_x < -0.15 else 0
        self.cv.create_oval(x0 + 8 + eye_shift, y0 + 8, x0 + 10 + eye_shift, y0 + 10, fill=eye, outline="")
        self.cv.create_oval(x0 + 13 + eye_shift, y0 + 8, x0 + 15 + eye_shift, y0 + 10, fill=eye, outline="")
        self.cv.create_line(x0 + 5, y0 + 15, x0 + p.w - 5, y0 + 15, fill=scarf, width=3)
        self.cv.create_oval(x0 + 9, y0 + 15, x0 + 14, y0 + 20, fill=glow, outline=COL["spark_core"])
        foot = 1 if p.anim_i % 2 else 0
        self.cv.create_line(x0 + 6, y0 + p.h, x0 + 3 + foot, y0 + p.h + 3, fill=boot, width=3)
        self.cv.create_line(x0 + p.w - 6, y0 + p.h, x0 + p.w - 3 - foot, y0 + p.h + 3, fill=boot, width=3)
        if p.armor > 0:
            self.cv.create_oval(x0 - 4, y0 - 4, x0 + p.w + 4, y0 + p.h + 5, outline=self._lit(COL["armor_bar"], p.cx, p.cy, w, 0.52), width=2)
        if p.rage_t > 0:
            self.cv.create_oval(x0 - 7, y0 - 7, x0 + p.w + 7, y0 + p.h + 8, outline=self._lit(COL["alert"], p.cx, p.cy, w, 0.58), width=2)
        self._player_weapon(w, sx, y0)
        if p.atk_t > 0:
            self._atk_fx(w)

    def _player_weapon(self, w: World, sx: float, sy: float) -> None:
        p = w.player
        if not p.wp or p.inv.get(p.wp, 0) <= 0:
            return
        bx = sx + p.w - 1
        by = sy + 3
        if p.wp == "blade":
            self.cv.create_line(bx, by + 12, bx + 12, by, fill=COL["blade"], width=3)
            self.cv.create_line(bx + 2, by + 10, bx + 12, by, fill=COL["blade_core"], width=1)
        elif p.wp == "shuriken":
            self.cv.create_polygon(bx + 6, by, bx + 9, by + 6, bx + 6, by + 12, bx + 3, by + 6, fill=COL["shuriken"], outline=COL["shuriken_edge"])
        else:
            self.cv.create_rectangle(bx + 1, by + 4, bx + 13, by + 8, fill=COL["gun"], outline=COL["gun_edge"])
            self.cv.create_line(bx + 12, by + 6, bx + 18, by + 6, fill=COL["spark_core"], width=2)

    def _atk_fx(self, w: World) -> None:
        p = w.player
        cx, cy = self.cam.apply(p.view_x + p.w / 2, p.view_y + p.h / 2)
        k = max(0.0, min(1.0, p.atk_t / BLADE_COOLDOWN))
        kind = p.atk_wp or p.wp or "blade"
        if kind == "blade":
            r = WEAPON_RANGE["blade"] * (0.42 + (1.0 - k) * 0.23)
            col = self._lit(COL["slash"], p.cx, p.cy, w, 0.62)
            edge = self._lit(COL["blade_edge"], p.cx, p.cy, w, 0.50)
            self.cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline=edge, width=2)
            self.cv.create_line(cx - r * 0.65, cy, cx + r * 0.65, cy, fill=col, width=2)
            self.cv.create_line(cx, cy - r * 0.65, cx, cy + r * 0.65, fill=col, width=2)
            return

        tx, ty = self.cam.apply(p.atk_x, p.atk_y)
        if kind == "shuriken":
            col = self._lit(COL["shuriken"], p.cx, p.cy, w, 0.58)
            edge = self._lit(COL["shuriken_edge"], p.cx, p.cy, w, 0.45)
            self.cv.create_line(cx, cy, tx, ty, fill=edge, width=2)
            self.cv.create_polygon(tx, ty - 9, tx + 4, ty - 3, tx + 9, ty, tx + 4, ty + 3, tx, ty + 9, tx - 4, ty + 3, tx - 9, ty, tx - 4, ty - 3, fill=col, outline="")
        else:
            col = self._lit(COL["gun"], p.cx, p.cy, w, 0.58)
            core = self._lit(COL["spark_core"], p.cx, p.cy, w, 0.70)
            self.cv.create_line(cx, cy, tx, ty, fill=col, width=4)
            self.cv.create_line(cx, cy, tx, ty, fill=core, width=1)
            self.cv.create_oval(tx - 5, ty - 5, tx + 5, ty + 5, fill=core, outline=col)

    def _enemies(self, w: World) -> None:
        col_map = {
            EnemyState.PATROL: COL["enemy_patrol"],
            EnemyState.CHASE: COL["enemy_chase"],
            EnemyState.ATTACK: COL["enemy_attack"],
        }
        for e in w.enemies:
            if not e.alive or not self.cam.visible(e.cx, e.cy):
                continue
            sx, sy = self.cam.apply(e.view_x, e.view_y)
            self._enemy_sprite(e, sx, sy, col_map[e.state], w)

    def _enemy_sprite(self, e, sx: float, sy: float, state_col: str, w: World) -> None:
        if getattr(e, "kind", "guard") == "shooter":
            self._shooter_sprite(e, sx, sy, state_col, w)
            return
        if getattr(e, "kind", "guard") == "tank":
            self._tank_sprite(e, sx, sy, state_col, w)
            return
        bob = 1 if e.anim_i % 2 else 0
        body = self._lit(COL["enemy_body"], e.cx, e.cy, w, SPRITE_MIN)
        body2 = self._lit(COL["enemy_body2"], e.cx, e.cy, w, SPRITE_MIN + 0.04)
        edge = self._lit(state_col, e.cx, e.cy, w, SPRITE_MIN + 0.08)
        eye = self._lit(COL["enemy_eye"], e.cx, e.cy, w, 0.55)
        dark = self._lit(COL["dark"], e.cx, e.cy, w, 0.35)
        x0 = sx
        y0 = sy - bob
        self.cv.create_oval(x0 - 3, y0 + e.h - 5, x0 + e.w + 3, y0 + e.h + 5, fill=dark, outline="")
        self.cv.create_polygon(
            x0 + 2, y0 + 8,
            x0 + e.w - 2, y0 + 8,
            x0 + e.w + 2, y0 + e.h + 3,
            x0 + e.w / 2, y0 + e.h - 1,
            x0 - 2, y0 + e.h + 3,
            fill=body,
            outline=edge,
        )
        self.cv.create_oval(x0 + 3, y0 + 1, x0 + e.w - 3, y0 + e.h - 4, fill=body2, outline=edge, width=2)
        self.cv.create_polygon(x0 + 4, y0 + 5, x0 + 7, y0 - 3, x0 + 11, y0 + 4, fill=edge, outline="")
        self.cv.create_polygon(x0 + e.w - 4, y0 + 5, x0 + e.w - 7, y0 - 3, x0 + e.w - 11, y0 + 4, fill=edge, outline="")
        if e.state is EnemyState.ATTACK:
            self.cv.create_line(x0 + 7, y0 + 10, x0 + 10, y0 + 8, fill=eye, width=2)
            self.cv.create_line(x0 + e.w - 7, y0 + 10, x0 + e.w - 10, y0 + 8, fill=eye, width=2)
        else:
            self.cv.create_oval(x0 + 6, y0 + 8, x0 + 10, y0 + 12, fill=eye, outline="")
            self.cv.create_oval(x0 + e.w - 10, y0 + 8, x0 + e.w - 6, y0 + 12, fill=eye, outline="")
        self.cv.create_line(x0 + 7, y0 + 16, x0 + e.w - 7, y0 + 16, fill=dark, width=2)
        self.cv.create_line(x0 + 4, y0 + e.h + 1, x0 + 8, y0 + e.h + 4, fill=edge, width=2)
        self.cv.create_line(x0 + e.w - 4, y0 + e.h + 1, x0 + e.w - 8, y0 + e.h + 4, fill=edge, width=2)
        self._enemy_hp(e, x0, y0)

    def _shooter_sprite(self, e, sx: float, sy: float, state_col: str, w: World) -> None:
        bob = 1 if e.anim_i % 2 else 0
        x0 = sx
        y0 = sy - bob
        cloak = self._lit(COL["enemy_shooter2"], e.cx, e.cy, w, SPRITE_MIN)
        edge = self._lit(COL["enemy_shooter"], e.cx, e.cy, w, SPRITE_MIN + 0.10)
        eye = self._lit(COL["bolt"], e.cx, e.cy, w, 0.58)
        dark = self._lit(COL["dark"], e.cx, e.cy, w, 0.35)
        self.cv.create_oval(x0 - 2, y0 + e.h - 4, x0 + e.w + 2, y0 + e.h + 4, fill=dark, outline="")
        self.cv.create_polygon(x0 + 2, y0 + 5, x0 + e.w / 2, y0 - 3, x0 + e.w - 2, y0 + 5, x0 + e.w - 1, y0 + e.h, x0 + 1, y0 + e.h, fill=cloak, outline=edge)
        self.cv.create_oval(x0 + 5, y0 + 6, x0 + e.w - 5, y0 + 15, fill=dark, outline=edge, width=1)
        self.cv.create_line(x0 + 7, y0 + 10, x0 + e.w - 7, y0 + 10, fill=eye, width=2)
        self.cv.create_line(x0 - 4, y0 + 14, x0 + e.w + 7, y0 + 8, fill=edge, width=3)
        self.cv.create_oval(x0 + e.w + 4, y0 + 5, x0 + e.w + 10, y0 + 11, fill=eye, outline="")
        self.cv.create_line(x0 + 5, y0 + e.h, x0 + 1, y0 + e.h + 3, fill=edge, width=2)
        self.cv.create_line(x0 + e.w - 5, y0 + e.h, x0 + e.w - 1, y0 + e.h + 3, fill=edge, width=2)
        self._enemy_hp(e, x0, y0)

    def _tank_sprite(self, e, sx: float, sy: float, state_col: str, w: World) -> None:
        bob = 0.5 if e.anim_i % 2 else 0
        x0 = sx
        y0 = sy - bob
        body = self._lit(COL["enemy_tank2"], e.cx, e.cy, w, SPRITE_MIN)
        armor = self._lit(COL["enemy_tank"], e.cx, e.cy, w, SPRITE_MIN + 0.08)
        edge = self._lit(state_col, e.cx, e.cy, w, SPRITE_MIN + 0.10)
        eye = self._lit(COL["enemy_eye"], e.cx, e.cy, w, 0.56)
        dark = self._lit(COL["dark"], e.cx, e.cy, w, 0.35)
        self.cv.create_oval(x0 - 4, y0 + e.h - 5, x0 + e.w + 4, y0 + e.h + 5, fill=dark, outline="")
        self.cv.create_rectangle(x0 + 2, y0 + 7, x0 + e.w - 2, y0 + e.h + 1, fill=body, outline=edge, width=2)
        self.cv.create_polygon(x0 + 4, y0 + 6, x0 + e.w / 2, y0 - 3, x0 + e.w - 4, y0 + 6, x0 + e.w - 1, y0 + 18, x0 + 1, y0 + 18, fill=armor, outline=edge)
        self.cv.create_rectangle(x0 + 7, y0 + 9, x0 + e.w - 7, y0 + 14, fill=dark, outline="")
        self.cv.create_oval(x0 + 9, y0 + 10, x0 + 12, y0 + 13, fill=eye, outline="")
        self.cv.create_oval(x0 + e.w - 12, y0 + 10, x0 + e.w - 9, y0 + 13, fill=eye, outline="")
        self.cv.create_line(x0 + 4, y0 + 20, x0 + e.w - 4, y0 + 20, fill=armor, width=3)
        self.cv.create_line(x0 + 5, y0 + e.h + 1, x0 + 2, y0 + e.h + 5, fill=edge, width=3)
        self.cv.create_line(x0 + e.w - 5, y0 + e.h + 1, x0 + e.w - 2, y0 + e.h + 5, fill=edge, width=3)
        self._enemy_hp(e, x0, y0)

    def _enemy_hp(self, e, x0: float, y0: float) -> None:
        if e.hp >= e.max_hp or e.max_hp <= 0:
            return
        ww = max(16, e.w)
        k = max(0.0, min(1.0, e.hp / e.max_hp))
        self.cv.create_rectangle(x0, y0 - 8, x0 + ww, y0 - 5, fill=COL["hp_bg"], outline="")
        self.cv.create_rectangle(x0, y0 - 8, x0 + ww * k, y0 - 5, fill=COL["hp"], outline="")

    def _parts(self, w: World) -> None:
        for p in w.parts.items:
            if not p.alive or not self.cam.visible(p.x, p.y):
                continue
            sx, sy = self.cam.apply(p.x, p.y)
            col = self._part_col(p.kind)
            col = self._lit(col, p.x, p.y, w, SPRITE_MIN)
            size = max(1.0, p.size * p.left())
            if p.kind in ("spark", "blade", "shuriken", "gun") and size > 2.0:
                core = self._lit(COL["spark_core"] if p.kind in ("spark", "gun") else COL["blade_core"], p.x, p.y, w, 0.52)
                self.cv.create_line(sx - size, sy, sx + size, sy, fill=col, width=2)
                self.cv.create_line(sx, sy - size, sx, sy + size, fill=core, width=2)
                self.cv.create_oval(sx - 1.5, sy - 1.5, sx + 1.5, sy + 1.5, fill=core, outline="")
            else:
                self.cv.create_oval(sx - size, sy - size, sx + size, sy + size, fill=col, outline="")

    def _part_col(self, kind: str) -> str:
        if kind in KEY_KINDS:
            return COL[f"key_{kind}"]
        if kind in ("key_red", "key_blue", "key_green"):
            return COL[kind]
        return {
            "hurt": COL["enemy_attack"],
            "win": COL["exit"],
            "xp": COL["xp"],
            "dash": COL["blade_edge"],
            "rage": COL["alert"],
            "alert": COL["alert"],
            "bolt": COL["bolt"],
            "blade": COL["blade"],
            "shuriken": COL["shuriken"],
            "gun": COL["gun"],
            "heal": COL["heal"],
            "armor": COL["armor"],
        }.get(kind, COL["spark"])

    def _hud(self, w: World) -> None:
        p = w.player
        self.cv.create_rectangle(14, 14, 222, 40, fill=COL["hp_bg"], outline="")
        max_hp = max(1, p.max_hp)
        hp_w = 200 * max(0, p.hp) / max_hp
        self.cv.create_rectangle(18, 18, 18 + hp_w, 36, fill=COL["hp"], outline="")
        self.cv.create_text(120, 27, text=f"HP {max(0, p.hp)}/{max_hp}", fill=COL["ui"], font=("Arial", 11, "bold"))

        self.cv.create_rectangle(14, 44, 222, 62, fill=COL["armor_bg"], outline="")
        ar_w = 200 * max(0, p.armor) / ARMOR_MAX
        self.cv.create_rectangle(18, 47, 18 + ar_w, 59, fill=COL["armor_bar"], outline="")
        self.cv.create_text(120, 53, text=f"Броня {max(0, p.armor)}/{ARMOR_MAX}", fill=COL["ui"], font=("Arial", 9, "bold"))

        wp = "нет"
        if p.wp and p.inv.get(p.wp, 0) > 0:
            if p.wp == "gun":
                wp = f"{WEAPON_NAMES[p.wp]} {p.inv[p.wp]}/{GUN_MAX}, -1 искра"
            else:
                wp = f"{WEAPON_NAMES[p.wp]} x{p.inv[p.wp]}"
        txt = f"Искры {p.gems}/{SPARKS_NEEDED}   Опыт {p.xp}   Уровень {w.level_no}/{MAX_LEVEL}   Оружие: {wp}   Seed: {w.lvl.seed}"
        self.cv.create_text(20, 78, text=txt, fill=COL["ui"], anchor="w", font=("Arial", 11))
        self.cv.create_text(20, 100, text="Ключи:", fill=COL["ui"], anchor="w", font=("Arial", 10, "bold"))
        x = 75
        for key in KEY_KINDS:
            got = key in p.keys
            col = COL[f"key_{key}"] if got else COL["exit_lock"]
            self.cv.create_oval(x, 92, x + 14, 106, fill=col if got else "", outline=col, width=2)
            x += 22

        cd_txt = []
        if p.skills.get("dash", 0) > 0:
            cd_txt.append(f"Shift рывок {p.dash_cd:.1f}" if p.dash_cd > 0 else "Shift рывок готов")
        if p.skills.get("rage", 0) > 0:
            if p.rage_t > 0:
                cd_txt.append(f"Ярость {p.rage_t:.1f}с")
            elif p.rage_cd > 0:
                cd_txt.append(f"F ярость {p.rage_cd:.1f}")
            else:
                cd_txt.append("F ярость готова")
        if cd_txt:
            self.cv.create_text(20, 122, text="   ".join(cd_txt), fill=COL["spark"], anchor="w", font=("Arial", 10, "bold"))
        if w.alert:
            self.cv.create_text(SCREEN_W - 20, 52, text="ТРЕВОГА: свет сузился, врагов больше", fill=COL["alert"], anchor="e", font=("Arial", 11, "bold"))

        self.cv.create_text(20, SCREEN_H - 22, text="WASD/стрелки — движение   I/Tab/G — инвентарь   Space/E — автоатака   Shift/F — умения   Q — смена оружия   F1 — отладка", fill=COL["muted"], anchor="w", font=("Arial", 10))
        if w.msg_t > 0 and w.msg:
            self.cv.create_text(SCREEN_W / 2, 56, text=w.msg, fill=COL["spark"], font=("Arial", 14, "bold"))

    def _inventory(self, w: World) -> None:
        p = w.player
        self.cv.create_rectangle(0, 0, SCREEN_W, SCREEN_H, fill="#000000", stipple="gray50", outline="")
        x0, y0 = 92, 58
        x1, y1 = SCREEN_W - 92, SCREEN_H - 58
        self.cv.create_rectangle(x0, y0, x1, y1, fill=COL["panel"], outline=COL["wall_hi"], width=2)
        self.cv.create_rectangle(x0 + 10, y0 + 10, x1 - 10, y0 + 52, fill=COL["panel2"], outline="")
        self.cv.create_text(x0 + 24, y0 + 31, text="ИНВЕНТАРЬ И УМЕНИЯ", fill=COL["spark"], anchor="w", font=("Arial", 18, "bold"))
        self.cv.create_text(x1 - 24, y0 + 31, text=f"XP: {p.xp}", fill=COL["xp_core"], anchor="e", font=("Arial", 16, "bold"))

        left_x = x0 + 28
        right_x = x0 + 408
        top = y0 + 82
        self.cv.create_text(left_x, top, text="Оружие — выбрать активное", fill=COL["ui"], anchor="w", font=("Arial", 14, "bold"))
        self.cv.create_text(right_x, top, text="Умения — купить за опыт", fill=COL["ui"], anchor="w", font=("Arial", 14, "bold"))

        desc = {
            "blade": "автоудар рядом; удобно добивать танков",
            "shuriken": "один бросок по ближайшей видимой цели",
            "gun": "дальность; тратит искры, максимум 3 выстрела",
        }
        for i, kind in enumerate(WEAPON_KINDS, start=1):
            y = top + 34 + (i - 1) * 70
            cnt = p.inv.get(kind, 0)
            active = p.wp == kind and cnt > 0
            border = COL[kind] if active else COL["wall_edge"]
            bg = COL["panel2"] if cnt > 0 else COL["bg"]
            self.cv.create_rectangle(left_x, y, left_x + 340, y + 54, fill=bg, outline=border, width=2 if active else 1)
            self.cv.create_text(left_x + 14, y + 15, text=f"{i}. {WEAPON_NAMES[kind]}", fill=COL[kind], anchor="w", font=("Arial", 12, "bold"))
            mark = "активно" if active else ("есть" if cnt > 0 else "нет")
            self.cv.create_text(left_x + 326, y + 15, text=f"{mark}  x{cnt}", fill=COL["ui"] if cnt > 0 else COL["muted"], anchor="e", font=("Arial", 10, "bold"))
            stat = f"урон {WEAPON_DMG[kind]}   радиус {int(WEAPON_RANGE[kind])}"
            if kind == "gun":
                stat += f"   заряд {cnt}/{GUN_MAX}"
            self.cv.create_text(left_x + 14, y + 32, text=stat, fill=COL["muted"], anchor="w", font=("Arial", 9))
            self.cv.create_text(left_x + 14, y + 46, text=desc[kind], fill=COL["muted"], anchor="w", font=("Arial", 9))

        for n, key in enumerate(SKILL_KINDS, start=4):
            lvl = p.skills.get(key, 0)
            mx = SKILL_MAX[key]
            cost = SKILL_COST[key] + lvl
            can = lvl < mx and p.xp >= cost
            y = top + 34 + (n - 4) * 54
            outline = COL["exit"] if can else COL["wall_edge"]
            self.cv.create_rectangle(right_x, y, x1 - 28, y + 42, fill=COL["panel2"], outline=outline)
            self.cv.create_text(right_x + 12, y + 13, text=f"{n}. {SKILL_NAMES[key]}", fill=COL["spark"] if can else COL["ui"], anchor="w", font=("Arial", 11, "bold"))
            state = "MAX" if lvl >= mx else f"цена {cost} XP"
            self.cv.create_text(x1 - 42, y + 13, text=f"{lvl}/{mx}   {state}", fill=COL["xp_core"] if can else COL["muted"], anchor="e", font=("Arial", 10, "bold"))
            self.cv.create_text(right_x + 12, y + 30, text=SKILL_DESC[key], fill=COL["muted"], anchor="w", font=("Arial", 9))

        hint = "1–3 — выбрать оружие    4–9 — улучшить умение    Shift — рывок    F — ярость    G/I/Tab/Esc — закрыть"
        self.cv.create_text(SCREEN_W / 2, y1 - 28, text=hint, fill=COL["muted"], font=("Arial", 10, "bold"))

    def _debug(self, w: World) -> None:
        self.cv.create_text(SCREEN_W - 20, 18, text=f"FPS {w.fps():.0f}", fill=COL["debug"], anchor="e", font=("Consolas", 11, "bold"))
        p = w.player
        sx, sy = self.cam.apply(p.x, p.y)
        self.cv.create_rectangle(sx, sy, sx + p.w, sy + p.h, outline=COL["hit"], width=2)
        rng = WEAPON_RANGE.get(p.wp, 0.0)
        if rng > 0:
            cx, cy = self.cam.apply(p.cx, p.cy)
            self.cv.create_oval(cx - rng, cy - rng, cx + rng, cy + rng, outline=COL["blade_edge"])
        for e in w.enemies:
            if not self.cam.visible(e.cx, e.cy):
                continue
            sx, sy = self.cam.apply(e.x, e.y)
            self.cv.create_rectangle(sx, sy, sx + e.w, sy + e.h, outline=COL["hit"], width=2)
            self.cv.create_text(sx + e.w / 2, sy - 10, text=e.state.name, fill=COL["debug"], font=("Consolas", 8))
            r = ENEMY_SEE
            cx, cy = self.cam.apply(e.cx, e.cy)
            self.cv.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#34424b")
            if len(e.path) > 1:
                pts = []
                for c, r0 in e.path[:18]:
                    x, y = self.cam.apply(c * TILE + TILE / 2, r0 * TILE + TILE / 2)
                    pts.extend([x, y])
                if len(pts) >= 4:
                    self.cv.create_line(*pts, fill=COL["path"], width=2)

    def _menu(self, w: World) -> None:
        self.cv.create_rectangle(0, 0, SCREEN_W, SCREEN_H, fill=COL["bg"], outline="")
        self.cv.create_text(SCREEN_W / 2, 160, text="ЛАБИРИНТ ИСКР", fill=COL["spark"], font=("Arial", 38, "bold"))
        self.cv.create_text(SCREEN_W / 2, 225, text="Пройди 10 уровней: собирай искры, три цветных ключа и ищи портал", fill=COL["ui"], font=("Arial", 15))
        self.cv.create_text(SCREEN_W / 2, 286, text="Enter — старт", fill=COL["exit"], font=("Arial", 18, "bold"))
        self.cv.create_text(SCREEN_W / 2, 330, text="WASD/стрелки — движение    Space/E — автоатака    G/I/Tab — инвентарь    F1 — отладка", fill=COL["muted"], font=("Arial", 12))
        self.cv.create_text(SCREEN_W / 2, 370, text="Оружие, опыт и умения: 1–3 выбирают оружие, 4–9 прокачивают героя.", fill=COL["muted"], font=("Arial", 12))
        self.cv.create_text(SCREEN_W / 2, 410, text="После открытия портала включается тревога: света меньше, врагов больше.", fill=COL["muted"], font=("Arial", 12))

    def _overlay(self, title: str, sub: str) -> None:
        self.cv.create_rectangle(0, 0, SCREEN_W, SCREEN_H, fill="", outline="")
        self.cv.create_rectangle(250, 210, SCREEN_W - 250, 385, fill=COL["bg"], outline=COL["muted"], width=2)
        self.cv.create_text(SCREEN_W / 2, 270, text=title, fill=COL["spark"], font=("Arial", 32, "bold"))
        self.cv.create_text(SCREEN_W / 2, 330, text=sub, fill=COL["ui"], font=("Arial", 13))

    def _lit(self, base: str, x: float, y: float, w: World, min_l: float = LIGHT_MIN) -> str:
        rad = ALERT_LIGHT_R if getattr(w, "alert", False) else LIGHT_R
        d = dist(x, y, w.player.cx, w.player.cy)
        light = clamp(1.0 - (d / rad) ** 1.25, min_l, 1.0)
        return _mix(COL["dark"], base, light)


def _item_col(it: Item) -> str:
    if it.kind == "spark":
        return COL["spark"]
    if it.kind == "xp":
        return COL["xp"]
    if it.kind in KEY_KINDS or it.kind.startswith("key_"):
        key = it.kind.split("_", 1)[1] if it.kind.startswith("key_") else it.kind
        return COL.get(f"key_{key}", COL["key"])
    if it.kind in WEAPON_KINDS:
        return COL[it.kind]
    if it.kind in ("heal", "armor"):
        return COL[it.kind]
    return COL["exit"]


def _mix(a: str, b: str, t: float) -> str:
    ar, ag, ab = _rgb(a)
    br, bg, bb = _rgb(b)
    r = int(ar + (br - ar) * t)
    g = int(ag + (bg - ag) * t)
    bl = int(ab + (bb - ab) * t)
    return f"#{r:02x}{g:02x}{bl:02x}"


def _rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
