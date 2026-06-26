import math
from typing import Protocol

from .alg import aabb, astar, los
from .cfg import (
    ARMOR_ADD,
    BLADE_COOLDOWN,
    BOLT_SIZE,
    BOLT_SPEED,
    CHASE_MUL,
    DASH_CD,
    DASH_SPEED,
    DASH_TIME,
    ENEMY_ATTACK,
    ENEMY_COOLDOWN,
    ENEMY_LOSE,
    ENEMY_SEE,
    HEAL_AMOUNT,
    KEY_KINDS,
    KEY_NAMES,
    MAGNET_RANGE,
    ARMOR_MAX,
    MAX_LEVEL,
    PATH_DELAY,
    PLAYER_ACCEL,
    PLAYER_DECEL,
    PLAYER_HP,
    PLAYER_SPEED,
    RAGE_CD,
    RAGE_DMG_MUL,
    RAGE_SPEED_MUL,
    RAGE_TIME,
    SHOT_CD,
    SHOT_MIN,
    SHOT_RANGE,
    SKILL_COST,
    SKILL_KINDS,
    SKILL_MAX,
    SKILL_NAMES,
    SPARKS_NEEDED,
    GUN_COST,
    GUN_MAX,
    TILE,
    WEAPON_AMMO,
    WEAPON_DMG,
    WEAPON_KINDS,
    WEAPON_NAMES,
    WEAPON_RANGE,
    WEAPON_RESPAWN,
    XP_PICKUP_RANGE,
)
from .entities import Actor, EnemyState, Enemy, GameState, Player, Shot
from .vec import dist, dist_sq
from .world import World, count_weapons, spawn_wave, spawn_blade, spawn_spark, spawn_weapon, spawn_xp


class InputLike(Protocol):
    def down(self, *names: str) -> bool: ...
    def take(self, *names: str) -> bool: ...


def input_sys(w: World, inp: InputLike, dt: float) -> None:
    p = w.player
    _tick_player(p, dt)

    if inp.take("shift", "shift_l", "shift_r"):
        use_dash(w)
    if inp.take("f"):
        use_rage(w)

    dx = float(inp.down("d", "right")) - float(inp.down("a", "left"))
    dy = float(inp.down("s", "down")) - float(inp.down("w", "up"))
    ln = math.hypot(dx, dy)
    if ln > 0:
        dx /= ln
        dy /= ln
        p.face_x = dx
        p.face_y = dy

    p.speed = player_speed(p)
    if p.dash_t > 0:
        p.vx = p.dash_x * DASH_SPEED
        p.vy = p.dash_y * DASH_SPEED
    else:
        tx = dx * p.speed
        ty = dy * p.speed
        k = min(1.0, (PLAYER_ACCEL if ln > 0 else PLAYER_DECEL) * dt)
        p.vx += (tx - p.vx) * k
        p.vy += (ty - p.vy) * k
        if ln <= 0 and abs(p.vx) + abs(p.vy) < 1.0:
            p.stop()

    if inp.take("q"):
        switch_weapon(w)
    if inp.take("space", "e"):
        use_weapon(w)


def enemy_sys(w: World, dt: float) -> None:
    p = w.player
    if not p.alive:
        for e in w.enemies:
            e.stop()
        return

    for e in w.enemies:
        if not e.alive:
            continue
        e.path_t -= dt
        e.atk_t -= dt
        if e.kind == "shooter":
            _shooter_ai(e, w, dt)
        else:
            _melee_ai(e, w, dt)


