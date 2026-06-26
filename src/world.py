import math
import random
from dataclasses import dataclass, field

from .alg import bfs, h
from .bus import Bus
from .cfg import (
    ALERT_ADD,
    ENEMY_W,
    KEY_KINDS,
    MAX_LEVEL,
    PARTICLE_LIMIT,
    PLAYER_SPEED,
    SPARKS_ON_MAP,
    TANK_HP_MUL,
    WEAPON_KINDS,
    WEAPON_MAX,
    WEAPON_NAMES,
    WEAPON_SIZE,
    enemy_dmg,
    enemy_speed,
    level_t,
)
from .entities import Enemy, GameState, Item, Particle, Player, Shot
from .level import Level, make_level


class ParticlePool:
    def __init__(self, rng: random.Random, max_n: int = PARTICLE_LIMIT) -> None:
        self.rng = rng
        self.items = [Particle() for _ in range(max_n)]
        self.at = 0

    def live(self) -> list[Particle]:
        return [p for p in self.items if p.alive]

    def burst(self, x: float, y: float, kind: str = "spark", count: int = 14) -> None:
        for _ in range(count):
            p = self._next()
            ang = self.rng.random() * math.tau
            spd = self.rng.uniform(45.0, 145.0)
            life = self.rng.uniform(0.25, 0.65)
            size = self.rng.uniform(2.0, 5.0)
            p.reset(x, y, math.cos(ang) * spd, math.sin(ang) * spd, life, size, kind)

    def _next(self) -> Particle:
        for _ in range(len(self.items)):
            p = self.items[self.at]
            self.at = (self.at + 1) % len(self.items)
            if not p.alive:
                return p
        p = self.items[self.at]
        self.at = (self.at + 1) % len(self.items)
        return p


@dataclass(slots=True)
class World:
    lvl: Level
    rng: random.Random
    bus: Bus
    player: Player
    enemies: list[Enemy]
    items: list[Item]
    parts: ParticlePool
    shots: list[Shot] = field(default_factory=list)
    state: GameState = GameState.MENU
    debug: bool = False
    msg: str = ""
    msg_t: float = 0.0
    time_scale: float = 1.0
    wp_cd: float = 0.0
    wp_wait: str = ""
    level_no: int = 1
    alert: bool = False
    alert_n: int = 0
    step_one: bool = False
    fps_buf: list[float] = field(default_factory=lambda: [1 / 60] * 90)
    fps_i: int = 0

    @classmethod
    def new(cls, seed: int | None = None, level_no: int = 1) -> "World":
        level_no = max(1, min(MAX_LEVEL, level_no))
        lvl = make_level(seed)
        rng = random.Random(lvl.seed + 77 + level_no * 19)
        bus = Bus()
        px, py = lvl.rect_pos(lvl.start, 22, 22)
        player = Player.make(px, py, PLAYER_SPEED)
        cells = sorted(bfs(lvl, lvl.start), key=lambda cell: h(cell, lvl.start), reverse=True)
        items = _make_items(lvl, cells, rng)
        enemies = _make_enemies(lvl, cells, rng, level_no)
        parts = ParticlePool(rng)
        world = cls(lvl, rng, bus, player, enemies, items, parts, level_no=level_no)
        bus.on("burst", parts.burst)
        bus.on("note", world.note)
        return world

    def note(self, text: str, sec: float = 2.0) -> None:
        self.msg = text
        self.msg_t = sec

    def add_fps(self, dt: float) -> None:
        self.fps_buf[self.fps_i] = max(0.0001, dt)
        self.fps_i = (self.fps_i + 1) % len(self.fps_buf)

    def fps(self) -> float:
        avg = sum(self.fps_buf) / len(self.fps_buf)
        return 1.0 / avg if avg > 0 else 0.0

    def reset_run(self, seed: int | None = None, level_no: int = 1) -> None:
        nw = World.new(seed, level_no)
        self.lvl = nw.lvl
        self.rng = nw.rng
        self.bus = Bus()
        self.player = nw.player
        self.enemies = nw.enemies
        self.items = nw.items
        self.parts = nw.parts
        self.shots = []
        self.bus.on("burst", self.parts.burst)
        self.bus.on("note", self.note)
        self.state = GameState.PLAY
        self.msg = ""
        self.msg_t = 0.0
        self.time_scale = 1.0
        self.wp_cd = nw.wp_cd
        self.wp_wait = nw.wp_wait
        self.level_no = nw.level_no
        self.alert = False
        self.alert_n = 0
        self.step_one = False
        self.fps_buf = [1 / 60] * 90
        self.fps_i = 0

    def next_level(self) -> None:
        old_no = self.level_no
        if old_no >= MAX_LEVEL:
            self.state = GameState.WIN
            self.note("Все 10 уровней пройдены", 3.0)
            return

        old_p = self.player
        keep_hp = max(1, old_p.hp)
        keep_ar = old_p.armor
        keep_max = old_p.max_hp
        keep_xp = old_p.xp
        keep_skills = dict(old_p.skills)
        keep_inv = dict(old_p.inv)
        keep_wp = old_p.wp if old_p.wp in keep_inv else ""

        nw = World.new(level_no=old_no + 1)
        self.lvl = nw.lvl
        self.rng = nw.rng
        self.bus = Bus()
        self.player = nw.player
        self.player.hp = min(keep_hp, keep_max)
        self.player.max_hp = keep_max
        self.player.armor = keep_ar
        self.player.xp = keep_xp
        self.player.skills = keep_skills
        self.player.inv = keep_inv
        self.player.wp = keep_wp
        self.enemies = nw.enemies
        self.items = nw.items
        self.parts = nw.parts
        self.shots = []
        self.bus.on("burst", self.parts.burst)
        self.bus.on("note", self.note)
        self.state = GameState.PLAY
        self.msg = ""
        self.msg_t = 0.0
        self.time_scale = 1.0
        self.wp_cd = 0.0
        self.wp_wait = ""
        self.level_no = nw.level_no
        self.alert = False
        self.alert_n = 0
        self.step_one = False
        self.fps_buf = [1 / 60] * 90
        self.fps_i = 0
        self.note(f"Уровень {self.level_no}", 2.0)