def _melee_ai(e: Enemy, w: World, dt: float) -> None:
    p = w.player
    d2 = dist_sq(e.cx, e.cy, p.cx, p.cy)
    sees = d2 <= ENEMY_SEE * ENEMY_SEE and los(w.lvl, e.cx, e.cy, p.cx, p.cy)

    if e.state is EnemyState.PATROL:
        if sees or w.alert:
            e.state = EnemyState.CHASE
            e.lost_t = 0.0
            e.path_t = 0.0
            if w.msg_t <= 0:
                w.bus.emit("note", "Страж заметил тебя", 1.2)
        else:
            _patrol(e, w, dt)
            return

    if e.state is EnemyState.CHASE:
        if d2 <= ENEMY_ATTACK * ENEMY_ATTACK:
            e.state = EnemyState.ATTACK
            e.stop()
        else:
            if sees or w.alert:
                e.lost_t = 0.0
            elif d2 > ENEMY_LOSE * ENEMY_LOSE:
                e.lost_t += dt * 1.5
            else:
                e.lost_t += dt

            if e.lost_t > 1.5:
                e.state = EnemyState.PATROL
                e.path.clear()
                e.stop()
            else:
                _chase(e, w, dt)

    if e.state is EnemyState.ATTACK:
        d = dist(e.cx, e.cy, p.cx, p.cy)
        if d > ENEMY_ATTACK * 1.55:
            e.state = EnemyState.CHASE
            e.path_t = 0.0
        else:
            e.stop()
            if e.atk_t <= 0:
                e.atk_t = ENEMY_COOLDOWN * (1.15 if e.kind == "tank" else 1.0)
                hit_player(w, e.dmg)


def _shooter_ai(e: Enemy, w: World, dt: float) -> None:
    p = w.player
    d = dist(e.cx, e.cy, p.cx, p.cy)
    sees = d <= SHOT_RANGE and los(w.lvl, e.cx, e.cy, p.cx, p.cy)

    if e.state is EnemyState.PATROL:
        if sees or w.alert:
            e.state = EnemyState.CHASE
            e.lost_t = 0.0
            e.path_t = 0.0
            if w.msg_t <= 0:
                w.bus.emit("note", "Стрелок заметил тебя", 1.1)
        else:
            _patrol(e, w, dt)
            return

    if e.state in (EnemyState.CHASE, EnemyState.ATTACK):
        if sees:
            e.lost_t = 0.0
            if d < SHOT_MIN:
                e.state = EnemyState.CHASE
                _move_away(e, p.cx, p.cy, 0.90)
            elif d <= SHOT_RANGE:
                e.state = EnemyState.ATTACK
                e.stop()
                if e.atk_t <= 0:
                    _fire_bolt(w, e)
                    e.atk_t = SHOT_CD
            else:
                e.state = EnemyState.CHASE
                _chase(e, w, dt)
        else:
            e.lost_t += dt
            if e.lost_t > 1.5:
                e.state = EnemyState.PATROL
                e.path.clear()
                e.stop()
            else:
                e.state = EnemyState.CHASE
                _chase(e, w, dt)


def move_sys(w: World, dt: float) -> None:
    _move_actor(w.player, w, dt)
    for e in w.enemies:
        if e.alive:
            _move_actor(e, w, dt)
    _move_shots(w, dt)