def _make_items(lvl: Level, cells: list[tuple[int, int]], rng: random.Random) -> list[Item]:
    used = {lvl.start, lvl.exit}
    items: list[Item] = []

    def put(kind: str, cell: tuple[int, int], size: int = 18, val: int = 0) -> None:
        used.add(cell)
        x, y = lvl.rect_pos(cell, size, size)
        items.append(Item(kind, x, y, size, size, val=val))

    far = [c for c in cells if h(c, lvl.start) > 12 and c not in used]
    rng.shuffle(far)
    for cell in far[:SPARKS_ON_MAP]:
        put("spark", cell)

    for key in KEY_KINDS:
        cell = _pick_cell(lvl, cells, used, rng, min_start=10)
        put(f"key_{key}", cell, 20)

    for kind in WEAPON_KINDS:
        cell = _pick_cell(lvl, cells, used, rng, min_start=8)
        put(kind, cell, WEAPON_SIZE)

    for kind in ("heal", "heal", "armor", "armor"):
        cell = _pick_cell(lvl, cells, used, rng, min_start=7)
        size = 20 if kind == "heal" else 22
        put(kind, cell, size)

    ex_x, ex_y = lvl.rect_pos(lvl.exit, 28, 28)
    items.append(Item("exit", ex_x, ex_y, 28, 28))
    return items


def _pick_cell(
    lvl: Level,
    cells: list[tuple[int, int]],
    used: set[tuple[int, int]],
    rng: random.Random,
    min_start: int = 6,
) -> tuple[int, int]:
    cand = [c for c in cells if c not in used and h(c, lvl.start) >= min_start and h(c, lvl.exit) > 4 and lvl.walk(*c)]
    if not cand:
        cand = [c for c in cells if c not in used and lvl.walk(*c)]
    if not cand:
        return lvl.start
    cell = rng.choice(cand)
    used.add(cell)
    return cell


def count_weapons(w: World) -> int:
    return sum(1 for it in w.items if it.alive and it.kind in WEAPON_KINDS)


def spawn_weapon(w: World, kind: str | None = None) -> bool:
    if count_weapons(w) >= WEAPON_MAX:
        return False
    k = kind if kind in WEAPON_KINDS else w.rng.choice(WEAPON_KINDS)
    cell = _free_cell(w, min_player=7)
    if cell is None:
        return False
    x, y = w.lvl.rect_pos(cell, WEAPON_SIZE, WEAPON_SIZE)
    w.items.append(Item(k, x, y, WEAPON_SIZE, WEAPON_SIZE))
    w.bus.emit("note", f"В лабиринте появилось оружие: {WEAPON_NAMES[k]}", 1.7)
    return True


def spawn_spark(w: World) -> bool:
    cell = _free_cell(w, min_player=5)
    if cell is None:
        return False
    x, y = w.lvl.rect_pos(cell, 18, 18)
    w.items.append(Item("spark", x, y, 18, 18))
    return True


def spawn_blade(w: World) -> bool:
    return spawn_weapon(w, "blade")


def spawn_xp(w: World, x: float, y: float, val: int) -> None:
    w.items.append(Item("xp", x - 9, y - 9, 18, 18, val=max(1, val)))


def spawn_wave(w: World) -> int:
    if w.alert_n > 0:
        return 0
    n = ALERT_ADD + min(3, w.level_no // 3)
    made = 0
    kinds = ["guard", "shooter", "guard", "tank"]
    for i in range(n):
        kind = kinds[(i + w.level_no) % len(kinds)]
        if spawn_enemy(w, kind, min_player=8):
            made += 1
    w.alert_n = made
    return made


def spawn_enemy(w: World, kind: str = "guard", min_player: int = 7) -> bool:
    cell = _free_cell(w, min_player=min_player)
    if cell is None:
        return False
    e = make_enemy(w.lvl, cell, w.rng, w.level_no, kind)
    w.enemies.append(e)
    return True


def _free_cell(w: World, min_player: int = 6) -> tuple[int, int] | None:
    pc = w.lvl.to_cell(w.player.cx, w.player.cy)
    used = {w.lvl.start, w.lvl.exit, pc}
    for it in w.items:
        if it.alive:
            used.add(w.lvl.to_cell(it.cx, it.cy))
    for e in w.enemies:
        if e.alive:
            used.add(w.lvl.to_cell(e.cx, e.cy))

    cells = [c for c in w.lvl.floor_cells() if c not in used and h(c, pc) > min_player and h(c, w.lvl.start) > 5]
    if not cells:
        cells = [c for c in w.lvl.floor_cells() if c not in used]
    if not cells:
        return None
    return w.rng.choice(cells)


def _make_enemies(lvl: Level, cells: list[tuple[int, int]], rng: random.Random, level_no: int = 1) -> list[Enemy]:
    good = [c for c in cells if h(c, lvl.start) > 13 and h(c, lvl.exit) > 5]
    rng.shuffle(good)
    enemies: list[Enemy] = []
    base_n = 5 + min(2, level_no // 4)
    for cell in good[:base_n]:
        enemies.append(make_enemy(lvl, cell, rng, level_no, "guard"))
    idx = base_n
    if level_no >= 2 and idx < len(good):
        enemies.append(make_enemy(lvl, good[idx], rng, level_no, "shooter"))
        idx += 1
    if level_no >= 4 and idx < len(good):
        enemies.append(make_enemy(lvl, good[idx], rng, level_no, "tank"))
        idx += 1
    if level_no >= 7 and idx < len(good):
        enemies.append(make_enemy(lvl, good[idx], rng, level_no, "shooter"))
    return enemies


def make_enemy(lvl: Level, cell: tuple[int, int], rng: random.Random, level_no: int = 1, kind: str = "guard") -> Enemy:
    pts = _patrol(lvl, cell, rng)
    base_spd = enemy_spd(level_no)
    base_dmg = enemy_hit(level_no)
    t = level_t(level_no)

    if kind == "shooter":
        size = ENEMY_W
        spd = base_spd * 0.82
        hp = int(18 + 5 * t)
        dmg = max(3, int(base_dmg * 0.72))
        xp = 2
    elif kind == "tank":
        size = ENEMY_W + 6
        spd = base_spd * 0.58
        hp = int(24 * TANK_HP_MUL + 14 * t)
        dmg = int(base_dmg * 1.45)
        xp = 4
    else:
        size = ENEMY_W
        spd = base_spd
        hp = int(20 + 3 * t)
        dmg = base_dmg
        xp = 1

    x, y = lvl.rect_pos(cell, size, size)
    return Enemy.make(x, y, spd, pts, dmg, kind=kind, hp=hp, xp=xp, size=size)


def enemy_spd(level_no: int) -> float:
    return enemy_speed(level_no)


def enemy_hit(level_no: int) -> int:
    return enemy_dmg(level_no)


def _patrol(lvl: Level, cell: tuple[int, int], rng: random.Random) -> list[tuple[int, int]]:
    c, r = cell
    near = []
    for rr in range(r - 6, r + 7):
        for cc in range(c - 6, c + 7):
            if lvl.walk(cc, rr) and h((cc, rr), cell) >= 3:
                near.append((cc, rr))
    rng.shuffle(near)
    pts = [cell] + near[:3]
    return pts