def logic_sys(w: World, dt: float) -> None:
    p = w.player
    cd = w.wp_cd
    if cd > 0:
        new_cd = max(0.0, cd - dt)
        wp = w.wp_wait
        _set_wp_cd(w, new_cd)
        if new_cd <= 0:
            spawn_weapon(w, wp if wp in WEAPON_KINDS else None)
            w.wp_wait = ""
    elif count_weapons(w) == 0 and not _has_ammo(p):
        spawn_blade(w)

    if w.msg_t > 0:
        w.msg_t = max(0.0, w.msg_t - dt)

    for it in w.items:
        if not it.alive:
            continue
        if it.kind == "exit":
            if aabb(p.rect(), it.rect()) and _try_exit(w, it):
                return
            continue

        if not _touch_item(w, it):
            continue

        if it.kind == "heal":
            if p.hp >= p.max_hp:
                if w.msg_t <= 0:
                    w.bus.emit("note", "HP уже полные", 1.0)
                continue
            it.alive = False
            p.hp = min(p.max_hp, p.hp + HEAL_AMOUNT)
            w.bus.emit("burst", it.cx, it.cy, "heal", 26)
            w.bus.emit("note", f"Аптечка: HP {p.hp}/{p.max_hp}", 1.4)
        elif it.kind == "armor":
            if p.armor >= ARMOR_MAX:
                if w.msg_t <= 0:
                    w.bus.emit("note", "Броня уже полная", 1.0)
                continue
            it.alive = False
            p.armor = min(ARMOR_MAX, p.armor + ARMOR_ADD)
            w.bus.emit("burst", it.cx, it.cy, "armor", 28)
            w.bus.emit("note", f"Броня: {p.armor}/{ARMOR_MAX}", 1.4)
        elif it.kind == "xp":
            it.alive = False
            p.xp += max(1, it.val)
            w.bus.emit("burst", it.cx, it.cy, "xp", 20)
            w.bus.emit("note", f"Опыт +{max(1, it.val)}. Открой инвентарь: I / Tab / G", 1.5)
        elif it.kind == "spark":
            it.alive = False
            p.gems += 1
            w.bus.emit("burst", it.cx, it.cy, "spark", 22)
            if p.gems >= SPARKS_NEEDED:
                w.bus.emit("note", "Искр хватает. Ищи три ключа и выход", 2.0)
            else:
                w.bus.emit("note", f"Искры: {p.gems}/{SPARKS_NEEDED}", 1.1)
        elif it.kind in KEY_KINDS or it.kind.startswith("key_"):
            it.alive = False
            key = it.kind.split("_", 1)[1] if it.kind.startswith("key_") else it.kind
            p.keys.add(key)
            p.has_key = _has_keys(p)
            w.bus.emit("burst", it.cx, it.cy, f"key_{key}", 30)
            left = _miss_keys(p)
            if left:
                txt = ", ".join(KEY_NAMES[k] for k in left)
                w.bus.emit("note", f"Нужны ещё ключи: {txt}", 1.8)
            else:
                w.bus.emit("note", "Все три ключа собраны. Ищи выход", 2.0)
        elif it.kind in WEAPON_KINDS:
            it.alive = False
            add = WEAPON_AMMO[it.kind]
            if it.kind == "gun":
                p.inv[it.kind] = min(GUN_MAX, p.inv.get(it.kind, 0) + add)
            else:
                p.inv[it.kind] = p.inv.get(it.kind, 0) + add
            p.wp = it.kind
            _sync_player(p)
            w.bus.emit("burst", it.cx, it.cy, it.kind, 26)
            if it.kind == "gun":
                w.bus.emit("note", f"Искромёт: {p.inv[it.kind]}/{GUN_MAX}. Удачный выстрел тратит 1 искру", 2.4)
            else:
                w.bus.emit("note", f"Оружие: {WEAPON_NAMES[it.kind]} x{p.inv[it.kind]}. Space/E — атака", 2.0)

    _check_alert(w)
    _sync_player(p)
    if p.hp <= 0 and p.alive:
        p.alive = False
        w.state = GameState.LOSE
        w.bus.emit("burst", p.cx, p.cy, "hurt", 55)
        w.bus.emit("note", "Ты проиграл", 3.0)


def anim_sys(w: World, dt: float) -> None:
    for act in [w.player, *w.enemies]:
        k = min(1.0, 26.0 * dt)
        act.view_x += (act.x - act.view_x) * k
        act.view_y += (act.y - act.view_y) * k

        moving = abs(act.vx) + abs(act.vy) > 1
        act.anim_t += dt
        if moving and act.anim_t >= 0.12:
            act.anim_t -= 0.12
            act.anim_i = (act.anim_i + 1) % 4
        elif not moving and act.anim_t >= 0.35:
            act.anim_t -= 0.35
            act.anim_i = (act.anim_i + 1) % 2

    key_parts = tuple(f"key_{k}" for k in KEY_KINDS)
    for it in w.items:
        if it.alive:
            it.anim_t += dt
            if it.anim_t >= 0.18:
                it.anim_t -= 0.18
                it.anim_i = (it.anim_i + 1) % 6

    for p in w.parts.items:
        if p.alive:
            grav = 80.0 if p.kind in ("spark", "heal", "xp", *KEY_KINDS, *key_parts) else 30.0
            p.update(dt, grav=grav)


def cleanup_sys(w: World) -> None:
    if len(w.shots) > 80:
        w.shots = [b for b in w.shots if b.alive]


def use_weapon(w: World) -> bool:
    p = w.player
    if p.atk_t > 0:
        return False

    kind = _pick_weapon(p)
    if not kind:
        if w.msg_t <= 0:
            w.bus.emit("note", "Найди оружие, чтобы отбиться от стража", 1.2)
        return False

    if kind == "gun" and p.gems < GUN_COST:
        if w.msg_t <= 0:
            w.bus.emit("note", "Для искромёта нужна хотя бы 1 собранная искра", 1.4)
        return False

    rng = WEAPON_RANGE[kind]
    target = _near_enemy(w, rng, need_los=(kind != "blade"))
    p.atk_t = BLADE_COOLDOWN
    p.atk_wp = kind

    if target is None:
        p.atk_x = p.cx + p.face_x * min(rng, 55.0)
        p.atk_y = p.cy + p.face_y * min(rng, 55.0)
        w.bus.emit("burst", p.atk_x, p.atk_y, kind, 8)
        if kind == "gun":
            w.bus.emit("note", "Нет видимой цели — искра не потрачена", 1.0)
        else:
            w.bus.emit("note", "Рядом нет видимого стража", 1.0)
        return False

    dx = target.cx - p.cx
    dy = target.cy - p.cy
    ln = math.hypot(dx, dy)
    if ln > 0.001:
        p.face_x = dx / ln
        p.face_y = dy / ln
    p.atk_x = target.cx
    p.atk_y = target.cy

    dmg = wp_damage(p, kind)
    target.hp -= dmg
    killed = target.hp <= 0
    if killed:
        kill_enemy(w, target, kind)
    else:
        target.state = EnemyState.CHASE
        w.bus.emit("burst", target.cx, target.cy, kind, 22)

    if kind == "gun":
        p.gems = max(0, p.gems - GUN_COST)
        spawn_spark(w)
    p.inv[kind] = max(0, p.inv.get(kind, 0) - 1)
    if p.inv[kind] <= 0:
        del p.inv[kind]
        _set_wp_cd(w, WEAPON_RESPAWN[kind], kind)

    if kind == "blade":
        w.bus.emit("burst", p.cx, p.cy, "blade", 20)
    elif kind == "shuriken":
        w.bus.emit("burst", target.cx, target.cy, "shuriken", 28)
    else:
        w.bus.emit("burst", p.cx, p.cy, "gun", 18)
        w.bus.emit("burst", target.cx, target.cy, "gun", 28)

    spent_last = kind == "gun" and p.inv.get("gun", 0) <= 0
    _auto_switch(p)
    _sync_player(p)
    if killed:
        if spent_last:
            w.bus.emit("note", "Враг уничтожен. Искромёт перегорел и появится позже", 2.0)
        elif _has_ammo(p):
            w.bus.emit("note", f"Враг уничтожен. Активно: {_wp_text(p)}", 1.6)
        else:
            w.bus.emit("note", "Враг уничтожен. Подбери выпавший опыт", 1.8)
    else:
        w.bus.emit("note", f"Попадание: -{dmg}. У врага {max(0, target.hp)}/{target.max_hp} HP", 1.4)
    return True


def use_blade(w: World) -> bool:
    return use_weapon(w)


def switch_weapon(w: World) -> bool:
    p = w.player
    kinds = [k for k in WEAPON_KINDS if p.inv.get(k, 0) > 0]
    if not kinds:
        if w.msg_t <= 0:
            w.bus.emit("note", "Нет оружия для смены", 1.0)
        return False
    if p.wp not in kinds:
        p.wp = kinds[0]
    else:
        i = (kinds.index(p.wp) + 1) % len(kinds)
        p.wp = kinds[i]
    _sync_player(p)
    w.bus.emit("note", f"Выбрано: {_wp_text(p)}", 1.1)
    return True


def choose_weapon(w: World, idx: int) -> bool:
    p = w.player
    kinds = list(WEAPON_KINDS)
    if idx < 0 or idx >= len(kinds):
        return False
    kind = kinds[idx]
    if p.inv.get(kind, 0) <= 0:
        w.bus.emit("note", f"В инвентаре нет оружия: {WEAPON_NAMES[kind]}", 1.2)
        return False
    p.wp = kind
    _sync_player(p)
    w.bus.emit("note", f"Выбрано: {_wp_text(p)}", 1.2)
    return True


def buy_skill(w: World, key: str) -> bool:
    p = w.player
    key = key if key in SKILL_KINDS else ""
    if not key:
        return False
    lvl = p.skills.get(key, 0)
    if lvl >= SKILL_MAX[key]:
        w.bus.emit("note", f"Умение уже на максимуме: {SKILL_NAMES[key]}", 1.2)
        return False
    cost = skill_cost(p, key)
    if p.xp < cost:
        w.bus.emit("note", f"Не хватает опыта: нужно {cost}, есть {p.xp}", 1.2)
        return False
    p.xp -= cost
    p.skills[key] = lvl + 1
    if key == "vit":
        p.max_hp += 15
        p.hp = min(p.max_hp, p.hp + 15)
    p.speed = player_speed(p)
    w.bus.emit("burst", p.cx, p.cy, "xp", 28)
    w.bus.emit("note", f"Улучшено: {SKILL_NAMES[key]} {p.skills[key]}/{SKILL_MAX[key]}", 1.7)
    return True


def skill_cost(p: Player, key: str) -> int:
    lvl = p.skills.get(key, 0)
    if lvl >= SKILL_MAX.get(key, 0):
        return 0
    return SKILL_COST[key] + lvl


def use_dash(w: World) -> bool:
    p = w.player
    if p.skills.get("dash", 0) <= 0:
        if w.msg_t <= 0:
            w.bus.emit("note", "Рывок нужно открыть в инвентаре", 1.0)
        return False
    if p.dash_cd > 0 or p.dash_t > 0:
        return False
    dx, dy = p.face_x, p.face_y
    ln = math.hypot(dx, dy)
    if ln < 0.001:
        dx, dy = 1.0, 0.0
    else:
        dx, dy = dx / ln, dy / ln
    p.dash_x = dx
    p.dash_y = dy
    p.dash_t = DASH_TIME
    p.dash_cd = DASH_CD
    w.bus.emit("burst", p.cx, p.cy, "dash", 22)
    return True


def use_rage(w: World) -> bool:
    p = w.player
    if p.skills.get("rage", 0) <= 0:
        if w.msg_t <= 0:
            w.bus.emit("note", "Ярость нужно открыть в инвентаре", 1.0)
        return False
    if p.rage_cd > 0 or p.rage_t > 0:
        return False
    p.rage_t = RAGE_TIME
    p.rage_cd = RAGE_CD
    w.bus.emit("burst", p.cx, p.cy, "rage", 42)
    w.bus.emit("note", "Ярость: скорость и урон повышены", 1.6)
    return True


def player_speed(p: Player) -> float:
    mul = 1.0 + 0.08 * p.skills.get("spd", 0)
    if p.rage_t > 0:
        mul *= RAGE_SPEED_MUL
    return PLAYER_SPEED * mul


def wp_damage(p: Player, kind: str) -> int:
    dmg = WEAPON_DMG.get(kind, 0)
    dmg *= 1.0 + 0.20 * p.skills.get("pow", 0)
    if p.rage_t > 0:
        dmg *= RAGE_DMG_MUL
    return max(1, int(round(dmg)))


def kill_enemy(w: World, e: Enemy, kind: str = "") -> None:
    if not e.alive:
        return
    e.alive = False
    e.stop()
    e.path.clear()
    spawn_xp(w, e.cx, e.cy, e.xp)
    w.bus.emit("burst", e.cx, e.cy, kind or e.kind, 42)


def hit_player(w: World, dmg: int) -> None:
    p = w.player
    block = min(p.armor, dmg)
    p.armor -= block
    real = dmg - block
    if real > 0:
        p.hp -= real
    p.hurt_t = 0.18

    if block > 0:
        w.bus.emit("burst", p.cx, p.cy, "armor", 14)
    if real > 0:
        w.bus.emit("burst", p.cx, p.cy, "hurt", 18)

    if block > 0 and real > 0:
        w.bus.emit("note", f"Броня -{block}, урон -{real} HP", 0.9)
    elif block > 0:
        w.bus.emit("note", f"Броня приняла удар: -{block}", 0.8)
    else:
        w.bus.emit("note", f"Урон: -{real} HP", 0.7)


def _hurt_player(w: World, dmg: int) -> None:
    hit_player(w, dmg)


def _try_exit(w: World, it) -> bool:
    p = w.player
    miss = _miss_keys(p)
    if p.gems >= SPARKS_NEEDED and not miss:
        old_x, old_y = it.cx, it.cy
        if w.level_no >= MAX_LEVEL:
            w.state = GameState.WIN
            w.bus.emit("burst", old_x, old_y, "win", 60)
            w.bus.emit("note", "Все 10 уровней пройдены", 3.0)
        else:
            w.next_level()
            w.bus.emit("burst", old_x, old_y, "win", 48)
            w.bus.emit("note", f"Переход на уровень {w.level_no}", 2.2)
        return True
    if w.msg_t > 0:
        return False
    parts = []
    if p.gems < SPARKS_NEEDED:
        parts.append(f"искры {p.gems}/{SPARKS_NEEDED}")
    if miss:
        parts.append("ключи: " + ", ".join(KEY_NAMES[k] for k in miss))
    w.bus.emit("note", "Нужно собрать " + " и ".join(parts), 1.6)
    return False


def _near_enemy(w: World, rng: float, need_los: bool = True) -> Enemy | None:
    p = w.player
    target: Enemy | None = None
    best = rng + 1.0
    for e in w.enemies:
        if not e.alive:
            continue
        d = dist(p.cx, p.cy, e.cx, e.cy)
        if d <= rng and d < best:
            if need_los and not los(w.lvl, p.cx, p.cy, e.cx, e.cy):
                continue
            target = e
            best = d
    return target


def _pick_weapon(p: Player) -> str:
    if p.wp in WEAPON_KINDS and p.inv.get(p.wp, 0) > 0:
        _sync_player(p)
        return p.wp
    res = _auto_switch(p)
    _sync_player(p)
    return res


def _auto_switch(p: Player) -> str:
    for k in WEAPON_KINDS:
        if p.inv.get(k, 0) > 0:
            p.wp = k
            return k
    p.wp = ""
    return ""


def _has_ammo(p: Player) -> bool:
    return any(n > 0 for n in p.inv.values())


def _wp_text(p: Player) -> str:
    if not p.wp:
        return "нет"
    left = p.inv.get(p.wp, 0)
    if p.wp == "gun":
        return f"{WEAPON_NAMES[p.wp]} {left}/{GUN_MAX}, искры {p.gems}"
    return f"{WEAPON_NAMES[p.wp]} x{left}"


def _has_keys(p: Player) -> bool:
    return all(k in p.keys for k in KEY_KINDS)


def _miss_keys(p: Player) -> list[str]:
    return [k for k in KEY_KINDS if k not in p.keys]


def _norm_wp(kind: str) -> str:
    if kind == "knife":
        return "blade"
    return kind if kind in WEAPON_KINDS else ""


def _sync_player(p: Player) -> None:
    for key in SKILL_KINDS:
        p.skills.setdefault(key, 0)
    if p.wp and p.inv.get(p.wp, 0) <= 0:
        _auto_switch(p)
    p.has_key = _has_keys(p)
    if p.inv.get("gun", 0) > GUN_MAX:
        p.inv["gun"] = GUN_MAX
    p.hp = min(p.hp, p.max_hp)


def _set_wp_cd(w: World, val: float, kind: str | None = None) -> None:
    w.wp_cd = val
    if kind is not None:
        w.wp_wait = kind if val > 0 else ""


def _patrol(e: Enemy, w: World, dt: float) -> None:
    if not e.patrol:
        e.stop()
        return

    goal = e.patrol[e.wp % len(e.patrol)]
    gx, gy = w.lvl.cell_pos(goal)
    if dist(e.cx, e.cy, gx, gy) < 9:
        e.wp = (e.wp + 1) % len(e.patrol)
        e.path.clear()
        e.path_t = 0.0
        e.last_cell = None
        goal = e.patrol[e.wp % len(e.patrol)]

    _go_path(e, w, goal, PATH_DELAY * 2.5, 1.0)


def _chase(e: Enemy, w: World, dt: float) -> None:
    pc = w.lvl.to_cell(w.player.cx, w.player.cy)

    if los(w.lvl, e.cx, e.cy, w.player.cx, w.player.cy):
        e.path.clear()
        e.last_cell = pc
        _move_to(e, w.player.cx, w.player.cy, CHASE_MUL)
        return

    _go_path(e, w, pc, PATH_DELAY, CHASE_MUL)


def _go_path(e: Enemy, w: World, goal: tuple[int, int], delay: float, mul: float) -> None:
    ec = w.lvl.to_cell(e.cx, e.cy)
    if e.path_t <= 0 or e.last_cell != goal or not e.path:
        e.path = astar(w.lvl, ec, goal)
        e.path_t = delay
        e.last_cell = goal
    _walk_path(e, w, mul)


def _walk_path(e: Enemy, w: World, mul: float) -> None:
    if not e.path:
        e.stop()
        return

    ec = w.lvl.to_cell(e.cx, e.cy)
    if ec in e.path:
        i = e.path.index(ec)
        if i > 0:
            del e.path[:i]

    if len(e.path) > 1 and e.path[0] == ec:
        cx, cy = w.lvl.cell_pos(ec)
        if dist(e.cx, e.cy, cx, cy) > 5:
            _move_to(e, cx, cy, mul)
            return
        e.path.pop(0)

    if not e.path:
        e.stop()
        return

    tx, ty = w.lvl.cell_pos(e.path[0])
    if dist(e.cx, e.cy, tx, ty) < 6:
        e.path.pop(0)
        if not e.path:
            e.stop()
            return
        tx, ty = w.lvl.cell_pos(e.path[0])

    _move_to(e, tx, ty, mul)


def _move_to(e: Enemy, tx: float, ty: float, mul: float = 1.0) -> None:
    dx = tx - e.cx
    dy = ty - e.cy
    ln = math.hypot(dx, dy)
    if ln < 0.001:
        e.stop()
        return
    spd = e.speed * mul
    e.vx = dx / ln * spd
    e.vy = dy / ln * spd


def _move_away(e: Enemy, tx: float, ty: float, mul: float = 1.0) -> None:
    dx = e.cx - tx
    dy = e.cy - ty
    ln = math.hypot(dx, dy)
    if ln < 0.001:
        e.stop()
        return
    spd = e.speed * mul
    e.vx = dx / ln * spd
    e.vy = dy / ln * spd


def _move_actor(a: Actor, w: World, dt: float) -> None:
    if not a.alive:
        return
    _axis_move(a, w, a.vx * dt, 0.0)
    _axis_move(a, w, 0.0, a.vy * dt)


def _axis_move(a: Actor, w: World, dx: float, dy: float) -> None:
    if dx == 0 and dy == 0:
        return
    a.x += dx
    a.y += dy
    walls = _hit_walls(a, w)
    if not walls:
        return

    if dx > 0:
        a.x = min(c * TILE - a.w - 0.01 for c, _ in walls)
        a.vx = 0.0
    elif dx < 0:
        a.x = max((c + 1) * TILE + 0.01 for c, _ in walls)
        a.vx = 0.0
    elif dy > 0:
        a.y = min(r * TILE - a.h - 0.01 for _, r in walls)
        a.vy = 0.0
    elif dy < 0:
        a.y = max((r + 1) * TILE + 0.01 for _, r in walls)
        a.vy = 0.0


def _hit_walls(a: Actor, w: World) -> list[tuple[int, int]]:
    left = int(a.x // TILE)
    right = int((a.x + a.w - 0.01) // TILE)
    top = int(a.y // TILE)
    bot = int((a.y + a.h - 0.01) // TILE)
    res = []
    for r in range(top, bot + 1):
        for c in range(left, right + 1):
            if w.lvl.is_wall(c, r):
                res.append((c, r))
    return res


def _move_shots(w: World, dt: float) -> None:
    p = w.player
    for b in w.shots:
        if not b.alive:
            continue
        b.life -= dt
        b.x += b.vx * dt
        b.y += b.vy * dt
        c = int(b.cx // TILE)
        r = int(b.cy // TILE)
        if b.life <= 0 or w.lvl.is_wall(c, r):
            b.alive = False
            continue
        if p.alive and aabb(b.rect(), p.rect()):
            b.alive = False
            hit_player(w, b.dmg)
            w.bus.emit("burst", b.cx, b.cy, "bolt", 16)


def _fire_bolt(w: World, e: Enemy) -> None:
    p = w.player
    dx = p.cx - e.cx
    dy = p.cy - e.cy
    ln = math.hypot(dx, dy)
    if ln < 0.001:
        return
    dx /= ln
    dy /= ln
    x = e.cx + dx * 12 - BOLT_SIZE / 2
    y = e.cy + dy * 12 - BOLT_SIZE / 2
    w.shots.append(Shot(x, y, dx * BOLT_SPEED, dy * BOLT_SPEED, e.dmg, "bolt", BOLT_SIZE, BOLT_SIZE))
    w.bus.emit("burst", e.cx, e.cy, "bolt", 10)


def _tick_player(p: Player, dt: float) -> None:
    if p.hurt_t > 0:
        p.hurt_t = max(0.0, p.hurt_t - dt)
    if p.atk_t > 0:
        p.atk_t = max(0.0, p.atk_t - dt)
    if p.dash_t > 0:
        p.dash_t = max(0.0, p.dash_t - dt)
    if p.dash_cd > 0:
        p.dash_cd = max(0.0, p.dash_cd - dt)
    if p.rage_t > 0:
        p.rage_t = max(0.0, p.rage_t - dt)
    if p.rage_cd > 0:
        p.rage_cd = max(0.0, p.rage_cd - dt)


def _touch_item(w: World, it) -> bool:
    p = w.player
    if aabb(p.rect(), it.rect()):
        return True
    if it.kind not in ("spark", "xp"):
        return False
    mag = p.skills.get("mag", 0)
    rng = XP_PICKUP_RANGE + mag * (MAGNET_RANGE - XP_PICKUP_RANGE) / 2
    if dist(p.cx, p.cy, it.cx, it.cy) <= rng:
        dx = p.cx - it.cx
        dy = p.cy - it.cy
        ln = math.hypot(dx, dy)
        if ln > 1:
            it.x += dx / ln * min(3.0 + mag * 2.0, ln)
            it.y += dy / ln * min(3.0 + mag * 2.0, ln)
        return mag > 0 or it.kind == "xp"
    return False


def _check_alert(w: World) -> None:
    p = w.player
    if w.alert or not (p.gems >= SPARKS_NEEDED and _has_keys(p)):
        return
    w.alert = True
    made = spawn_wave(w)
    w.bus.emit("burst", p.cx, p.cy, "alert", 48)
    if made > 0:
        w.bus.emit("note", f"Портал открыт — тревога! Новые враги: {made}", 2.3)
    else:
        w.bus.emit("note", "Портал открыт — свет сузился, беги к выходу", 2.3)
